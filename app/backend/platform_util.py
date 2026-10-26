# -*- coding: utf-8 -*-
"""Diferențele dintre Windows, macOS și Linux, adunate într-un singur loc:
foldere, deschiderea fișierelor, identificatorul calculatorului, imprimantele
instalate și dispozitivele USB Canon."""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from typing import List, Optional

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
_NO_WINDOW = 0x08000000 if WIN else 0

APP_NAME = "MDN Printer Service"


def run(cmd: List[str], timeout: int = 15) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=_NO_WINDOW).stdout or ""
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- foldere
def data_dir() -> str:
    """Setări, istoric și jurnal (nevizibile în mod obișnuit)."""
    if WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    elif MAC:
        path = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        path = os.path.join(base, "mdn-printer-service")
    os.makedirs(path, exist_ok=True)
    return path


def documents_base() -> str:
    """Folderul Documente real al utilizatorului."""
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    if WIN:
        try:  # inclusiv când e mutat (OneDrive etc.)
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                docs = buf.value
        except Exception:  # noqa: BLE001
            pass
    elif LINUX:
        out = run(["xdg-user-dir", "DOCUMENTS"]).strip()
        if out and os.path.isdir(out) and out != home:
            docs = out
    return docs


# ---------------------------------------------------------------- deschidere
def open_path(path: str) -> bool:
    """Deschide un fișier sau un folder cu programul implicit al sistemului."""
    try:
        if WIN:
            os.startfile(path)  # type: ignore[attr-defined]
        elif MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- identificator calculator
def machine_raw_id() -> str:
    """Identificatorul de instalare al sistemului (se transformă ireversibil în license.py)."""
    try:
        if WIN:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        if MAC:
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"',
                          run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]))
            if m:
                return m.group(1)
        if LINUX:
            for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    v = open(f, encoding="ascii").read().strip()
                    if v:
                        return v
                except OSError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    import uuid
    return str(uuid.getnode())  # adresa MAC, ca ultimă variantă


# ---------------------------------------------------------------- imprimante instalate
def installed_printers() -> List[dict]:
    """Imprimantele configurate în sistem: nume, driver, conexiune."""
    if WIN:
        from . import winprinters
        return winprinters.installed_printers()
    # macOS și Linux: CUPS
    out = run(["lpstat", "-v"])
    res = []
    for line in out.splitlines():
        m = re.match(r"device for (.+?):\s*(\S+)", line.strip())
        if not m:
            continue
        name, uri = m.group(1), m.group(2)
        conn = "USB" if uri.startswith("usb:") else ("Rețea" if "://" in uri else "")
        res.append({"name": name, "driver": "", "port": uri, "connection": conn, "offline": False})
    return res


# ---------------------------------------------------------------- USB Canon (doar citire)
def usb_devices(vendor: str) -> List[dict]:
    """Dispozitivele USB ale unui producător (VID hex, ex. "04A9"), fără a le deschide."""
    vendor = vendor.upper()
    res: List[dict] = []
    if MAC:
        # ioreg listează dispozitivele USB cu idVendor/idProduct în zecimal.
        out = run(["ioreg", "-p", "IOUSB", "-l", "-w0"])
        for block in out.split("+-o ")[1:]:
            v = re.search(r'"idVendor"\s*=\s*(\d+)', block)
            p = re.search(r'"idProduct"\s*=\s*(\d+)', block)
            if not (v and p) or "%04X" % int(v.group(1)) != vendor:
                continue
            name = re.search(r'"USB Product Name"\s*=\s*"([^"]*)"', block)
            serial = re.search(r'"USB Serial Number"\s*=\s*"([^"]*)"', block)
            res.append({"pid": "%04X" % int(p.group(1)), "serial": serial.group(1) if serial else "",
                        "name": name.group(1) if name else "", "status": "", "cls": ""})
    elif LINUX:
        for d in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            base = os.path.dirname(d)
            try:
                if open(d).read().strip().upper() != vendor:
                    continue
                rd = lambda n: (open(os.path.join(base, n)).read().strip()  # noqa: E731
                                if os.path.exists(os.path.join(base, n)) else "")
                res.append({"pid": rd("idProduct").upper(), "serial": rd("serial"),
                            "name": rd("product"), "status": "", "cls": ""})
            except OSError:
                continue
    return res


def open_printer_maintenance(printer_name: str) -> bool:
    """Fereastra de întreținere a driverului (curățare, verificare duze, aliniere)."""
    try:
        if WIN:
            if not printer_name:
                return False
            subprocess.Popen(["rundll32", "printui.dll,PrintUIEntry", "/e", "/n", printer_name],
                             creationflags=_NO_WINDOW)
            return True
        if MAC:
            # Utilitarul Canon, dacă e instalat; altfel Imprimante și scanere din Setări.
            for app in ("Canon IJ Printer Utility2", "Canon IJ Printer Assistant Tool"):
                if subprocess.run(["open", "-a", app], capture_output=True).returncode == 0:
                    return True
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.Print-Scan-Settings.extension"])
            return True
        if LINUX:
            url = "http://localhost:631/printers/" + printer_name if printer_name else "http://localhost:631/printers/"
            subprocess.Popen(["xdg-open", url])
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


# ---------------------------------------------------------------- acces USB pe Linux
UDEV_RULE = ('# MDN Printer Service: acces la imprimantele Epson și Canon pe USB\n'
             'SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666"\n'
             'SUBSYSTEM=="usb", ATTRS{idVendor}=="04a9", MODE="0666"\n')
UDEV_PATH = "/etc/udev/rules.d/60-mdn-printer-service.rules"


def linux_usb_ready() -> Optional[bool]:
    """None în afara Linux; True dacă regula de acces USB e instalată."""
    if not LINUX:
        return None
    return os.path.exists(UDEV_PATH)


def linux_usb_setup() -> bool:
    """Instalează regula udev; sistemul cere parola administratorului într-o fereastră grafică."""
    if not LINUX:
        return False
    script = (f"printf '%s' '{UDEV_RULE}' > {UDEV_PATH} && udevadm control --reload-rules "
              f"&& udevadm trigger --subsystem-match=usb")
    try:
        return subprocess.run(["pkexec", "sh", "-c", script], timeout=300).returncode == 0
    except Exception:  # noqa: BLE001
        return False


_SSL = None


def ssl_context():
    """Context TLS cu certificatele de încredere: în aplicația împachetată (macOS/Linux)
    Python nu găsește mereu certificatele sistemului, așa că folosim pachetul certifi."""
    global _SSL
    if _SSL is None:
        import ssl
        try:
            import certifi
            _SSL = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            _SSL = ssl.create_default_context()
    return _SSL
