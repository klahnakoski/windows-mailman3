================
Deleting members
================

The ``mailman delmembers`` command allows a site administrator to delete members
from a mailing list.

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_delmembers.delmembers')

Usage
-----

Here is the complete usage for the command.
::

    >>> command('mailman delmembers --help')
    Usage: delmembers [OPTIONS]
    <BLANKLINE>
      Delete members from a mailing list.
    <BLANKLINE>
    Options:
      -l, --list LISTSPEC             The list to operate on.  Required unless
                                      --fromall is specified.
    <BLANKLINE>
      -f, --file FILENAME             Delete list members whose addresses are in
                                      FILENAME in addition to those specified with
                                      -m/--member if any.  FILENAME can be '-' to
                                      indicate standard input.  Blank lines and
                                      lines that start with a '#' are ignored.
    <BLANKLINE>
      -m, --member ADDRESS            Delete the list member whose address is
                                      ADDRESS in addition to those specified with
                                      -f/--file if any.  This option may be repeated
                                      for multiple addresses.
    <BLANKLINE>
      -a, --all                       Delete all the members of the list.  If
                                      specified, none of -f/--file, -m/--member or
                                      --fromall may be specified.
    <BLANKLINE>
      --fromall                       Delete the member(s) specified by -m/--member
                                      and/or -f/--file from all lists in the
                                      installation.  This may not be specified
                                      together with -a/--all or -l/--list.
    <BLANKLINE>
      -g, --goodbye-msg / -G, --no-goodbye-msg
                                      Override the list's setting for
                                      send_goodbye_message to deleted members.
    <BLANKLINE>
      -n, --admin-notify / -N, --no-admin-notify
                                      Override the list's setting for
                                      admin_notify_mchanges.
    <BLANKLINE>
      --help                          Show this message and exit.

Examples
--------

You can delete members from a mailing list from the command line.  To do so, you
need a file containing email addresses and optional display names that can be
parsed by ``email.utils.parseaddr()``.  All mail addresses in the file will be
deleted from the mailing list.  You can also specify members with command
options on the command line.

First we need a list with some members.
::

    >>> from mailman.app.lifecycle import create_list
    >>> bee = create_list('bee@example.com')
    >>> from mailman.testing.helpers import subscribe
    >>> subscribe(bee, 'Anne')
    <Member: Anne Person <aperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Bart')
    <Member: Bart Person <bperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Cate')
    <Member: Cate Person <cperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Doug')
    <Member: Doug Person <dperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Elly')
    <Member: Elly Person <eperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Fred')
    <Member: Fred Person <fperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Greg')
    <Member: Greg Person <gperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Irma')
    <Member: Irma Person <iperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Jeff')
    <Member: Jeff Person <jperson@example.com> on bee@example.com
             as MemberRole.member>

Now we can delete some members.
::

    >>> from mailman.testing.tempfile import NamedTemporaryFile
    >>> from mailman.utilities.filesystem import open
    >>> filename = cleanups.enter_context(NamedTemporaryFile()).name
    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... aperson@example.com
    ... cperson@example.com (Cate Person)
    ... """, file=fp)

    >>> command('mailman delmembers -f ' + filename + ' -l  bee.example.com')

    >>> from operator import attrgetter
    >>> from mailman.testing.documentation import dump_list    
    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Bart Person <bperson@example.com>
    Doug Person <dperson@example.com>
    Elly Person <eperson@example.com>
    Fred Person <fperson@example.com>
    Greg Person <gperson@example.com>
    Irma Person <iperson@example.com>
    Jeff Person <jperson@example.com>

You can also specify ``-`` as the filename, in which case the addresses are
taken from standard input.
::

    >>> stdin = """\
    ... dperson@example.com
    ... Elly Person <eperson@example.com>
    ... """
    >>> command('mailman delmembers -f - -l bee.example.com', input=stdin)

    >>> from mailman.testing.documentation import dump_list    
    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Bart Person <bperson@example.com>
    Fred Person <fperson@example.com>
    Greg Person <gperson@example.com>
    Irma Person <iperson@example.com>
    Jeff Person <jperson@example.com>

Blank lines and lines that begin with '#' are ignored.
::

    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... # cperson@example.com
    ...
    ... bperson@example.com
    ... """, file=fp)

    >>> command('mailman delmembers -f ' + filename + ' -l bee.example.com')

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Fred Person <fperson@example.com>
    Greg Person <gperson@example.com>
    Irma Person <iperson@example.com>
    Jeff Person <jperson@example.com>

Addresses which are not subscribed are ignored, although a warning is
printed.
::

    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... kperson@example.com
    ... iperson@example.com
    ... """, file=fp)

    >>> command('mailman delmembers -f ' + filename + ' -l bee.example.com')
    Member not subscribed (skipping): kperson@example.com

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Fred Person <fperson@example.com>
    Greg Person <gperson@example.com>
    Jeff Person <jperson@example.com>

Addresses to delete can be specified on the command line.
::

    >>> command('mailman delmembers -m gperson@example.com -l bee.example.com')

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Fred Person <fperson@example.com>
    Jeff Person <jperson@example.com>

All members can be deleted as well.
::

    >>> command('mailman delmembers --all -l bee.example.com')

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    *Empty*

You can also delete members from all lists in the installation.  Lets create
another list and populate our lists.
::

    >>> ant = create_list('ant@example.com')
    >>> subscribe(ant, 'Anne')
    <Member: Anne Person <aperson@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(ant, 'Bart')
    <Member: Bart Person <bperson@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(ant, 'Cate')
    <Member: Cate Person <cperson@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(ant, 'Doug')
    <Member: Doug Person <dperson@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(ant, 'Elly')
    <Member: Elly Person <eperson@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Cate')
    <Member: Cate Person <cperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Doug')
    <Member: Doug Person <dperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Elly')
    <Member: Elly Person <eperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Fred')
    <Member: Fred Person <fperson@example.com> on bee@example.com
             as MemberRole.member>
    >>> subscribe(bee, 'Greg')
    <Member: Greg Person <gperson@example.com> on bee@example.com
             as MemberRole.member>

Now lets remove ``Bart``, ``Cate`` and ``Doug`` from all lists.  Note that
``Bart`` is not a member of ``bee``, but that's OK, and we don't get a message
about that if we're doing all lists.  Also, we can build the deletion list from
a file and the command line combined.
::

    >>> with open(filename, 'w', encoding='utf-8') as fp:
    ...     print("""\
    ... Bart <bperson@example.com>
    ... cperson@example.com (Cate Person)
    ... """, file=fp)
    >>> command('mailman delmembers -f ' + filename + ' -m dperson@example.com '
    ... '--fromall')

    >>> dump_list(ant.members.addresses, key=attrgetter('email'))
    Anne Person <aperson@example.com>
    Elly Person <eperson@example.com>

    >>> dump_list(bee.members.addresses, key=attrgetter('email'))
    Elly Person <eperson@example.com>
    Fred Person <fperson@example.com>
    Greg Person <gperson@example.com>
