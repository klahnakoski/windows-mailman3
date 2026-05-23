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

from mailman.utilities.filesystem import File


def fake_makedirs(path, mode, exist_ok=False):
    """A fake makedirs function"""

    with File(path).open('a'):
        pass

    raise FileExistsError("%s exists.", path)


class TestMakedirs(unittest.TestCase):
    """Tests the makedirs utility function"""

    def setUp(self):
        self.test_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_directory)

        self.foo = os.path.join(self.test_directory, "foo")
        self.bar = os.path.join(self.foo, "bar")
        self.baz = os.path.join(self.bar, "baz")
