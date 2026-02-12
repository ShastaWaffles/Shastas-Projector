from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QWidget,
)


def _enumerate_windows_win32() -> List[Tuple[int, str]]:
    """Returns list of (hwnd, title) for visible windows with non-empty titles."""
    if sys.platform != "win32":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    result: List[Tuple[int, str]] = []

    def enum_callback(hwnd: int, _: int) -> int:
        if not user32.IsWindowVisible(hwnd):
            return 1
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        title = buf.value.strip()
        if title:
            result.append((hwnd, title))
        return 1

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return result


def _enumerate_windows_macos() -> List[Tuple[int, str]]:
    """Returns list of (window_id, title) for visible windows with non-empty titles. Uses Quartz."""
    if sys.platform != "darwin":
        return []
    try:
        import Quartz

        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        raw = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        if raw is None:
            return []
        result: List[Tuple[int, str]] = []
        for w in raw:
            if not w.get(Quartz.kCGWindowIsOnScreen):
                continue
            layer = w.get(Quartz.kCGWindowLayer, 0)
            if layer != 0:
                continue
            name = w.get(Quartz.kCGWindowName) or ""
            owner = w.get(Quartz.kCGWindowOwnerName) or ""
            title = (name or owner or "").strip()
            if not title:
                title = owner.strip() or "Untitled"
            wid = w.get(Quartz.kCGWindowNumber)
            if wid is not None:
                result.append((int(wid), title))
        return result
    except Exception:
        return []


class WindowPickerDialog(QDialog):
    """Dialog that lists visible windows; user selects one. Returns (hwnd, title) or None."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Select window to project")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        self.setMaximumSize(700, 550)
        self._result: Optional[Tuple[int, str]] = None
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.doubleClicked.connect(self._on_accept)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a window to capture (e.g. Minecraft, browser):"))
        layout.addWidget(self._list)

        btn_refresh = QPushButton("Refresh list")
        btn_refresh.clicked.connect(self._populate)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(btn_refresh)
        layout.addWidget(buttons)

        self._populate()

    def _populate(self) -> None:
        self._list.clear()
        if sys.platform == "win32":
            windows = _enumerate_windows_win32()
        elif sys.platform == "darwin":
            windows = _enumerate_windows_macos()
        else:
            windows = []
        for window_id, title in windows:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, (window_id, title))
            self._list.addItem(item)

    def _on_accept(self) -> None:
        item = self._list.currentItem()
        if item:
            self._result = item.data(Qt.UserRole)
        self.accept()

    def get_selection(self) -> Optional[Tuple[int, str]]:
        return self._result
