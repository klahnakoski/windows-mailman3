===================
Dumping queue files
===================

The ``qfile`` command dumps the contents of a queue pickle file.  This is
especially useful when you have shunt files you want to inspect.


Pretty printing
===============

By default, the ``qfile`` command pretty prints the contents of a queue pickle
file to standard output.
::

    >>> from mailman.testing.documentation import cli   
    >>> command = cli('mailman.commands.cli_qfile.qfile')

Let's say Mailman shunted a message file.
::

    >>> from mailman.testing.helpers import (specialized_message_from_string
    ...   as message_from_string)   
    >>> msg = message_from_string("""\
    ... From: aperson@example.com
    ... To: ant@example.com
    ... Subject: Uh oh
    ...
    ... I borkeded Mailman.
    ... """)

    >>> from mailman.config import config
    >>> shuntq = config.switchboards['shunt']
    >>> basename = shuntq.enqueue(msg, foo=7, bar='baz', bad='yes')

Once we've figured out the file name of the shunted message, we can print it.
::

    >>> from mailman.utilities.filesystem import File, open
    >>> qfile = str(File(shuntq.queue_directory) / (basename + '.pck'))

    >>> command('mailman qfile ' + qfile)
    [----- start pickle -----]
    <----- start object 1 ----->
    From: aperson@example.com
    To: ant@example.com
    Subject: Uh oh
    <BLANKLINE>
    I borkeded Mailman.
    <BLANKLINE>
    <----- start object 2 ----->
    {'_parsemsg': False, 'bad': 'yes', 'bar': 'baz', 'foo': 7, 'version': 3}
    [----- end pickle -----]

Maybe we don't want to print the contents of the file though, in case we want
to enter the interactive prompt.

    >>> command('mailman qfile --no-print ' + qfile)
