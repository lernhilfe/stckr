"""Disk-backed, reversible linear-data brush strokes."""
from pathlib import Path
import json
import os
import uuid
import numpy as np


class Retoucher:
    def __init__(self, directory):
        self.root = Path(directory)
        self.image = np.load(self.root / "result.npy", mmap_mode="r+")
        self.original = np.load(self.root / "original.npy", mmap_mode="r")
        self.history = self.root / "history"
        self.history.mkdir(exist_ok=True)
        self.journal = self.history / "journal.json"
        state = json.loads(self.journal.read_text()) if self.journal.exists() else {"strokes": [], "cursor": 0}
        self.strokes, self.cursor = state["strokes"], state["cursor"]
        self.handle = None
        self.current = None

    def begin(self):
        if self.handle:
            return
        self.current = uuid.uuid4().hex + ".bin"
        self.handle = (self.history / self.current).open("wb")
        self.offsets = []

    def dab(self, source, x, y, radius, hardness, opacity):
        if self.handle is None:
            self.begin()
        h, w = self.image.shape[:2]
        r = max(1., float(radius))
        x0, y0, x1, y1 = max(0, int(x - r)), max(0, int(y - r)), min(w, int(x + r) + 1), min(h, int(y + r) + 1)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        d = np.sqrt((xx - x)**2 + (yy - y)**2) / r
        alpha = np.clip((1 - d) / max(1e-4, 1 - hardness), 0, 1) * opacity
        before = self.image[y0:y1, x0:x1].copy()
        after = before * (1 - alpha[..., None]) + source[y0:y1, x0:x1] * alpha[..., None]
        self.offsets.append(self.handle.tell())
        np.save(self.handle, np.array([x0, y0, x1, y1]))
        np.save(self.handle, before)
        np.save(self.handle, after)
        self.image[y0:y1, x0:x1] = after

    def end(self):
        if not self.handle:
            return
        self.handle.close()
        (self.history / (self.current + ".json")).write_text(json.dumps(self.offsets))
        self.handle = None
        self.strokes = self.strokes[:self.cursor] + [self.current]
        self.cursor += 1
        self.image.flush()
        self._save()

    def _save(self):
        temp = self.journal.with_suffix(".tmp")
        temp.write_text(json.dumps({"strokes": self.strokes, "cursor": self.cursor}))
        os.replace(temp, self.journal)

    def _read(self, name, reverse=False):
        index = self.history / (name + ".json")
        with (self.history / name).open("rb") as handle:
            if index.exists():
                offsets = json.loads(index.read_text())
            else:
                # Compatibility with early journals; only one patch is resident at a time.
                offsets = []
                while handle.tell() < os.fstat(handle.fileno()).st_size:
                    offsets.append(handle.tell())
                    for _ in range(3):
                        array = np.load(handle)
                        del array
            for offset in reversed(offsets) if reverse else offsets:
                handle.seek(offset)
                yield np.load(handle), np.load(handle), np.load(handle)

    def undo(self):
        self.end()
        if self.cursor:
            for (x0, y0, x1, y1), before, _ in self._read(self.strokes[self.cursor - 1], reverse=True):
                self.image[y0:y1, x0:x1] = before
            self.cursor -= 1
            self.image.flush()
            self._save()

    def redo(self):
        if self.cursor < len(self.strokes):
            for (x0, y0, x1, y1), _, after in self._read(self.strokes[self.cursor]):
                self.image[y0:y1, x0:x1] = after
            self.cursor += 1
            self.image.flush()
            self._save()
