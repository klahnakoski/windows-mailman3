===================
Importing list data
===================

If you have the ``config.pck`` file for a version 2.1 mailing list, you can
import that into an existing mailing list in Mailman 3.0.

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_import.import21')

You must specify the mailing list you are importing into, and it must exist.

    >>> command('mailman import21')
    Usage: ... [OPTIONS] LISTSPEC PICKLE_FILE
    Try 'import21 --help' for help.
    <BLANKLINE>
    Error: Missing argument 'LISTSPEC'.

You must also specify a pickle file to import.

    >>> command('mailman import21 import@example.com')
    Usage: ... [OPTIONS] LISTSPEC PICKLE_FILE
    Try 'import21 --help' for help.
    <BLANKLINE>
    Error: Missing argument 'PICKLE_FILE'.

Too bad the list doesn't exist.

    >>> from mailman.utilities.filesystem import File
    >>> from importlib.resources import path
    >>> with path('mailman.testing', 'config.pck') as pickle_path:
    ...     pickle_file = str(File(pickle_path))
    ...     command('mailman import21 import@example.com ' + pickle_file)
    Usage: ... [OPTIONS] LISTSPEC PICKLE_FILE
    Try 'import21 --help' for help.
    <BLANKLINE>
    Error: No such list: import@example.com

When the mailing list exists, you must specify a real pickle file to import
from.
::

    >>> from mailman.app.lifecycle import create_list
    >>> mlist = create_list('import@example.com')
    >>> from mailman.config import config
    >>> transaction = config.db    
    >>> transaction.commit()
    >>> command('mailman import21 import@example.com ' + str(File(__file__)))
    Usage: ... [OPTIONS] LISTSPEC PICKLE_FILE
    Try 'import21 --help' for help.
    <BLANKLINE>
    Error: Not a Mailman 2.1 configuration file: .../import.rst'...

Now we can import the test pickle file.  As a simple illustration of the
import, the mailing list's "real name" will change.
::

    >>> print(mlist.display_name)
    Import

    >>> command('mailman import21 import@example.com ' + pickle_file)
    Importing ...
    >>> print(mlist.display_name)
    Test
