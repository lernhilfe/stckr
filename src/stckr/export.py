"""Atomic exports. DNG pixels stay linear in native camera RGB."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import os
import uuid
import numpy as np
import tifffile
from PIL import Image, ImageCms

from .models import ColorInfo
from .imaging import develop, thumbnail, exiftool_path


def rational(values, signed=False):
    out = []
    for value in np.ravel(values):
        f = Fraction(float(value)).limit_denominator(1_000_000)
        if not signed and f < 0:
            raise ValueError("Negativer unsigned rational")
        out.extend((f.numerator, f.denominator))
    return tuple(out)


def export_image(path, image, color: ColorInfo, exposure=0., warmth=0., overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Datei existiert bereits: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}-{uuid.uuid4().hex}.tmp")
    try:
        suffix = path.suffix.lower()
        if suffix == ".dng":
            if not color.raw:
                raise ValueError("DNG-Export benötigt eine kompatible RAW-Serie")
            matrix = np.asarray(color.matrix, dtype=float)
            if matrix.shape != (3, 3) or abs(np.linalg.det(matrix)) < 1e-8:
                raise ValueError("Ungültige Kamerafarbmatrix")
            pixels = np.rint(np.clip(image, 0, 1) * 65535).astype(np.uint16)
            h, w = pixels.shape[:2]
            tags = [
                (50706, "B", 4, (1, 4, 0, 0), False),
                (50707, "B", 4, (1, 3, 0, 0), False),
                (50708, "s", 0, f"{color.make} {color.model}".strip(), False),
                (271, "s", 0, color.make or "Unknown", False),
                (272, "s", 0, color.model, False),
                (274, "H", 1, 1, False),
                (50714, "2I", 3, (0, 1, 0, 1, 0, 1), False),
                (50717, "I", 3, (65535, 65535, 65535), False),
                (50718, "2I", 2, (1, 1, 1, 1), False),
                (50719, "I", 2, (0, 0), False),
                (50720, "I", 2, (w, h), False),
                (50721, "2i", 9, rational(matrix, signed=True), False),
                (50728, "2I", 3, rational(color.neutral), False),
                (50778, "H", 1, color.illuminant, False),
                (50829, "I", 4, (0, 0, h, w), False),
                (50936, "s", 0, "STCKR camera matrix", False),
            ]
            # Main IFD is the full-resolution LinearRaw image; SubIFD is a preview.
            with tifffile.TiffWriter(tmp) as writer:
                writer.write(pixels, photometric=34892, planarconfig="contig", extrasamples=False,
                             subfiletype=0, subifds=1,
                             metadata=None, software="STCKR 0.1",
                             extratags=tags, compression=None, rowsperstrip=min(128, h))
                writer.write(thumbnail(image, color, 1024), photometric="rgb", subfiletype=1,
                             metadata=None)
        elif suffix in {".tif", ".tiff"}:
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            tifffile.imwrite(tmp, develop(image, color, exposure, warmth), photometric="rgb",
                             metadata=None, software="STCKR 0.1", iccprofile=profile)
        elif suffix in {".jpg", ".jpeg"}:
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            pixels = (develop(image, color, exposure, warmth) / 257).astype(np.uint8)
            Image.fromarray(pixels).save(tmp, format="JPEG", quality=96, subsampling=0, icc_profile=profile)
        else:
            raise ValueError("Exportformat: .dng, .tif oder .jpg")
        if color.raw and suffix in {".dng", ".tif", ".tiff", ".jpg", ".jpeg"}:
            tool = exiftool_path()
            if tool:
                import subprocess
                import sys
                tags = []
                for name, value in (("ISO", color.iso), ("ExposureTime", color.exposure), ("FNumber", color.aperture)):
                    if value > 0:
                        tags.append(f"-{name}={value}")
                if tags:
                    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    subprocess.run([tool, "-overwrite_original", "-n", *tags, str(tmp)],
                                   check=True, capture_output=True, timeout=60, creationflags=flags)
        # Never publish an incomplete file. A concurrent writer cannot be silently replaced.
        if overwrite:
            os.replace(tmp, path)
        else:
            os.link(tmp, path)
            tmp.unlink()
    finally:
        tmp.unlink(missing_ok=True)
