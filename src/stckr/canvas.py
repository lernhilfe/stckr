import math
import cv2
from PySide6.QtCore import Property, Signal, Slot, QObject, QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtQuick import QQuickPaintedItem

from .imaging import thumbnail


class ViewState(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.scale = 0.
        self.cx = .5
        self.cy = .5
        self.exposure = 0.
        self.warmth = 0.

    @Slot()
    def fit(self):
        self.scale, self.cx, self.cy = 0., .5, .5
        self.changed.emit()

    @Slot()
    def actual(self):
        self.scale = 1.
        self.changed.emit()


class PhotoCanvas(QQuickPaintedItem):
    imageChanged = Signal()
    viewChanged = Signal()
    backend = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = False
        self._view = None
        self.setAntialiasing(True)

    @Property(bool, notify=imageChanged)
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        self._source = value
        self.update()

    @Property(QObject, notify=viewChanged)
    def view(self):
        return self._view

    @view.setter
    def view(self, value):
        if self._view:
            self._view.changed.disconnect(self.update)
        self._view = value
        if value:
            value.changed.connect(self.update)
        self.viewChanged.emit()

    def image(self):
        if self.backend is None:
            return None
        return self.backend.source_image if self._source else self.backend.result_image

    def geometry(self):
        image = self.image()
        if image is None or not self._view:
            return None
        h, w = image.shape[:2]
        scale = self._view.scale or min(self.width() / w, self.height() / h) * .94
        left = self.width() / 2 - self._view.cx * w * scale
        top = self.height() / 2 - self._view.cy * h * scale
        return w, h, scale, left, top

    def paint(self, painter):
        painter.fillRect(self.boundingRect(), QColor("#11171b"))
        image = self.image()
        geometry = self.geometry()
        if image is None or geometry is None:
            return
        w, h, scale, left, top = geometry
        x0, y0 = max(0, math.floor(-left / scale)), max(0, math.floor(-top / scale))
        x1 = min(w, math.ceil((self.width() - left) / scale))
        y1 = min(h, math.ceil((self.height() - top) / scale))
        if x1 <= x0 or y1 <= y0:
            return
        roi = image[y0:y1, x0:x1]
        size = (max(1, round((x1 - x0) * min(1, scale))), max(1, round((y1 - y0) * min(1, scale))))
        if size != (x1 - x0, y1 - y0):
            roi = cv2.resize(roi, size, interpolation=cv2.INTER_AREA)
        rgb = thumbnail(roi, self.backend.color_info, limit=10000,
                        exposure=self._view.exposure, warmth=self._view.warmth)
        qimage = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, scale < 1)
        painter.drawImage(QRectF(left + x0 * scale, top + y0 * scale,
                                (x1 - x0) * scale, (y1 - y0) * scale), qimage)

    @Slot(float, float)
    def pan(self, dx, dy):
        g = self.geometry()
        if g:
            w, h, scale, _, _ = g
            self._view.cx -= dx / scale / w
            self._view.cy -= dy / scale / h
            self._view.changed.emit()

    @Slot(float, float, float)
    def zoomAt(self, factor, x, y):
        g = self.geometry()
        if g:
            w, h, scale, left, top = g
            ix, iy = (x - left) / scale, (y - top) / scale
            self._view.scale = min(8., max(.02, scale * factor))
            self._view.cx = (ix - (x - self.width() / 2) / self._view.scale) / w
            self._view.cy = (iy - (y - self.height() / 2) / self._view.scale) / h
            self._view.changed.emit()

    @Slot(float, float, float, float, float, bool)
    def brush(self, x, y, radius, hardness, opacity, erase):
        g = self.geometry()
        if g and self.backend and self.backend.retoucher:
            _, _, scale, left, top = g
            self.backend.paint_dab((x - left) / scale, (y - top) / scale,
                                   radius / scale, hardness, opacity, erase)
