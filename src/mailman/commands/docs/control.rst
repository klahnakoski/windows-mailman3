=============================
Starting and stopping Mailman
=============================

.. unix-only

The Mailman daemon processes can be started and stopped from the command
line.


Set up
======

All we care about is the master process; normally it starts a bunch of
runners, but we don't care about any of them, so write a test configuration
file for the master that disables all the runners.

    >>> from mailman.commands.tests.test_cli_control import make_config
    >>> make_config(cleanups)


Starting
========

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_control.start')

Starting the daemons prints a useful message and starts the master watcher
process in the background.

    >>> command('mailman start')
    Starting Mailman's master runner
    Generating MTA alias maps

    >>> from mailman.commands.tests.test_cli_control import find_master

The process exists, and its pid is available in a run time file.

    >>> pid = find_master()
    >>> pid is not None
    True


Stopping
========

You can also stop the master watcher process from the command line, which
stops all the child processes too.
::

    >>> command = cli('mailman.commands.cli_control.stop')
    >>> command('mailman stop')
    Shutting down Mailman's master runner

..
    # Clean up.
    >>> from mailman.commands.tests.test_cli_control import (
    ...     kill_with_extreme_prejudice, clean_stale_locks)
    >>> kill_with_extreme_prejudice(pid)
    >>> clean_stale_locks()
