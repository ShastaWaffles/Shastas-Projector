from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt, QRect, QEvent
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QWidget, QLabel


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
        self._resize_from_left = False
        self._resize_from_right = False
        self._resize_from_top = False
        self._resize_from_bottom = False
        self._panning_content = False
        self._pan_start_pos: Optional[QPoint] = None
        self._draw_resize_border = False
        self._border_color = QColor(139, 92, 246)  # default dark theme purple

        self.on_state_changed: Optional[Callable[[], None]] = None

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
        self._draw_resize_border = interactive
        self.setStyleSheet("border: none;")
        self.update()

    def set_overlay_border_color(self, hex_color: str) -> None:
        """Set the resizable border color to match the app theme (e.g. '#8B5CF6')."""
        hex_color = (hex_color or "").strip().lstrip("#")
        if not hex_color or len(hex_color) != 6:
            return
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            self._border_color = QColor(r, g, b)
            self.update()
        except ValueError:
            pass

    def paintEvent(self, event) -> None:
        """Draw a visible resizable border when interactive (stylesheet often invisible with translucent windows)."""
        super().paintEvent(event)
        if not self._draw_resize_border:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        m = self.RESIZE_MARGIN
        rect = self.rect().adjusted(m // 2, m // 2, -(m // 2), -(m // 2))
        pen = QPen(self._border_color)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()

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
        if not self.isVisible():
            return
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        if not hwnd:
            return
        import ctypes

        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        HWND_TOPMOST = -1
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

    def fit_to_content(self) -> None:
        """Subclasses can override if they can infer an ideal content size."""
        return None

    # mouse handling

    def eventFilter(self, obj, event):  # type: ignore[override]
        if isinstance(event, QWheelEvent):
            self.wheelEvent(event)
            return True
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

        # Only pan content when Ctrl is explicitly held; otherwise always move/resize the overlay
        ctrl_held = (event.modifiers() & Qt.ControlModifier) == Qt.ControlModifier
        if ctrl_held and hasattr(self, "pan_content"):
            self._panning_content = True
            self._pan_start_pos = event.globalPosition().toPoint()
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return

        # Plain left-click: move overlay or resize from corner (never pan)
        self._panning_content = False
        self._pan_start_pos = None
        geom = self.geometry()
        pos = self.mapFromGlobal(event.globalPosition().toPoint())
        w, h = geom.width(), geom.height()
        margin = self.RESIZE_MARGIN

        self._resize_from_left = pos.x() < margin
        self._resize_from_right = pos.x() >= w - margin
        self._resize_from_top = pos.y() < margin
        self._resize_from_bottom = pos.y() >= h - margin
        self._resizing = (
            self._resize_from_left
            or self._resize_from_right
            or self._resize_from_top
            or self._resize_from_bottom
        )

        self._drag_start_pos = event.globalPosition().toPoint()
        self._start_geom = geom

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._locked:
            return super().mouseMoveEvent(event)

        if self._panning_content and self._pan_start_pos is not None:
            # Only pan while Ctrl is still held; otherwise cancel pan
            if (event.modifiers() & Qt.ControlModifier) != Qt.ControlModifier:
                self._panning_content = False
                self._pan_start_pos = None
                self._update_cursor_shape(event)
                event.accept()
                return
            curr = event.globalPosition().toPoint()
            delta = curr - self._pan_start_pos
            self._pan_start_pos = curr
            if hasattr(self, "pan_content"):
                self.pan_content(delta.x(), delta.y())
            if self.on_state_changed:
                self.on_state_changed()
            event.accept()
            return

        if self._drag_start_pos is None or self._start_geom is None:
            self._update_cursor_shape(event)
            return super().mouseMoveEvent(event)

        delta = event.globalPosition().toPoint() - self._drag_start_pos

        if self._resizing:
            new_geom = QRect(self._start_geom)
            if self._resize_from_left:
                new_geom.setLeft(new_geom.left() + delta.x())
            if self._resize_from_right:
                new_geom.setRight(new_geom.right() + delta.x())
            if self._resize_from_top:
                new_geom.setTop(new_geom.top() + delta.y())
            if self._resize_from_bottom:
                new_geom.setBottom(new_geom.bottom() + delta.y())
            min_w, min_h = 150, 150
            if new_geom.width() < min_w:
                if self._resize_from_left:
                    new_geom.setLeft(new_geom.right() - min_w)
                else:
                    new_geom.setWidth(min_w)
            if new_geom.height() < min_h:
                if self._resize_from_top:
                    new_geom.setTop(new_geom.bottom() - min_h)
                else:
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
            self._resize_from_left = False
            self._resize_from_right = False
            self._resize_from_top = False
            self._resize_from_bottom = False
            self._panning_content = False
            self._pan_start_pos = None
            self._update_cursor_shape(event)
        return super().mouseReleaseEvent(event)

    def _update_cursor_shape(self, event: QMouseEvent) -> None:
        pos = self.mapFromGlobal(event.globalPosition().toPoint())
        w, h = self.width(), self.height()
        margin = self.RESIZE_MARGIN
        left = pos.x() < margin
        right = pos.x() >= w - margin
        top = pos.y() < margin
        bottom = pos.y() >= h - margin

        if top and left:
            self.setCursor(Qt.SizeFDiagCursor)
        elif top and right:
            self.setCursor(Qt.SizeBDiagCursor)
        elif bottom and left:
            self.setCursor(Qt.SizeBDiagCursor)
        elif bottom and right:
            self.setCursor(Qt.SizeFDiagCursor)
        elif left or right:
            self.setCursor(Qt.SizeHorCursor)
        elif top or bottom:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """When unlocked, scroll wheel over overlay zooms in/out if the overlay supports zoom."""
        if self._locked:
            return super().wheelEvent(event)
        current = None
        if hasattr(self, "_zoom"):
            current = getattr(self, "_zoom", None)
        elif callable(getattr(self, "zoom", None)):
            current = self.zoom()
        if current is not None and hasattr(self, "set_zoom"):
            delta = event.angleDelta().y()
            step = 0.08
            if delta > 0:
                new_zoom = min(3.0, current + step)
            else:
                new_zoom = max(0.5, current - step)
            self.set_zoom(new_zoom)
            if self.on_state_changed:
                self.on_state_changed()
            event.accept()
            return
        return super().wheelEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.on_state_changed:
            self.on_state_changed()

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self.ensure_topmost()


class OverlayDragHandle(QLabel):
    """Small bar to drag the parent overlay window; use when content (e.g. web view) captures mouse."""

    def __init__(self, overlay: "BaseOverlayWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__("Drag", parent)
        self._overlay = overlay
        self._drag_start: Optional[QPoint] = None
        self._start_geom: Optional[QRect] = None
        self.setFixedHeight(22)
        self.setFixedWidth(44)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.SizeAllCursor)
        self.setStyleSheet(
            "font-size: 10px; color: black; background: rgba(255,255,255,90); border: none; border-radius: 3px;"
        )
        self.setToolTip("Drag to move overlay")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and not self._overlay.is_locked():
            self._drag_start = event.globalPosition().toPoint()
            self._start_geom = self._overlay.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and self._start_geom is not None:
            delta = event.globalPosition().toPoint() - self._drag_start
            self._drag_start = event.globalPosition().toPoint()
            self._overlay.move(self._start_geom.topLeft() + delta)
            self._start_geom = self._overlay.geometry()
            if self._overlay.on_state_changed:
                self._overlay.on_state_changed()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self._start_geom = None
        super().mouseReleaseEvent(event)

