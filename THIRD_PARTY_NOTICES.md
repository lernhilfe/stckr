# Third-party notices

STCKR application code is MIT-licensed. This does not relicense its dependencies.

| Component | License / source |
| --- | --- |
| Qt / PySide6 / Shiboken | LGPL-3.0 or commercial; [Qt licensing](https://doc.qt.io/qtforpython-6/licenses.html) |
| rawpy | MIT; [source](https://github.com/letmaik/rawpy) |
| LibRaw, bundled with rawpy | LGPL-2.1 / CDDL-1.0; [source](https://github.com/LibRaw/LibRaw) |
| NumPy | BSD-3-Clause; [source](https://github.com/numpy/numpy) |
| OpenCV | Apache-2.0; [source](https://github.com/opencv/opencv) |
| tifffile | BSD-3-Clause; [source](https://github.com/cgohlke/tifffile) |
| Pillow / LittleCMS | HPND / MIT; [Pillow](https://github.com/python-pillow/Pillow), [LittleCMS](https://github.com/mm2/Little-CMS) |
| psutil | BSD-3-Clause; [source](https://github.com/giampaolo/psutil) |
| ExifTool | Artistic License / GPL; [source](https://github.com/exiftool/exiftool) |
| ExifTool vendored distributions | See included package LICENSE and ExifTool/Perl notices; [source](https://github.com/photostructure/exiftool-vendored.exe) |
| PyInstaller runtime | GPL with bootloader exception; [source](https://github.com/pyinstaller/pyinstaller) |

Qt and LibRaw remain dynamically linked in the portable directory distribution. Users may replace compatible shared libraries; application source and reproducible packaging instructions are provided in this repository. Dependency license texts are collected in the portable package's `licenses` directory by `scripts/collect_licenses.py`; the ExifTool distribution retains its own notices and Perl runtime files. No GPL demosaicing packs are added by STCKR.

The application's algorithms and UI were written independently. OpenFocus (MIT) and Shine Stacker (LGPL-3.0) were inspected as reference projects, but no source code, logos, screenshots or sample photographs were copied into this project. Helicon Focus is a workflow reference and is not affiliated with STCKR. Synthetic examples and screenshots in this repository were generated from STCKR's own deterministic demo generator.

Adobe DNG SDK is used only as an external validation tool, not distributed as part of STCKR. Its license remains with Adobe. Real M50 sample photographs from lclevy/canon_cr3 were used locally for testing and are not redistributed here.
