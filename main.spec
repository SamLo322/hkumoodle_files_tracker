# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
import sys
import os

datas = []
datas += collect_data_files('emoji')

main_path = os.path.join('app', 'main.py')
if sys.platform == "win32":
    icon_path = os.path.join('media', 'icons', 'icon.ico')
elif sys.platform == "darwin":
    icon_path = os.path.join('media', 'icons', 'icon.icns')

a = Analysis(
    [main_path],
    pathex=['app'],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='moodle_scraper',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,  # Windowed for macOS, console for Windows
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_path
    )
elif sys.platform == "darwin":
    app = BUNDLE(
        EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='moodle_scraper',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # Windowed for macOS, console for Windows
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_path
    ),
        name='moodle_scraper.app',
        icon=icon_path,
        bundle_identifier=None
    )