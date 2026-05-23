# Copyright (C) 2009-2025 by the Free Software Foundation, Inc.
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

"""Filesystem utilities."""

import os
import sys
import builtins

from contextlib import suppress
from public import public


# ---------------------------------------------------------------------------
# Characters that are invalid in filenames on Windows.
# ---------------------------------------------------------------------------
WINDOWS_UNSAFE_CHARS = ':*?"<>|'

# drop in replacement for builtins.open
def open(path, mode="r", **kwargs):
    return File(path).open(mode, **kwargs)


def sanitize_filename(name):
    """Sanitize a bare filename (no directory separators) for the platform.

    On Windows, characters invalid in filenames (``:``, ``*``, etc.) are
    replaced with underscores.  On other platforms the name is returned
    unchanged.

    :param name: The filename to sanitize.
    :type name: str
    :return: The sanitized filename.
    :rtype: str
    """
    if sys.platform != "win32":
        return name
    for ch in WINDOWS_UNSAFE_CHARS:
        name = name.replace(ch, "_")
    return name


def sanitize_path(path):
    """Sanitize a filesystem path for the current platform.

    On Windows, characters like colons are replaced with underscores
    (except for the drive letter prefix, e.g. ``C:\\``).  On other
    platforms the path is returned unchanged.

    :param path: The filesystem path to sanitize.
    :type path: str
    :return: The sanitized path.
    :rtype: str
    """
    if sys.platform != "win32":
        return path
    path = path.os_path if hasattr(path, "os_path") else str(path)
    # File URIs on Windows arrive as /C:\... or /C:/... — strip leading slash.
    if len(path) >= 3 and path[0] == "/" and path[2] in (":", "|"):
        path = path[1:]
    # Preserve drive letter (e.g. C:\)
    drive, tail = os.path.splitdrive(path)
    for ch in WINDOWS_UNSAFE_CHARS:
        tail = tail.replace(ch, "_")
    return drive + tail


@public
def safe_rename(src, dst):
    """Rename *src* to *dst*, working correctly on all platforms.

    On POSIX, :func:`os.rename` atomically replaces an existing destination
    file and raises :exc:`OSError` only if *dst* is a non-empty directory.

    On Windows, :func:`os.rename` raises :exc:`FileExistsError` whenever
    *dst* already exists (file **or** directory), and :func:`os.replace`
    raises :exc:`PermissionError` when *dst* is an existing directory.
    This function normalises the behaviour:

    * If *dst* is an existing file, use :func:`os.replace` for an atomic
      overwrite (matching POSIX rename semantics).
    * If *dst* is an existing **empty** directory, remove it first, then
      rename, so that migrating a list data directory over the old path does
      not fail.
    * Otherwise delegate directly to :func:`os.rename`.

    :param src: The source path.
    :type src: str or path-like
    :param dst: The destination path.
    :type dst: str or path-like
    """
    try:
        os.rename(src, dst)
    except FileExistsError:
        # Windows raises FileExistsError when dst already exists.
        if os.path.isdir(dst):
            # os.replace() cannot atomically replace a directory on Windows.
            # Remove the empty destination directory first, then rename.
            os.rmdir(dst)
            os.rename(src, dst)
        else:
            os.replace(src, dst)


@public
class File:
    """A cross-platform filesystem path.

    ``str(File(path))`` always uses ``/`` as the separator (Linux-like).
    ``File.os_path`` returns the OS-native absolute path.

    Examples::

        f = File('/tmp/foo') / 'bar'
        str(f)              # '/tmp/foo/bar'
        f.os_path         # OS-native absolute path (backslashes on Windows)
        f.makedirs()        # create the directory tree
        with f.open('w') as fp:
            fp.write('hello')
        with f as fp:       # default read mode
            print(fp.read())

    """

    def __new__(cls, path, *args, **kwargs):
        if kwargs:
            return File(path).open(*args, **kwargs)
        return object.__new__(cls)

    def __init__(self, *parts, **kwargs):
        # Normalise separators to forward slash.
        parts = [str(p) for p in parts]
        path = os.path.join(*parts)
        # On Windows, file URI paths and url2pathname() output can arrive as
        # '/C:/...' or '\C:\...' (leading slash/backslash before drive letter).
        # Strip the leading separator so os.path.abspath() doesn't mangle it.
        if (
            sys.platform == "win32"
            and len(path) >= 3
            and path[0] in ("/", "\\")
            and path[1:2].isalpha()
            and path[2] == ":"
        ):
            path = path[1:]
        self._path = path.replace(os.sep, "/")
        self._fh = None

    # ------------------------------------------------------------------
    # String / path protocol
    # ------------------------------------------------------------------

    def __str__(self):
        return self._path

    def __repr__(self):
        return f"File({self._path!r})"

    def __eq__(self, other):
        if isinstance(other, File):
            return self.os_path == other.os_path
        if isinstance(other, str):
            return self.os_path == File(other).os_path
        return NotImplemented

    def __hash__(self):
        return hash(self.os_path)

    def __truediv__(self, other):
        """Join with a sub-path, returning a new File."""
        other_s = str(other).replace(os.sep, "/")
        return File(self._path.rstrip("/") + "/" + other_s.lstrip("/"))

    def __rtruediv__(self, other):
        return File(str(other)) / self._path

    def __fspath__(self):
        """Support os.fspath() — returns the forward-slash path string."""
        return self._path

    def startswith(self, prefix, *args):
        """str.startswith with OS-separator normalisation."""
        if isinstance(prefix, str):
            prefix = prefix.replace(os.sep, "/")
        elif isinstance(prefix, tuple):
            prefix = tuple(p.replace(os.sep, "/") if isinstance(p, str) else p for p in prefix)
        return self._path.startswith(prefix, *args)

    # ------------------------------------------------------------------
    # Path properties
    # ------------------------------------------------------------------
    @property
    def os_path(self):
        """OS-native absolute path string."""
        return sanitize_path(os.path.abspath(self._path))

    @property
    def parent(self):
        """Parent directory as a :class:`File`."""
        stripped = self._path.rstrip("/")
        if "/" not in stripped:
            return File(".")
        head, _ = stripped.rsplit("/", 1)
        return File(head or "/")

    @property
    def name(self):
        """Final path component (filename)."""
        return self._path.rstrip("/").rsplit("/", 1)[-1]

    @property
    def stem(self):
        """Filename without extension."""
        n = self.name
        if "." not in n or n.startswith("."):
            return n
        return n.rsplit(".", 1)[0]

    @property
    def extension(self):
        """File extension without leading dot, or empty string."""
        n = self.name
        if "." not in n or n.startswith("."):
            return ""
        return n.rsplit(".", 1)[1]

    @property
    def suffix(self):
        """File extension with leading dot (e.g. ``'.cfg'``), or empty string.

        Mirrors :attr:`pathlib.Path.suffix`.
        """
        ext = self.extension
        return ("." + ext) if ext else ""

    @property
    def exists(self):
        """True if the path exists on disk."""
        return os.path.exists(sanitize_path(self._path))

    @property
    def is_dir(self):
        """True if the path is a directory."""
        return os.path.isdir(sanitize_path(self._path))

    @property
    def is_file(self):
        """True if the path is a regular file."""
        return os.path.isfile(sanitize_path(self._path))

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def open(self, mode="r", **kwargs):
        """Open and return a file handle context manager.

        Equivalent to the old ``safe_open(path, mode)``: sanitizes the path
        and defaults text-mode encoding to ``utf-8``.
        """
        if "b" not in mode:
            kwargs.setdefault("encoding", "utf-8")
        if "w" in mode and not self.parent.exists:
            os.makedirs(self.parent.os_path, exist_ok=True)
        return builtins.open(self.os_path, mode, **kwargs)

    def __enter__(self):
        """Open for reading; use as ``with open(path, 'r') as fp:``."""
        self._fh = self.open(mode="r", encoding="utf-8")
        return self._fh

    def __exit__(self, *exc):
        self._fh.close()
        self._fh = None
        return False

    def read_text(self, encoding="utf-8"):
        """Return the file contents as a string."""
        with builtins.open(self.os_path, encoding=encoding) as fp:
            return fp.read()

    def readlines(self):
        with self.open() as fp:
            return fp.readlines()

    def iterdir(self):
        """Yield :class:`File` objects for each entry in this directory."""
        for entry in os.scandir(self.os_path):
            yield File(entry.path)

    def listdir(self):
        return [entry.name for entry in os.scandir(self.os_path)]

    def makedirs(self, mode=0o0755):
        """Create this directory and all missing parents."""
        old_umask = os.umask(0)
        try:
            try:
                os.makedirs(self.os_path, mode, exist_ok=True)
            except FileExistsError:
                pass
        finally:
            os.umask(old_umask)

        for dirpath, dirnames, filenames in os.walk(self.os_path):
            with suppress(OSError):
                os.chmod(dirpath, mode)
        return self

    def rename(self, dst):
        """Rename / move this path to *dst*."""
        safe_rename(self.os_path, File(dst).os_path)

    def remove(self):
        """Remove this file, silently ignoring if it does not exist."""
        with suppress(FileNotFoundError):
            os.remove(self.os_path)


    # ------------------------------------------------------------------
    # Static utilities
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_name(name):
        """Sanitize a bare filename for the current platform.

        On Windows replaces characters invalid in filenames (``:``, ``*``,
        etc.) with underscores.  On other platforms returns *name* unchanged.
        """
        return sanitize_filename(name)
