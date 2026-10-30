"""File decoding, native camera colour, and display-only development."""
from __future__ import annotations

from pathlib import Path
from io import BytesIO
import json
import os
import shutil
import subprocess
import sys
import numpy as np
import cv2
os.environ.setdefault("OMP_NUM_THREADS", "4")
import rawpy
import tifffile
from PIL import Image, ImageCms, ImageOps

from .models import ColorInfo

RAW_EXTENSIONS = {".cr3", ".cr2", ".nef", ".arw", ".orf", ".rw2", ".raf", ".dng", ".pef"}
EXTENSIONS = RAW_EXTENSIONS | {".tif", ".tiff", ".png", ".jpg", ".jpeg"}


def exiftool_path():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[2]))
    candidates = [os.environ.get("STCKR_EXIFTOOL", ""),
                  str(root / "vendor" / "bin" / "exiftool.exe"), str(root / "vendor" / "bin" / "exiftool"), shutil.which("exiftool") or ""]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def metadata(path):
    tool = exiftool_path()
    if not tool:
        return {}
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    response = subprocess.run([tool, "-j", "-n", "-Make", "-Model", "-ISO", "-ExposureTime",
                               "-FNumber", str(Path(path).resolve())], capture_output=True,
                              timeout=30, creationflags=flags, check=True)
    return json.loads(response.stdout)[0]


def srgb_to_linear(a):
    return np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(a):
    a = np.maximum(a, 0)
    return np.where(a <= .0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - .055)


def decode(path: str, preview=False):
    path = Path(path)
    if path.suffix.lower() in RAW_EXTENSIONS:
        with rawpy.imread(str(path)) as raw:
            # Unity WB is essential: use_camera_wb=False alone applies daylight WB.
            rgb = raw.postprocess(output_color=rawpy.ColorSpace.raw, output_bps=16,
                                  gamma=(1, 1), user_wb=[1, 1, 1, 1],
                                  use_camera_wb=False, use_auto_wb=False,
                                  no_auto_bright=True, adjust_maximum_thr=0,
                                  demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                                  half_size=preview)
            matrix = raw.rgb_xyz_matrix[:3, :].astype(float)
            dng_tags = {}
            if path.suffix.lower() == ".dng":
                with tifffile.TiffFile(path) as tf:
                    dng_tags = {t.code: t.value for t in tf.pages[0].tags.values()}
                if 50721 in dng_tags:
                    fractions = np.asarray(dng_tags[50721], dtype=float).reshape(-1, 2)
                    matrix = (fractions[:, 0] / fractions[:, 1]).reshape(3, 3)
            if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-8:
                raise ValueError(f"Keine gültige Kamerafarbmatrix: {path.name}")
            wb = np.asarray(raw.camera_whitebalance[:3], dtype=float)
            if np.any(wb <= 0) or not np.isfinite(wb).all():
                wb = np.asarray(raw.daylight_whitebalance[:3], dtype=float)
            neutral = 1 / np.maximum(wb, 1e-8)
            neutral /= neutral[1]
            if 50728 in dng_tags:
                fractions = np.asarray(dng_tags[50728], dtype=float).reshape(-1, 2)
                neutral = fractions[:, 0] / fractions[:, 1]
                neutral /= neutral[1]
            tags = metadata(path)
            if dng_tags:
                tags.setdefault("Make", dng_tags.get(271, ""))
                tags.setdefault("Model", dng_tags.get(272, ""))
            if not tags:
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        exif = Image.open(BytesIO(thumb.data)).getexif()
                        tags = {"Make": exif.get(271, ""), "Model": exif.get(272, "")}
                except (rawpy.LibRawError, OSError):
                    pass
            if not tags.get("Model"):
                # Do not invent a camera identity or an Adobe camera profile.
                tags["Model"] = "LibRaw " + str(matrix.round(5).tolist())
            color = ColorInfo(True, tags.get("Make", ""), tags["Model"], matrix.tolist(),
                              neutral.tolist(), iso=int(tags.get("ISO", 0)),
                              exposure=float(tags.get("ExposureTime", 0)),
                              aperture=float(tags.get("FNumber", 0)))
            image = rgb.astype(np.float32) / 65535
    else:
        if path.suffix.lower() in {".tif", ".tiff"}:
            with tifffile.TiffFile(path) as tf:
                page = tf.pages[0]
                image = page.asarray()
                # TIFF with ICC other than sRGB is rejected rather than silently misinterpreted.
                profile = page.tags.get(34675)
                if profile:
                    p = ImageCms.ImageCmsProfile(BytesIO(profile.value))
                    if "srgb" not in ImageCms.getProfileDescription(p).lower():
                        raise ValueError("TIFF bitte mit sRGB-Profil importieren; andere TIFF-Profile folgen später.")
                orientation = int(page.tags[274].value) if 274 in page.tags else 1
                if orientation != 1:
                    # Preserve 16-bit precision while applying EXIF orientation.
                    ops = {2: lambda a: a[:, ::-1], 3: lambda a: a[::-1, ::-1],
                           4: lambda a: a[::-1], 5: lambda a: a.swapaxes(0, 1),
                           6: lambda a: np.rot90(a, -1), 7: lambda a: a.swapaxes(0, 1)[::-1, ::-1],
                           8: lambda a: np.rot90(a, 1)}
                    image = ops[orientation](image)
        else:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                icc = im.info.get("icc_profile")
                if icc:
                    im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(BytesIO(icc)),
                                                  ImageCms.createProfile("sRGB"), outputMode="RGB")
                image = np.array(im.convert("RGB"))
        if image.ndim == 2:
            image = np.repeat(image[..., None], 3, axis=2)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Bitte RGB-Bilder ohne Alphakanal verwenden")
        if image.dtype.kind not in "uf" or image.dtype.itemsize > 4:
            raise ValueError("Nicht unterstützter Bilddatentyp")
        if image.dtype.kind == "u":
            image = image.astype(np.float32) / np.iinfo(image.dtype).max
        image = srgb_to_linear(image)
        color = ColorInfo()
    if preview and max(image.shape[:2]) > 1600:
        scale = 1600 / max(image.shape[:2])
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if not np.isfinite(image).all() or min(image.shape[:2]) < 16:
        raise ValueError(f"Ungültiges Bild: {path.name}")
    return np.ascontiguousarray(image, dtype=np.float32), color


XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -.4985314],
                        [-.9692660, 1.8760108, .0415560],
                        [.0556434, -.2040259, 1.0572252]], np.float32)


def develop(image, color: ColorInfo, exposure=0., warmth=0.):
    a = np.asarray(image, dtype=np.float32)
    if color.raw:
        # Invert camera matrix only for display, never for the stored RAW stack.
        matrix = np.asarray(color.matrix, dtype=np.float32)
        gains = 1 / np.asarray(color.neutral, dtype=np.float32)
        # Normalize for the calibrated neutral so gray maps to D65.
        daylight = matrix @ np.array([.95047, 1, 1.08883], np.float32)
        transform = XYZ_TO_SRGB @ np.linalg.inv(matrix) @ np.diag(daylight * gains)
        a = cv2.transform(a, transform)
    a = a * (2. ** exposure) * np.array([2. ** warmth, 1., 2. ** -warmth], np.float32)
    return np.rint(np.clip(linear_to_srgb(a), 0, 1) * 65535).astype(np.uint16)


def thumbnail(image, color, limit=1600, exposure=0., warmth=0.):
    h, w = image.shape[:2]
    if max(h, w) > limit:
        image = cv2.resize(image, (round(w * limit / max(h, w)), round(h * limit / max(h, w))),
                           interpolation=cv2.INTER_AREA)
    return (develop(image, color, exposure, warmth) / 257).astype(np.uint8)
