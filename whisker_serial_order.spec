# -*- mode: python -*-

"""
PyInstaller .spec file for whisker_serial_order.

This should be executed from the project base directory.
To check that directory references are working, break hooks/hook-serial.py
and ensure the build crashes.
"""

block_cipher = None

a = Analysis(
    ['whisker_serial_order/main.py'],
    binaries=None,
    datas=[
        # tuple is: source path/glob, destination directory
        # (regardless of what the docs suggest) and '' seems to
        # work for "the root directory"
        # ... no, not as of PyInstaller==3.4 (2018-09-24); use '.'
        ('whisker_serial_order/alembic.ini', '.'),
        ('whisker_serial_order/alembic/env.py', 'alembic'),
        ('whisker_serial_order/alembic/versions/*.py', 'alembic/versions'),
    ],
    hiddenimports=[
        'cardinal_pythonlib.sqlalchemy.alembic_ops',  # used by alembic/versions/*  # noqa
    ],
    hookspath=['pyinstaller_hooks'],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='whisker_serial_order',
    debug=False,
    strip=False,
    upx=True,
    console=False  # NB!
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='whisker_serial_order'
)
