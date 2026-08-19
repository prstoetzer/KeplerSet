from __future__ import annotations

import ctypes
import os
import tempfile
import uuid
from pathlib import Path


class OutputPathError(OSError):
    """Raised when an export destination is not safe or writable."""


def _windows_documents_known_folder() -> Path | None:
    """Return the redirected Windows Documents known folder when available."""
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = GUID()
        ctypes.memmove(
            ctypes.byref(guid),
            uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le,
            ctypes.sizeof(guid),
        )
        path_ptr = ctypes.c_void_p()
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.HRESULT
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
        )
        if result != 0 or not path_ptr.value:
            return None
        try:
            return Path(ctypes.wstring_at(path_ptr.value))
        finally:
            ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole32.CoTaskMemFree(path_ptr)
    except (AttributeError, OSError, ValueError):
        return None


def user_documents_dir() -> Path:
    """Return a user-writable default directory for exported documents.

    Windows uses the Documents Known Folder so redirected/OneDrive locations are
    honored. macOS and other desktop Unix systems use ~/Documents, with the home
    directory as a conservative fallback if Documents does not exist.
    """
    if os.name == "nt":
        known = _windows_documents_known_folder()
        if known is not None:
            return known
        profile = os.environ.get("USERPROFILE")
        if profile:
            candidate = Path(profile) / "Documents"
            if candidate.exists():
                return candidate
        home = Path.home()
        candidate = home / "Documents"
        return candidate if candidate.exists() else home

    home = Path.home()
    candidate = home / "Documents"
    return candidate if candidate.exists() else home


def resolve_output_path(path: Path) -> Path:
    """Expand and make an export path absolute without requiring it to exist."""
    return path.expanduser().resolve(strict=False)


def preflight_output_path(path: Path) -> Path:
    """Validate that an export destination can be written before network I/O."""
    output = resolve_output_path(path)
    parent = output.parent

    if output.exists() and output.is_dir():
        raise OutputPathError(f"Export destination is a directory, not a file: {output}")
    if not parent.exists():
        raise OutputPathError(
            f"Export folder does not exist: {parent}\nChoose an existing folder."
        )
    if not parent.is_dir():
        raise OutputPathError(f"Export parent is not a directory: {parent}")
    if output.exists() and not os.access(output, os.W_OK):
        raise OutputPathError(
            f"KeplerSet cannot overwrite this file because it is not writable:\n{output}"
        )

    probe: Path | None = None
    try:
        fd, probe_name = tempfile.mkstemp(
            prefix=f".{output.name}.keplerset-", suffix=".tmp", dir=parent
        )
        os.close(fd)
        probe = Path(probe_name)
    except OSError as exc:
        raise OutputPathError(
            f"KeplerSet cannot write to this folder:\n{parent}\n\n{exc}"
        ) from exc
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
    return output


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically replace an output file using a temporary file in the same folder."""
    output = resolve_output_path(path)
    parent = output.parent
    temp_path: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{output.name}.keplerset-", suffix=".tmp", dir=parent
        )
        temp_path = Path(temp_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, output)
        temp_path = None
    except OSError as exc:
        raise OutputPathError(
            f"KeplerSet could not save the export to:\n{output}\n\n{exc}"
        ) from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
