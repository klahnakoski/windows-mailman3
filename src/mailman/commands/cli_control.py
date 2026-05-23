# Copyright (C) 2009-2025 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
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

"""Start/stop/reopen/restart commands."""

import os
import sys
import click
import errno
import signal
import logging
import subprocess

from mailman.bin.master import _command_file, master_state, WatcherState
from mailman.config import config
from mailman.core.i18n import _
from mailman.interfaces.command import ICLISubCommand
from mailman.utilities.filesystem import File, open
from mailman.utilities.modules import call_name
from mailman.utilities.options import I18nCommand
from public import public
from zope.interface import implementer


qlog = logging.getLogger('mailman.runner')


@click.command(
    cls=I18nCommand,
    help=_('Start the Mailman master and runner processes.'))
@click.option(
    '--force', '-f',
    is_flag=True, default=False,
    help=_("""\
    If the master watcher finds an existing master lock, it will normally exit
    with an error message.  With this option, the master will perform an extra
    level of checking.  If a process matching the host/pid described in the
    lock file is running, the master will still exit, requiring you to manually
    clean up the lock.  But if no matching process is found, the master will
    remove the apparently stale lock and make another attempt to claim the
    master lock."""))
@click.option(
    '--generate-alias-file', '-g',
    is_flag=True, default=True,
    help=_("""\
    Generate the MTA alias files upon startup. Some MTA, like postfix, can't
    deliver email if alias files mentioned in its configuration are not
    present. In some situations, this could lead to a deadlock at the first
    start of mailman3 server. Setting this option to true will make this
    script create the files and thus allow the MTA to operate smoothly."""))
@click.option(
    '--run-as-user', '-u',
    is_flag=True, default=True,
    help=_("""\
    Normally, this script will refuse to run if the user id and group id are
    not set to the 'mailman' user and group (as defined when you configured
    Mailman).  If run as root, this script will change to this user and group
    before the check is made.

    This can be inconvenient for testing and debugging purposes, so the -u flag
    means that the step that sets and checks the uid/gid is skipped, and the
    program is run as the current user and group.  This flag is not recommended
    for normal production environments.

    Note though, that if you run with -u and are not in the mailman group, you
    may have permission problems, such as being unable to delete a list's
    archives through the web.  Tough luck!"""))
@click.option(
    '--quiet', '-q',
    is_flag=True, default=False,
    help=_("""\
    Don't print status messages.  Error messages are still printed to standard
    error."""))
@click.pass_context
def start(ctx, force, generate_alias_file, run_as_user, quiet):
    # Although there's a potential race condition here, it's a better user
    # experience for the parent process to refuse to start twice, rather than
    # having it try to start the master, which will error exit.
    status, lock = master_state()
    if status is WatcherState.conflict:
        ctx.fail(_('GNU Mailman is already running'))
    elif status in (WatcherState.stale_lock, WatcherState.host_mismatch):
        if not force:
            ctx.fail(
                _('A previous run of GNU Mailman did not exit '
                  'cleanly ({}).  Try using --force'.format(status.name)))
    # Build the command to start the master process as a detached subprocess.
    os.environ['MAILMAN_VAR_DIR'] = config.VAR_DIR
    master_args = [
        sys.executable,
        os.path.join(config.BIN_DIR, 'master'),
        ]
    if force:
        master_args.append('--force')
    # Always pass the configuration file path to the master process, so there's
    # no confusion about which one is being used.
    master_args.extend(['-C', config.filename])
    qlog.debug('starting: %s', master_args)
    # Launch the master as a detached subprocess.
    # On Windows use CREATE_NO_WINDOW | DETACHED_PROCESS;
    # on POSIX use start_new_session=True.
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['creationflags'] = (
            subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    else:
        kwargs['start_new_session'] = True
    subprocess.Popen(master_args, **kwargs)
    if not quiet:
        print(_("Starting Mailman's master runner"))
    if generate_alias_file:
        if not quiet:
            print(_("Generating MTA alias maps"))
        call_name(config.mta.incoming).regenerate()


@public
@implementer(ICLISubCommand)
class Start:
    name = 'start'
    command = start


def kill_watcher(sig):
    """Send a signal or command to the master watcher.

    On POSIX, if the signal is available, send it directly.
    Always write a command file as cross-platform fallback.
    """
    try:
        with open(config.PID_FILE, 'r') as fp:
            pid = int(fp.read().strip())
    except (IOError, ValueError) as error:        # pragma: nocover
        # For i18n convenience
        print(_('PID unreadable in: ${config.PID_FILE}'), file=sys.stderr)
        print(error, file=sys.stderr)
        print(_('Is the master even running?'), file=sys.stderr)
        return
    # Map signal to command name for the command file.
    sig_to_cmd = {}
    if hasattr(signal, 'SIGHUP'):
        sig_to_cmd[signal.SIGHUP] = 'reopen'
    if hasattr(signal, 'SIGUSR1'):
        sig_to_cmd[signal.SIGUSR1] = 'restart'
    sig_to_cmd[signal.SIGTERM] = 'stop'
    # Write command file for cross-platform IPC.
    cmd = sig_to_cmd.get(sig)
    if cmd:
        try:
            with File(_command_file(), 'w') as fp:
                fp.write(cmd)
        except OSError:
            pass
    # Also send the actual signal on POSIX (for immediate response),
    # or SIGTERM on Windows (which calls TerminateProcess).
    try:
        if sig == signal.SIGTERM:
            os.kill(pid, signal.SIGTERM)
        elif hasattr(os, 'kill') and hasattr(signal, 'SIGHUP'):
            # On POSIX, send the original signal for fast wakeup.
            os.kill(pid, sig)
    except OSError as error:                      # pragma: nocover
        if error.errno != errno.ESRCH:
            raise
        print(_('No child with pid: ${pid}'), file=sys.stderr)
        print(error, file=sys.stderr)
        print(_('Stale pid file removed.'), file=sys.stderr)
        os.unlink(config.PID_FILE)


@click.command(
    cls=I18nCommand,
    help=_('Stop the Mailman master and runner processes.'))
@click.option(
    '--quiet', '-q',
    is_flag=True, default=False,
    help=_("""\
    Don't print status messages.  Error messages are still printed to standard
    error."""))
def stop(quiet):
    if not quiet:
        print(_("Shutting down Mailman's master runner"))
    kill_watcher(signal.SIGTERM)


@public
@implementer(ICLISubCommand)
class Stop:
    name = 'stop'
    command = stop


@click.command(
    cls=I18nCommand,
    help=_('Signal the Mailman processes to re-open their log files.'))
@click.option(
    '--quiet', '-q',
    is_flag=True, default=False,
    help=_("""\
    Don't print status messages.  Error messages are still printed to standard
    error."""))
def reopen(quiet):
    if not quiet:
        print(_('Reopening the Mailman runners'))
    # Use SIGHUP if available (POSIX), otherwise use command file via SIGTERM
    # path (the command file written by kill_watcher handles this).
    if hasattr(signal, 'SIGHUP'):
        kill_watcher(signal.SIGHUP)
    else:
        # On Windows, write the command file directly.
        try:
            with File(_command_file(), 'w') as fp:
                fp.write('reopen')
        except OSError:
            pass


@public
@implementer(ICLISubCommand)
class Reopen:
    name = 'reopen'
    command = reopen


@click.command(
    cls=I18nCommand,
    help=_('Stop and restart the Mailman runner subprocesses. '
           'Note: runners that have died and are not currently '
           'running will not be restarted by this command. '
           'To restart dead runners, use mailman stop '
           'followed by mailman start.'))
@click.option(
    '--quiet', '-q',
    is_flag=True, default=False,
    help=_("""\
    Don't print status messages.  Error messages are still printed to standard
    error."""))
def restart(quiet):
    if not quiet:
        print(_('Restarting the Mailman runners'))
    # Use SIGUSR1 if available (POSIX), otherwise use command file.
    if hasattr(signal, 'SIGUSR1'):
        kill_watcher(signal.SIGUSR1)
    else:
        # On Windows, write the command file directly.
        try:
            with File(_command_file(), 'w') as fp:
                fp.write('restart')
        except OSError:
            pass


@public
@implementer(ICLISubCommand)
class Restart:
    name = 'restart'
    command = restart
