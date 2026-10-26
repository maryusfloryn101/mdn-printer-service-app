# MDN Printer Service

Aplicație pentru citirea imprimantelor cu jet de cerneală și resetarea contorului de cerneală uzată (Epson), cu ghiduri de service Canon/Brother. Dezvoltată de Madena Digital SRL.

**Descărcare:** [printer.mdndigital.ro](https://printer.mdndigital.ro) sau pagina [Releases](https://github.com/maryusfloryn101/mdn-printer-service-app/releases/latest) (Windows, macOS Apple Silicon și Intel, Linux).

- `app/` – aplicația (Python + pywebview)
- `packaging/build.py` – construirea pentru macOS (.dmg) și Linux (.AppImage)
- `packaging/windows/` – installerul Windows (NSIS)
- `.github/workflows/build.yml` – construire automată (din fila Actions sau la fiecare etichetă `v*`); installerele ajung în Releases

Codul este distribuit sub licența EUPL-1.2 (vezi `NOTICE.txt`, `EULA.txt`).
