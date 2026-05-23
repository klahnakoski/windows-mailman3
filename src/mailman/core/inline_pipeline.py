# Copyright (C) 2025 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <https://www.gnu.org/licenses/>.

"""Inline (in-process) pipeline setup and DirectLmtp injector.

Replaces the file-backed switchboard queues for the hot-path runners with
synchronous in-process dispatch.  Call setup_inline_pipeline() once at startup
and then use DirectLmtp (or call config.switchboards['in'].enqueue() directly)
to inject messages into the full Mailman pipeline without any subprocess or TCP
socket.

Message flow after patching::

    DirectLmtp.send_mail()
        → LMTPHandler._handle_DATA()          # parses bytes → Message
            → config.switchboards['in'].enqueue()   # inline → IncomingRunner
                → chains / rules
                    → config.switchboards['pipeline'].enqueue()  # inline
                        → pipeline handlers
                            → config.switchboards['out'].enqueue()  # inline
                                → SMTP delivery
                            → config.switchboards['archive'].enqueue()  # inline
                                → archivers

Queues intentionally left file-backed (they accumulate state over time or
require human inspection):

- ``digest``  – accumulates messages until volume/time trigger fires
- ``retry``   – SMTP temporary failures; polled by RetryRunner thread
- ``shunt``   – dead-letter queue; needs human review
- ``bad``     – corrupt / unparseable messages

Transient re-queue (keepqueued=True) path
------------------------------------------
When a runner's _dispose() returns True (e.g. OutgoingRunner on socket.error),
_process_one_file() calls runner.switchboard.enqueue().  We redirect that to the
file-backed ``retry`` queue so that the message survives a process restart and
is picked up by the RetryRunner thread rather than looping immediately.
"""

import logging

from mailman.config import config
from mailman.core.initialize import initialize
from mailman.runners.archive import ArchiveRunner
from mailman.runners.bounce import BounceRunner
from mailman.runners.command import CommandRunner
from mailman.runners.incoming import IncomingRunner
from mailman.runners.lmtp import LMTPHandler
from mailman.runners.outgoing import OutgoingRunner
from mailman.runners.pipeline import PipelineRunner
from mailman.runners.virgin import VirginRunner
from public import public


log = logging.getLogger('mailman.inline_pipeline')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _Envelope:
    """Minimal SMTP envelope compatible with LMTPHandler._handle_DATA.

    aiosmtpd's real Envelope has many more attributes, but _handle_DATA only
    reads mail_from, rcpt_tos, and content.
    """

    __slots__ = ('mail_from', 'rcpt_tos', 'content')

    def __init__(self, mail_from, rcpt_tos, content):
        self.mail_from = mail_from
        self.rcpt_tos = list(rcpt_tos)
        # content must be bytes (RFC 2822 message)
        if isinstance(content, bytes):
            self.content = content
        else:
            self.content = content.encode('latin-1')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@public
def setup_inline_pipeline(config_file=None):
    """Initialize Mailman and switch hot-path queues to in-process dispatch.

    Must be called exactly once per process before any mail injection.

    :param config_file: Path to ``mailman.cfg``, or ``None`` to auto-discover
        via the normal search order (env var → ``./mailman.cfg`` → etc.).
    :returns: A dict mapping queue name → runner instance for every queue that
        was patched.  Callers that also want to start service threads can use
        these runner instances directly.
    """
    initialize(config_file)

    # Note: OutgoingRunner.__init__ takes (self, slice=None, numslices=1) and
    # passes its first positional arg as the *name* to Runner.__init__.  This
    # is a naming quirk in the original code; calling OutgoingRunner('out')
    # works correctly and sets self.name = 'out'.
    runner_factories = {
        'in':       IncomingRunner,
        'pipeline': PipelineRunner,
        'out':      OutgoingRunner,
        'archive':  ArchiveRunner,
        'bounces':  BounceRunner,
        'command':  CommandRunner,
        'virgin':   VirginRunner,
    }

    runners = {}
    for name, cls in runner_factories.items():
        runners[name] = cls(name)
        log.debug('Created inline runner for queue %r', name)

    # The retry switchboard stays file-backed.  Any keepqueued=True scenario
    # (e.g. SMTP socket.error in OutgoingRunner) is redirected here so the
    # message survives until the RetryRunner thread processes it.
    retry_sb = config.switchboards.get('retry')

    for name, runner in runners.items():
        sb = config.switchboards.get(name)
        if sb is None:
            log.warning(
                'No switchboard registered for queue %r — inline patch skipped',
                name)
            continue

        # Replace the filesystem enqueue with a direct _process_one_file call.
        # We capture `runner` in the closure via the default-argument trick to
        # avoid the late-binding problem with loop variables.
        def _make_inline_enqueue(r):
            def _inline_enqueue(msg, md=None, **kw):
                if md is None:
                    md = {}
                md.update(kw)
                r._process_one_file(msg, md)
            return _inline_enqueue

        sb.enqueue = _make_inline_enqueue(runner)
        # No .bak files are written, so finish() is a no-op.
        sb.finish = lambda *a, **kw: None  # noqa: E731

        # Redirect the runner's own self.switchboard (used when keepqueued=True)
        # to the retry queue so transient failures don't loop back inline.
        if runner.switchboard is not None and retry_sb is not None:
            runner.switchboard.enqueue = retry_sb.enqueue
            log.debug(
                'Queue %r keepqueued path redirected to retry queue', name)

    log.info('Inline pipeline active for queues: %s', ', '.join(runners))
    return runners


@public
class DirectLmtp:
    """Drop-in replacement for LazyLmtp that injects mail without a TCP socket.

    Requires that :func:`setup_inline_pipeline` has already been called in this
    process.  The ``send_mail`` method mirrors ``LazyLmtp.send_mail`` exactly so
    that ``Pop3ToLmtp`` can swap the two without any other changes::

        # Before (aws-email/remote/pop3_to_lmtp.py):
        with LazyLmtp(**config.lmtp) as lmtp:
            Pop3ToLmtp(pop3=pop3, lmtp=lmtp, ...).move_mail()

        # After:
        setup_inline_pipeline(config.mailman_cfg)
        with DirectLmtp() as lmtp:
            Pop3ToLmtp(pop3=pop3, lmtp=lmtp, ...).move_mail()

    The LMTPHandler._handle_DATA call is decorated with @transactional, so
    each message is committed (or aborted) atomically — no extra transaction
    management is needed here.
    """

    def __init__(self):
        self._handler = LMTPHandler()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # nothing to close; the pipeline is entirely in-process

    def send_mail(self, sender_email, recipient_emails, content):
        """Inject a message directly into the Mailman pipeline.

        :param sender_email: The envelope sender address (Return-Path value).
        :type sender_email: str
        :param recipient_emails: One or more envelope recipient addresses.
        :type recipient_emails: list[str]
        :param content: Raw RFC 2822 message bytes *without* the envelope
            headers that Pop3ToLmtp.send() strips (Return-Path, X-Original-To,
            Delivered-To lines).
        :type content: bytes
        :raises RuntimeError: If any recipient receives a non-250 response
            (e.g. unknown list address → 550, or parse error → 501).  The
            caller (Pop3ToLmtp.move_mail) catches this and skips the POP3
            delete so the message is retried on the next run.
        """
        envelope = _Envelope(sender_email, recipient_emails, content)
        # _handle_DATA is @transactional — it commits on success, aborts on
        # exception.  It returns a CRLF-joined string of per-recipient status
        # codes, e.g. "250 Ok\r\n250 Ok" or "550 Requested action not taken…"
        result = self._handler._handle_DATA(None, None, envelope)
        errors = [
            line for line in result.split('\r\n')
            if line and not line.startswith('250')
        ]
        if errors:
            raise RuntimeError(
                'LMTP inline delivery error(s): {}'.format('; '.join(errors)))

