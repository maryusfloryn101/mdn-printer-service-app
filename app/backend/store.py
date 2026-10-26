# -*- coding: utf-8 -*-
"""Date locale: baza de modele (fișier JSON livrat cu aplicația) și istoricul
lucrărilor (SQLite în folderul utilizatorului)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import List, Optional

APP_NAME = "MDN Printer Service"


def data_dir() -> str:
    from .platform_util import data_dir as _d
    return _d()


def documents_dir() -> str:
    """Documente/MDN Printer Service (backup-uri și rapoarte, vizibile utilizatorului)."""
    from .platform_util import documents_base
    path = os.path.join(documents_base(), APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


# ----------------------------------------------------------------------
# Baza de modele
# ----------------------------------------------------------------------
class Models:
    def __init__(self, path: str):
        self.path = path
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.version = data.get("version")
        self.items: List[dict] = data["models"]
        self.by_key = {}
        for m in self.items:
            self.by_key[(m["brand"].lower(), m["model"].upper())] = m

    def find(self, brand: str, model: Optional[str]) -> Optional[dict]:
        if not model:
            return None
        return self.by_key.get((brand.lower(), model.upper()))

    def match_name(self, name: str) -> Optional[dict]:
        """Recunoaște un model din numele unei imprimante instalate în Windows."""
        up = name.upper()
        best = None
        for m in self.items:
            if m["brand"].upper() not in up:
                continue
            keys = [m["model"]] + m.get("match", [])
            for k in keys:
                if k.upper() in up and (best is None or len(k) > best[0]):
                    best = (len(k), m)
        return best[1] if best else None

    def search(self, q: str = "", brand: str = "") -> List[dict]:
        q = (q or "").strip().upper().replace(" ", "")
        res = []
        for m in self.items:
            if brand and brand != "Toate" and m["brand"] != brand:
                continue
            hay = (m["brand"] + m["model"] + " ".join(m.get("aliases", []))).upper().replace(" ", "")
            if q and q not in hay:
                continue
            res.append(m)
        return res

    def counts(self) -> dict:
        c = {}
        for m in self.items:
            c[m["brand"]] = c.get(m["brand"], 0) + 1
        return c


# ----------------------------------------------------------------------
# Istoric
# ----------------------------------------------------------------------
class History:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TEXT NOT NULL,
        client TEXT,
        client_contact TEXT,
        brand TEXT, model TEXT, serial TEXT, firmware TEXT,
        connection TEXT,
        kind TEXT NOT NULL,            -- reset | temp_unlock | check | guide | restore
        waste_before TEXT, waste_after TEXT,   -- JSON
        stats TEXT,                    -- JSON
        backup_path TEXT,
        report_path TEXT,
        notes TEXT
    );
    """

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        with self._conn() as c:
            c.executescript(self.SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def add(self, **row) -> int:
        row.setdefault("created", time.strftime("%Y-%m-%d %H:%M:%S"))
        for k in ("waste_before", "waste_after", "stats"):
            if k in row and not isinstance(row[k], (str, type(None))):
                row[k] = json.dumps(row[k], ensure_ascii=False)
        cols = ",".join(row.keys())
        qs = ",".join("?" for _ in row)
        with self.lock, self._conn() as c:
            cur = c.execute(f"INSERT INTO jobs ({cols}) VALUES ({qs})", list(row.values()))
            return cur.lastrowid

    def update(self, job_id: int, **row):
        for k in ("waste_before", "waste_after", "stats"):
            if k in row and not isinstance(row[k], (str, type(None))):
                row[k] = json.dumps(row[k], ensure_ascii=False)
        sets = ",".join(f"{k}=?" for k in row)
        with self.lock, self._conn() as c:
            c.execute(f"UPDATE jobs SET {sets} WHERE id=?", list(row.values()) + [job_id])

    def get(self, job_id: int) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row(r) if r else None

    def list(self, q: str = "", limit: int = 500) -> List[dict]:
        sql = "SELECT * FROM jobs"
        args: list = []
        if q:
            sql += " WHERE client LIKE ? OR serial LIKE ? OR model LIKE ?"
            like = f"%{q}%"
            args = [like, like, like]
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            return [_row(r) for r in c.execute(sql, args).fetchall()]


def _row(r) -> dict:
    d = dict(r)
    for k in ("waste_before", "waste_after", "stats"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


# ----------------------------------------------------------------------
# Setări
# ----------------------------------------------------------------------
class Settings:
    def __init__(self, path: str):
        self.path = path
        self.data = {"lang": "ro"}
        try:
            with open(path, encoding="utf-8") as fh:
                self.data.update(json.load(fh))
        except (OSError, ValueError):
            pass

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1)
        os.replace(tmp, self.path)
