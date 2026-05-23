"""Cross-platform file lock for Mailman.

On Linux/POSIX this module re-exports ``flufl.lock`` unchanged.
On Windows it provides a drop-in replacement that keeps the lock file
descriptor open so the OS prevents deletion by other processes.

Public API (mirrors flufl.lock):
    Lock, LockError, NotLockedError, TimeOutError, AlreadyLockedError,
    LockState, SEP, pid_exists
"""

from __future__ import annotations

import os
import sys

from public import public


_is_windows = sys.platform == 'win32'

# ---------------------------------------------------------------------------
# POSIX: just re-export flufl.lock — nothing changes on Linux.
# ---------------------------------------------------------------------------

if not _is_windows:
    from flufl.lock import (  # noqa: F401
        AlreadyLockedError,
        Lock,
        LockError,
        LockState,
        NotLockedError,
        SEP,
        TimeOutError,
    )
    public(
        AlreadyLockedError=AlreadyLockedError,
        Lock=Lock,
        LockError=LockError,
        LockState=LockState,
        NotLockedError=NotLockedError,
        SEP=SEP,
        TimeOutError=TimeOutError,
    )

    @public
    def pid_exists(pid: int) -> bool:
        """Check whether a process with the given pid exists."""
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

# ---------------------------------------------------------------------------
# Windows: custom implementation using O_CREAT|O_EXCL with held-open fd.
# ---------------------------------------------------------------------------

else:
    import time
    import errno
    import ctypes
    import random
    import socket
    import logging

    from contextlib import suppress
    from datetime import datetime, timedelta
    from enum import Enum
    from mailman.utilities.filesystem import File, open
    from typing import Final, Literal, TYPE_CHECKING, Union
    if TYPE_CHECKING:
        from types import TracebackType

    Interval = Union[timedelta, int]

    DEFAULT_LOCK_LIFETIME: Final = timedelta(seconds=15)

    SEP: Final = '^'
    public(SEP=SEP)

    log = logging.getLogger('mailman.lock')

    # -- exceptions ----------------------------------------------------------

    @public
    class LockError(Exception):
        """Base class for lock exceptions."""

    @public
    class AlreadyLockedError(LockError):
        """Lock is already held by us."""

    @public
    class NotLockedError(LockError):
        """Attempt to unlock a lock we don't hold."""

    @public
    class TimeOutError(LockError):
        """Timed out waiting for the lock."""

    # -- LockState -----------------------------------------------------------

    @public
    class LockState(Enum):
        unlocked = 1
        ours = 2
        ours_expired = 3
        stale = 4
        theirs_expired = 5
        unknown = 6

    # -- helpers -------------------------------------------------------------

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    @public
    def pid_exists(pid: int) -> bool:
        """Check whether a process with the given pid exists (Windows).

        Does NOT use os.kill(pid, 0) because on Windows that sends
        CTRL_C_EVENT which triggers KeyboardInterrupt in the target.
        Uses ctypes OpenProcess instead.
        """
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False

    def _to_seconds(value: Interval | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, timedelta):
            return value.total_seconds()
        return float(value)

    # -- Lock ----------------------------------------------------------------

    @public
    class Lock:
        """Portable file-based lock for Windows.

        The file descriptor is kept **open** for the lifetime of the lock.
        This prevents other processes from deleting the file, which is how
        we detect whether the lock is still actively held.  Stale-lock
        detection: if ``os.unlink`` succeeds the previous holder is gone.

        Constructor signature matches ``flufl.lock.Lock``.
        """

        def __init__(
            self,
            lockfile,
            lifetime: Interval | None = None,
            separator: str = SEP,
            default_timeout: Interval | None = None,
        ):
            self._lockfile = str(lockfile)
            self._separator = separator
            self._hostname = socket.getfqdn()
            self._lifetime = (
                lifetime if isinstance(lifetime, timedelta)
                else timedelta(seconds=lifetime) if lifetime is not None
                else DEFAULT_LOCK_LIFETIME
            )
            self._default_timeout = default_timeout
            self._owned = False
            self._lock_time: datetime | None = None
            self._fd: int | None = None

        def __repr__(self) -> str:
            status = 'locked' if self._owned else 'unlocked'
            return (f'<Lock {self._lockfile} [{status}] '
                    f'pid={os.getpid()} at {id(self):#x}>')

        # -- properties ------------------------------------------------------

        @property
        def hostname(self) -> str:
            return self._hostname

        @property
        def lifetime(self) -> timedelta:
            return self._lifetime

        @lifetime.setter
        def lifetime(self, value: Interval) -> None:
            if isinstance(value, timedelta):
                self._lifetime = value
            else:
                self._lifetime = timedelta(seconds=value)

        @property
        def details(self) -> tuple[str, int, str]:
            """Read ``(hostname, pid, lockfile)`` from the lock file.

            Content format (matches flufl.lock): ``lockfile^hostname^pid^random``
            """
            if self._owned and self._fd is not None:
                try:
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    raw = os.read(self._fd, 4096)
                    data = raw.decode().strip()
                except OSError:
                    raise NotLockedError('Details are unavailable')
            else:
                try:
                    with open(self._lockfile, 'r') as fp:
                        data = fp.read().strip()
                except OSError:
                    raise NotLockedError('Details are unavailable')
            try:
                lockfile, hostname, pid_str, _random = data.split(self._separator)
                pid = int(pid_str)
            except (ValueError, TypeError):
                raise NotLockedError('Details are unavailable')
            return hostname, pid, lockfile

        @property
        def is_locked(self) -> bool:
            """True if *we* hold the lock."""
            if not self._owned:
                return False
            try:
                hostname, pid, _ = self.details
            except NotLockedError:
                self._owned = False
                return False
            if hostname == self._hostname and pid == os.getpid():
                return True
            self._owned = False
            return False

        @property
        def state(self) -> LockState:
            try:
                hostname, pid, _ = self.details
            except NotLockedError:
                return LockState.unlocked
            expired = (
                self._lock_time is not None
                and datetime.now() > self._lock_time + self._lifetime
            )
            if hostname == self._hostname and pid == os.getpid():
                return LockState.ours_expired if expired else LockState.ours
            if hostname != self._hostname:
                return LockState.unknown
            if pid_exists(pid):
                return LockState.unknown
            return LockState.stale

        # -- lock / unlock ---------------------------------------------------

        def lock(self, timeout: Interval | None = None) -> None:
            """Acquire the lock.

            :raises AlreadyLockedError: if we already hold the lock.
            :raises TimeOutError: if *timeout* expires.
            """
            if self._owned:
                raise AlreadyLockedError('We already have the lock')
            if timeout is None:
                timeout = self._default_timeout
            deadline = _to_seconds(timeout)
            end_time = (
                (time.monotonic() + deadline) if deadline is not None
                else None
            )
            while True:
                if self._try_acquire():
                    return
                if end_time is not None and time.monotonic() >= end_time:
                    raise TimeOutError('Could not acquire the lock')
                if self._break_if_stale():
                    continue
                time.sleep(
                    0.1 + 0.1 * (hash(self._lockfile) % 10) / 10)

        def unlock(self, *, unconditionally: bool = False) -> None:
            """Release the lock."""
            if not self._owned and not unconditionally:
                raise NotLockedError('Already unlocked')
            if self._fd is not None:
                with suppress(OSError):
                    os.close(self._fd)
                self._fd = None
            with suppress(OSError):
                os.unlink(self._lockfile)
            self._owned = False
            self._lock_time = None

        def refresh(
            self,
            lifetime: Interval | None = None,
            *,
            unconditionally: bool = False,
        ) -> None:
            if lifetime is not None:
                self.lifetime = lifetime
            if not self.is_locked and not unconditionally:
                raise NotLockedError(f'{self!r}')
            self._lock_time = datetime.now()

        # -- context manager -------------------------------------------------

        def __enter__(self) -> Lock:
            self.lock()
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> Literal[False]:
            self.unlock()
            return False

        # -- internals -------------------------------------------------------

        def _try_acquire(self) -> bool:
            """Attempt atomic lock file creation."""
            try:
                fd = os.open(
                    self._lockfile,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                    0o644,
                )
            except FileExistsError:
                return False
            except OSError as e:
                if e.errno == errno.ENOENT:
                    File(self._lockfile).parent.makedirs()
                    return self._try_acquire()
                raise
            try:
                # Write in the same 4-field format as flufl.lock:
                # lockfile^hostname^pid^random
                content = self._separator.join([
                    self._lockfile,
                    self._hostname,
                    str(os.getpid()),
                    str(random.randint(0, 2**31)),
                ]) + '\n'
                os.write(fd, content.encode())
            except BaseException:
                os.close(fd)
                raise
            # Keep fd open — Windows prevents deletion while open.
            self._fd = fd
            self._owned = True
            self._lock_time = datetime.now()
            return True

        def _break_if_stale(self) -> bool:
            """Break the lock if it appears stale. Return True if broken."""
            # On Windows, if the owning process holds the fd open,
            # os.unlink will fail with PermissionError -> not stale.
            # If the process has exited, Windows closed the fd and we
            # can delete -> stale.
            try:
                os.unlink(self._lockfile)
            except PermissionError:
                return False
            except FileNotFoundError:
                return True
            except OSError:
                return False
            log.warning('Breaking stale lock %s', self._lockfile)
            return True

        def force_acquire(
            self, timeout: Interval | None = None,
        ) -> None:
            """Force-acquire the lock, killing the holder if necessary.

            1. Try normal acquire first.
            2. Read the lock file to find the holding pid.
            3. If the process is dead, just wait for stale-break.
            4. If alive, terminate it and wait for the fd to close.
            5. Acquire normally.

            :raises TimeOutError: if we still can't acquire.
            """
            # Try normal acquire first.
            if timeout is None:
                timeout = self._default_timeout
            try:
                self.lock(timeout)
                return
            except TimeOutError:
                pass
            # Read details from the lock file (without owning it).
            try:
                hostname, holder_pid, _ = self.details
            except NotLockedError:
                # Lock file vanished — retry.
                self.lock(timeout)
                return
            # Only kill processes on the same host.
            if hostname != self._hostname:
                raise TimeOutError(
                    f'Lock held by different host: {hostname}')
            # If we are the holder (another Lock instance in this process),
            # just force-delete the file rather than killing ourselves.
            if holder_pid == os.getpid():
                log.warning(
                    'Force-acquiring lock %s: breaking own stale lock',
                    self._lockfile)
                with suppress(OSError):
                    os.unlink(self._lockfile)
                self.lock(timeout)
                return
            # Terminate the holding process.
            if pid_exists(holder_pid):
                log.warning(
                    'Force-acquiring lock %s: terminating pid %d',
                    self._lockfile, holder_pid)
                PROCESS_TERMINATE = 0x0001
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_TERMINATE, False, holder_pid)
                if handle:
                    ctypes.windll.kernel32.TerminateProcess(handle, 1)
                    ctypes.windll.kernel32.CloseHandle(handle)
                # TerminateProcess is asynchronous.  Rather than waiting for
                # pid_exists() to return False (which requires *all* handles to
                # the process object to be closed — including any pipe handles
                # held by the caller), wait for the lock file to become
                # unlinkable.  File handles are released as part of kernel-level
                # process teardown, which happens before user-space handles drop.
                deadline = time.monotonic() + 10
                while True:
                    try:
                        os.unlink(self._lockfile)
                        break           # file released — process is terminated
                    except PermissionError:
                        if time.monotonic() >= deadline:
                            raise TimeOutError(
                                f'Could not terminate pid {holder_pid}')
                        time.sleep(0.05)
                    except FileNotFoundError:
                        break           # already gone
            # Lock file is gone; acquire a fresh one.
            effective_timeout = timeout if timeout is not None else timedelta(seconds=5)
            self.lock(effective_timeout)

