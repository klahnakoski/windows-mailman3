===============
Syncing members
===============

The ``mailman syncmembers`` command allows a site administrator to sync the
membership of a mailing list with an input file.

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_syncmembers.syncmembers')

Usage
-----

Here is the complete usage for the command.
::

    >>> command('mailman syncmembers --help')
    Usage: syncmembers [OPTIONS] FILENAME LISTSPEC
    <BLANKLINE>
      Add and delete members as necessary to syncronize a list's membership with
      an input file.  FILENAME is the file containing the new membership, one
      member per line.  Blank lines and lines that start with a '#' are ignored.
      Addresses in FILENAME which are not current list members will be added to
      the list with delivery mode as specified with -d/--delivery.  List members
      whose addresses are not in FILENAME will be removed from the list.
      FILENAME can be '-' to indicate standard input.
    <BLANKLINE>
    Options:
      -d, --delivery [regular|mime|plain|summary|disabled]
                                      Set the added members delivery mode to
                                      'regular', 'mime', 'plain', 'summary' or
                                      'disabled'.  I.e., one of regular, three
                                      modes of digest or no delivery.  If not
                                      given, the default is regular.
    <BLANKLINE>
      -w, --welcome-msg / -W, --no-welcome-msg
                                      Override the list's setting for
                                      send_welcome_message to added members.
    <BLANKLINE>
      -g, --goodbye-msg / -G, --no-goodbye-msg
                                      Override the list's setting for
                                      send_goodbye_message to deleted members.
    <BLANKLINE>
      -a, --admin-notify / -A, --no-admin-notify
                                      Override the list's setting for
                                      admin_notify_mchanges.
    <BLANKLINE>
      -n, --no-change                 Don't actually make the changes.  Instead,
                                      print out what would be done to the list.
    <BLANKLINE>
      --help                          Show this message and exit.

Examples
--------

You can synchronize all member addresses of a mailing list with the
member addresses found in a file from the command line.  To do so, you
need a file containing email addresses and optional display names that can be
parsed by ``email.utils.parseaddr()``.  All mail addresses *not contained* in
the file will be *deleted* from the mailing list. Every address *found* in the
specified file will be added to the specified mailing list.

First we create a list and add a few members.
::

    >>> from mailman.app.lifecycle import create_list   
    >>> bee = create_list('bee@example.com')
    >>> from mailman.testing.helpers import subscribe
    >>> subscribe(bee, 'Fred')
    <Member: Fred Person <fperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Greg')
    <Member: Greg Person <gperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Jeff')
    <Member: Jeff Person <jperson@example.com> on bee@example.com
             as MemberRole.member>

*Note* that only changes of the mailing list will be written to output so in
the first example, Fred is a member who remains on the list and isn't reported.
::

    >>> from mailman.testing.tempfile import NamedTemporaryFile
    >>> from mailman.utilities.filesystem import File, open
    >>> filename = cleanups.enter_context(NamedTemporaryFile()).name
    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... aperson@example.com
    ... cperson@example.com (Cate Person)
    ... Fred Person <fperson@example.com>
    ... """, file=fp)

    >>> command('mailman syncmembers ' + filename + ' bee.example.com')
    [ADD] aperson@example.com
    [ADD] Cate Person <cperson@example.com>
    [DEL] Greg Person <gperson@example.com>
    [DEL] Jeff Person <jperson@example.com>

    >>> from operator import attrgetter
    >>> from mailman.testing.documentation import dump_list        
    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    aperson@example.com
    Cate Person <cperson@example.com>
    Fred Person <fperson@example.com>

You can also specify ``-`` as the filename, in which case the addresses are
taken from standard input.
::

    >>> stdin = """\
    ... dperson@example.com
    ... Elly Person <eperson@example.com>
    ... """
    >>> command('mailman syncmembers - bee.example.com', input=stdin)
    [ADD] dperson@example.com
    [ADD] Elly Person <eperson@example.com>
    [DEL] aperson@example.com
    [DEL] Cate Person <cperson@example.com>
    [DEL] Fred Person <fperson@example.com>

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    dperson@example.com
    Elly Person <eperson@example.com>

Blank lines and lines that begin with '#' are ignored.
::

    >>> from mailman.utilities.filesystem import File, open
    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... #cperson@example.com
    ... eperson@example.com
    ...
    ... bperson@example.com
    ... """, file=fp)

    >>> command('mailman syncmembers ' + filename + ' bee.example.com')
    [ADD] bperson@example.com
    [DEL] dperson@example.com

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    bperson@example.com
    Elly Person <eperson@example.com>

If there is nothing to do, it will output just that.
::

    >>> from mailman.utilities.filesystem import open
    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... bperson@example.com
    ... eperson@example.com
    ... """, file=fp)

    >>> command('mailman syncmembers ' + filename + ' bee.example.com')
    Nothing to do

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    bperson@example.com
    Elly Person <eperson@example.com>
