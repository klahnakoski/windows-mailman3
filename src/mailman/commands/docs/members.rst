================
Managing members
================

The ``mailman members`` command allows a site administrator to display the
members of a mailing list.

    >>> from mailman.testing.documentation import cli
    >>> command = cli('mailman.commands.cli_members.members')


Listing members
===============

You can list all the members of a mailing list by calling the command with no
options.  To start with, there are no members of the mailing list.

    >>> from mailman.app.lifecycle import create_list
    >>> ant = create_list('ant@example.com')
    >>> command('mailman members ant.example.com')
    ant.example.com has no members

Once the mailing list add some members, they will be displayed.
::

    >>> from mailman.testing.helpers import subscribe
    >>> subscribe(ant, 'Anne', email='anne@example.com')
    <Member: Anne Person <anne@example.com> on ant@example.com
             as MemberRole.member>
    >>> subscribe(ant, 'Bart', email='bart@example.com')
    <Member: Bart Person <bart@example.com> on ant@example.com
             as MemberRole.member>

    >>> command('mailman members ant.example.com')
    Anne Person <anne@example.com>
    Bart Person <bart@example.com>

Members are displayed in alphabetical order based on their address.
::

    >>> subscribe(ant, 'Anne', email='anne@aaaxample.com')
    <Member: Anne Person <anne@aaaxample.com> on ant@example.com
             as MemberRole.member>

    >>> command('mailman members ant.example.com')
    Anne Person <anne@aaaxample.com>
    Anne Person <anne@example.com>
    Bart Person <bart@example.com>

You can also output this list to a file.
::

    >>> from mailman.testing.tempfile import NamedTemporaryFile
    >>> from mailman.utilities.filesystem import open
    >>> filename = cleanups.enter_context(NamedTemporaryFile()).name

    >>> command('mailman members -o ' + filename + ' ant.example.com')
    >>> with open(filename, 'r', encoding='utf-8') as fp:
    ...     print(fp.read())
    Anne Person <anne@aaaxample.com>
    Anne Person <anne@example.com>
    Bart Person <bart@example.com>

The output file can also be standard out.

    >>> command('mailman members -o - ant.example.com')
    Anne Person <anne@aaaxample.com>
    Anne Person <anne@example.com>
    Bart Person <bart@example.com>


Filtering on delivery mode
--------------------------

You can limit output to just the regular non-digest members...
::

    >>> member = ant.members.get_member('anne@example.com')
    >>> from mailman.interfaces.member import DeliveryMode
    >>> member.preferences.delivery_mode = DeliveryMode.plaintext_digests

    >>> command('mailman members --regular ant.example.com')
    Anne Person <anne@aaaxample.com>
    Bart Person <bart@example.com>

...or just the digest members.  Furthermore, you can either display all digest
members...
::

    >>> member = ant.members.get_member('anne@aaaxample.com')
    >>> member.preferences.delivery_mode = DeliveryMode.mime_digests

    >>> command('mailman members --digest any ant.example.com')
    Anne Person <anne@aaaxample.com>
    Anne Person <anne@example.com>

...just plain text digest members...

    >>> command('mailman members --digest plaintext ant.example.com')
    Anne Person <anne@example.com>

...or just MIME digest members.
::

    >>> command('mailman members --digest mime ant.example.com')
    Anne Person <anne@aaaxample.com>


Filtering on delivery status
----------------------------

You can also filter the display on the member's delivery status.  By default,
all members are displayed, but you can filter out only those whose delivery
status is enabled...
::

    >>> from mailman.interfaces.member import DeliveryStatus

    >>> member = ant.members.get_member('anne@aaaxample.com')
    >>> member.preferences.delivery_status = DeliveryStatus.by_moderator
    >>> member = ant.members.get_member('bart@example.com')
    >>> member.preferences.delivery_status = DeliveryStatus.by_user

    >>> member = subscribe(ant, 'Cris', email='cris@example.com')
    >>> member.preferences.delivery_status = DeliveryStatus.unknown
    >>> member = subscribe(ant, 'Dave', email='dave@example.com')
    >>> member.preferences.delivery_status = DeliveryStatus.enabled
    >>> member = subscribe(ant, 'Elle', email='elle@example.com')
    >>> member.preferences.delivery_status = DeliveryStatus.by_bounces

    >>> command('mailman members --nomail enabled ant.example.com')
    Anne Person <anne@example.com>
    Dave Person <dave@example.com>

...or disabled by the user...

    >>> command('mailman members --nomail byuser ant.example.com')
    Bart Person <bart@example.com>

...or disabled by the list administrator (or moderator)...

    >>> command('mailman members --nomail byadmin ant.example.com')
    Anne Person <anne@aaaxample.com>

...or by the bounce processor...

    >>> command('mailman members --nomail bybounces ant.example.com')
    Elle Person <elle@example.com>

...or for unknown (legacy) reasons.

    >>> command('mailman members --nomail unknown ant.example.com')
    Cris Person <cris@example.com>

You can also display all members who have delivery disabled for any reason.
::

    >>> command('mailman members --nomail any ant.example.com')
    Anne Person <anne@aaaxample.com>
    Bart Person <bart@example.com>
    Cris Person <cris@example.com>
    Elle Person <elle@example.com>
