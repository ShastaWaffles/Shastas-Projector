from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizeGrip

from .base_overlay import BaseOverlayWindow, OverlayDragHeader


class ImageOverlayWindow(BaseOverlayWindow):
    """Overlay window that shows a static image."""

    def __init__(self, image_path: str, opacity: float = 0.8, locked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(opacity=opacity, locked=locked, parent=parent)

        self._image_path = image_path
        self._original_pixmap = QPixmap()
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setText("No image selected")
        self._label.setMouseTracking(True)
        self._label.installEventFilter(self)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._label)
        self.setLayout(root_layout)

        header = OverlayDragHeader(self, parent=self)
        self.register_header_widget(header)

        self._size_grip = QSizeGrip(self)
        self.register_resize_handle_widget(self._size_grip)

        self.load_image(image_path)
        self._position_chrome()

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
        self._position_chrome()
        self._refresh_pixmap()

    def _position_chrome(self) -> None:
        if self._header_widget is not None:
            self._header_widget.move(6, 6)
            self._header_widget.raise_()
        if self._resize_handle_widget is not None:
            margin = 2
            x = max(0, self.width() - self._resize_handle_widget.width() - margin)
            y = max(0, self.height() - self._resize_handle_widget.height() - margin)
            self._resize_handle_widget.move(x, y)
            self._resize_handle_widget.raise_()

    def _refresh_pixmap(self) -> None:
        if self._original_pixmap.isNull():
            return
        scaled = self._original_pixmap.scaled(
            max(1, self._label.width()),
            max(1, self._label.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

    @property
    def image_path(self) -> str:
        return self._image_path

