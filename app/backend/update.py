# -*- coding: utf-8 -*-
"""Verificarea și descărcarea versiunilor noi.

Aplicația citește https://printer.mdndigital.ro/versiune.json (fără date despre utilizator)
și, dacă există o versiune mai nouă, descarcă la cerere installerul potrivit sistemului
(de pe site sau din pagina de versiuni GitHub a proiectului) în folderul Descărcări,
verifică amprenta SHA-256 și îl deschide.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
import threading
import urllib.parse
import urllib.request

from . import config, platform_util

MANIFEST = config.SITE_URL.rstrip("/") + "/versiune.json"
_ALLOWED = (config.SITE_URL.rstrip("/") + "/", config.RELEASES_URL.rstrip("/") + "/")


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in str(v).split(".") if x.isdigit())


def platform_key() -> str:
    if platform_util.WIN:
        return "win"
    if platform_util.MAC:
        return "mac-arm" if platform.machine() == "arm64" else "mac-intel"
    return "linux"


def downloads_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(d):
        d = platform_util.documents_base()
    return d


def _get(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": "MDNPrinterService/" + config.VERSION})
    return urllib.request.urlopen(req, timeout=timeout, context=platform_util.ssl_context())


class Updater:
    def __init__(self):
        self.info = None
        self.job = {"state": "idle"}
        self._lock = threading.Lock()

    def check(self) -> dict:
        try:
            with _get(MANIFEST) as r:
                m = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": "offline"}
        f = (m.get("files") or {}).get(platform_key()) or {}
        newer = bool(m.get("version")) and _ver(m["version"]) > _ver(config.VERSION) and bool(f.get("url"))
        self.info = {"version": m.get("version"), "date": m.get("date"), "notes": m.get("notes") or {},
                     "file": f, "page": m.get("page") or config.SITE_URL}
        return {"available": newer, "current": config.VERSION, "version": m.get("version"),
                "date": m.get("date"), "notes": m.get("notes") or {}, "size": f.get("size"),
                "page": self.info["page"]}

    def download(self) -> dict:
        if not self.info or not self.info["file"].get("url"):
            return {"ok": False, "error": "no_update"}
        url = urllib.parse.urljoin(config.SITE_URL + "/", self.info["file"]["url"])
        if not url.startswith(_ALLOWED):
            return {"ok": False, "error": "bad_url"}
        with self._lock:
            if self.job.get("state") == "running":
                return {"started": False}
            self.job = {"state": "running", "done": 0, "total": self.info["file"].get("size") or 0}
        threading.Thread(target=self._run, args=(url, self.info["file"].get("sha256")), daemon=True).start()
        return {"started": True}

    def _run(self, url: str, sha: str | None):
        name = os.path.basename(urllib.parse.urlparse(url).path)
        dest = os.path.join(downloads_dir(), name)
        part = dest + ".part"
        h = hashlib.sha256()
        try:
            with _get(url, timeout=30) as r, open(part, "wb") as fh:
                total = int(r.headers.get("Content-Length") or 0) or self.job.get("total", 0)
                self.job["total"] = total
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                    h.update(chunk)
                    self.job["done"] += len(chunk)
            if sha and h.hexdigest().lower() != sha.lower():
                os.remove(part)
                self.job = {"state": "error", "error": "checksum"}
                return
            os.replace(part, dest)
            if dest.endswith(".AppImage"):
                os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self.job = {"state": "done", "path": dest}
        except Exception as exc:  # noqa: BLE001
            try:
                os.remove(part)
            except OSError:
                pass
            self.job = {"state": "error", "error": "download", "detail": str(exc)}

    def progress(self) -> dict:
        return dict(self.job)

    def open_installer(self) -> dict:
        p = self.job.get("path")
        if not p or not os.path.exists(p):
            return {"ok": False, "error": "no_file"}
        if p.endswith(".AppImage"):
            # Pe Linux arătăm fișierul; utilizatorul închide aplicația veche și pornește noua versiune.
            platform_util.open_path(os.path.dirname(p))
        else:
            platform_util.open_path(p)
        return {"path": p, "quit": sys.platform == "win32"}
