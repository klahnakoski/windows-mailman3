"""Long-lived Mailman services.

Starts the following threads and blocks until interrupted:

    rest      — REST API server (wsgiref WSGI on the configured host:port)
    lmtp      — LMTPRunner: accepts incoming mail from the MTA
    task      — TaskRunner: evicts expired pendings, cleans old helds (every 1 min)
    digest    — DigestRunner: polls var/queue/digest/, fires digests on schedule
    retry     — RetryRunner: moves var/queue/retry/ back to 'out' (every 15 min)

The inline pipeline patch (setup_inline_pipeline) is applied so that REST-
triggered moderator approvals — which call
    config.switchboards['pipeline'].enqueue(msg, msgdata)
— also run the full pipeline synchronously in this process.

Usage::

    python services.py [path/to/mailman.cfg]

The optional argument overrides the normal mailman.cfg search order
(env var MAILMAN_CONFIG_FILE → ./mailman.cfg → ./var/etc/mailman.cfg → …).

Public helpers (usable without calling main())::

    services = WindowsServices()
    services.start('rest', 'lmtp')   # start services
    services.stop()                  # stop all
"""

import sys
import logging
import threading

from mailman.windows.inline_pipeline import setup_inline_pipeline
from mailman.runners.digest import DigestRunner
from mailman.runners.lmtp import LMTPRunner
from mailman.runners.retry import RetryRunner
from mailman.runners.task import TaskRunner
from mailman.windows.rest_runner import RestRunner


log = logging.getLogger("mailman.process2")


class WindowsServices:
    """In-process service manager for Windows testing.

    Drop-in replacement for ``mailman.testing.helpers.TestableMaster``.
    Instead of fork+exec, each named runner is started as a daemon thread.
    Mirrors the ``start(*runners)`` / ``stop()`` interface of TestableMaster.

    Any runner name registered in ``_RUNNER_FACTORIES`` is supported.
    """

    def __init__(self, start_check=None):
        """
        :param start_check: Optional callable invoked after all services have
            started their threads, used to block until the service is
            accepting connections.  Same role as in TestableMaster.
        """
        self.start_check = start_check
        self._runners = []  # list of (runner, thread)

    def start(self, *runner_names):
        """Start the named services and wait until they are ready."""
        for name in runner_names:
            if name not in _RUNNER_FACTORIES:
                raise NotImplementedError("No Windows in-thread support for runner: {!r}".format(name))
            runner = _RUNNER_FACTORIES[name]()
            t = threading.Thread(target=runner.run, daemon=True, name="mailman-{}".format(name))
            t.start()
            log.debug("%s thread started", runner.name)
            self._runners.append((runner, t))
        if self.start_check is not None:
            self.start_check()

    def stop(self):
        """Stop all running services and join their threads."""
        for runner, t in self._runners:
            runner.stop()
            t.join(timeout=5)
        self._runners.clear()


# Central registry
# Add entries here to support new runner names in WindowsServices and main().
_RUNNER_FACTORIES = {
    "rest": lambda: RestRunner("rest"),
    "lmtp": lambda: LMTPRunner("lmtp"),
    "task": lambda: TaskRunner("task"),
    "digest": lambda: DigestRunner("digest"),
    "retry": lambda: RetryRunner("retry"),
}


def main():
    mailman_cfg = sys.argv[1] if len(sys.argv) > 1 else None

    setup_inline_pipeline(mailman_cfg)

    services = WindowsServices()
    services.start(*_RUNNER_FACTORIES)
    log.info("Process 2 running — Ctrl-C to stop.")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        log.info("Shutting down Process 2…")
        services.stop()


if __name__ == "__main__":
    main()
