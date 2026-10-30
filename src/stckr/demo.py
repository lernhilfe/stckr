"""Deterministic, original synthetic focus series (no external image rights)."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def create_demo(directory, width=1200, height=800):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(821)
    canvas = np.full((height, width, 3), (30, 45, 47), np.uint8)
    for _ in range(350):
        center = (int(rng.integers(10, width - 10)), int(rng.integers(10, height - 10)))
        radius = int(rng.integers(3, 35))
        color = tuple(int(v) for v in rng.integers(60, 240, 3))
        cv2.circle(canvas, center, radius, color, 1, cv2.LINE_AA)
    cv2.putText(canvas, "STCKR", (width // 8, height // 2), cv2.FONT_HERSHEY_DUPLEX,
                width / 260, (190, 232, 210), 3, cv2.LINE_AA)
    cv2.putText(canvas, "EVERY FOCUS PLANE", (width // 8, height // 2 + height // 9),
                cv2.FONT_HERSHEY_SIMPLEX, width / 1250, (100, 180, 160), 1, cv2.LINE_AA)
    focus_depth = np.linspace(0, 5, width)[None, :, None]
    for i in range(6):
        output = np.zeros(canvas.shape, np.float32)
        for depth in range(6):
            blurred = cv2.GaussianBlur(canvas, (0, 0), max(.01, abs(i - depth) * 2.4))
            weight = np.clip(1 - np.abs(focus_depth - depth), 0, 1)
            output += blurred * weight
        Image.fromarray(np.rint(output).astype(np.uint8)).save(directory / f"focus-{i + 1:02d}.png")
    Image.fromarray(canvas).save(directory / "ground-truth.png")
