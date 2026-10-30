"""Adjacent-frame registration; composed transforms, a single final resampling."""
import cv2
import numpy as np


def estimate_gray(image, limit=1600):
    h, w = image.shape[:2]
    scale = min(1., limit / max(h, w))
    if scale < 1:
        image = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(np.asarray(image, np.float32), cv2.COLOR_RGB2GRAY)
    lo, hi = np.percentile(gray, [1, 99])
    gray = np.clip((gray - lo) / max(float(hi - lo), 1e-6), 0, 1)
    return np.ascontiguousarray(gray), scale


def estimate_transform(reference, current, affine=False):
    """Return a current→reference 3×3 matrix in original pixel coordinates."""
    ref, scale = estimate_gray(reference)
    cur, other_scale = estimate_gray(current)
    if ref.shape != cur.shape or scale != other_scale:
        raise ValueError("Quellbilder müssen dieselbe Größe haben")
    detector = cv2.SIFT_create(nfeatures=6000, contrastThreshold=.015)
    kp0, d0 = detector.detectAndCompute((ref * 255).astype(np.uint8), None)
    kp1, d1 = detector.detectAndCompute((cur * 255).astype(np.uint8), None)
    forward = None
    if d0 is not None and d1 is not None and min(len(d0), len(d1)) >= 6:
        matches = cv2.BFMatcher().knnMatch(d1, d0, k=2)
        good = [m[0] for m in matches if len(m) == 2 and m[0].distance < .75 * m[1].distance]
        if len(good) >= 6:
            src = np.float32([kp1[m.queryIdx].pt for m in good])
            dst = np.float32([kp0[m.trainIdx].pt for m in good])
            estimator = cv2.estimateAffine2D if affine else cv2.estimateAffinePartial2D
            forward, inliers = estimator(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.,
                                        maxIters=4000, confidence=.999)
            if forward is not None and np.count_nonzero(inliers) < 6:
                forward = None
    if forward is None:
        shift, response = cv2.phaseCorrelate(ref, cur)
        if response < .03:
            raise ValueError("Zu wenige gemeinsame Details für eine zuverlässige Ausrichtung")
        forward = np.array([[1, 0, -shift[0]], [0, 1, -shift[1]]], np.float64)
    initial = np.vstack([forward, [0, 0, 1]])
    inverse = np.linalg.inv(initial)[:2].astype(np.float32)
    try:
        score, inverse = cv2.findTransformECC(
            ref, cur, inverse, cv2.MOTION_AFFINE,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 120, 1e-6), None, 5)
        if score < .3:
            raise ValueError("Ausrichtungskonfidenz zu gering")
        refined = np.linalg.inv(np.vstack([inverse, [0, 0, 1]]))
        if not affine:
            # Project affine refinement back onto a rotation + uniform scale.
            u, s, vt = np.linalg.svd(refined[:2, :2])
            rotation = u @ vt
            if np.linalg.det(rotation) <= 0:
                raise ValueError("Ungültige Spiegelung bei der Ausrichtung")
            linear = rotation * np.mean(s)
            center = np.array([ref.shape[1] / 2, ref.shape[0] / 2])
            refined[:2, 2] += (refined[:2, :2] - linear) @ center
            refined[:2, :2] = linear
        forward3 = refined
    except cv2.error:
        # RANSAC is a valid estimate when ECC cannot converge on defocus changes.
        forward3 = initial
    singular = np.linalg.svd(forward3[:2, :2], compute_uv=False)
    if not np.isfinite(forward3).all() or np.any(singular < .5) or np.any(singular > 2):
        raise ValueError("Unplausible Größenänderung; Referenz oder Bildauswahl ändern")
    to_small = np.diag([scale, scale, 1.])
    return np.linalg.inv(to_small) @ forward3 @ to_small


def valid_crop(mask):
    """Largest guaranteed-valid block rectangle; O(HW) downsampling, O(512²) search."""
    h, w = mask.shape
    step = max(1, int(np.ceil(max(h, w) / 512)))
    bh, bw = h // step, w // step
    blocks = mask[:bh * step, :bw * step].reshape(bh, step, bw, step).all(axis=(1, 3))
    heights = np.zeros(bw, int)
    best, rect = 0, (0, 0, 0, 0)
    for y, row in enumerate(blocks):
        heights = np.where(row, heights + 1, 0)
        stack = []
        for x in range(bw + 1):
            height = int(heights[x]) if x < bw else 0
            start = x
            while stack and stack[-1][1] > height:
                sx, sh = stack.pop()
                area = sh * (x - sx)
                if area > best:
                    best, rect = area, (sx * step, (y + 1 - sh) * step,
                                        x * step, (y + 1) * step)
                start = sx
            if not stack or stack[-1][1] < height:
                stack.append((start, height))
    if best * step * step < h * w * .1:
        raise ValueError("Weniger als 10 % gemeinsame Bildfläche nach der Ausrichtung")
    return list(rect)
