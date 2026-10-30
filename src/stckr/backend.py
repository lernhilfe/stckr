from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from queue import Empty, SimpleQueue
import multiprocessing as mp
import os
import uuid
import re
import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, QStandardPaths, QSettings
from PySide6.QtWidgets import QFileDialog

from .canvas import PhotoCanvas, ViewState
from .engine import worker
from .imaging import decode, thumbnail, EXTENSIONS
from .models import Settings, ColorInfo
from .retouch import Retoucher
from .export import export_image
from .project import save_project, load_project


def natural_key(path):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(path))]


class Backend(QObject):
    changed = Signal()
    imagesChanged = Signal()
    filesChanged = Signal()
    resultsChanged = Signal()
    errorRaised = Signal(str)
    noteRaised = Signal(str)

    def __init__(self):
        super().__init__()
        self._files, self._results = [], []
        self._selected, self._active_result = -1, -1
        self._busy, self._progress, self._phase = False, 0., "Bereit für deinen nächsten Stack"
        self._method, self._workspace = "C", "Stacken"
        self.result_image, self.source_image = None, None
        self.color_info = ColorInfo()
        self.retoucher = None
        self.view_state = ViewState()
        self.preferences = QSettings()
        cache_base = (os.environ.get("STCKR_CACHE_DIR") or self.preferences.value("cacheRoot", "")
                      or QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
        self.root = Path(cache_base) / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache = self.root / uuid.uuid4().hex[:12]
        self.cache.mkdir(exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.thumbnail_pool = ThreadPoolExecutor(max_workers=1)
        self.messages = SimpleQueue()
        self.process = None
        self.cancel_event = None
        self.ctx = mp.get_context("spawn")
        self.worker_queue = None
        self._load_token = 0
        self._brush_source = None
        self._last_dab = None
        PhotoCanvas.backend = self
        self.imagesChanged.connect(self.view_state.changed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(40)

    @Property("QVariantList", notify=filesChanged)
    def files(self):
        return self._files

    @Property("QVariantList", notify=resultsChanged)
    def results(self):
        return [{**r, "thumb": QUrl.fromLocalFile(str(Path(r["directory"]) / "preview.jpg")).toString(),
                 "label": f"Methode {r['settings']['method']}",
                 "detail": f"{r['width']} × {r['height']} · {r['elapsed']:.1f} s"} for r in self._results]

    @Property(int, notify=changed)
    def selected(self):
        return self._selected

    @Property(int, notify=changed)
    def activeResult(self):
        return self._active_result

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def canCancel(self):
        return self.process is not None and self.process.is_alive()

    @Property(float, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def phase(self):
        return self._phase

    @Property(str, notify=changed)
    def method(self):
        return self._method

    @method.setter
    def method(self, value):
        self._method = value
        self.changed.emit()

    @Property(str, notify=changed)
    def workspace(self):
        return self._workspace

    @workspace.setter
    def workspace(self, value):
        self._workspace = value
        self.changed.emit()

    @Property(QObject, constant=True)
    def view(self):
        return self.view_state

    @Property(bool, notify=changed)
    def hasImage(self):
        return self.source_image is not None or self.result_image is not None

    @Property(bool, notify=changed)
    def canDng(self):
        return self.color_info.raw and self._active_result >= 0 and not self._results[self._active_result]["preview"]

    @Property(str, notify=changed)
    def imageInfo(self):
        if self._active_result >= 0:
            r = self._results[self._active_result]
            prefix = "VORSCHAU · " if r["preview"] else ""
            return f"{prefix}{r['width']} × {r['height']} · {'Linear RAW' if self.color_info.raw else 'Linear RGB'} · 32-Bit-Verarbeitung"
        return "Quelle · Vorschau" if self.hasImage else "RAW rein. Schärfe bis ins Detail."

    @Property(str, notify=changed)
    def cameraInfo(self):
        return self.color_info.model if self.color_info.raw else "RGB · sRGB"

    def task(self, fn, callback, busy_task=False):
        def execute():
            try:
                self.messages.put(("callback", callback, fn()))
            except Exception as error:
                self.messages.put(("error", str(error), busy_task))
        self.pool.submit(execute)

    @Slot()
    def chooseCacheFolder(self):
        if self._busy:
            return
        directory = QFileDialog.getExistingDirectory(None, "SSD-Ordner für neue Stacks wählen", str(self.root.parent))
        if directory:
            try:
                root = Path(directory) / "sessions"
                cache = root / uuid.uuid4().hex[:12]
                cache.mkdir(parents=True)
                self.root, self.cache = root, cache
                self.preferences.setValue("cacheRoot", directory)
                self.noteRaised.emit("Neue Stacks werden auf der gewählten SSD gespeichert. Bestehende Ergebnisse bleiben erhalten.")
            except OSError as error:
                self.errorRaised.emit(str(error))

    @Slot()
    def chooseFiles(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Aufnahmen hinzufügen", "",
                                               "Fotos (*.cr3 *.CR3 *.cr2 *.CR2 *.nef *.arw *.dng *.tif *.tiff *.png *.jpg *.jpeg);;Alle Dateien (*)")
        self.add_paths(files)

    @Slot("QVariantList")
    def dropFiles(self, urls):
        self.add_paths([QUrl(url).toLocalFile() for url in urls])

    def add_paths(self, paths):
        if self._busy:
            return
        expanded = []
        for p in paths:
            path = Path(p)
            expanded.extend(path.iterdir() if path.is_dir() else [path])
        known = {f["path"] for f in self._files}
        for path in sorted(expanded, key=natural_key):
            if path.suffix.lower() not in EXTENSIONS or not path.is_file():
                continue
            path = str(path.resolve())
            if path in known:
                continue
            known.add(path)
            self._files.append({"path": path, "name": Path(path).name, "enabled": True, "thumb": "",
                                "format": Path(path).suffix[1:].upper(), "missing": False})
        if self._files and self._selected < 0:
            self.selectSource(0)
        for item in self._files:
            if not item["thumb"]:
                self.thumbnail_pool.submit(self.create_thumbnail, item["path"])
        self.filesChanged.emit()
        self.changed.emit()

    def create_thumbnail(self, path):
        try:
            import hashlib
            from io import BytesIO
            import rawpy
            from PIL import ImageOps
            from .imaging import RAW_EXTENSIONS
            target = self.cache / ("thumb-" + hashlib.sha256(path.encode()).hexdigest()[:16] + ".jpg")
            if not target.exists():
                if Path(path).suffix.lower() in RAW_EXTENSIONS:
                    with rawpy.imread(path) as raw:
                        thumb = raw.extract_thumb()
                        im = Image.open(BytesIO(thumb.data)) if thumb.format == rawpy.ThumbFormat.JPEG else Image.fromarray(thumb.data)
                        im = ImageOps.exif_transpose(im).convert("RGB")
                elif Path(path).suffix.lower() in {".tif", ".tiff"}:
                    image, color = decode(path, preview=True)
                    im = Image.fromarray(thumbnail(image, color, 240))
                else:
                    with Image.open(path) as source:
                        im = ImageOps.exif_transpose(source).convert("RGB")
                im.thumbnail((240, 180))
                im.save(target, quality=85)
            def ready(_):
                for item in self._files:
                    if item["path"] == path:
                        item["thumb"] = QUrl.fromLocalFile(str(target)).toString()
                self.filesChanged.emit()
            self.messages.put(("callback", ready, None))
        except Exception:
            pass  # Actual decode reports errors when the source is selected/rendered.

    @Slot(int)
    def selectSource(self, index):
        if not 0 <= index < len(self._files):
            return
        self._selected = index
        self._load_token += 1
        token = self._load_token
        path = self._files[index]["path"]
        self._brush_source = None
        if self._active_result >= 0:
            r = self._results[self._active_result]
            if path in r["sources"]:
                i = r["sources"].index(path)
                self.source_image = np.load(Path(r["directory"]) / f"source-{i:04d}.npy", mmap_mode="r")
                self.imagesChanged.emit()
                self.changed.emit()
                return
            self.noteRaised.emit("Diese Quelle gehört nicht zum gewählten Ergebnis. Zum Import zurückkehren, um sie anzuzeigen.")
            return

        def load():
            image, color = decode(path, preview=True)
            thumb_path = self.cache / f"thumb-{index}.jpg"
            Image.fromarray(thumbnail(image, color, 240)).save(thumb_path)
            return image, color, str(thumb_path)

        def loaded(value):
            if token != self._load_token or self._active_result >= 0:
                return
            image, color, thumb_path = value
            self.source_image, self.result_image, self.color_info = image, image, color
            for item in self._files:
                if item["path"] == path:
                    item["thumb"] = QUrl.fromLocalFile(thumb_path).toString()
            self.filesChanged.emit()
            self.imagesChanged.emit()
            self.changed.emit()
        self.task(load, loaded)
        self.changed.emit()

    @Slot(int)
    def toggleSource(self, index):
        if not self._busy:
            self._files[index]["enabled"] = not self._files[index]["enabled"]
            self.filesChanged.emit()
            self.changed.emit()

    @Slot(int, int)
    def moveSource(self, index, delta):
        target = index + delta
        if not self._busy and 0 <= target < len(self._files):
            self._files[index], self._files[target] = self._files[target], self._files[index]
            self._selected = target
            self.filesChanged.emit()
            self.changed.emit()

    @Slot()
    def reverseSources(self):
        if not self._busy:
            self._files.reverse()
            self._selected = len(self._files) - 1 - self._selected
            self.filesChanged.emit()
            self.changed.emit()

    @Slot()
    def clearSources(self):
        if not self._busy:
            self._files, self._selected, self._active_result = [], -1, -1
            self.source_image = self.result_image = self.retoucher = None
            self._load_token += 1
            self.view_state.fit()
            self.filesChanged.emit()
            self.resultsChanged.emit()
            self.changed.emit()

    @Slot(int, float, int, bool, bool, bool, bool)
    def render(self, radius, smoothing, levels, align, affine, selected_ref, preview):
        if self._busy:
            return
        sources = [f["path"] for f in self._files if f["enabled"]]
        reference = -1
        if selected_ref and 0 <= self._selected < len(self._files):
            current = self._files[self._selected]["path"]
            if current not in sources:
                self.errorRaised.emit("Das Referenzbild muss aktiviert sein.")
                return
            reference = sources.index(current)
        if len(sources) < 2:
            self.errorRaised.emit("Bitte mindestens zwei Aufnahmen aktivieren.")
            return
        settings = Settings(self._method, radius, smoothing, levels, align, affine, reference, preview)
        self.worker_queue = self.ctx.Queue()
        self.cancel_event = self.ctx.Event()
        self.process = self.ctx.Process(target=worker,
                                        args=(sources, asdict(settings), str(self.cache), self.worker_queue,
                                              self.cancel_event))
        self._busy, self._progress, self._phase = True, 0., "Stack wird vorbereitet …"
        self.process.start()
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self.cancel_event:
            self.cancel_event.set()
            self._phase = "Abbruch wird ausgeführt …"
            self.changed.emit()

    @Slot(int)
    def selectResult(self, index):
        if not 0 <= index < len(self._results):
            return
        if self.retoucher:
            self.retoucher.end()
        self._active_result = index
        self._load_token += 1
        r = self._results[index]
        self.retoucher = Retoucher(r["directory"])
        self.result_image = self.retoucher.image
        self.color_info = ColorInfo(**r["color"])
        self._brush_source = None
        selected_path = self._files[self._selected]["path"] if self._selected >= 0 else ""
        source_index = r["sources"].index(selected_path) if selected_path in r["sources"] else 0
        self.source_image = np.load(Path(r["directory"]) / f"source-{source_index:04d}.npy", mmap_mode="r")
        self.imagesChanged.emit()
        self.changed.emit()

    @Slot(int)
    def useResultAsSource(self, index):
        if self._active_result < 0 or not 0 <= index < len(self._results):
            return
        current, candidate = self._results[self._active_result], self._results[index]
        if (current["sources"] != candidate["sources"] or current["crop"] != candidate["crop"]
                or not np.allclose(current["transforms"], candidate["transforms"])):
            self.errorRaised.emit("Nur Ergebnisse mit denselben Quellen und derselben Ausrichtung können als Pinselquelle dienen.")
            return
        if index == self._active_result:
            self.errorRaised.emit("Bitte ein anderes Ergebnis als Quelle wählen.")
            return
        self._brush_source = np.load(Path(candidate["directory"]) / "result.npy", mmap_mode="r")
        self.source_image = self._brush_source
        self.imagesChanged.emit()
        self.noteRaised.emit("Pinselquelle: Methode " + candidate["settings"]["method"])

    def paint_dab(self, x, y, radius, hardness, opacity, erase):
        if self._busy or not self.retoucher:
            return
        source = self.retoucher.original if erase else self.source_image
        if source is None:
            return
        if self._last_dab:
            px, py = self._last_dab
            count = max(1, int(np.hypot(x - px, y - py) / max(1, radius / 4)))
        else:
            px, py, count = x, y, 1
        for t in np.linspace(0, 1, count + 1)[1:]:
            self.retoucher.dab(source, px + (x - px) * t, py + (y - py) * t, radius, hardness, opacity)
        self._last_dab = (x, y)
        self.imagesChanged.emit()

    @Slot()
    def endStroke(self):
        if self.retoucher:
            self.retoucher.end()
        self._last_dab = None

    @Slot()
    def undo(self):
        if self.retoucher and not self._busy:
            self.retoucher.undo()
            self.imagesChanged.emit()

    @Slot()
    def redo(self):
        if self.retoucher and not self._busy:
            self.retoucher.redo()
            self.imagesChanged.emit()

    @Slot(float, float)
    def displaySettings(self, exposure, warmth):
        self.view_state.exposure, self.view_state.warmth = exposure, warmth
        self.imagesChanged.emit()

    @Slot(str)
    def export(self, kind):
        if self._busy or self._active_result < 0:
            return
        result = self._results[self._active_result]
        if result["preview"]:
            self.errorRaised.emit("Für den Export bitte zuerst einen Stack in voller Auflösung berechnen.")
            return
        path, _ = QFileDialog.getSaveFileName(None, "Ergebnis exportieren", f"STCKR-{result['settings']['method']}.{kind}",
                                             f"{kind.upper()} (*.{kind})")
        if not path:
            return
        if Path(path).suffix.lower() != "." + kind:
            path += "." + kind
        self.endStroke()
        self._busy, self._phase = True, "Export wird geschrieben …"
        self.changed.emit()
        self.task(lambda: export_image(path, self.result_image, self.color_info,
                                        self.view_state.exposure, self.view_state.warmth, overwrite=True),
                  lambda _: self.finish_task("Export gespeichert"), busy_task=True)

    def finish_task(self, message):
        self._busy, self._phase = False, message
        self.changed.emit()
        self.noteRaised.emit(message)

    @Slot()
    def saveProject(self):
        if self._busy or not self._files:
            return
        path, _ = QFileDialog.getSaveFileName(None, "Projekt unter neuem Namen speichern", "Mein Stack.stckr", "STCKR-Projekt (*.stckr)")
        if path:
            self.endStroke()
            self._busy, self._phase = True, "Projekt und Retusche werden gespeichert …"
            self.changed.emit()
            self.task(lambda: save_project(path, self._files, self._results),
                      lambda _: self.finish_task("Projekt gespeichert"), busy_task=True)

    @Slot()
    def openProject(self):
        if self._busy:
            return
        path, _ = QFileDialog.getOpenFileName(None, "Projekt öffnen", "", "Projektdatei (project.json)")
        if not path:
            return
        try:
            data = load_project(path)
            self._files, self._results = data["sources"], data["results"]
            for source in self._files:
                source["missing"] = not Path(source["path"]).exists()
            self._selected = 0 if self._files else -1
            self._active_result = -1
            self.source_image = self.result_image = self.retoucher = None
            if self._results:
                self.selectResult(len(self._results) - 1)
            elif self._files:
                self.selectSource(0)
            self.view_state.fit()
            self.filesChanged.emit()
            self.resultsChanged.emit()
            self.changed.emit()
        except Exception as error:
            self.errorRaised.emit(str(error))

    @Slot()
    def relinkSource(self):
        if self._selected < 0 or self._busy:
            return
        old = self._files[self._selected]["path"]
        new, _ = QFileDialog.getOpenFileName(None, "Original neu zuordnen: " + Path(old).name)
        if new:
            self._files[self._selected].update(path=str(Path(new).resolve()), name=Path(new).name, missing=False)
            self.filesChanged.emit()
            # Existing renders keep provenance; only future stacks use the replacement.
            self.changed.emit()
            self.selectSource(self._selected)

    def poll(self):
        while True:
            try:
                message = self.messages.get_nowait()
            except Empty:
                break
            if message[0] == "callback":
                try:
                    message[1](message[2])
                except Exception as error:
                    self._busy = False
                    self.errorRaised.emit(str(error))
                    self.changed.emit()
            else:
                if message[2]:
                    self._busy = False
                self.errorRaised.emit(message[1])
                self.changed.emit()
        if self.worker_queue is not None:
            while True:
                try:
                    message = self.worker_queue.get_nowait()
                except Empty:
                    break
                if message[0] == "progress":
                    _, self._phase, self._progress = message
                elif message[0] == "result":
                    self._results.append(message[1])
                    self.resultsChanged.emit()
                    self._busy, self._phase, self._progress = False, "Stack fertig", 1.
                    self.selectResult(len(self._results) - 1)
                else:
                    self._busy, self._phase = False, message[1]
                    if message[0] == "error":
                        self.errorRaised.emit(message[1])
                self.changed.emit()
        if self.process and not self.process.is_alive():
            self.process.join()
            # Let the multiprocessing queue feeder deliver its final message before detecting a crash.
            if self._busy and self.process.exitcode != 0:
                self._busy = False
                self.errorRaised.emit(f"Verarbeitungsprozess beendet (Code {self.process.exitcode})")
                self.changed.emit()
            self.process = None

    def shutdown(self):
        self.endStroke()
        if self.process and self.process.is_alive():
            self.cancel_event.set()
            self.process.join(2)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join()
        self.thumbnail_pool.shutdown(wait=True, cancel_futures=True)
        self.pool.shutdown(wait=True)
