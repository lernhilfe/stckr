"""Streaming fusion in Float32. No full N×H×W stack or 8-bit intermediate."""
import cv2
import numpy as np

from .models import check_cancel


def luminance(image):
    # Green-heavy contrast proxy is stable in both camera RGB and linear sRGB.
    return cv2.transform(image, np.array([[.25, .5, .25]], np.float32))


def focus_measure(image, radius):
    gray = luminance(image)
    # Local gradient energy: noise floor suppression without changing source pixels.
    smooth = cv2.GaussianBlur(gray, (0, 0), .6)
    dx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    energy = dx * dx + dy * dy
    return cv2.boxFilter(energy, -1, (2 * radius + 1,) * 2, normalize=True)


def fuse(paths, settings, progress=lambda *a: None, cancel=None, output_path=None):
    # Tracebacks retain local arrays after an exception. Windows cannot unlink an
    # open mapping, so close live mappings explicitly before the engine removes a job.
    # Weak references avoid pinning every source frame in memory during long stacks.
    import weakref
    references = []
    def mapped(path, output_shape=None):
        array = (np.load(path, mmap_mode="r") if output_shape is None else
                 np.lib.format.open_memmap(path, mode="w+", dtype=np.float32, shape=output_shape))
        references.append(weakref.ref(array))
        return array
    try:
        return _fuse(paths, settings, progress, cancel, output_path, mapped)
    except BaseException:
        for reference in references:
            array = reference()
            if array is not None and getattr(array, "_mmap", None) is not None:
                array._mmap.close()
        raise


def _fuse(paths, settings, progress, cancel, output_path, mapped):
    """paths are linear RGB .npy files; returns RGB and a source-index map."""
    first = mapped(paths[0])
    h, w = first.shape[:2]
    count = len(paths)
    output = (mapped(output_path, first.shape)
              if output_path else np.empty(first.shape, np.float32))
    winner = np.zeros((h, w), np.uint16 if count < 65536 else np.uint32)
    best = np.full((h, w), -1., np.float32)
    sigma = settings.smoothing
    if settings.method in ("A", "B"):
        if settings.method == "A":
            output[:] = 0
            total = np.zeros((h, w), np.float32)
        for i, path in enumerate(paths):
            check_cancel(cancel)
            image = mapped(path)
            score = focus_measure(image, settings.radius)
            selected = score > best
            best[selected], winner[selected] = score[selected], i
            if settings.method == "A":
                if sigma > 0:
                    score = cv2.GaussianBlur(score, (0, 0), sigma)
                # Sharper weighting than a plain average. Tiny equal weights avoid division by zero.
                weight = score * score + 1e-16
                for y in range(0, h, 256):
                    output[y:y + 256] += image[y:y + 256] * weight[y:y + 256, :, None]
                total += weight
            progress("Fusion", (i + 1) / (count + (1 if settings.method == "B" else 0)))
        if settings.method == "A":
            for y in range(0, h, 256):
                output[y:y + 256] /= total[y:y + 256, :, None]
        else:
            depth = cv2.medianBlur(winner.astype(np.float32), 3)
            if sigma > 0:
                # Joint bilateral filtering prevents depth averaging across visible object edges.
                guide = luminance(mapped(paths[count // 2]))
                depth = guided_depth(guide, depth, settings.radius, sigma)
            depth = np.clip(np.rint(depth), 0, count - 1).astype(winner.dtype)
            for i, path in enumerate(paths):
                check_cancel(cancel)
                image = mapped(path)
                for y in range(0, h, 256):
                    selected = depth[y:y + 256] == i
                    output[y:y + 256][selected] = image[y:y + 256][selected]
            winner = depth
    else:
        levels = min(settings.levels, max(2, int(np.log2(min(h, w))) - 2))
        bands, energies = [], []
        for i, path in enumerate(paths):
            check_cancel(cancel)
            image = mapped(path)
            gauss = [np.asarray(image)]
            for _ in range(levels - 1):
                gauss.append(cv2.pyrDown(gauss[-1]))
            score = focus_measure(image, settings.radius)
            selected = score > best
            best[selected], winner[selected] = score[selected], i
            for level in range(levels):
                check_cancel(cancel)
                if level == levels - 1:
                    if i == 0:
                        bands.append(gauss[level].copy())
                    else:
                        # Stable low-frequency average, invariant to source ordering.
                        bands[level] += (gauss[level] - bands[level]) / (i + 1)
                    continue
                band = gauss[level] - cv2.pyrUp(gauss[level + 1], dstsize=gauss[level].shape[1::-1])
                energy = np.abs(luminance(band))
                if sigma > 0:
                    energy = cv2.GaussianBlur(energy, (0, 0), sigma)
                if i == 0:
                    bands.append(band.copy())
                    energies.append(energy)
                else:
                    win = energy > energies[level]
                    bands[level][win] = band[win]
                    energies[level][win] = energy[win]
            del gauss
            progress("Pyramidenfusion", (i + 1) / count)
        rebuilt = bands[-1]
        for level in range(levels - 2, -1, -1):
            check_cancel(cancel)
            rebuilt = cv2.pyrUp(rebuilt, dstsize=bands[level].shape[1::-1]) + bands[level]
        output[:] = rebuilt
    check_cancel(cancel)
    if hasattr(output, "flush"):
        output.flush()
    return output, winner


def guided_depth(guide, depth, radius, sigma):
    """Guided filter with a linear local model; no opencv-contrib dependency."""
    k = 2 * max(1, round(radius * sigma)) + 1
    def box(a):
        return cv2.boxFilter(a, -1, (k, k), normalize=True)
    mean_g, mean_d = box(guide), box(depth)
    variance = np.maximum(box(guide * guide) - mean_g * mean_g, 0)
    covariance = box(guide * depth) - mean_g * mean_d
    a = covariance / (variance + 1e-5)
    b = mean_d - a * mean_g
    return box(a) * guide + box(b)
