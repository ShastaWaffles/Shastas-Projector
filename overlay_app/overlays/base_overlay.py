from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt, QRect, QEvent
from PySide6.QtGui import QMouseEvent, QResizeEvent
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout


class BaseOverlayWindow(QWidget):
    """
    Frameless, always-on-top, translucent overlay window with basic drag/resize and lock support.
    """

    RESIZE_MARGIN = 14

    def __init__(self, opacity: float = 0.8, locked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Window
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(opacity)

        self._locked = locked
        self._click_through = False
        self._drag_start_pos: Optional[QPoint] = None
        self._start_geom: Optional[QRect] = None
        self._resizing = False
        self._resize_from_right = False
        self._resize_from_bottom = False

        self.on_state_changed: Optional[Callable[[], None]] = None

        self._header_widget: Optional[QWidget] = None
        self._resize_handle_widget: Optional[QWidget] = None
        self.set_locked(locked)

    # locking / opacity

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self._apply_interaction_state()

    def is_locked(self) -> bool:
        return self._locked

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        if sys.platform == "win32":
            self._set_click_through_windows(enabled)
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
            if self.isVisible():
                self.show()
        self._apply_interaction_state()
        if self.on_state_changed:
            self.on_state_changed()

    def is_click_through(self) -> bool:
        return self._click_through

    def _apply_interaction_state(self) -> None:
        interactive = not self._locked and not self._click_through
        if self._header_widget is not None:
            self._header_widget.setEnabled(interactive)
            self._header_widget.setVisible(interactive)
        if self._resize_handle_widget is not None:
            self._resize_handle_widget.setEnabled(interactive)
            self._resize_handle_widget.setVisible(interactive)
        if interactive:
            self.setStyleSheet("border: 2px solid rgba(255, 255, 255, 120);")
        else:
            self.setStyleSheet("border: none;")

    def _set_click_through_windows(self, enabled: bool) -> None:
        # Use native extended styles on Windows so toggling click-through does not
        # recreate/hide the overlay window.
        import ctypes

        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x20
        WS_EX_LAYERED = 0x00080000

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            ex_style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        self.ensure_topmost()

    def ensure_topmost(self) -> None:
        if sys.platform != "win32":
            return
        import ctypes

        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        HWND_TOPMOST = -1
        hwnd = int(self.winId())
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def set_overlay_opacity(self, opacity: float) -> None:
        self.setWindowOpacity(opacity)
        if self.on_state_changed:
            self.on_state_changed()

    # register chrome

    def register_header_widget(self, widget: QWidget) -> None:
        self._header_widget = widget
        widget.raise_()

    def register_resize_handle_widget(self, widget: QWidget) -> None:
        self._resize_handle_widget = widget
        widget.raise_()

    def fit_to_content(self) -> None:
        """Subclasses can override if they can infer an ideal content size."""
        return None

    # mouse handling

    def eventFilter(self, obj, event):  # type: ignore[override]
        if isinstance(event, QMouseEvent):
            et = event.type()
            if et == QEvent.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            if et == QEvent.MouseMove:
                self.mouseMoveEvent(event)
                return True
            if et == QEvent.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self._locked:
            return super().mousePressEvent(event)

        geom = self.geometry()
        pos = self.mapFromGlobal(event.globalPosition().toPoint())

        right_edge = geom.width() - self.RESIZE_MARGIN
        bottom_edge = geom.height() - self.RESIZE_MARGIN

        self._resize_from_right = pos.x() >= right_edge
        self._resize_from_bottom = pos.y() >= bottom_edge
        self._resizing = self._resize_from_right or self._resize_from_bottom

        self._drag_start_pos = event.globalPosition().toPoint()
        self._start_geom = geom

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._locked:
            return super().mouseMoveEvent(event)

        if self._drag_start_pos is None or self._start_geom is None:
            self._update_cursor_shape(event)
            return super().mouseMoveEvent(event)

        delta = event.globalPosition().toPoint() - self._drag_start_pos

        if self._resizing:
            new_geom = QRect(self._start_geom)
            if self._resize_from_right:
                new_geom.setRight(new_geom.right() + delta.x())
            if self._resize_from_bottom:
                new_geom.setBottom(new_geom.bottom() + delta.y())
            min_w, min_h = 150, 150
            if new_geom.width() < min_w:
                new_geom.setWidth(min_w)
            if new_geom.height() < min_h:
                new_geom.setHeight(min_h)
            self.setGeometry(new_geom)
        else:
            new_pos = self._start_geom.topLeft() + delta
            self.move(new_pos)

        if self.on_state_changed:
            self.on_state_changed()

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = None
            self._start_geom = None
            self._resizing = False
            self._resize_from_right = False
            self._resize_from_bottom = False
        return super().mouseReleaseEvent(event)

    def _update_cursor_shape(self, event: QMouseEvent) -> None:
        pos = self.mapFromGlobal(event.globalPosition().toPoint())
        w, h = self.width(), self.height()
        margin = self.RESIZE_MARGIN

        if pos.x() >= w - margin and pos.y() >= h - margin:
            self.setCursor(Qt.SizeFDiagCursor)
        elif pos.x() >= w - margin:
            self.setCursor(Qt.SizeHorCursor)
        elif pos.y() >= h - margin:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.on_state_changed:
            self.on_state_changed()

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self.ensure_topmost()


class OverlayDragHeader(QWidget):
    """Small header bar that allows dragging the parent overlay window."""

    def __init__(self, overlay: BaseOverlayWindow, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._overlay = overlay
        self._drag_start_pos: Optional[QPoint] = None
        self._start_geom: Optional[QRect] = None
        self.setFixedHeight(20)
        self.setCursor(Qt.SizeAllCursor)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 60);")

        layout = QHBoxLayout()
        layout.setContentsMargins(6, 0, 6, 0)
        label = QLabel("Drag to move")
        label.setStyleSheet("color: black; font-size: 10px;")
        layout.addWidget(label)
        layout.addStretch(1)
        self.setLayout(layout)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self._overlay.is_locked():
            return super().mousePressEvent(event)
        self._drag_start_pos = event.globalPosition().toPoint()
        self._start_geom = self._overlay.geometry()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._overlay.is_locked() or self._drag_start_pos is None or self._start_geom is None:
            return super().mouseMoveEvent(event)
        delta = event.globalPosition().toPoint() - self._drag_start_pos
        new_pos = self._start_geom.topLeft() + delta
        self._overlay.move(new_pos)
        if self._overlay.on_state_changed:
            self._overlay.on_state_changed()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start_pos = None
        self._start_geom = None
        return super().mouseReleaseEvent(event)

