from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QMouseEvent,
    QPixmap,
    QBrush,
    QPen,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
    QApplication,
)

from overlay_app.models.config import CaptureRect


HANDLE_SIZE = 10
MIN_CROP_SIZE = 20


def _capture_rect(left: int, top: int, width: int, height: int) -> Optional[QPixmap]:
    """Capture screen region (left, top, width, height). Returns QPixmap or None."""
    if width < 1 or height < 1:
        return None
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return None
    pix = screen.grabWindow(0, left, top, width, height)
    return pix if not pix.isNull() else None


class CropPreviewWidget(QWidget):
    """
    Shows a window preview with a draggable crop rectangle (edges and corners).
    Crop is stored in window-relative coords (0,0 = top-left of window).
    """

    crop_changed = Signal(object)  # CaptureRect

    def __init__(
        self,
        window_pix: QPixmap,
        win_w: int,
        win_h: int,
        initial_crop: Optional[CaptureRect],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._pix = window_pix
        self._win_w = max(1, win_w)
        self._win_h = max(1, win_h)
        # Crop in window coords: x, y, w, h (clamped to window)
        if initial_crop:
            self._cx = max(0, min(initial_crop.x, self._win_w - 1))
            self._cy = max(0, min(initial_crop.y, self._win_h - 1))
            self._cw = max(MIN_CROP_SIZE, min(initial_crop.width, self._win_w - self._cx))
            self._ch = max(MIN_CROP_SIZE, min(initial_crop.height, self._win_h - self._cy))
        else:
            self._cx, self._cy = 0, 0
            self._cw, self._ch = self._win_w, self._win_h
        self._preview_rect = QRect()  # set in paintEvent / resize
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._drag_handle: Optional[str] = None
        self._drag_start: Optional[QPoint] = None
        self._drag_start_crop: Optional[Tuple[int, int, int, int]] = None
        # Larger default so users can clearly see what they're cropping
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)

    def _window_to_preview(self, wx: int, wy: int) -> QPoint:
        return QPoint(
            int(self._preview_rect.x() + wx * self._scale_x),
            int(self._preview_rect.y() + wy * self._scale_y),
        )

    def _preview_to_window(self, px: int, py: int) -> Tuple[int, int]:
        wx = int((px - self._preview_rect.x()) / self._scale_x)
        wy = int((py - self._preview_rect.y()) / self._scale_y)
        return (wx, wy)

    def _crop_preview_rect(self) -> QRect:
        """Crop rectangle in widget (preview) coordinates."""
        x = self._preview_rect.x() + int(self._cx * self._scale_x)
        y = self._preview_rect.y() + int(self._cy * self._scale_y)
        w = max(1, int(self._cw * self._scale_x))
        h = max(1, int(self._ch * self._scale_y))
        return QRect(x, y, w, h)

    def _hit_handle(self, pos: QPoint) -> Optional[str]:
        r = self._crop_preview_rect()
        hs = HANDLE_SIZE
        # Corners first (inner square of handle area)
        if (pos - r.topLeft()).manhattanLength() < hs:
            return "top_left"
        if (pos - r.topRight()).manhattanLength() < hs:
            return "top_right"
        if (pos - r.bottomLeft()).manhattanLength() < hs:
            return "bottom_left"
        if (pos - r.bottomRight()).manhattanLength() < hs:
            return "bottom_right"
        # Edges (expand rect by hs for hit area)
        left = r.x() - hs
        right = r.x() + r.width() + hs
        top = r.y() - hs
        bottom = r.y() + r.height() + hs
        if left <= pos.x() <= r.x() and r.y() <= pos.y() <= r.y() + r.height():
            return "left"
        if r.x() + r.width() <= pos.x() <= right and r.y() <= pos.y() <= r.y() + r.height():
            return "right"
        if r.x() <= pos.x() <= r.x() + r.width() and top <= pos.y() <= r.y():
            return "top"
        if r.x() <= pos.x() <= r.x() + r.width() and r.y() + r.height() <= pos.y() <= bottom:
            return "bottom"
        # Inside the crop rectangle: allow click-drag to move the whole crop
        if r.contains(pos):
            return "move"
        return None

    def _cursor_for_handle(self, handle: Optional[str]):
        cursors = {
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "top_left": Qt.SizeFDiagCursor,
            "bottom_right": Qt.SizeFDiagCursor,
            "top_right": Qt.SizeBDiagCursor,
            "bottom_left": Qt.SizeBDiagCursor,
        }
        if handle == "move":
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(cursors.get(handle, Qt.ArrowCursor))

    def get_crop_rect(self) -> CaptureRect:
        return CaptureRect(x=self._cx, y=self._cy, width=self._cw, height=self._ch)

    def set_crop_full_window(self) -> None:
        self._cx, self._cy = 0, 0
        self._cw, self._ch = self._win_w, self._win_h
        self.update()
        self.crop_changed.emit(self.get_crop_rect())

    def _clamp_crop(self) -> None:
        self._cx = max(0, min(self._cx, self._win_w - MIN_CROP_SIZE))
        self._cy = max(0, min(self._cy, self._win_h - MIN_CROP_SIZE))
        self._cw = max(MIN_CROP_SIZE, min(self._cw, self._win_w - self._cx))
        self._ch = max(MIN_CROP_SIZE, min(self._ch, self._win_h - self._cy))

    def _apply_drag(self, pos: QPoint) -> None:
        if not self._drag_handle or self._drag_start is None or self._drag_start_crop is None:
            return
        cx0, cy0, cw0, ch0 = self._drag_start_crop
        dx_w, dy_w = self._preview_to_window(pos.x(), pos.y())
        sx_w, sy_w = self._preview_to_window(self._drag_start.x(), self._drag_start.y())
        dx = dx_w - sx_w
        dy = dy_w - sy_w

        if self._drag_handle == "left":
            self._cx = max(0, min(cx0 + dx, cx0 + cw0 - MIN_CROP_SIZE))
            self._cw = cw0 + (cx0 - self._cx)
        elif self._drag_handle == "right":
            self._cw = max(MIN_CROP_SIZE, cw0 + dx)
        elif self._drag_handle == "top":
            self._cy = max(0, min(cy0 + dy, cy0 + ch0 - MIN_CROP_SIZE))
            self._ch = ch0 + (cy0 - self._cy)
        elif self._drag_handle == "bottom":
            self._ch = max(MIN_CROP_SIZE, ch0 + dy)
        elif self._drag_handle == "top_left":
            self._cx = max(0, min(cx0 + dx, cx0 + cw0 - MIN_CROP_SIZE))
            self._cy = max(0, min(cy0 + dy, cy0 + ch0 - MIN_CROP_SIZE))
            self._cw = cw0 + (cx0 - self._cx)
            self._ch = ch0 + (cy0 - self._cy)
        elif self._drag_handle == "top_right":
            self._cy = max(0, min(cy0 + dy, cy0 + ch0 - MIN_CROP_SIZE))
            self._cw = max(MIN_CROP_SIZE, cw0 + dx)
            self._ch = ch0 + (cy0 - self._cy)
        elif self._drag_handle == "bottom_left":
            self._cx = max(0, min(cx0 + dx, cx0 + cw0 - MIN_CROP_SIZE))
            self._cw = cw0 + (cx0 - self._cx)
            self._ch = max(MIN_CROP_SIZE, ch0 + dy)
        elif self._drag_handle == "bottom_right":
            self._cw = max(MIN_CROP_SIZE, cw0 + dx)
            self._ch = max(MIN_CROP_SIZE, ch0 + dy)
        elif self._drag_handle == "move":
            # Move entire crop rectangle without resizing
            self._cx = cx0 + dx
            self._cy = cy0 + dy
        self._clamp_crop()
        self.update()
        self.crop_changed.emit(self.get_crop_rect())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            h = self._hit_handle(event.position().toPoint())
            if h:
                self._drag_handle = h
                self._drag_start = event.position().toPoint()
                self._drag_start_crop = (self._cx, self._cy, self._cw, self._ch)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_handle:
            self._apply_drag(pos)
        else:
            self._cursor_for_handle(self._hit_handle(pos))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._drag_handle:
            self._drag_handle = None
            self._drag_start = None
            self._drag_start_crop = None
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if self._pix.isNull():
            painter.fillRect(self.rect(), QColor(60, 60, 60))
            painter.end()
            return
        # Scale pixmap to fit, keep aspect ratio
        pix_w = self._pix.width()
        pix_h = self._pix.height()
        if pix_w < 1 or pix_h < 1:
            painter.end()
            return
        scale = min(self.width() / pix_w, self.height() / pix_h)
        pw = int(pix_w * scale)
        ph = int(pix_h * scale)
        px = (self.width() - pw) // 2
        py = (self.height() - ph) // 2
        self._preview_rect = QRect(px, py, pw, ph)
        self._scale_x = pw / pix_w
        self._scale_y = ph / pix_h

        painter.drawPixmap(self._preview_rect, self._pix)

        # Crop border and handles (no dark overlay so the whole window stays visible)
        crop_r = self._crop_preview_rect()
        painter.setPen(QPen(QColor(0, 200, 255), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(crop_r)

        handle_color = QColor(0, 200, 255)
        painter.setBrush(QBrush(handle_color))
        painter.setPen(QPen(QColor(0, 150, 190), 1))
        hs = HANDLE_SIZE
        cx, cy = crop_r.center().x(), crop_r.center().y()
        for pt in [
            crop_r.topLeft(),
            crop_r.topRight(),
            crop_r.bottomLeft(),
            crop_r.bottomRight(),
            QPoint(crop_r.x(), cy),
            QPoint(crop_r.x() + crop_r.width(), cy),
            QPoint(cx, crop_r.y()),
            QPoint(cx, crop_r.y() + crop_r.height()),
        ]:
            painter.drawRect(pt.x() - hs // 2, pt.y() - hs // 2, hs, hs)

        painter.end()


class WindowCropPickerDialog(QDialog):
    """Dialog to choose a crop rectangle within a window. Returns CaptureRect (window-relative) on accept."""

    def __init__(
        self,
        parent: Optional[QWidget],
        window_rect: Tuple[int, int, int, int],
        initial_crop: Optional[CaptureRect],
        window_title: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Crop window" + (" – " + window_title[:40] if window_title else ""))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        # Give the crop dialog a larger default footprint so the preview is easier to see
        self.setMinimumSize(700, 500)
        self.resize(900, 650)
        self.setMaximumSize(1400, 1000)
        left, top, width, height = window_rect
        self._win_rect = (left, top, width, height)
        self._result: Optional[CaptureRect] = None

        pix = _capture_rect(left, top, width, height)
        if pix is None or pix.isNull():
            self._preview = QLabel("Could not capture window.")
            self._preview.setAlignment(Qt.AlignCenter)
            self._preview.setMinimumSize(320, 240)
            self._ok_enabled = False
        else:
            self._preview = CropPreviewWidget(
                pix, width, height, initial_crop, self
            )
            self._ok_enabled = True

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drag the edges or corners to select the area to project:"))
        layout.addWidget(self._preview)
        btn_row = QHBoxLayout()
        if self._ok_enabled:
            btn_reset = QPushButton("Reset (full window)")
            btn_reset.clicked.connect(self._on_reset)
            btn_row.addWidget(btn_reset)
        btn_row.addStretch(1)
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.setEnabled(self._ok_enabled)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _on_reset(self) -> None:
        if isinstance(self._preview, CropPreviewWidget):
            self._preview.set_crop_full_window()

    def _on_ok(self) -> None:
        if isinstance(self._preview, CropPreviewWidget):
            self._result = self._preview.get_crop_rect()
        self.accept()

    def get_crop_rect(self) -> Optional[CaptureRect]:
        """Returns the chosen crop (window-relative) or None if cancelled / capture failed."""
        return self._result
