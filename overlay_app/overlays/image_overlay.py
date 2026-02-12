from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QSizePolicy

from .base_overlay import BaseOverlayWindow


class ImageOverlayWindow(BaseOverlayWindow):
    """Overlay window that shows a static image."""

    def __init__(self, image_path: str, opacity: float = 0.8, locked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(opacity=opacity, locked=locked, parent=parent)

        self._image_path = image_path
        self._original_pixmap = QPixmap()
        self._pan_x = 0
        self._pan_y = 0
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setText("No image selected")
        self._label.setMouseTracking(True)
        self._label.installEventFilter(self)
        # Prevent label size hint from driving window size (stops unbounded growth when unlocked)
        self._label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._label)
        self.setLayout(root_layout)

        # Cap size so overlay cannot grow beyond screen when unlocked
        screen = QApplication.primaryScreen()
        if screen:
            gr = screen.availableGeometry()
            self.setMaximumSize(gr.width(), gr.height())

        self.load_image(image_path)

    def load_image(self, path: str) -> None:
        self._image_path = path
        pixmap = QPixmap(path)
        self._original_pixmap = pixmap
        if self._original_pixmap.isNull():
            self._label.clear()
            self._label.setText(f"Image not found:\n{Path(path).name}")
        else:
            self._label.clear()
            self._refresh_pixmap()
        if self.on_state_changed:
            self.on_state_changed()

    def fit_to_content(self) -> None:
        if self._original_pixmap.isNull():
            return
        self.resize(self._original_pixmap.width(), self._original_pixmap.height())
        if self.on_state_changed:
            self.on_state_changed()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._original_pixmap.isNull():
            return
        lw = max(1, self._label.width())
        lh = max(1, self._label.height())
        scaled = self._original_pixmap.scaled(
            lw,
            lh,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        # Apply pan offset: draw scaled image at (pan_x, pan_y), clamp so we don't show empty space
        base_dx = (lw - scaled.width()) // 2
        base_dy = (lh - scaled.height()) // 2
        pan_x_min = lw - scaled.width() - base_dx
        pan_x_max = -base_dx
        pan_y_min = lh - scaled.height() - base_dy
        pan_y_max = -base_dy
        self._pan_x = max(pan_x_min, min(pan_x_max, self._pan_x))
        self._pan_y = max(pan_y_min, min(pan_y_max, self._pan_y))
        dx = base_dx + self._pan_x
        dy = base_dy + self._pan_y
        if scaled.width() > lw or scaled.height() > lh or dx != base_dx or dy != base_dy:
            from PySide6.QtGui import QPainter
            result = QPixmap(lw, lh)
            result.fill(Qt.transparent)
            painter = QPainter(result)
            painter.drawPixmap(dx, dy, scaled)
            painter.end()
            scaled = result
        self._label.setPixmap(scaled)

    def pan_content(self, dx: int, dy: int) -> None:
        """Pan the image by (dx, dy) pixels. Ctrl+drag inside overlay to use."""
        self._pan_x += dx
        self._pan_y += dy
        self._refresh_pixmap()
        if self.on_state_changed:
            self.on_state_changed()

    def fit_to_overlay(self) -> None:
        """Reset pan so image is centered in the overlay."""
        self._pan_x = 0
        self._pan_y = 0
        self._refresh_pixmap()
        if self.on_state_changed:
            self.on_state_changed()

    @property
    def image_path(self) -> str:
        return self._image_path

