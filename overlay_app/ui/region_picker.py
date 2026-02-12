from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QMouseEvent, QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget


class RegionPickerOverlay(QWidget):
    """
    Fullscreen semi-transparent overlay. User clicks and drags to select a rectangle.
    On release, selection_finished is emitted (with rect or None if cancelled) and widget closes.
    """

    selection_finished = Signal(object)  # Optional[Tuple[int,int,int,int]]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        self._start: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._result: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
        self._screen_geometry = self._get_screen_geometry()

    def _get_screen_geometry(self) -> QRect:
        screen = QApplication.primaryScreen()
        if screen:
            return screen.geometry()
        return QRect(0, 0, 1920, 1080)

    def show_fullscreen(self) -> None:
        self._screen_geometry = self._get_screen_geometry()
        self.setGeometry(self._screen_geometry)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (x, y, width, height) in screen coordinates, or None if cancelled."""
        return self._result

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._start = event.globalPosition().toPoint()
            self._current = self._start
            self._result = None
            self.update()
        elif event.button() == Qt.RightButton:
            self._result = None
            self.close()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._current = event.globalPosition().toPoint()
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._start is not None:
            end = event.globalPosition().toPoint()
            x = min(self._start.x(), end.x())
            y = min(self._start.y(), end.y())
            w = max(1, abs(end.x() - self._start.x()))
            h = max(1, abs(end.y() - self._start.y()))
            self._result = (x, y, w, h)
            self._start = None
            self._current = None
            self.close()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._result = None
            self.close()
        event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.selection_finished.emit(self.get_selection())
        super().closeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        # Dim entire screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self._start is not None and self._current is not None:
            rect = QRect(self._start, self._current).normalized()
            # Clear the selection area so it's bright
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # Border around selection
            painter.setPen(QColor(66, 208, 255))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
        painter.end()
