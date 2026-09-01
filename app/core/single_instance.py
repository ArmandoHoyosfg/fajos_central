"""Single-instance lock for launcher and related processes (Windows + POSIX)."""
from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

_LOCK_HANDLES: list = []


def _lock_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    d = root / ".runtime"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        d = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    return d


def acquire_lock(name: str) -> bool:
    """
    Try to acquire a process-wide lock named `name`.
    Returns True if this process owns the lock (first instance).
    Returns False if another instance already holds it.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:64]
    if sys.platform == "win32":
        return _acquire_windows(safe)
    return _acquire_posix(safe)


def _acquire_windows(name: str) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        # Local\ avoids admin elevation requirement of Global\
        mutex_name = f"Local\\FajosCentral_{name}"
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            return True  # fail open: allow start
        ERROR_ALREADY_EXISTS = 183
        err = ctypes.get_last_error()
        if err == ERROR_ALREADY_EXISTS:
            # Still holds a handle to existing mutex; release and report busy
            kernel32.CloseHandle(handle)
            return False
        _LOCK_HANDLES.append(("mutex", handle))
        atexit.register(lambda h=handle: kernel32.CloseHandle(h))
        return True
    except Exception:
        return _acquire_posix(name)


def _acquire_posix(name: str) -> bool:
    path = _lock_dir() / f"{name}.lock"
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
    except Exception:
        return True
    try:
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                os.close(fd)
                return False
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                return False
        # write pid
        try:
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        except Exception:
            pass
        _LOCK_HANDLES.append(("fd", fd, str(path)))
        def _release(f=fd):
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(f, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(f)
            except Exception:
                pass
        atexit.register(_release)
        return True
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        return True


def read_lock_pid(name: str) -> int | None:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:64]
    path = _lock_dir() / f"{safe}.lock"
    try:
        txt = path.read_text(encoding="utf-8").strip()
        return int(txt) if txt.isdigit() else None
    except Exception:
        return None
