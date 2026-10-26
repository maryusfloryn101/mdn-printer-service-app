# -*- coding: utf-8 -*-
"""Asistentul Canon: detectarea imprimantelor Canon pe USB și a intrării în
modul service, plus deschiderea ferestrei de întreținere a driverului Canon.

Modulul NU trimite comenzi către imprimantă și NU scrie în memoria acesteia.
Detectarea se face doar citind lista dispozitivelor USB din Windows:
la intrarea în modul service, imprimanta Canon se reconectează pe USB cu un
alt identificator de produs (PID), ceea ce se poate observa fără driver.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Dict, List, Optional

CANON_VID = "04A9"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def _ps(cmd: str, timeout: int = 15) -> str:
    if sys.platform != "win32":
        return ""
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW,
        ).stdout
    except Exception:  # noqa: BLE001
        return ""


def parse_instance(instance_id: str) -> Optional[Dict[str, str]]:
    """USB\\VID_04A9&PID_1865\\ABC123 -> {vid, pid, serial}; None pentru alte dispozitive."""
    m = re.match(r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&MI_[0-9A-F]{2})?\\(.*)$", instance_id or "", re.I)
    if not m:
        return None
    serial = m.group(3)
    if "&" in serial:  # identificator generat de Windows, nu seria reală
        serial = ""
    return {"vid": m.group(1).upper(), "pid": m.group(2).upper(), "serial": serial}


def usb_devices() -> List[dict]:
    """Dispozitivele Canon conectate acum pe USB (orice mod de funcționare)."""
    if sys.platform != "win32":
        from .platform_util import usb_devices as _u
        return _u(CANON_VID)
    out = _ps("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\\VID_04A9*' } | "
              "Select-Object InstanceId,FriendlyName,Status,Class | ConvertTo-Json -Compress")
    try:
        data = json.loads(out or "[]")
    except ValueError:
        data = []
    if isinstance(data, dict):
        data = [data]
    res, seen = [], set()
    for d in data:
        p = parse_instance(d.get("InstanceId") or "")
        if not p or p["vid"] != CANON_VID:
            continue
        key = (p["pid"], p["serial"])
        if key in seen:  # interfețele aceluiași dispozitiv compus
            continue
        seen.add(key)
        res.append({"pid": p["pid"], "serial": p["serial"],
                    "name": d.get("FriendlyName") or "", "status": d.get("Status") or "",
                    "cls": d.get("Class") or ""})
    return res


def compare(baseline: List[dict], now: List[dict]) -> dict:
    """Interpretează schimbarea față de starea de dinainte de secvența de butoane.

    state:
      none     – nicio imprimantă Canon pe USB (oprită, pornește sau cablu deconectat)
      same     – aceeași imprimantă, același PID: încă în modul normal
      changed  – a apărut un PID Canon nou și cel vechi a dispărut: probabil modul service
      new      – un PID Canon nou, fără referință anterioară (asistent pornit cu imprimanta oprită)
    """
    base_pids = {d["pid"] for d in baseline}
    now_pids = {d["pid"] for d in now}
    if not now:
        return {"state": "none", "devices": now}
    if base_pids and now_pids - base_pids and not (now_pids & base_pids):
        return {"state": "changed", "devices": now, "from": sorted(base_pids), "to": sorted(now_pids)}
    if not base_pids:
        return {"state": "new", "devices": now}
    if now_pids & base_pids and not (now_pids - base_pids):
        return {"state": "same", "devices": now}
    return {"state": "changed", "devices": now, "from": sorted(base_pids), "to": sorted(now_pids - base_pids)}


def open_maintenance(printer_name: str) -> bool:
    """Fereastra de întreținere a driverului Canon (curățare, verificare duze, aliniere)."""
    from .platform_util import open_printer_maintenance
    return open_printer_maintenance(printer_name)
