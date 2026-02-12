from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImage, QPixmap, QPainter, QResizeEvent, QCloseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from overlay_app.models.config import CaptureRect

from .base_overlay import BaseOverlayWindow

# All screen-capture overlay instances so we can mask them out using previous frame (avoid re-projecting)
_screen_capture_overlays: List["ScreenCaptureOverlay"] = []


def _get_window_rect_win32(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """Returns (left, top, width, height) in screen coords, or None if invalid."""
    if not hwnd or sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    RECT = wintypes.RECT()
    if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(RECT)):
        left, top = RECT.left, RECT.top
        width = max(1, RECT.right - RECT.left)
        height = max(1, RECT.bottom - RECT.top)
        return (left, top, width, height)
    return None


def _is_window_minimized_win32(hwnd: int) -> bool:
    """Returns True if the window is minimized (iconic)."""
    if not hwnd or sys.platform != "win32":
        return False
    import ctypes
    SW_SHOWMINIMIZED = 2
    return bool(ctypes.windll.user32.IsIconic(hwnd))


def _capture_window_by_handle_win32(
    hwnd: int,
    win_w: int,
    win_h: int,
    crop: Optional[CaptureRect],
) -> Optional[QPixmap]:
    """
    Capture a window by its handle using PrintWindow, so we get only that window's
    content even when other windows are in front. Returns QPixmap or None.
    """
    if not hwnd or win_w < 1 or win_h < 1 or sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    PW_RENDERFULLCONTENT = 2
    DIB_RGB_COLORS = 0
    BI_RGB = 0

    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        return None
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            return None
        try:
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, win_w, win_h)
            if not hbmp:
                return None
            try:
                old = gdi32.SelectObject(hdc_mem, hbmp)
                if not old:
                    return None
                # PrintWindow draws the window into our DC (window's own content, not what's on screen)
                ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
                if not ok:
                    # Some windows don't support PW_RENDERFULLCONTENT; try 0
                    gdi32.SelectObject(hdc_mem, hbmp)
                    ok = user32.PrintWindow(hwnd, hdc_mem, 0)
                gdi32.SelectObject(hdc_mem, old)
                if not ok:
                    return None

                # Get bitmap bits as 32-bit DIB (top-down)
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", wintypes.DWORD),
                        ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD),
                    ]

                class BITMAPINFO(ctypes.Structure):
                    _fields_ = [
                        ("bmiHeader", BITMAPINFOHEADER),
                        ("bmiColors", wintypes.DWORD * 3),
                    ]

                bmi = BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = BI_RGB
                bmi.bmiHeader.biWidth = win_w
                bmi.bmiHeader.biHeight = -win_h  # top-down

                lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, win_h, None, ctypes.byref(bmi), DIB_RGB_COLORS)
                if lines <= 0:
                    return None
                stride = win_w * 4
                buf_size = stride * win_h
                buf = (ctypes.c_uint8 * buf_size)()
                lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, win_h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
                if lines <= 0:
                    return None

                # Windows DIB is BGRA; QImage Format_ARGB32 is 0xAARRGGBB (platform-dependent). Use Format_ARGB32.
                img = QImage(buf, win_w, win_h, stride, QImage.Format.Format_ARGB32)
                if img.isNull():
                    return None
                # Copy buffer: QImage may not take ownership of buf; make a copy so it stays valid
                img = img.copy()
                if img.isNull():
                    return None

                if crop and (crop.x != 0 or crop.y != 0 or crop.width != win_w or crop.height != win_h):
                    x = max(0, min(crop.x, win_w - 1))
                    y = max(0, min(crop.y, win_h - 1))
                    w = max(1, min(crop.width, win_w - x))
                    h = max(1, min(crop.height, win_h - y))
                    img = img.copy(x, y, w, h)
                if img.isNull():
                    return None
                return QPixmap.fromImage(img)
            finally:
                if hbmp:
                    gdi32.DeleteObject(hbmp)
        finally:
            if hdc_mem:
                gdi32.DeleteDC(hdc_mem)
    finally:
        user32.ReleaseDC(0, hdc_screen)
    return None


def _get_window_rect_macos(window_id: int) -> Optional[Tuple[int, int, int, int]]:
    """Returns (left, top, width, height) in screen coords (top-left origin) for mss, or None."""
    if not window_id or sys.platform != "darwin":
        return None
    try:
        import Quartz

        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        raw = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        if raw is None:
            return None
        for w in raw:
            if w.get(Quartz.kCGWindowNumber) == window_id:
                bounds = w.get(Quartz.kCGWindowBounds)
                if not bounds:
                    return None
                # PyObjC may return dict with X,Y,Width,Height or .x,.y etc.
                if isinstance(bounds, dict):
                    x = int(bounds.get("X", bounds.get("x", 0)))
                    y = int(bounds.get("Y", bounds.get("y", 0)))
                    width = max(1, int(bounds.get("Width", bounds.get("width", 0))))
                    height = max(1, int(bounds.get("Height", bounds.get("height", 0))))
                else:
                    x, y = int(getattr(bounds, "x", 0)), int(getattr(bounds, "y", 0))
                    width = max(1, int(getattr(bounds, "width", 0)))
                    height = max(1, int(getattr(bounds, "height", 0)))
                # Quartz: origin bottom-left; convert to top-left for mss
                main_display = Quartz.CGMainDisplayID()
                display_bounds = Quartz.CGDisplayBounds(main_display)
                size = getattr(display_bounds, "size", None) or (display_bounds.get("size") if isinstance(display_bounds, dict) else None)
                screen_height = int(getattr(size, "height", 1080)) if size is not None else 1080
                top = screen_height - (y + height)
                return (x, top, width, height)
        return None
    except Exception:
        return None


def _is_window_minimized_or_hidden_darwin(window_id: int) -> bool:
    """Returns True if the window is not on screen (minimized, hidden, or closed)."""
    if not window_id or sys.platform != "darwin":
        return True
    try:
        import Quartz

        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        raw = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        if raw is None:
            return True
        for w in raw:
            if w.get(Quartz.kCGWindowNumber) == window_id:
                on_screen = w.get(Quartz.kCGWindowIsOnScreen, False)
                return not on_screen
        return True
    except Exception:
        return True


def _capture_window_by_id_darwin(
    window_id: int,
    win_w: int,
    win_h: int,
    crop: Optional[CaptureRect],
) -> Optional[QPixmap]:
    """
    Capture a window by its CGWindowID using CGWindowListCreateImage, so we get only
    that window's content (like PrintWindow on Windows). Returns QPixmap or None.
    """
    if not window_id or win_w < 1 or win_h < 1 or sys.platform != "darwin":
        return None
    try:
        import Quartz

        # Capture only this window (option including window + window ID)
        list_opt = Quartz.kCGWindowListOptionIncludingWindow
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            list_opt,
            window_id,
            Quartz.kCGWindowImageDefault,
        )
        if image is None:
            return None
        img_w = Quartz.CGImageGetWidth(image)
        img_h = Quartz.CGImageGetHeight(image)
        if img_w < 1 or img_h < 1:
            return None
        bpr = Quartz.CGImageGetBytesPerRow(image)
        prov = Quartz.CGImageGetDataProvider(image)
        if prov is None:
            return None
        data = Quartz.CGDataProviderCopyData(prov)
        if data is None:
            return None
        buf = bytes(data)
        # macOS CGImage is often bottom-up; bytes are typically BGRA
        stride = bpr
        img = QImage(buf, img_w, img_h, stride, QImage.Format.Format_ARGB32)
        if img.isNull():
            return None
        img = img.copy()
        if img.isNull():
            return None
        # CGImage may be bottom-up; flip if needed (Qt expects top-down)
        if img_h > 1:
            img = img.mirrored(False, True)
        if crop and (crop.x != 0 or crop.y != 0 or crop.width != win_w or crop.height != win_h):
            x = max(0, min(crop.x, img_w - 1))
            y = max(0, min(crop.y, img_h - 1))
            cw = max(1, min(crop.width, img_w - x))
            ch = max(1, min(crop.height, img_h - y))
            img = img.copy(x, y, cw, ch)
        if img.isNull():
            return None
        return QPixmap.fromImage(img)
    except Exception:
        return None


class ScreenCaptureOverlay(BaseOverlayWindow):
    """
    Overlay that captures a screen region or a window and displays it live.
    The projection is resizable (drag corner); content scales to fit.
    """

    def __init__(
        self,
        capture_mode: str,
        capture_rect: Optional[CaptureRect],
        window_handle: int = 0,
        window_title: str = "",
        opacity: float = 0.8,
        locked: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(opacity=opacity, locked=locked, parent=parent)

        # Transparent background so only the projected content is visible (no dark rectangle)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setAutoFillBackground(False)

        self._capture_mode = capture_mode  # "region" | "window"
        self._capture_rect = capture_rect  # for region mode; for window mode used as crop (optional)
        self._window_handle = window_handle
        self._window_title = window_title
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            "background: transparent; color: #e0e0e0; font-size: 14px; padding: 8px;"
        )
        self._label.setMouseTracking(True)
        self._label.installEventFilter(self)
        self._label.setMinimumSize(100, 100)
        self._label.setText("Starting capture…")

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._label)
        self.setLayout(root_layout)

        self._capture_timer = QTimer(self)
        self._capture_timer.timeout.connect(self._do_capture)
        self._capture_interval_ms = 1000 // 20  # 20 fps
        self._capture_timer.start(self._capture_interval_ms)

        # Previous frame pixmap (same size as capture) to patch over overlay regions so we don't re-project
        self._last_capture_pix: Optional[QPixmap] = None

        _screen_capture_overlays.append(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Force first paint so the overlay is visible on Windows (layered windows need content)
        self._do_capture()
        self.update()

    def _current_capture_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, width, height) for the area to capture, or None."""
        if self._capture_mode == "region" and self._capture_rect:
            return self._capture_rect.to_tuple()
        if self._capture_mode == "window" and self._window_handle:
            if sys.platform == "win32":
                return _get_window_rect_win32(self._window_handle)
            if sys.platform == "darwin":
                return _get_window_rect_macos(self._window_handle)
        return None

    def get_full_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, width, height) of the full window when in window mode, or None."""
        if self._capture_mode != "window" or not self._window_handle:
            return None
        return self._current_capture_rect()

    def get_crop_rect(self) -> Optional[CaptureRect]:
        """Returns the current crop within the window when in window mode, or None."""
        if self._capture_mode != "window":
            return None
        return self._capture_rect

    def _capture_with_qt(self, left: int, top: int, width: int, height: int) -> Optional[QPixmap]:
        """Use Qt's native screen capture (works reliably on Windows with Qt windows)."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return None
        # grabWindow(0, x, y, w, h) = capture from (x,y) with size (w,h) on the primary screen
        pix = screen.grabWindow(0, left, top, width, height)
        return pix if not pix.isNull() else None

    def _capture_with_mss(self, left: int, top: int, width: int, height: int) -> Optional[QPixmap]:
        """Fallback: mss capture, convert to QPixmap with copied buffer."""
        try:
            import mss
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                shot = sct.grab(monitor)
                if not shot:
                    return None
                raw = bytes(shot.bgra)
                w, h = shot.width, shot.height
            img = QImage(raw, w, h, w * 4, QImage.Format_ARGB32)
            return QPixmap.fromImage(img) if not img.isNull() else None
        except Exception:
            return None

    def _do_capture(self) -> None:
        rect = self._current_capture_rect()
        if not rect:
            if self._capture_mode == "window":
                self._label.setText("Window closed\nor invalid.\nRe-add via\nAdd Window Overlay.")
            else:
                self._label.setText("No region set.\nRe-add via\nAdd Region Overlay.")
            self._label.setPixmap(QPixmap())
            return

        # When window is minimized/hidden we can't capture. Show message only and clear last frame so we never get the tunnel/feedback artifact.
        if self._capture_mode == "window" and self._window_handle:
            minimized = False
            if sys.platform == "win32":
                minimized = _is_window_minimized_win32(self._window_handle)
            elif sys.platform == "darwin":
                minimized = _is_window_minimized_or_hidden_darwin(self._window_handle)
            if minimized:
                self._last_capture_pix = None
                self._label.setPixmap(QPixmap())
                self._label.setText("Window minimized\nRestore window to see content.")
                self._label.setToolTip("Restore the window to see it here.")
                return

        left, top, width, height = rect
        if width < 1 or height < 1:
            return

        # Optional crop (window mode)
        crop = self._capture_rect if self._capture_mode == "window" and self._capture_rect else None

        pix = None
        used_print_window = False
        capture_left, capture_top, capture_w, capture_h = left, top, width, height
        if crop and (crop.x != 0 or crop.y != 0 or crop.width != width or crop.height != height):
            capture_left = left + crop.x
            capture_top = top + crop.y
            capture_w = min(crop.width, width - crop.x)
            capture_h = min(crop.height, height - crop.y)
            capture_w = max(1, capture_w)
            capture_h = max(1, capture_h)

        # Windows: PrintWindow. macOS: CGWindowListCreateImage. Both capture only that window (no screen-grab fallback in window mode to avoid tunnel/feedback).
        if self._capture_mode == "window" and self._window_handle:
            if sys.platform == "win32":
                pix = _capture_window_by_handle_win32(self._window_handle, width, height, crop)
            elif sys.platform == "darwin":
                pix = _capture_window_by_id_darwin(self._window_handle, width, height, crop)
            else:
                pix = None
            if pix is not None and not pix.isNull():
                used_print_window = True
        # Fallback: screen grab only for region mode or when not using native window capture (Linux window mode has no native API)
        if pix is None or pix.isNull():
            if not (self._capture_mode == "window" and self._window_handle and (sys.platform == "win32" or sys.platform == "darwin")):
                if sys.platform == "win32":
                    pix = self._capture_with_qt(capture_left, capture_top, capture_w, capture_h)
                if pix is None or pix.isNull():
                    pix = self._capture_with_mss(capture_left, capture_top, capture_w, capture_h)

        if pix is None or pix.isNull():
            if self._capture_mode == "window" and (sys.platform == "win32" or sys.platform == "darwin"):
                self._last_capture_pix = None
                self._label.setText("Could not capture window.\nRestore or unminimize the window.")
                self._label.setToolTip("")
                self._label.setPixmap(QPixmap())
            else:
                self._label.setText("Capture failed\n(try moving overlay)")
                self._label.setPixmap(QPixmap())
            return

        # Patch out any screen-capture overlays that overlap the capture (only for screen grab; PrintWindow captures the window only)
        if not used_print_window:
            capture_rect = QRect(capture_left, capture_top, capture_w, capture_h)
            if (
                self._last_capture_pix is not None
                and not self._last_capture_pix.isNull()
                and self._last_capture_pix.size() == pix.size()
            ):
                painter = QPainter(pix)
                for w in _screen_capture_overlays:
                    if not w.isVisible():
                        continue
                    w_tl = w.mapToGlobal(QPoint(0, 0))
                    overlay_rect = QRect(w_tl.x(), w_tl.y(), w.width(), w.height())
                    if not overlay_rect.intersects(capture_rect):
                        continue
                    patch = overlay_rect.intersected(capture_rect)
                    ox = patch.x() - capture_left
                    oy = patch.y() - capture_top
                    painter.drawPixmap(ox, oy, self._last_capture_pix, ox, oy, patch.width(), patch.height())
                painter.end()

        self._last_capture_pix = pix.copy()
        self._show_scaled_capture(pix)
        self._label.setText("")
        self._label.setToolTip("")
        self._label.repaint()

    def _show_scaled_capture(self, pix: QPixmap) -> None:
        """Scale pix to fill the label box (zoom fit) and set it on the label. Uses _pan_x, _pan_y for offset."""
        if pix.isNull():
            return
        lw = max(1, self._label.width())
        lh = max(1, self._label.height())
        zw = int(lw * self._zoom)
        zh = int(lh * self._zoom)
        # Scale to fill the box (KeepAspectRatioByExpanding) so content is as large as possible;
        # then draw centered so the overlay box is always filled (edges may be cropped).
        filled = pix.scaled(zw, zh, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        base_dx = (lw - filled.width()) // 2
        base_dy = (lh - filled.height()) // 2
        # Clamp pan so we don't show empty space
        pan_x_min = lw - filled.width() - base_dx
        pan_x_max = -base_dx
        pan_y_min = lh - filled.height() - base_dy
        pan_y_max = -base_dy
        self._pan_x = max(pan_x_min, min(pan_x_max, self._pan_x))
        self._pan_y = max(pan_y_min, min(pan_y_max, self._pan_y))
        dx = base_dx + self._pan_x
        dy = base_dy + self._pan_y
        if filled.width() > lw or filled.height() > lh:
            result = QPixmap(lw, lh)
            result.fill(Qt.transparent)
            painter = QPainter(result)
            painter.drawPixmap(dx, dy, filled)
            painter.end()
            filled = result
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setPixmap(filled)

    def pan_content(self, dx: int, dy: int) -> None:
        """Pan the displayed content by (dx, dy) pixels. Ctrl+drag inside overlay to use."""
        self._pan_x += dx
        self._pan_y += dy
        if self._last_capture_pix is not None and not self._last_capture_pix.isNull():
            self._show_scaled_capture(self._last_capture_pix)
        self._label.repaint()

    def fit_to_overlay(self) -> None:
        """Reset pan so content is centered/fit in the overlay."""
        self._pan_x = 0
        self._pan_y = 0
        if self._last_capture_pix is not None and not self._last_capture_pix.isNull():
            self._show_scaled_capture(self._last_capture_pix)
        self._label.repaint()
        if self.on_state_changed:
            self.on_state_changed()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._do_capture()

    def set_capture_region(self, rect: Optional[CaptureRect]) -> None:
        self._capture_rect = rect
        if self.on_state_changed:
            self.on_state_changed()

    def set_capture_window(self, hwnd: int, title: str, crop_rect: Optional[CaptureRect] = None) -> None:
        self._window_handle = hwnd
        self._window_title = title
        self._capture_rect = crop_rect
        if self.on_state_changed:
            self.on_state_changed()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.5, min(3.0, zoom))
        if self.on_state_changed:
            self.on_state_changed()

    def stop_capture(self) -> None:
        self._capture_timer.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop_capture()
        try:
            _screen_capture_overlays.remove(self)
        except ValueError:
            pass
        super().closeEvent(event)
