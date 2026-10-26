# Arhitectura MDN Printer Service

## Componente
```
┌──────────────────────────┐      HTTPS       ┌──────────────────────────────┐
│ Aplicația (desktop)       │ ───────────────▶ │ licente.mdndigital.ro         │
│ Python + pywebview        │  activare/verif. │ /api/activate.php, check.php  │
│ app/main.py, app/backend  │  pași ghiduri    │ /api/guide.php (licență)      │
│ app/ui (HTML/JS)          │                  │ SQLite + chei Ed25519         │
└────────────┬─────────────┘                  └──────────────────────────────┘
             │ HTTPS: versiune.json                         ▲
             ▼                                              │ (admin: /admin)
┌──────────────────────────┐   302 redirect   ┌──────────────────────────────┐
│ printer.mdndigital.ro     │ ───────────────▶ │ GitHub Releases (public)      │
│ site PHP, 12 limbi        │  /download/*     │ installere Win/Mac/Linux      │
│ versiune.php (din GitHub) │                  │ construite de Actions         │
└──────────────────────────┘                  └──────────────────────────────┘
```

## Aplicația
- **`app/main.py`**: clasa `Api` expusă interfeței; fiecare metodă publică e apelabilă din JS (`pywebview.api.<metodă>`).
- **`app/backend/epson_service.py`**: comunicarea cu imprimantele Epson (USB și rețea), prin biblioteca `epson_print_conf`; citire, backup, resetare, deblocare temporară, unelte de service (contoare separate, întreținere, memorie, detectare cheie).
- **`app/backend/canon.py`**, **`platform_util.py`**: asistentul Canon și diferențele Windows/macOS/Linux.
- **`app/backend/license.py`**: activare și verificare săptămânală; jetonul e semnat Ed25519 de server și verificat local cu cheia publică din `config.py`.
- **`app/backend/update.py`**: verificarea versiunilor noi; descarcă doar de pe site sau din Releases, verifică SHA-256.
- **`app/backend/store.py`**: setări, istoric (SQLite), baza de modele; datele stau pe calculatorul utilizatorului.
- **`app/data/models.json`**: modelele cunoscute (Epson: resetare automată; Canon/Brother: ghiduri; pașii plătiți lipsesc intenționat).

## Licențiere și conținut plătit
- Citirea imprimantei e gratuită; scrierea (resetare, timer, editor memorie) cere licență activă.
- Pașii detaliați ai ghidurilor Canon/Brother vin de la `api/guide.php`, numai pentru licențe active (codul aplicației e open-source, EUPL-1.2).

## Construire
- `.github/workflows/build.yml`: 4 joburi (macOS Apple Silicon, macOS Intel, Linux, Windows), fiecare își publică fișierul în Release-ul versiunii din `config.py`.
- `packaging/build.py`: PyInstaller + DMG (macOS) / AppImage (Linux).
- `packaging/windows/ci_build.sh`: Python portabil pentru Windows + pachete win_amd64 + NSIS (`installer.nsi`).
