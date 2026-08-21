# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
datas = [('configs', 'configs')]
binaries = []
pcan_basic_dll = project_root / 'PCANBasic.dll'

if pcan_basic_dll.exists():
    binaries.append((str(pcan_basic_dll), '.'))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'can.interfaces.pcan',
        'can.interfaces.pcan.pcan',
        'can.interfaces.virtual',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='J1939_Simulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
