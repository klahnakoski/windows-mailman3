# Copyright (C) 2014-2025 by the Free Software Foundation, Inc.
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

"""Test the replybot handler."""

import unittest

from mailman.app.lifecycle import create_list
from mailman.config import config
from mailman.interfaces.autorespond import ResponseAction
from mailman.testing.helpers import (
    get_queue_messages,
    specialized_message_from_string as mfs,
)
from mailman.testing.layers import ConfigLayer


class TestReplybot(unittest.TestCase):
    """Test the replybot handler."""

    layer = ConfigLayer

    def setUp(self):
        self._mlist = create_list('ant@example.com')

    def test_response(self):
        """Response for a posting message."""
        self._mlist.autorespond_postings = ResponseAction.respond_and_continue
        msgdata = {'to_list': True}
        msg = mfs("""\
From: Alice <alice@exmaple.com>
To: test@example.com
Message-ID: <msgid@example.com>
Subject: Test

body
""")

        config.handlers['replybot'].process(
            self._mlist,
            msg,
            msgdata
        )
        items = get_queue_messages('virgin')
        self.assertEqual(len(items), 1)
        self.assertEqual(
            items[0].msg.get('x-mailer', None),
            'The Mailman Replybot'
        )

    def test_ignore_message_no_valid_sender(self):
        """Ignore a posting message with no valid sender address."""
        self._mlist.autorespond_postings = ResponseAction.respond_and_continue
        msgdata = {'to_list': True}
        msg = mfs('')

        config.handlers['replybot'].process(
            self._mlist,
            msg,
            msgdata
        )
        items = get_queue_messages('virgin')
        self.assertEqual(len(items), 0)
