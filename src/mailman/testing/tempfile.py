# Copyright (C) 2025 by the Free Software Foundation, Inc.
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

"""Windows-safe NamedTemporaryFile replacement and TempDir helper."""

import os
import shutil
import tempfile
import tempfile as _tempfile

from mailman.utilities.filesystem import File, open


class NamedTemporaryFile:
    """Drop-in for tempfile.NamedTemporaryFile compatible with Windows.

    Usage is identical to the stdlib version::

        with NamedTemporaryFile('w', buffering=1, encoding='utf-8') as fp:
            print('some content', file=fp)
            result = runner.invoke(cmd, (fp.name, ...))

    Key differences from stdlib:
    - The temp path is allocated via mkstemp() then the fd is immediately
      closed, so no O_TEMPORARY / exclusive-lock is held.  Other callers
      can freely open the same path while this context manager is active.
    - The write handle is opened lazily on the first write(), so tests that
      only need the path (CLI writes to the file, test reads it back) never
      hold a conflicting handle at all.
    - On __exit__ the file is deleted regardless of exceptions.
    """

    def __init__(self, mode='wb', buffering=-1, encoding=None,
                 delete=True, suffix=None, prefix=None, dir=None, **kwargs):
        # Ignore remaining unknown kwargs (e.g. 'errors') for drop-in compat.
        self._mode = mode
        self._buffering = buffering
        self._encoding = encoding
        self._delete = delete
        self._fh = None
        # Allocate the path now; close the fd immediately so no handle is held.
        fd, self._path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        os.close(fd)

    def __enter__(self):
        return self

    def close(self):
        """Close the file handle and, if *delete* is True (the default), delete the temp file."""
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        if self._delete:
            try:
                os.unlink(self._path)
            except FileNotFoundError:
                pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # File-like interface (enough for print() and explicit write/flush)
    # ------------------------------------------------------------------

    def _open_lazy(self):
        if self._fh is None:
            self._fh = open(
                self._path, self._mode,
                buffering=self._buffering,
                encoding=self._encoding,
            )

    def write(self, s):
        self._open_lazy()
        return self._fh.write(s)


    def flush(self):
        if self._fh is not None:
            self._fh.flush()
            # Close the write handle so that other callers can open the file
            # by name on Windows.  The file itself is not deleted; it persists
            # until close() / __exit__ is called.
            self._fh.close()
            self._fh = None

    # ------------------------------------------------------------------
    # Path access
    # ------------------------------------------------------------------

    @property
    def name(self):
        """Forward-slash path string for this temp file."""
        return str(File(self._path))


class TemporaryDirectory(File):
    """A temporary directory that deletes itself on context-manager exit.

    Usage::

        with TempDir() as d:
            # d is the TempDir (a File); str(d) is the forward-slash path
            (d / 'sub').makedirs()

    The directory is removed (recursively) when the ``with`` block exits.
    """

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, suffix=None, prefix=None, dir=None):
        super().__init__(_tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))

    def __enter__(self):
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        shutil.rmtree(self.os_path, ignore_errors=True)
        return False

    cleanup = __exit__
