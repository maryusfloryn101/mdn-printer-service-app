"""Construiește MDN Printer Service pentru macOS (.app în .dmg) sau Linux (AppImage).

Rulat automat de GitHub Actions (vezi .github/workflows/build.yml):
    python packaging/build.py --libusb /cale/libusb-1.0.dylib
Rezultatul ajunge în dist/.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
NAME = "MDN Printer Service"


def version() -> str:
    src = open(os.path.join(APP, "backend", "config.py"), encoding="utf-8").read()
    return re.search(r'VERSION\s*=\s*"([^"]+)"', src).group(1)


def icons() -> dict:
    """Generează icon.icns (macOS) și icon.png (Linux) din icon.ico."""
    from PIL import Image
    out = os.path.join(ROOT, "build", "icons")
    os.makedirs(out, exist_ok=True)
    ico = Image.open(os.path.join(APP, "ui", "assets", "icon.ico"))
    sizes = sorted(ico.info.get("sizes", {(256, 256)}))
    ico.size = sizes[-1]
    img = ico.convert("RGBA").resize((512, 512), Image.LANCZOS)
    png = os.path.join(out, "icon.png")
    img.save(png)
    icns = os.path.join(out, "icon.icns")
    img.save(icns)
    return {"png": png, "icns": icns}


def pyinstaller(libusb: str | None, ic: dict) -> str:
    sep = os.pathsep
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", NAME, "--distpath", os.path.join(ROOT, "dist", "pyi"),
        "--workpath", os.path.join(ROOT, "build", "pyi"),
        "--paths", os.path.join(APP, "lib"), "--paths", APP,
        "--icon", ic["icns"] if sys.platform == "darwin" else ic["png"],
    ]
    for d in ("ui", "data", "docs", "fonts", "lib"):
        args += ["--add-data", f"{os.path.join(APP, d)}{sep}{d}"]
    for p in ("pysnmp", "pysnmp_sync_adapter", "pyprintlpr", "epson_escp2", "epson_usb",
              "hexdump2", "fpdf", "webview", "proxy_tools", "pyasn1", "yaml", "certifi"):
        args += ["--collect-all", p]
    for m in ("epson_print_conf", "epson_usb_bridge", "backend.canon", "backend.report",
              "backend.license", "backend.epson_service", "backend.platform_util",
              "backend.winprinters", "backend.store", "backend.config"):
        args += ["--hidden-import", m]
    args += ["--add-data", f"{os.path.join(APP, 'backend', 'report_i18n.json')}{sep}backend"]
    if libusb:
        args += ["--add-binary", f"{libusb}{sep}native"]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "ro.mdndigital.printerservice"]
    args.append(os.path.join(APP, "main.py"))
    subprocess.check_call(args, cwd=ROOT)
    return os.path.join(ROOT, "dist", "pyi")


def macos(dist: str, ic: dict) -> str:
    v = version()
    arch = "AppleSilicon" if platform.machine() == "arm64" else "Intel"
    app = os.path.join(dist, NAME + ".app")
    plist = os.path.join(app, "Contents", "Info.plist")
    # Versiunea și limbile afișate de macOS.
    subprocess.call(["/usr/libexec/PlistBuddy", "-c", f"Set :CFBundleShortVersionString {v}", plist])
    subprocess.call(["/usr/libexec/PlistBuddy", "-c", f"Add :LSMinimumSystemVersion string 12.0", plist])
    subprocess.call(["/usr/libexec/PlistBuddy", "-c",
                     "Add :NSLocalNetworkUsageDescription string MDN Printer Service caută imprimantele din rețeaua locală.", plist])
    # Semnătură ad-hoc: obligatorie pe Apple Silicon pentru a putea fi deschisă.
    subprocess.check_call(["codesign", "--force", "--deep", "--sign", "-", app])
    stage = os.path.join(ROOT, "build", "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    shutil.copytree(app, os.path.join(stage, NAME + ".app"), symlinks=True)
    os.symlink("/Applications", os.path.join(stage, "Applications"))
    out = os.path.join(ROOT, "dist", f"MDN-Printer-Service-macOS-{arch}.dmg")
    subprocess.check_call(["hdiutil", "create", "-volname", NAME, "-srcfolder", stage,
                           "-ov", "-format", "UDZO", out])
    return out


def linux(dist: str, ic: dict, appimagetool: str) -> str:
    v = version()
    appdir = os.path.join(ROOT, "build", "AppDir")
    shutil.rmtree(appdir, ignore_errors=True)
    os.makedirs(os.path.join(appdir, "usr", "bin"))
    shutil.copytree(os.path.join(dist, NAME), os.path.join(appdir, "usr", "bin", "mdn-printer-service"),
                    symlinks=True)
    shutil.copy(ic["png"], os.path.join(appdir, "mdn-printer-service.png"))
    with open(os.path.join(appdir, "mdn-printer-service.desktop"), "w", encoding="utf-8") as fh:
        fh.write("[Desktop Entry]\nType=Application\nName=MDN Printer Service\n"
                 "Comment=Printer service: waste ink counter reset\nExec=mdn-printer-service\n"
                 "Icon=mdn-printer-service\nCategories=Utility;System;\nTerminal=false\n")
    with open(os.path.join(appdir, "AppRun"), "w", encoding="utf-8") as fh:
        fh.write('#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\n'
                 'exec "$HERE/usr/bin/mdn-printer-service/MDN Printer Service" "$@"\n')
    os.chmod(os.path.join(appdir, "AppRun"), 0o755)
    out = os.path.join(ROOT, "dist", "MDN-Printer-Service-Linux-x86_64.AppImage")
    env = dict(os.environ, ARCH="x86_64")
    subprocess.check_call([appimagetool, "--appimage-extract-and-run", appdir, out], env=env)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--libusb", help="libusb-1.0 de inclus în aplicație")
    ap.add_argument("--appimagetool", default="appimagetool")
    a = ap.parse_args()
    ic = icons()
    dist = pyinstaller(a.libusb, ic)
    out = macos(dist, ic) if sys.platform == "darwin" else linux(dist, ic, a.appimagetool)
    print("OK:", out)


if __name__ == "__main__":
    main()
