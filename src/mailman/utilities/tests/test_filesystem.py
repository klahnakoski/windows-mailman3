# Copyright (C) 2011-2025 by the Free Software Foundation, Inc.
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

"""Testing functions in the filesystem utilities."""

import os
import shutil
import tempfile
import unittest


from mailman.testing.helpers import skipLinux, skipWindows
from mailman.utilities.filesystem import File, safe_rename
from mailman.utilities.filesystem import sanitize_path


class TestMakedirs(unittest.TestCase):
    """Tests filesystem helpers."""

    def setUp(self):
        self.test_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_directory)

        self.foo = os.path.join(self.test_directory, "foo")
        self.bar = os.path.join(self.foo, "bar")
        self.baz = os.path.join(self.bar, "baz")

    def test_open_creates_parent_directories(self):
        with File(self.baz).open('w') as fp:
            fp.write('hello')
        self.assertTrue(File(self.baz).exists)
        self.assertEqual(File(self.baz).read_text(), 'hello')

    def test_makedirs_creates_directories(self):
        created = File(self.bar).makedirs()
        self.assertEqual(created, File(self.bar))
        self.assertTrue(File(self.bar).is_dir)

    def test_remove_deletes_file(self):
        path = File(self.baz)
        with path.open('w') as fp:
            fp.write('x')
        path.remove()
        self.assertFalse(path.exists)

    def test_remove_missing_is_ok(self):
        File(self.baz).remove()
        self.assertFalse(File(self.baz).exists)

    def test_safe_rename_replaces_existing_file(self):
        src = File(self.foo) / 'src.txt'
        dst = File(self.foo) / 'dst.txt'
        with src.open('w') as fp:
            fp.write('src')
        with dst.open('w') as fp:
            fp.write('dst')

        safe_rename(src.os_path, dst.os_path)

        self.assertFalse(src.exists)
        self.assertEqual(dst.read_text(), 'src')

    @skipLinux
    def test_sanitize_path_unsafe_chars(self):
        self.assertEqual(
            sanitize_path('list:admin:action:post.txt'),
            'list_admin_action_post.txt',
        )

    @skipLinux
    def test_sanitize_path_windows(self):
        self.assertEqual(
            sanitize_path('/C:/tmp/a:b.txt'),
            'C:/tmp/a_b.txt',
        )

    @skipWindows
    def test_sanitize_path_non_windows(self):
        original = '/tmp/a:b.txt'
        self.assertEqual(sanitize_path(original), original)

