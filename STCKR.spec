# PyInstaller: portable directory, native Qt and LibRaw, no installed Python needed.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / "src/stckr/qml"), "stckr/qml"),
         (str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), ".")]
if (root / "vendor").exists():
    datas.append((str(root / "vendor"), "vendor"))
datas += copy_metadata("stckr")
a = Analysis([str(root / "scripts/launch.py")], pathex=[str(root / "src")],
             binaries=collect_dynamic_libs("rawpy"), datas=datas,
             hiddenimports=["stckr", "stckr.engine", "PySide6.QtQuick", "PySide6.QtQml", "PIL.ImageCms"],
             excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
                       "PySide6.QtPdf", "PySide6.Qt3DCore", "tkinter", "matplotlib", "scipy"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="STCKR", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="STCKR")
