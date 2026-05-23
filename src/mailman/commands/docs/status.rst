==============
Getting status
==============

The status of the Mailman master process can be queried from the command line.
It's clear at this point that nothing is running.
::

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_status.status')

The status is printed to stdout and a status code is returned.

    >>> command('mailman status')
    GNU Mailman is not running

We can simulate the master starting up by acquiring its lock.

    >>> from datetime import timedelta
    >>> from mailman.lock import Lock
    >>> from mailman.config import config
    >>> lock = Lock(config.LOCK_FILE)
    >>> lock.lock(timeout=timedelta(seconds=20))
    >>> ignore = cleanups.callback(lock.unlock, unconditionally=True)

Getting the status confirms that the master is running.

    >>> command('mailman status')
    GNU Mailman is running (master pid: ...

We shut down the master and confirm the status.

    >>> lock.unlock(unconditionally=True)
    >>> command('mailman status')
    GNU Mailman is not running
