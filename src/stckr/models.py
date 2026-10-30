from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable
import math


class Cancelled(Exception):
    pass


@dataclass
class Settings:
    method: str = "C"
    radius: int = 5
    smoothing: float = 1.2
    levels: int = 7
    align: bool = True
    affine: bool = False
    reference: int = -1
    preview: bool = False
    memory_mb: int = 4096

    def validate(self):
        if self.method not in ("A", "B", "C"):
            raise ValueError("Unbekanntes Stacking-Verfahren")
        if not 1 <= self.radius <= 50 or not 2 <= self.levels <= 10:
            raise ValueError("Radius oder Pyramidenstufen außerhalb des gültigen Bereichs")
        if not math.isfinite(self.smoothing) or not 0 <= self.smoothing <= 20:
            raise ValueError("Ungültige Glättung")
        if not 256 <= self.memory_mb <= 65536:
            raise ValueError("Ungültiges Speicherbudget")


@dataclass
class ColorInfo:
    raw: bool = False
    make: str = ""
    model: str = ""
    # DNG XYZ-to-camera matrix (LibRaw cam_xyz), not its inverse.
    matrix: list = field(default_factory=list)
    neutral: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    illuminant: int = 21  # D65, LibRaw's daylight calibration
    iso: int = 0
    exposure: float = 0.0
    aperture: float = 0.0

    def compatible(self, other: ColorInfo) -> bool:
        import numpy as np
        return (self.raw == other.raw and (not self.raw or (
            self.make == other.make and self.model == other.model
            and np.allclose(self.matrix, other.matrix, atol=1e-5))))

    def to_dict(self):
        return asdict(self)


@dataclass
class Result:
    id: str
    directory: str
    settings: dict
    sources: list[str]
    color: dict
    crop: list[int]
    transforms: list
    width: int
    height: int
    elapsed: float
    preview: bool = False

    @property
    def image_path(self):
        return str(Path(self.directory) / "result.npy")

    def to_dict(self):
        return asdict(self)


Progress = Callable[[str, float], None]


def check_cancel(cancel=None):
    if cancel is not None and cancel.is_set():
        raise Cancelled("Verarbeitung abgebrochen")
