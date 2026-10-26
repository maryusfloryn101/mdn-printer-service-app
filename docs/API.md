# Interfețele de rețea

Toate cererile sunt `POST` cu corp JSON și răspund JSON. Erorile au forma `{"ok": false, "error": "<cod>"}`.

## Serverul de licențe: `https://licente.mdndigital.ro`

### `POST /api/activate.php`
Cerere: `{"key": "MDN-XXXX-XXXX-XXXX", "machine": "<ID calculator>", "app_version": "1.1.0"}`
Răspuns: `{"ok": true, "token": "<jeton semnat>", "valid_until": <unix>, ...}`
Erori: `invalid_key`, `revoked`, `already_used`, `rate_limited`.

### `POST /api/check.php`
Reînnoiește jetonul (aplicația o face o dată pe săptămână).
Cerere: `{"token": "...", "machine": "...", "app_version": "..."}`
Erori: `invalid_token`, `machine_mismatch`, `invalid_key`, `revoked`.

### `POST /api/guide.php`
Pașii detaliați ai unui ghid de service, doar pentru licențe active.
Cerere: `{"token": "...", "machine": "...", "model": "Canon|G2010", "lang": "ro"}`
Răspuns: `{"ok": true, "model": "...", "lang": "ro", "steps": ["..."]}`
Erori: `invalid_token`, `machine_mismatch`, `expired`, `revoked`, `not_found`.

## Site: `https://printer.mdndigital.ro`

### `GET /versiune.json`
Manifestul pentru actualizarea automată, construit din ultimul Release GitHub (cache 10 minute):
```json
{
  "version": "1.1.0",
  "date": "2026-10-26",
  "notes": {"ro": "..."},
  "page": "https://printer.mdndigital.ro/#descarca",
  "files": {
    "win":       {"url": "https://github.com/.../MDN-Printer-Service-Setup.exe", "size": 21914576, "sha256": "..."},
    "mac-arm":   {"url": "...", "size": 0, "sha256": "..."},
    "mac-intel": {"url": "...", "size": 0, "sha256": "..."},
    "linux":     {"url": "...", "size": 0, "sha256": "..."}
  }
}
```
### `GET /download/<fișier>`
Redirecționare 302 către `releases/latest/download/<fișier>` (installere) sau arhiva codului sursă.
