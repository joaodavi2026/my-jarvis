"""Windows VolumeProvider built on documented kernel32 APIs (ctypes; no extra dependency)."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

from .volumes import VolumeInfo, normalize_guid

log = logging.getLogger(__name__)

DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3
FILE_READ_ONLY_VOLUME = 0x00080000
SEM_FAILCRITICALERRORS = 0x0001
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
STORAGE_DEVICE_SEEK_PENALTY_PROPERTY = 7
OPEN_EXISTING = 3
FILE_SHARE_READ_WRITE = 0x3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _StoragePropertyQuery(ctypes.Structure):
    _fields_ = [("PropertyId", wintypes.DWORD), ("QueryType", wintypes.DWORD), ("Extra", ctypes.c_ubyte * 1)]


class _SeekPenaltyDescriptor(ctypes.Structure):
    _fields_ = [("Version", wintypes.DWORD), ("Size", wintypes.DWORD), ("IncursSeekPenalty", ctypes.c_ubyte)]


class WindowsVolumeProvider:
    """Enumerates fixed and removable drives that have a drive letter."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsVolumeProvider requires Windows")
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32.CreateFileW.restype = wintypes.HANDLE
        self._k32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        self._k32.DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        ]
        self._k32.CloseHandle.argtypes = [wintypes.HANDLE]

    def list_volumes(self) -> list[VolumeInfo]:
        previous = self._k32.SetErrorMode(SEM_FAILCRITICALERRORS)  # no "insert disk" dialogs
        try:
            mask = self._k32.GetLogicalDrives()
            volumes: list[VolumeInfo] = []
            for index in range(26):
                if not mask & (1 << index):
                    continue
                letter = chr(ord("A") + index)
                info = self._describe(f"{letter}:\\")
                if info is not None:
                    volumes.append(info)
            return volumes
        finally:
            self._k32.SetErrorMode(previous)

    def _describe(self, root: str) -> VolumeInfo | None:
        if self._k32.GetDriveTypeW(root) not in (DRIVE_REMOVABLE, DRIVE_FIXED):
            return None
        label = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        flags = wintypes.DWORD()
        if not self._k32.GetVolumeInformationW(root, label, 261, None, None, ctypes.byref(flags), fs, 261):
            return None  # not ready (e.g. empty card reader)
        name = ctypes.create_unicode_buffer(64)
        if not self._k32.GetVolumeNameForVolumeMountPointW(root, name, 64):
            return None
        try:
            guid = normalize_guid(name.value)
        except ValueError:
            return None
        free = ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()
        if not self._k32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), ctypes.byref(free)):
            return None
        return VolumeInfo(
            guid=guid,
            label=label.value,
            filesystem=fs.value,
            mount_path=Path(root),
            total_bytes=total.value,
            free_bytes=free.value,
            read_only=bool(flags.value & FILE_READ_ONLY_VOLUME),
            media_type=self._media_type(root[0]),
            letter=root[:2].upper(),
        )

    def _media_type(self, letter: str) -> str:
        """HDD/SSD via the seek-penalty property (read-only query; UNKNOWN if the device does not answer)."""
        device = chr(92) * 2 + "." + chr(92) + f"{letter}:"  # device path of the volume
        handle = self._k32.CreateFileW(device, 0, FILE_SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
        if handle is None or handle == INVALID_HANDLE_VALUE:
            return "UNKNOWN"
        try:
            query = _StoragePropertyQuery(STORAGE_DEVICE_SEEK_PENALTY_PROPERTY, 0, (ctypes.c_ubyte * 1)(0))
            out = _SeekPenaltyDescriptor()
            returned = wintypes.DWORD()
            ok = self._k32.DeviceIoControl(
                handle, IOCTL_STORAGE_QUERY_PROPERTY, ctypes.byref(query), ctypes.sizeof(query),
                ctypes.byref(out), ctypes.sizeof(out), ctypes.byref(returned), None,
            )
            if not ok or returned.value < ctypes.sizeof(out):
                return "UNKNOWN"
            return "HDD" if out.IncursSeekPenalty else "SSD"
        finally:
            self._k32.CloseHandle(handle)
