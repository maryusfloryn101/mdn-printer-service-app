# -*- coding: utf-8 -*-
"""Activarea cu cheie, verificată online pe serverul Madena.

Fluxul:
  1. Aplicația trimite cheia + ID-ul calculatorului la /api/activate.php.
  2. Serverul răspunde cu un "token" semnat Ed25519: payload.semnătură.
  3. Tokenul se păstrează local; e valid până la `valid_until` (câteva zile),
     apoi aplicația îl reîmprospătează la /api/check.php când are internet.
Cheia publică de mai jos verifică semnătura; cheia privată stă doar pe server.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from typing import Optional

import logging

from . import config, platform_util

log = logging.getLogger("mdnps.license")


def machine_id() -> str:
    from .platform_util import machine_raw_id
    raw = machine_raw_id()
    h = hashlib.sha256(("mdnps:" + raw).encode()).hexdigest().upper()
    return "-".join([h[0:4], h[4:8], h[8:12], h[12:16]])


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_token(token: str) -> Optional[dict]:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        body, sig = token.split(".")
        pub = Ed25519PublicKey.from_public_bytes(_b64d(config.LICENSE_PUBLIC_KEY))
        pub.verify(_b64d(sig), body.encode())
        return json.loads(_b64d(body))
    except Exception:  # noqa: BLE001
        return None


def _post(path: str, data: dict) -> dict:
    req = urllib.request.Request(
        config.LICENSE_SERVER.rstrip("/") + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "MDNPrinterService/" + config.VERSION},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12, context=platform_util.ssl_context()) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": f"server_{e.code}"}
    except Exception as exc:  # noqa: BLE001
        log.warning("server de licențe indisponibil (%s): %r", path, exc)
        return {"ok": False, "error": "offline"}


class License:
    def __init__(self, settings):
        self.settings = settings
        self.mid = machine_id()

    def state(self, refresh: bool = False) -> dict:
        if not config.LICENSE_PUBLIC_KEY or config.LICENSE_PUBLIC_KEY.startswith("REPLACE"):
            # Serverul de activare nu e încă configurat (versiune de test):
            # toate funcțiile sunt deschise.
            return {"active": True, "machine": self.mid, "key_hint": "mod de test", "test_mode": True}
        token = self.settings.get("license_token")
        payload = verify_token(token) if token else None
        now = int(time.time())
        if payload and payload.get("machine") != self.mid:
            payload = None
        if payload and (refresh or payload.get("valid_until", 0) - now < 2 * 86400):
            res = _post("/api/check.php", {"token": token, "machine": self.mid,
                                           "app_version": config.VERSION})
            if res.get("ok") and verify_token(res.get("token", "")):
                self.settings.set("license_token", res["token"])
                payload = verify_token(res["token"])
            elif res.get("error") in ("revoked", "invalid_key", "machine_mismatch"):
                self.settings.set("license_token", None)
                return {"active": False, "machine": self.mid, "reason": res["error"]}
        if payload and payload.get("valid_until", 0) >= now:
            return {"active": True, "machine": self.mid,
                    "key_hint": payload.get("key", "")[:9] + "…",
                    "valid_until": payload.get("valid_until")}
        return {"active": False, "machine": self.mid,
                "reason": "expired" if payload else "none"}

    def activate(self, key: str) -> dict:
        key = (key or "").strip().upper()
        res = _post("/api/activate.php", {"key": key, "machine": self.mid,
                                          "app_version": config.VERSION})
        if res.get("ok") and verify_token(res.get("token", "")):
            self.settings.set("license_token", res["token"])
            return {"ok": True, **self.state()}
        return {"ok": False, "error": res.get("error", "unknown")}

    def guide_steps(self, model_key: str, lang: str, cache_path: str) -> dict:
        """Pașii detaliați ai unui ghid, descărcați de pe serverul de licențe (doar cu licență activă).
        Se păstrează local, ca să funcționeze și fără internet cât timp licența e valabilă."""
        st = self.state()
        if not st.get("active"):
            return {"ok": False, "error": "license"}
        if st.get("test_mode"):
            return {"ok": False, "error": "offline"}
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cache = json.load(fh)
        except (OSError, ValueError):
            cache = {}
        ck = lang + "|" + model_key
        res = _post("/api/guide.php", {"token": self.settings.get("license_token"), "machine": self.mid,
                                        "model": model_key, "lang": lang})
        if res.get("ok"):
            cache[ck] = res.get("steps") or []
            try:
                tmp = cache_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(cache, fh, ensure_ascii=False)
                import os
                os.replace(tmp, cache_path)
            except OSError:
                pass
            return {"ok": True, "steps": cache[ck]}
        if ck in cache:
            return {"ok": True, "steps": cache[ck], "cached": True}
        return {"ok": False, "error": res.get("error", "offline")}

    def is_active(self) -> bool:
        return bool(self.state().get("active"))
