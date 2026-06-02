# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for CardWatcher.

Build with: pyinstaller cardwatcher.spec

The resulting executable expects cardwatcher-data/ directory
to be a sibling directory containing pages/, archive/, images/, changes/.
"""

block_cipher = None

a = Analysis(
    ['cardwatcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'flask_session',
        'cachelib',
        'cachelib.file',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'selenium',
        'undetected_chromedriver',
        'bs4',
        'lxml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # NOTE: This build uses a whitelist approach — see BUILD.md. The exe must be
    # built inside a clean virtualenv (.venv-build) that contains ONLY the packages
    # in requirements.txt. PyInstaller can then only bundle real dependencies, so no
    # excludes are needed. Building from a global Python that has extra packages
    # (torch, scipy, etc.) installed will bloat the exe with unrelated libraries.
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CardWatcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon='path/to/icon.ico' if you have one
)
