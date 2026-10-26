#!/bin/bash
# Asamblează folderul aplicației și installerul Windows.
set -euo pipefail
S=/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad
B=$S/mdnps/build
ST=$B/stage
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' $S/mdnps/app/backend/config.py)
rm -rf "$ST" && mkdir -p "$ST/app/lib"

# 1. Python portabil, fără părțile inutile
tar -xzf $S/dl/py.tar.gz -C "$ST"
( cd "$ST/python" && find . -name "*.pdb" -delete && rm -rf include libs Lib/test Lib/idlelib Lib/ensurepip Lib/lib2to3 Scripts tcl Lib/tkinter DLLs/_tkinter.pyd DLLs/tcl*.dll DLLs/tk*.dll && find . -name "__pycache__" -type d -prune -exec rm -rf {} + )

# 2. Biblioteci (pachete Windows)
for w in $S/dl/w2/*.whl; do unzip -q -o "$w" -d "$ST/app/lib"; done
cp -r $S/dl/x/pysnmp_sync_adapter-1.1.0/pysnmp_sync_adapter $S/dl/x/pyprintlpr-1.1.1/pyprintlpr $S/dl/x/epson_escp2-1.0.4/epson_escp2 $S/dl/x2/proxy_tools-0.1.0/proxy_tools "$ST/app/lib/"
cp $S/src/epson_print_conf/epson_print_conf.py $S/src/epson_print_conf/epson_usb_bridge.py "$ST/app/lib/"
cp $S/src/epson_print_conf/LICENSE "$ST/app/lib/epson_print_conf.LICENSE.txt"
find "$ST/app/lib" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 3. Aplicația
cp -r $S/mdnps/app/main.py $S/mdnps/app/backend $S/mdnps/app/ui $S/mdnps/app/fonts $S/mdnps/app/data $S/mdnps/app/docs "$ST/app/"
find "$ST/app" -name "__pycache__" -type d -prune -exec rm -rf {} +
cp $B/LICENSE.txt "$ST/LICENSE.txt"
cp $B/EULA.txt "$ST/EULA.txt"

# 4. Installer
cd $B && makensis -V2 -DVERSION=$VERSION -DSRCDIR=stage installer.nsi
ls -la $B/MDN-Printer-Service-Setup-$VERSION.exe
du -sh "$ST"
