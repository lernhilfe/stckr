from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import os
import shutil
import time
import uuid
import cv2
import numpy as np

from .models import Settings, Result, check_cancel
from .imaging import decode, thumbnail
from .alignment import estimate_transform, valid_crop
from .fusion import fuse


def fingerprint(path, preview=False):
    path = Path(path).resolve()
    stat = path.stat()
    return hashlib.sha256(f"{path}|{stat.st_size}|{stat.st_mtime_ns}|{preview}|decode-v2".encode()).hexdigest()


def run_stack(sources, settings: Settings, cache_root, progress=lambda *a: None, cancel=None):
    settings.validate()
    if len(sources) < 2:
        raise ValueError("Bitte mindestens zwei Bilder auswählen")
    if len(set(map(str, map(Path, sources)))) != len(sources):
        raise ValueError("Doppelte Quellen im Stack")
    cv2.setNumThreads(min(4, os.cpu_count() or 1))
    start = time.monotonic()
    cache_root = Path(cache_root)
    decoded_root = cache_root / "decoded"
    decoded_root.mkdir(parents=True, exist_ok=True)
    job = cache_root / "results" / uuid.uuid4().hex[:12]
    job.mkdir(parents=True)
    decoded, colors = [], []
    shape = None
    try:
        for i, source in enumerate(sources):
            check_cancel(cancel)
            key = fingerprint(source, settings.preview)
            target = decoded_root / f"{key}.npy"
            info = target.with_suffix(".json")
            if not target.exists() or not info.exists():
                image, color = decode(source, settings.preview)
                needed = image.nbytes * (2 * len(sources) - i + 3)
                if shutil.disk_usage(cache_root).free < needed:
                    raise ValueError(f"Zu wenig Platz im Cache. Benötigt ungefähr {needed / 2**30:.1f} GB.")
                temp = target.with_suffix(".tmp.npy")
                np.save(temp, image)
                os.replace(temp, target)
                info.write_text(json.dumps(color.to_dict()), encoding="utf-8")
                del image
            from .models import ColorInfo
            color = ColorInfo(**json.loads(info.read_text(encoding="utf-8")))
            image = np.load(target, mmap_mode="r")
            if shape is None:
                shape = image.shape
                # Bounded streaming working set; reject too-small budgets before starting fusion.
                if np.prod(shape) * 4 * 12 > settings.memory_mb * 2**20:
                    raise ValueError("Bildgröße überschreitet das gewählte Speicherbudget")
            if image.shape != shape:
                raise ValueError(f"Abweichende Bildgröße: {Path(source).name}")
            if colors and not colors[0].compatible(color):
                raise ValueError("Unterschiedliche Kameras/Farbräume bitte als getrennte Serien stacken")
            decoded.append(str(target))
            colors.append(color)
            progress("RAW dekodieren / Import", .3 * (i + 1) / len(sources))
        pending_bytes = int(np.prod(shape)) * 4 * (len(sources) + 3)
        if shutil.disk_usage(cache_root).free < pending_bytes:
            raise ValueError(f"Zu wenig freier SSD-Speicher für die ausgerichteten Bilder: ca. {pending_bytes / 2**30:.1f} GB nötig.")
        h, w = shape[:2]
        ref = len(sources) // 2 if settings.reference < 0 else settings.reference
        if not 0 <= ref < len(sources):
            raise ValueError("Ungültiges Referenzbild")
        transforms = [np.eye(3) for _ in sources]
        order = list(range(ref + 1, len(sources))) + list(range(ref - 1, -1, -1))
        valid = np.ones((h, w), bool)
        if settings.align:
            for n, i in enumerate(order):
                check_cancel(cancel)
                neighbor = i - 1 if i > ref else i + 1
                try:
                    pair = estimate_transform(np.load(decoded[neighbor], mmap_mode="r"),
                                              np.load(decoded[i], mmap_mode="r"), settings.affine)
                except (ValueError, cv2.error) as error:
                    raise ValueError(f"Ausrichtung fehlgeschlagen: {Path(sources[i]).name}: {error}") from error
                transforms[i] = transforms[neighbor] @ pair
                mask = cv2.warpAffine(np.ones((h, w), np.uint8), transforms[i][:2], (w, h),
                                      flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
                # Erode interpolation support so no Lanczos samples contain invalid borders.
                mask = cv2.erode(mask, np.ones((9, 9), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
                valid &= mask.astype(bool)
                progress("Subpixel-Ausrichtung", .3 + .2 * (n + 1) / len(order))
        crop = valid_crop(valid) if settings.align else [0, 0, w, h]
        x0, y0, x1, y1 = crop
        aligned = []
        for i, path in enumerate(decoded):
            check_cancel(cancel)
            image = np.load(path, mmap_mode="r")
            shift = transforms[i].copy()
            shift[:2, 2] -= [x0, y0]
            out = cv2.warpAffine(image, shift[:2], (x1 - x0, y1 - y0),
                                 flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)
            target = job / f"source-{i:04d}.npy"
            np.save(target, out)
            aligned.append(str(target))
            progress("Bilder ausrichten", .5 + .1 * (i + 1) / len(decoded))
        image, source_map = fuse(aligned, settings,
                                 lambda phase, value: progress(phase, .6 + .38 * value), cancel,
                                 str(job / "result.npy"))
        np.save(job / "source-map.npy", source_map)
        from PIL import Image
        Image.fromarray(thumbnail(image, colors[ref])).save(job / "preview.jpg", quality=94)
        np.save(job / "original.npy", image)
        result = Result(job.name, str(job.resolve()), asdict(settings), list(map(str, sources)),
                        colors[ref].to_dict(), crop, [m.tolist() for m in transforms],
                        x1 - x0, y1 - y0, time.monotonic() - start, settings.preview)
        (job / "result.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        progress("Fertig", 1.)
        return result
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise


def worker(sources, settings, cache_root, queue, cancel):
    """Only paths and small messages cross the process boundary."""
    try:
        result = run_stack(sources, Settings(**settings), cache_root,
                           lambda phase, value: queue.put(("progress", phase, value)), cancel)
        queue.put(("result", result.to_dict()))
    except Exception as error:
        from .models import Cancelled
        queue.put(("cancelled" if isinstance(error, Cancelled) else "error", str(error)))
