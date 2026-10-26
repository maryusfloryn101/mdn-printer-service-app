# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/ui', 'ui'), ('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/data', 'data'), ('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/docs', 'docs'), ('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/fonts', 'fonts'), ('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/lib', 'lib'), ('/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/backend/report_i18n.json', 'backend')]
binaries = [('/usr/lib/x86_64-linux-gnu/libusb-1.0.so.0', 'native')]
hiddenimports = ['epson_print_conf', 'epson_usb_bridge', 'backend.canon', 'backend.report', 'backend.license', 'backend.epson_service', 'backend.platform_util', 'backend.winprinters', 'backend.store', 'backend.config']
tmp_ret = collect_all('pysnmp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pysnmp_sync_adapter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyprintlpr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('epson_escp2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('epson_usb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('hexdump2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('fpdf')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('proxy_tools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyasn1')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yaml')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/main.py'],
    pathex=['/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app/lib', '/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/app'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MDN Printer Service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['/tmp/claude-0/-home-claude/ea3c309d-5f64-584c-981e-7ed251198c04/scratchpad/repo/build/icons/icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MDN Printer Service',
)
