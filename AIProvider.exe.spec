# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [
    ('web/dist', 'web/dist'),
    ('core/migrations/migrations', 'core/migrations/migrations'),
]
binaries = []
hiddenimports = [
    'main', 'multiprocessing',
    'win32gui', 'win32api', 'win32con', 'yaml',
]
hiddenimports += collect_submodules('core.migrations.migrations')
tmp_ret = collect_all('uvicorn')
tmp_ret2 = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
datas += tmp_ret2[0]; binaries += tmp_ret2[1]; hiddenimports += tmp_ret2[2]

# pywin32 / win32com are C-extension modules with DLL dependencies;
# collect_all bundles the full set. Wrapped in try/except so builds
# on non-Windows (or without pywin32 installed) still succeed.
try:
    tmp_win32 = collect_all('pywin32')
    datas += tmp_win32[0]; binaries += tmp_win32[1]; hiddenimports += tmp_win32[2]
except Exception:
    pass
try:
    tmp_com = collect_all('win32com')
    datas += tmp_com[0]; binaries += tmp_com[1]; hiddenimports += tmp_com[2]
except Exception:
    pass


a = Analysis(
    ['run.py'],
    pathex=[],
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
    a.binaries,
    a.datas,
    [],
    name='AIProvider.exe',
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
    entitlements_field=None,
)