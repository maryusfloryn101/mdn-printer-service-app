# -*- coding: utf-8 -*-
"""Comunicarea cu imprimantele Epson, peste biblioteca epson_print_conf.

O imprimantă e identificată printr-un "handle" text:
  usb:<cale dispozitiv>   sau   net:<adresa IP>
Toate funcțiile publice întorc dicționare simple (JSON), ca interfața să le
poată afișa direct.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Dict, List, Optional

log = logging.getLogger("mdnps.epson")

_LIB_LOCK = threading.Lock()
_epc = None  # modulul epson_print_conf, încărcat leneș


def _lib():
    """Încarcă biblioteca o singură dată și activează transportul USB."""
    global _epc
    with _LIB_LOCK:
        if _epc is None:
            import epson_print_conf as epc
            if epc.usb_library_available():
                epc.enable_usb_transport()
            _epc = epc
    return _epc


_EXTRA = None  # parametrii modelelor adăugate din baza ez-reset (devices.xml)


def _decode(o):
    if isinstance(o, dict):
        if set(o) == {"__bytes__"}:
            return bytes.fromhex(o["__bytes__"])
        return {(int(k[7:]) if k.startswith("__int__") else k): _decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_decode(x) for x in o]
    return o


def extra_conf() -> dict:
    """Configurația suplimentară, ca dicționar nou la fiecare apel (biblioteca îl modifică)."""
    global _EXTRA
    if _EXTRA is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "epson_extra.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _EXTRA = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            log.warning("Nu pot încărca modelele suplimentare: %s", exc)
            _EXTRA = {}
    return _decode(_EXTRA)


def _usb_class():
    epc = _lib()
    return epc.EpsonPrinter if hasattr(epc, "NetworkEpsonPrinter") else None


def _net_class():
    epc = _lib()
    return getattr(epc, "NetworkEpsonPrinter", epc.EpsonPrinter)


def normalize_model(raw: Optional[str]) -> Optional[str]:
    """'EPSON L3150 Series' -> 'L3150'; 'ET-2810 Series' -> 'ET-2810'."""
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"^EPSON\s+", "", s, flags=re.I)
    s = re.sub(r"\s+Series$", "", s, flags=re.I)
    return s.strip()


# ----------------------------------------------------------------------
# Detectare
# ----------------------------------------------------------------------
def list_usb_devices() -> List[dict]:
    """Imprimantele Epson pe USB (o intrare pe dispozitiv fizic)."""
    try:
        _lib()
        from epson_usb.backends import find_devices
    except Exception as exc:  # noqa: BLE001
        log.warning("USB indisponibil: %s", exc)
        return []
    try:
        devices = find_devices()
    except Exception as exc:  # noqa: BLE001
        log.warning("Nu pot lista USB: %s", exc)
        return []
    seen, out = set(), []
    for d in devices:
        key = re.sub(r"&mi_[0-9a-f]{2}", "", (d.path or "").lower())
        if (d.backend, key) in seen:
            continue
        seen.add((d.backend, key))
        out.append({"handle": "usb:" + d.path, "backend": d.backend,
                    "path": d.path, "connection": "USB"})
    # Pe Windows prefer backend-ul nativ usbprint (nu schimbă driverul).
    native = [o for o in out if o["backend"] == "usbprint"]
    return native or out


def scan_network(timeout: float = 0.6) -> List[dict]:
    """Caută în subrețeaua locală imprimante care răspund la SNMP ca Epson."""
    import socket
    ips = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 1))
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    found: List[str] = []
    lock = threading.Lock()

    def probe(ip):
        for port in (9100, 515, 631):
            try:
                with socket.create_connection((ip, port), timeout=timeout):
                    with lock:
                        found.append(ip)
                    return
            except OSError:
                continue

    threads = []
    for local in ips:
        base = local.rsplit(".", 1)[0] + "."
        for i in range(1, 255):
            t = threading.Thread(target=probe, args=(base + str(i),), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout + 0.5)

    out = []
    for ip in sorted(set(found), key=lambda x: tuple(int(p) for p in x.split("."))):
        try:
            p = _net_class()(hostname=ip, timeout=1, retries=0)
            info = p.get_snmp_info("Model") or {}
            model = info.get("Model")
        except Exception:  # noqa: BLE001
            model = None
        if model and "epson" in model.lower():
            out.append({"handle": "net:" + ip, "ip": ip, "connection": "Wi-Fi",
                        "raw_model": model, "model": normalize_model(model)})
        elif model:
            out.append({"handle": None, "ip": ip, "connection": "Rețea",
                        "raw_model": model, "model": model, "foreign": True})
    return out


# ----------------------------------------------------------------------
# Sesiune cu o imprimantă
# ----------------------------------------------------------------------
class EpsonSession:
    """O conexiune deschisă la o imprimantă Epson (USB sau rețea)."""

    def __init__(self, handle: str, model: Optional[str] = None):
        self.handle = handle
        self.lock = threading.Lock()
        self.model = model
        self.printer = self._build(model)

    def _build(self, model):
        kind, _, target = self.handle.partition(":")
        if kind == "usb":
            cls = _usb_class()
            if cls is None:
                raise RuntimeError("Biblioteca USB lipsește din aplicație.")
            return cls(conf_dict=extra_conf(), model=model, device=target, usb_options=None)
        if kind == "net":
            return _net_class()(conf_dict=extra_conf(), model=model, hostname=target,
                                timeout=3, retries=1)
        raise ValueError("Handle necunoscut: " + self.handle)

    def close(self):
        try:
            if hasattr(self.printer, "close"):
                self.printer.close()
        except Exception:  # noqa: BLE001
            pass

    def set_model(self, model: str):
        """Reconstruiește obiectul cu parametrii modelului recunoscut."""
        if model == self.model and self.printer.parm:
            return
        self.close()
        self.model = model
        self.printer = self._build(model)

    # --- citiri ---------------------------------------------------------
    def identify(self) -> dict:
        p = self.printer
        ident = {}
        try:
            ident = p.get_device_identification() or {}
        except TimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.info("di: %s", exc)
        raw = " ".join(ident.get("Model", [])) or None
        if not raw and self.handle.startswith("net:"):
            try:
                raw = (p.get_snmp_info("Model") or {}).get("Model")
            except Exception:  # noqa: BLE001
                pass
        return {"raw_model": raw, "model": normalize_model(raw),
                "manufacturer": " ".join(ident.get("Manufacturer", [])) or "EPSON"}

    def read_all(self) -> dict:
        """Tot ce se poate citi, fiecare parte separat (o eroare nu le strică pe celelalte)."""
        p = self.printer
        out: Dict[str, object] = {"errors": []}

        def safe(name, fn):
            try:
                return fn()
            except TimeoutError:
                raise
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(f"{name}: {exc}")
                return None

        status = safe("status", p.get_printer_status) or {}
        if isinstance(status, str):
            out["errors"].append("status: " + status)
            status = {}
        out["status"] = _status_to_json(status)
        out["serial"] = None
        if p.parm:
            ser = safe("serie", p.get_serial_number)
            if ser and "?" not in str(ser):
                out["serial"] = ser
        if not out["serial"]:
            out["serial"] = status.get("serial_number_info") or status.get("serial")
        out["firmware"] = safe("firmware", p.get_firmware_version)
        if p.parm:
            out["waste"] = safe("tampoane", p.get_waste_ink_levels)
            stats = safe("contoare", p.get_stats) or {}
            out["stats"] = {k: v for k, v in stats.items()}
            fatal = safe("erori", p.get_last_printer_fatal_errors)
            out["fatal_errors"] = [x for x in (fatal or []) if x and x not in ("00", "FF")]
        else:
            out["waste"] = None
            out["stats"] = {}
            out["fatal_errors"] = []
        if self.handle.startswith("net:"):
            info = safe("snmp", lambda: p.get_snmp_info()) or {}
            out["mac"] = info.get("MAC Address") or info.get("MAC Addr")
            out["ip"] = self.handle[4:]
        else:
            out["mac"] = None
        return out

    # --- backup / scriere ------------------------------------------------
    def cells_to_backup(self) -> List[int]:
        parm = self.printer.parm or {}
        cells = set(range(0, 0x100))
        cells.update(parm.get("raw_waste_reset", {}).keys())
        cells.update((parm.get("waste_reset_commit") or {}).keys())
        for key in ("main_waste", "borderless_waste", "first_waste",
                    "second_waste", "third_waste"):
            cells.update((parm.get(key) or {}).get("oids", []))
        for oids in (parm.get("stats") or {}).values():
            cells.update(oids)
        return sorted(c for c in cells if isinstance(c, int))

    def backup(self, folder: str, meta: dict) -> dict:
        cells = self.cells_to_backup()
        values: Dict[int, Optional[str]] = {}
        for i in range(0, len(cells), 32):
            part = cells[i:i + 32]
            res = self.printer.read_eeprom(part, label="backup")
            if not isinstance(res, list):
                res = [res]
            for a, v in zip(part, res):
                values[a] = v
        parm = self.printer.parm or {}
        important = set(parm.get("raw_waste_reset", {}).keys())
        for key in ("main_waste", "borderless_waste"):
            important.update((parm.get(key) or {}).get("oids", []))
        missing = sorted(a for a in important if values.get(a) is None)
        if missing:
            raise RuntimeError(
                "Nu am putut citi celulele contoarelor (%s). Nu fac backup și nu "
                "recomand resetarea." % ", ".join(map(str, missing)))
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        serial = re.sub(r"[^A-Za-z0-9]", "", str(meta.get("serial") or "")) or "fara-serie"
        path = os.path.join(folder, f"backup_{self.model}_{serial}_{stamp}.json")
        data = {"app": "MDN Printer Service", "model": self.model,
                "serial": meta.get("serial"), "date": stamp,
                "waste": meta.get("waste"),
                "eeprom": {str(a): v for a, v in sorted(values.items())}}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        return {"path": path, "cells": len(values),
                "unread": sum(1 for v in values.values() if v is None)}

    def reset(self) -> dict:
        report: list = []
        ok = self.printer.reset_waste_ink_levels(report=report)
        cells = [{"cell": oid, "before": prev, "after": val, "changed": ch}
                 for oid, prev, val, ch in report]
        return {"ok": bool(ok), "cells": cells}

    def temporary_unlock(self) -> dict:
        ok = self.printer.temporary_reset_waste()
        return {"ok": bool(ok)}

    def restore(self, path: str) -> dict:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("model") and self.model and data["model"] != self.model:
            raise RuntimeError("Backup-ul e pentru %s, imprimanta e %s." % (data["model"], self.model))
        parm = self.printer.parm or {}
        cells = sorted(set(parm.get("raw_waste_reset", {}).keys()) |
                       set((parm.get("main_waste") or {}).get("oids", [])) |
                       set((parm.get("borderless_waste") or {}).get("oids", [])))
        results = []
        for addr in cells:
            val = data["eeprom"].get(str(addr))
            if val is None:
                results.append({"cell": addr, "ok": None})
                continue
            ok = self.printer.write_eeprom(addr, int(val, 16), label="restore")
            results.append({"cell": addr, "value": val, "ok": bool(ok)})
        return {"ok": all(r["ok"] is not False for r in results), "cells": results}


# ----------------------------------------------------------------------
# Unelte de service (citiri suplimentare, contoare separate, întreținere, memorie)
# ----------------------------------------------------------------------
COUNTERS = ("main_waste", "borderless_waste", "third_waste", "first_waste", "second_waste")


def find_conf_model(model: Optional[str], raw: Optional[str] = None) -> Optional[str]:
    """Numele de configurație (biblioteca + ez-reset) pentru un model, inclusiv după alias.
    Folosit pentru modelele care nu au date de resetare, dar au cheie de citire și contoare."""
    if not model and not raw:
        return None
    want = {x.upper().replace(" ", "") for x in (model, raw) if x}
    want |= {w.replace("SERIES", "") for w in want}
    confs = dict(_lib().EpsonPrinter.PRINTER_CONFIG) if hasattr(_lib().EpsonPrinter, "PRINTER_CONFIG") else {}
    confs.update(extra_conf())
    for name, c in confs.items():
        names = [name] + list((c or {}).get("alias", []) if isinstance(c, dict) else [])
        if any(n.upper().replace(" ", "") in want for n in names):
            return name
    return None


def service_counters(printer) -> list:
    parm = printer.parm or {}
    out = []
    for key in COUNTERS:
        c = parm.get(key)
        if isinstance(c, dict) and c.get("oids"):
            out.append({"key": key, "oids": list(c["oids"])})
    return out


def _session_service_info(self) -> dict:
    p = self.printer
    out: Dict[str, object] = {"errors": []}

    def safe(name, fn):
        try:
            return fn()
        except TimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"{name}: {exc}")
            return None

    out["model_conf"] = self.model
    out["has_keys"] = bool(p.parm and p.parm.get("read_key"))
    out["can_write"] = bool(p.parm and p.parm.get("write_key"))
    out["network"] = self.handle.startswith("net:")
    out["counters"] = [{"key": c["key"]} for c in service_counters(p)]
    levels = safe("tampoane", p.get_waste_ink_levels) if p.parm else None
    for c in out["counters"]:
        c["level"] = (levels or {}).get(c["key"])
    out["head_id"] = safe("cap", p.get_printer_head_id) if p.parm else None
    irc = safe("cerneala", p.get_ink_replacement_counters) if p.parm else None
    out["ink_replacements"] = [{"color": c, "counter": n, "value": v} for c, n, v in sorted(irc)] if irc else []
    out["cartridges"] = safe("cartuse", p.get_cartridges)
    info = safe("info_cartuse", p.get_cartridge_information) or []
    out["cartridge_info"] = [x if isinstance(x, dict) else str(x) for x in info]
    stats = safe("contoare", p.get_stats) if p.parm else {}
    out["poweroff"] = (stats or {}).get("Power off timer")
    out["poweroff_supported"] = bool(p.parm and "Power off timer" in (p.parm.get("stats") or {}))
    return out


def _session_reset_counter(self, key: str) -> dict:
    match = [c for c in service_counters(self.printer) if c["key"] == key]
    if not match:
        raise RuntimeError("Contorul nu există la acest model.")
    report: list = []
    oks = [self.printer.write_eeprom(oid, 0, label="reset_" + key, report=report) for oid in match[0]["oids"]]
    cells = [{"cell": oid, "before": prev, "after": val, "changed": ch} for oid, prev, val, ch in report]
    return {"ok": all(bool(x) for x in oks), "cells": cells}


def _session_dump(self, start: int, end: int, progress=None) -> Dict[int, Optional[str]]:
    values: Dict[int, Optional[str]] = {}
    addrs = list(range(start, end + 1))
    for i in range(0, len(addrs), 64):
        part = addrs[i:i + 64]
        res = self.printer.read_eeprom(part, label="dump")
        if not isinstance(res, list):
            res = [res]
        for a, v in zip(part, res):
            values[a] = v
        if progress:
            progress(min(len(addrs), i + 64), len(addrs))
    return values


def _session_write_cell(self, addr: int, value: int) -> dict:
    report: list = []
    before = self.printer.read_eeprom(addr, label="editor")
    ok = self.printer.write_eeprom(addr, value, label="editor", report=report)
    after = self.printer.read_eeprom(addr, label="editor")
    return {"ok": bool(ok), "cell": addr, "before": before, "after": after}


def _session_print(self, what: str, power: bool = False) -> dict:
    p = self.printer
    if not self.handle.startswith("net:"):
        raise RuntimeError("network_only")
    if what == "nozzle":
        ok = p.print_check_nozzles()
    elif what == "pattern":
        ok = p.print_test_color_pattern()
    elif what == "clean":
        ok = p.print_clean_nozzles(0, power_clean=power)
    else:
        raise ValueError(what)
    return {"ok": bool(ok)}


def _session_poweroff(self, mins: int) -> dict:
    report: list = []
    ok = self.printer.write_poweroff_timer(int(mins), report=report)
    return {"ok": bool(ok)}


def _session_find_key(self, progress=None) -> dict:
    if self.printer.parm is None:
        self.printer.parm = {}
    key = self.printer.brute_force_read_key(progress=progress)
    return {"key": list(key) if key else None}


EpsonSession.service_info = _session_service_info
EpsonSession.reset_counter = _session_reset_counter
EpsonSession.dump = _session_dump
EpsonSession.write_cell = _session_write_cell
EpsonSession.print_service = _session_print
EpsonSession.set_poweroff = _session_poweroff
EpsonSession.find_key = _session_find_key


def _status_to_json(st: dict) -> dict:
    out = {}
    if not isinstance(st, dict):
        return out
    if "status" in st and isinstance(st["status"], tuple):
        out["code"], out["text"] = st["status"][0], st["status"][1]
    out["ready"] = st.get("ready")
    out["error"] = st.get("errcode")
    out["warnings"] = st.get("warning_code") or []
    inks = []
    for item in st.get("ink_level") or []:
        try:
            _c, _ic, name, ink_name, level = item
            inks.append({"color": name, "ink": ink_name, "level": level})
        except Exception:  # noqa: BLE001
            continue
    out["inks"] = inks
    for k in ("paper_jam", "tray_open", "paper_count_normal", "paper_count_page",
              "paper_count_color", "paper_count_monochrome"):
        if k in st:
            out[k] = st[k]
    boxes = {k: v for k, v in st.items() if k.startswith("maintenance_box")}
    if boxes:
        out["maintenance_box"] = boxes
    return out
