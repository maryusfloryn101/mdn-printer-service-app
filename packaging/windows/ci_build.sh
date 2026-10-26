#!/bin/bash
# Construiește installerul Windows (NSIS) pe un runner Linux din GitHub Actions.
# Python portabil pentru Windows (python-build-standalone) + pachetele pentru win_amd64.
set -euo pipefail
trap 'echo "::error::ci_build.sh linia $LINENO: $BASH_COMMAND"' ERR
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
B="$ROOT/build/win"; ST="$B/stage"
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/app/backend/config.py")
rm -rf "$B" && mkdir -p "$ST/app/lib"

# 1. Python 3.12 portabil pentru Windows
if [ -n "${PY_TGZ:-}" ]; then
  cp "$PY_TGZ" "$B/py.tar.gz"
else
  RID=$(gh api repos/astral-sh/python-build-standalone/releases/latest --jq .id)
  ASSETS=$(gh api --paginate "repos/astral-sh/python-build-standalone/releases/$RID/assets?per_page=100" --jq '.[].browser_download_url')
  URL=$(echo "$ASSETS" | grep -E 'cpython-3\.12\.[0-9]+\+[0-9]+-x86_64-pc-windows-msvc-install_only(_stripped)?\.tar\.gz$' | sort | tail -1 || true)
  if [ -z "$URL" ]; then echo "Nu am găsit Python pentru Windows"; echo "::error::Python Windows negăsit; fișiere în listă: $(echo "$ASSETS" | grep -c .); exemple: $(echo "$ASSETS" | grep -i "windows" | grep "3\.12" | head -3 | xargs -n1 basename | tr "\n" " ")"; exit 1; fi
  echo "Python: $URL"
  curl -fsSL -o "$B/py.tar.gz" "$URL"
fi
tar -xzf "$B/py.tar.gz" -C "$ST"
( cd "$ST/python" && find . -name "*.pdb" -delete && rm -rf include libs Lib/test Lib/idlelib Lib/ensurepip Lib/lib2to3 Scripts tcl Lib/tkinter DLLs/_tkinter.pyd DLLs/tcl*.dll DLLs/tk*.dll && find . -name "__pycache__" -type d -prune -exec rm -rf {} + )

# 2. Pachete: cele cu cod compilat, direct pentru Windows; cele pur Python, de oriunde
python -m pip install --quiet --target "$ST/app/lib" --platform win_amd64 --python-version 3.12 \
  --implementation cp --only-binary=:all: --no-deps \
  pywebview==6.2.1 pythonnet==3.2.1 clr_loader==0.3.1 cffi pycparser bottle==0.13.4 \
  pysnmp==7.1.30 pyasn1 epson-usb==0.1.2 pyusb==1.3.1 fpdf2==2.8.9 pillow fonttools \
  defusedxml==0.7.1 pyyaml cryptography colorama typing_extensions certifi hexdump2==1.2.2
python -m pip install --quiet --target "$ST/app/lib" --no-deps \
  pysnmp-sync-adapter==1.1.0 pyprintlpr==1.1.1 epson-escp2==1.0.4 proxy-tools==0.1.0
rm -rf "$ST/app/lib/bin" "$ST/app/lib/share" && find "$ST/app/lib" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 3. Aplicația
cp -r "$ROOT/app/main.py" "$ROOT/app/backend" "$ROOT/app/ui" "$ROOT/app/fonts" "$ROOT/app/data" "$ROOT/app/docs" "$ST/app/"
cp "$ROOT/app/lib/"* "$ST/app/lib/"
find "$ST/app" -name "__pycache__" -type d -prune -exec rm -rf {} +
cp "$ROOT/NOTICE.txt" "$ST/LICENSE.txt"
cp "$ROOT/EULA.txt" "$ST/EULA.txt"

# 4. Installer
cp "$ROOT/packaging/windows/installer.nsi" "$B/"
( cd "$B" && makensis -V2 -DVERSION="$VERSION" -DSRCDIR=stage installer.nsi )
mkdir -p "$ROOT/dist"
mv "$B/MDN-Printer-Service-Setup-$VERSION.exe" "$ROOT/dist/MDN-Printer-Service-Setup.exe"
ls -la "$ROOT/dist"
