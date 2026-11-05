"""A stable ID for this installation on this computer.

It combines the operating system's machine ID with a random ID created on first run, so copying the data folder to
another computer gives a different ID (that computer needs its own seat), and reinstalling keeps the same one.
"""

import platform
import socket
import uuid
from pathlib import Path

from app.core.config import get_settings


def _os_machine_id() -> str:
    if platform.system() == "Windows":
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except OSError:
            return ""
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        path = Path(candidate)
        if path.is_file():
            return path.read_text().strip()
    return ""


def install_id() -> str:
    path = Path(get_settings().storage_dir) / ".install-id"
    if path.is_file():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = uuid.uuid4().hex
    path.write_text(value)
    return value


def machine_id() -> str:
    return f"{_os_machine_id() or 'unknown'}:{install_id()}"


def machine_name() -> str:
    return socket.gethostname()[:120]
