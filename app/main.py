# -*- coding: utf-8 -*-
"""MDN Printer Service — punctul de pornire.

Deschide o fereastră Windows (Edge WebView2) cu interfața din ui/ și îi expune
clasa Api: fiecare metodă publică poate fi apelată din JavaScript ca
`await pywebview.api.<metodă>(...)`.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import traceback

# În aplicația împachetată (macOS/Linux) resursele stau în folderul PyInstaller.
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)
# libusb livrată cu aplicația (macOS/Linux), folosită pentru imprimantele Epson pe USB.
for _n in ("libusb-1.0.dylib", "libusb-1.0.so.0"):
    _p = os.path.join(HERE, "native", _n)
    if os.path.exists(_p):
        os.environ.setdefault("EPSON_USB_LIBUSB", _p)

from backend import config, store, platform_util  # noqa: E402

DATA = store.data_dir()
logging.basicConfig(
    filename=os.path.join(DATA, "jurnal.txt"), level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", encoding="utf-8")
log = logging.getLogger("mdnps")


def _safe(fn):
    """Orice excepție devine {ok: False, error: ...} ca interfața să o arate frumos."""
    def wrap(*a, **k):
        try:
            res = fn(*a, **k)
            if isinstance(res, dict) and "ok" not in res:
                res["ok"] = True
            return res
        except TimeoutError as exc:
            log.warning("timeout %s: %s", fn.__name__, exc)
            return {"ok": False, "error": "no_answer", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            log.error("%s: %s\n%s", fn.__name__, exc, traceback.format_exc())
            return {"ok": False, "error": "exception", "detail": str(exc)}
    wrap.__name__ = fn.__name__
    return wrap


class Api:
    def __init__(self):
        self._settings = store.Settings(os.path.join(DATA, "setari.json"))
        self._history = store.History(os.path.join(DATA, "istoric.db"))
        self._models = store.Models(os.path.join(HERE, "data", "models.json"))
        from backend.license import License
        self._lic = License(self._settings)
        self._sessions = {}
        self._meta = {}
        self._lock = threading.Lock()
        self._window = None
        self._job = {"state": "idle"}
        from backend.update import Updater
        self._upd = Updater()

    # ---------------- general ----------------
    @_safe
    def info(self):
        return {"version": config.VERSION, "vendor": config.VENDOR,
                "email": config.SUPPORT_EMAIL, "price": config.LICENSE_PRICE,
                "lang": self._settings.get("lang", "ro"),
                "models": self._models.counts(), "models_version": self._models.version,
                "license": self._lic.state(), "linux_usb": platform_util.linux_usb_ready(),
                "platform": sys.platform}

    # ---------------- unelte de service ----------------
    def _job_start(self, name, fn):
        with self._lock:
            if self._job.get("state") == "running":
                return {"ok": False, "error": "busy"}
            self._job = {"state": "running", "name": name, "done": 0, "total": 0}

        def progress(done, total, *_):
            self._job["done"], self._job["total"] = done, total

        def run():
            try:
                res = fn(progress)
                self._job = dict(res or {}, state="done", name=name)
            except Exception as exc:  # noqa: BLE001
                log.error("%s: %s\n%s", name, exc, traceback.format_exc())
                self._job = {"state": "error", "name": name, "error": str(exc)}
        threading.Thread(target=run, daemon=True).start()
        return {"started": True}

    @_safe
    def job_progress(self):
        return dict(self._job)

    def _read_meta(self, handle):
        return (self._meta.get(handle) or {}).get("read") or {}

    @_safe
    def service_info(self, handle):
        s = self._session(handle)
        with s.lock:
            return s.service_info()

    @_safe
    def reset_counter(self, handle, key, client="", contact="", notes=""):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        meta = self._meta.get(handle) or {}
        if not meta.get("backup"):
            return {"ok": False, "error": "no_backup"}
        read = meta.get("read") or {}
        s = self._session(handle)
        with s.lock:
            res = s.reset_counter(key)
            after = s.printer.get_waste_ink_levels() if res["ok"] else None
        job_id = None
        if res["ok"]:
            job_id = self._history.add(
                client=client, client_contact=contact, brand="Epson",
                model=read.get("db_model") or read.get("model"), serial=read.get("serial"),
                firmware=read.get("firmware"), connection=read.get("connection"),
                kind="reset", waste_before=read.get("waste"), waste_after=after,
                stats=read.get("stats"), backup_path=meta.get("backup"),
                notes=(f"[{key}] " + (notes or "")).strip())
        res.update({"waste_after": after, "job_id": job_id})
        return res

    @_safe
    def service_print(self, handle, what, power=False):
        s = self._session(handle)
        with s.lock:
            try:
                res = s.print_service(what, bool(power))
            except RuntimeError as exc:
                if str(exc) == "network_only":
                    return {"ok": False, "error": "network_only"}
                raise
        read = self._read_meta(handle)
        if res.get("ok"):
            self._history.add(brand="Epson", model=read.get("db_model") or read.get("model"),
                              serial=read.get("serial"), connection=read.get("connection"),
                              kind="service", notes=what + (" (power)" if power else ""))
        return res

    @_safe
    def set_poweroff(self, handle, mins):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        s = self._session(handle)
        with s.lock:
            return s.set_poweroff(int(mins))

    def _mem_folder(self):
        return os.path.join(store.documents_dir(), "Backup", "Memorie")

    @_safe
    def dump_start(self, handle, start=0, end=255):
        start, end = max(0, int(start)), min(0xFFFF, int(end))
        if end < start:
            return {"ok": False, "error": "range"}
        s = self._session(handle)
        read = self._read_meta(handle)

        def job(progress):
            with s.lock:
                values = s.dump(start, end, progress)
            os.makedirs(self._mem_folder(), exist_ok=True)
            import re as _re
            import time as _time
            stamp = _time.strftime("%Y-%m-%d_%H-%M-%S")
            serial = _re.sub(r"[^A-Za-z0-9]", "", str(read.get("serial") or "")) or "fara-serie"
            path = os.path.join(self._mem_folder(), f"memorie_{read.get('model') or 'epson'}_{serial}_{stamp}.json")
            with open(path, "w", encoding="utf-8") as fh:
                import json as _json
                _json.dump({"app": "MDN Printer Service", "kind": "dump", "model": read.get("model"),
                            "serial": read.get("serial"), "date": stamp, "range": [start, end],
                            "eeprom": {str(a): v for a, v in values.items()}}, fh, indent=1)
            return {"path": path, "cells": len(values), "unread": sum(1 for v in values.values() if v is None)}
        return self._job_start("dump", job)

    @_safe
    def snapshots_list(self):
        import json as _json
        out = []
        folder = self._mem_folder()
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder), reverse=True):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(folder, f), encoding="utf-8") as fh:
                            d = _json.load(fh)
                        out.append({"file": f, "model": d.get("model"), "serial": d.get("serial"),
                                    "date": d.get("date"), "range": d.get("range")})
                    except Exception:  # noqa: BLE001
                        continue
        return {"items": out, "folder": folder}

    @_safe
    def snapshots_compare(self, a, b):
        import json as _json
        folder = self._mem_folder()
        def load(f):
            if os.path.basename(f) != f:
                raise ValueError("fișier invalid")
            with open(os.path.join(folder, f), encoding="utf-8") as fh:
                return _json.load(fh)
        A, B = load(a), load(b)
        ea, eb = A.get("eeprom") or {}, B.get("eeprom") or {}
        diff = []
        for k in sorted(set(ea) & set(eb), key=int):
            if ea[k] != eb[k] and ea[k] is not None and eb[k] is not None:
                diff.append({"addr": int(k), "a": ea[k], "b": eb[k]})
        return {"diff": diff, "a": A.get("date"), "b": B.get("date"),
                "same_printer": (A.get("serial") == B.get("serial"))}

    @_safe
    def read_cells(self, handle, start, count=16):
        start, count = max(0, int(start)), max(1, min(256, int(count)))
        s = self._session(handle)
        with s.lock:
            vals = s.dump(start, start + count - 1)
        return {"cells": [{"addr": a, "value": v} for a, v in sorted(vals.items())]}

    @_safe
    def write_cell(self, handle, addr, value, notes=""):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        addr, value = int(addr), int(value)
        if not (0 <= addr <= 0xFFFF and 0 <= value <= 255):
            return {"ok": False, "error": "range"}
        s = self._session(handle)
        with s.lock:
            res = s.write_cell(addr, value)
        read = self._read_meta(handle)
        self._history.add(brand="Epson", model=read.get("db_model") or read.get("model"),
                          serial=read.get("serial"), connection=read.get("connection"), kind="eeprom_write",
                          notes=f"adresa {addr}: {res.get('before')} -> {res.get('after')} " + (notes or ""))
        return res

    @_safe
    def find_key_start(self, handle):
        s = self._session(handle)
        read = self._read_meta(handle)

        def job(progress):
            with s.lock:
                res = s.find_key(progress)
            if res.get("key") and read.get("model"):
                keys = dict(self._settings.get("found_keys") or {})
                keys[read["model"]] = res["key"]
                self._settings.set("found_keys", keys)
            return res
        return self._job_start("find_key", job)

    # ---------------- actualizări ----------------
    @_safe
    def update_check(self):
        r = self._upd.check()
        r["dismissed"] = self._settings.get("update_dismissed", "")
        return r

    @_safe
    def update_dismiss(self, version):
        self._settings.set("update_dismissed", str(version))
        return {}

    @_safe
    def update_download(self):
        return self._upd.download()

    @_safe
    def update_progress(self):
        return self._upd.progress()

    @_safe
    def update_open(self):
        r = self._upd.open_installer()
        if r.get("quit") and self._window is not None:
            # Pe Windows installerul înlocuiește fișierele aplicației: închidem fereastra.
            threading.Timer(1.5, self._window.destroy).start()
        return r

    @_safe
    def set_lang(self, lang):
        self._settings.set("lang", lang if lang in config.LANGS else "ro")
        return {"lang": self._settings.get("lang")}

    @_safe
    def license_state(self, refresh=False):
        return self._lic.state(refresh=bool(refresh))

    @_safe
    def activate(self, key):
        return self._lic.activate(key)

    @_safe
    def open_folder(self, kind="backup"):
        base = store.documents_dir()
        path = os.path.join(base, "Backup" if kind == "backup" else "Rapoarte")
        os.makedirs(path, exist_ok=True)
        platform_util.open_path(path)
        return {"path": path}

    # ---------------- detectare ----------------
    @_safe
    def scan(self, network=True):
        from backend import epson_service as es, winprinters
        found = []
        for dev in es.list_usb_devices():
            item = dict(dev)
            try:
                s = es.EpsonSession(dev["handle"])
                ident = s.identify()
                s.close()
                item.update(ident)
            except Exception as exc:  # noqa: BLE001
                item["identify_error"] = str(exc)
            found.append(item)
        if network:
            for n in es.scan_network():
                if not n.get("foreign"):
                    found.append(n)
        for f in found:
            m = self._models.find("Epson", f.get("model"))
            f["brand"] = "Epson"
            f["support"] = (m or {}).get("mode", "temp")
            f["tested"] = bool((m or {}).get("tested"))
            f["db_model"] = (m or {}).get("model")
            if f["support"] == "temp" and not f.get("identify_error"):
                try:
                    s = es.EpsonSession(f["handle"])
                    box = _box(es._status_to_json(s.printer.get_printer_status() or {}))
                    s.close()
                    if box:
                        f["support"], f["box"] = "box", box
                except Exception:  # noqa: BLE001
                    pass
        others = []
        for p in platform_util.installed_printers():
            name = p["name"]
            if "epson" in name.lower():
                continue
            m = self._models.match_name(name)
            if m:
                others.append({"brand": m["brand"], "model": m["model"], "name": name,
                               "connection": p["connection"], "support": m.get("mode"),
                               "db_model": m["model"]})
        return {"printers": found, "others": others}

    # ---------------- fișa imprimantei ----------------
    def _session(self, handle, model=None):
        from backend import epson_service as es
        with self._lock:
            s = self._sessions.get(handle)
            if s is None:
                s = es.EpsonSession(handle)
                self._sessions[handle] = s
        if model:
            s.set_model(model)
        return s

    @_safe
    def open_printer(self, handle):
        s = self._session(handle)
        with s.lock:
            ident = s.identify()
            entry = self._models.find("Epson", ident.get("model"))
            if entry:
                s.set_model(entry["family"])
            else:
                # Fără date de resetare: folosim totuși configurația de citire (cheie, contoare),
                # din bibliotecă sau din cheia găsită anterior cu „Detectare cheie”.
                from backend import epson_service as es
                conf = es.find_conf_model(ident.get("model"), ident.get("raw_model"))
                if conf:
                    s.set_model(conf)
                key = (self._settings.get("found_keys") or {}).get(ident.get("model") or "")
                if key and not (s.printer.parm or {}).get("read_key"):
                    s.printer.parm = dict(s.printer.parm or {}, read_key=list(key))
            data = s.read_all()
        data.update(ident)
        data["handle"] = handle
        data["connection"] = "USB" if handle.startswith("usb:") else "Wi-Fi"
        data["support"] = (entry or {}).get("mode", "temp")
        box = _box(data.get("status"))
        if box and data["support"] == "temp":
            # Fără contor de resetat: cerneala uzată merge într-o cutie înlocuibilă.
            data["support"] = "box"
            data["box"] = box
        data["tested"] = bool((entry or {}).get("tested"))
        data["db_model"] = (entry or {}).get("model")
        data["leds"] = _leds(data)
        self._meta[handle] = {"read": data, "backup": None}
        return data

    @_safe
    def backup(self, handle):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        s = self._session(handle)
        meta = self._meta.get(handle) or {}
        read = meta.get("read") or {}
        folder = os.path.join(store.documents_dir(), "Backup")
        with s.lock:
            res = s.backup(folder, {"serial": read.get("serial"), "waste": read.get("waste")})
        meta["backup"] = res["path"]
        self._meta[handle] = meta
        return res

    @_safe
    def reset(self, handle, client="", contact="", notes=""):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        meta = self._meta.get(handle) or {}
        if not meta.get("backup"):
            return {"ok": False, "error": "no_backup"}
        read = meta.get("read") or {}
        if read.get("support") != "auto":
            return {"ok": False, "error": "unsupported"}
        s = self._session(handle)
        with s.lock:
            res = s.reset()
            after = s.printer.get_waste_ink_levels() if res["ok"] else None
        job_id = None
        if res["ok"]:
            job_id = self._history.add(
                client=client, client_contact=contact, brand="Epson",
                model=read.get("db_model") or read.get("model"), serial=read.get("serial"),
                firmware=read.get("firmware"), connection=read.get("connection"),
                kind="reset", waste_before=read.get("waste"), waste_after=after,
                stats=read.get("stats"), backup_path=meta.get("backup"), notes=notes)
        res.update({"waste_after": after, "job_id": job_id})
        return res

    @_safe
    def temporary_unlock(self, handle, client="", contact="", notes=""):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        read = (self._meta.get(handle) or {}).get("read") or {}
        s = self._session(handle)
        with s.lock:
            res = s.temporary_unlock()
        if res["ok"]:
            res["job_id"] = self._history.add(
                client=client, client_contact=contact, brand="Epson",
                model=read.get("db_model") or read.get("model"), serial=read.get("serial"),
                firmware=read.get("firmware"), connection=read.get("connection"),
                kind="temp_unlock", waste_before=read.get("waste"),
                stats=read.get("stats"), notes=notes)
        return res

    @_safe
    def restore(self, handle):
        if not self._lic.is_active():
            return {"ok": False, "error": "license"}
        import webview
        folder = os.path.join(store.documents_dir(), "Backup")
        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG, directory=folder, file_types=("Backup (*.json)",))
        if not paths:
            return {"ok": False, "error": "cancelled"}
        s = self._session(handle)
        with s.lock:
            res = s.restore(paths[0])
            res["waste_after"] = s.printer.get_waste_ink_levels()
        read = (self._meta.get(handle) or {}).get("read") or {}
        self._history.add(brand="Epson", model=read.get("db_model") or read.get("model"),
                         serial=read.get("serial"), kind="restore",
                         waste_before=read.get("waste"), waste_after=res["waste_after"],
                         backup_path=paths[0])
        return res

    @_safe
    def save_check(self, handle, client="", contact="", notes=""):
        read = (self._meta.get(handle) or {}).get("read") or {}
        job_id = self._history.add(
            client=client, client_contact=contact, brand="Epson",
            model=read.get("db_model") or read.get("model"), serial=read.get("serial"),
            firmware=read.get("firmware"), connection=read.get("connection"),
            kind="check", waste_before=read.get("waste"), stats=read.get("stats"), notes=notes)
        return {"job_id": job_id}

    # ---------------- baza de modele + ghiduri ----------------
    @_safe
    def models_search(self, q="", brand=""):
        items = self._models.search(q, brand)
        return {"items": items[:400], "total": len(items)}

    @_safe
    def guide_steps(self, brand, model):
        """Pașii detaliați ai ghidului, în limba aplicației (cu licență activă)."""
        lang = self._settings.get("lang", "ro")
        return self._lic.guide_steps(f"{brand}|{model}", lang, os.path.join(DATA, "ghiduri.json"))

    @_safe
    def save_guide_job(self, brand, model, client="", contact="", notes=""):
        job_id = self._history.add(brand=brand, model=model, kind="guide",
                                  client=client, client_contact=contact, notes=notes)
        return {"job_id": job_id}

    # ---------------- asistentul Canon (fără scriere în imprimantă) ----------------
    @_safe
    def canon_usb(self):
        from backend import canon
        return {"devices": canon.usb_devices()}

    @_safe
    def canon_compare(self, baseline):
        from backend import canon
        return canon.compare(baseline or [], canon.usb_devices())

    @_safe
    def canon_printers(self):
        return {"printers": [p for p in platform_util.installed_printers()
                             if "canon" in (p["name"] + " " + (p.get("driver") or "")).lower()]}

    @_safe
    def canon_maintenance(self, printer_name):
        from backend import canon
        return {"opened": canon.open_maintenance(printer_name)}

    @_safe
    def linux_usb(self, setup=False):
        if setup:
            return {"ready": platform_util.linux_usb_setup() and bool(platform_util.linux_usb_ready())}
        return {"ready": platform_util.linux_usb_ready()}

    @_safe
    def save_canon_job(self, model, client="", contact="", notes="", details=None):
        job_id = self._history.add(brand="Canon", model=model, kind="canon_assist",
                                  connection="USB", client=client, client_contact=contact,
                                  notes=notes, stats={"canon": details or {}})
        return {"job_id": job_id}

    # ---------------- istoric + rapoarte ----------------
    @_safe
    def history_list(self, q=""):
        return {"items": self._history.list(q)}

    @_safe
    def history_update(self, job_id, client="", contact="", notes=""):
        self._history.update(int(job_id), client=client, client_contact=contact, notes=notes)
        return {}

    @_safe
    def report(self, job_id, open_it=True):
        from backend import report
        job = self._history.get(int(job_id))
        if not job:
            return {"ok": False, "error": "not_found"}
        path = report.build(job, os.path.join(store.documents_dir(), "Rapoarte"),
                            os.path.join(HERE, "ui", "assets"), os.path.join(HERE, "fonts"),
                            self._settings.get("lang", "ro"))
        self._history.update(int(job_id), report_path=path)
        if open_it:
            platform_util.open_path(path)
        return {"path": path}

    @_safe
    def open_doc(self, kind):
        """Documentele legale (pe site, în limba aplicației) și manualul (PDF local)."""
        lang = self._settings.get("lang", "ro")
        if kind == "manual":
            p = os.path.join(HERE, "docs", f"Manual-{lang.upper()}.pdf")
            if not os.path.exists(p):
                p = os.path.join(HERE, "docs", "Manual-EN.pdf")
            if os.path.exists(p):
                platform_util.open_path(p)
                return {"path": p}
        pages = {"eula": "licenta", "privacy": "confidentialitate", "terms": "termeni", "manual": "manual"}
        import webbrowser
        if kind == "download":
            url = f"{config.SITE_URL}{'' if lang == 'ro' else '/' + lang}/#descarca"
            webbrowser.open(url)
            return {"url": url}
        if kind not in pages:
            return {"ok": False, "error": "unknown"}
        import webbrowser
        url = f"{config.SITE_URL}{'' if lang == 'ro' else '/' + lang}/{pages[kind]}.html"
        webbrowser.open(url)
        return {"url": url}

    @_safe
    def open_path(self, path):
        if path and os.path.exists(path):
            platform_util.open_path(os.path.dirname(path) if path.endswith(".json") else path)
        return {}


def _box(status):
    """Cutia de întreținere (modelele Epson fără tampon intern): starea cea mai gravă."""
    mb = (status or {}).get("maintenance_box") or {}
    states = [str(v) for k, v in mb.items() if k[len("maintenance_box_"):].isdigit()]
    if not states:
        return None
    rank = {"full": 3, "near": 2, "not": 1}
    worst = max(states, key=lambda s: rank.get(s.split(" ")[0], 0))
    state = {"full": "full", "near": "near", "not": "ok"}.get(worst.split(" ")[0], "unknown")
    return {"state": state, "replaced": mb.get("maintenance_box_replacement_counter")}


def _leds(d):
    """Ce LED-uri arată probabil imprimanta, dedus din stare și tampoane."""
    st = d.get("status") or {}
    err = (st.get("error") or "").lower()
    waste = d.get("waste") or {}
    full = "ink overflow" in err or "waste" in err or any(
        (v or 0) >= 100 for v in waste.values() if isinstance(v, (int, float)))
    if full:
        return {"power": "on", "ink": "blink", "paper": "blink", "reason": "waste_full"}
    if "paper" in err:
        return {"power": "on", "ink": "off", "paper": "on", "reason": "paper"}
    if "ink" in err:
        return {"power": "on", "ink": "on", "paper": "off", "reason": "ink"}
    return {"power": "on", "ink": "off", "paper": "off", "reason": "ok"}


def main():
    import webview
    api = Api()
    window = webview.create_window(
        f"{config.APP_NAME} {config.VERSION}",
        url=os.path.join(HERE, "ui", "index.html"),
        js_api=api, width=1280, height=820, min_size=(1100, 720),
        background_color="#E8ECF0")
    api._window = window
    webview.start(gui="edgechromium" if platform_util.WIN else ("qt" if platform_util.LINUX else None), debug="--debug" in sys.argv,
                  storage_path=os.path.join(DATA, "webview"))


if __name__ == "__main__":
    main()
