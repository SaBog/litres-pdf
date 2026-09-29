# -*- mode: python ; coding: utf-8 -*-
# Build: uv run pyinstaller litres-pdf.spec

EXCLUDE_BINARY_PARTS = (
    "selenium-manager",  # replaced below: keep only the Windows one
    "_avif",             # Pillow AVIF support
)
KEEP_BINARY = ("windows\selenium-manager.exe", "windows/selenium-manager.exe")


def keep(dest: str) -> bool:
    if dest.endswith(KEEP_BINARY):
        return True
    return not any(part in dest for part in EXCLUDE_BINARY_PARTS)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "pydoc", "doctest", "test"],
    noarchive=False,
)
a.binaries = [b for b in a.binaries if keep(b[0])]
a.datas = [d for d in a.datas if keep(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="litres-pdf",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
