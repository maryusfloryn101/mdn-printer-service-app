# -*- coding: utf-8 -*-
"""Imprimantele instalate în Windows (orice marcă), pentru a recunoaște
modelele Canon și Brother și a le lega de ghidurile din baza de modele."""
from __future__ import annotations

import json
import subprocess
import sys
from typing import List

SKIP = ("microsoft", "onenote", "fax", "pdf", "xps", "anydesk", "send to")


def installed_printers() -> List[dict]:
    if sys.platform != "win32":
        return []
    ps = ("Get-CimInstance Win32_Printer | Select-Object Name,DriverName,PortName,"
          "WorkOffline,PrinterStatus | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        ).stdout
        data = json.loads(out or "[]")
    except Exception:  # noqa: BLE001
        return []
    if isinstance(data, dict):
        data = [data]
    res = []
    for p in data:
        name = p.get("Name") or ""
        if any(s in name.lower() for s in SKIP):
            continue
        port = p.get("PortName") or ""
        conn = "USB" if port.upper().startswith("USB") else ("Rețea" if port else "")
        res.append({"name": name, "driver": p.get("DriverName"), "port": port,
                    "connection": conn, "offline": bool(p.get("WorkOffline"))})
    return res
