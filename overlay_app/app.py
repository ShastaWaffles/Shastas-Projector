from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QAbstractNativeEventFilter, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from overlay_app.models.config import AppConfig, load_config, save_config
from overlay_app.ui.control_panel import ControlPanel


class WindowsHotkeyManager(QAbstractNativeEventFilter):
    """Registers one or more global hotkeys on Windows and dispatches callbacks."""

    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000

    _MODIFIER_TOKENS = {
        "ALT": MOD_ALT,
        "CTRL": MOD_CONTROL,
        "CONTROL": MOD_CONTROL,
        "SHIFT": MOD_SHIFT,
        "WIN": MOD_WIN,
        "WINDOWS": MOD_WIN,
        "META": MOD_WIN,
    }

    _KEY_TOKENS = {
        "SPACE": 0x20,
        "TAB": 0x09,
        "ENTER": 0x0D,
        "RETURN": 0x0D,
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "BACKSPACE": 0x08,
        "DELETE": 0x2E,
        "INSERT": 0x2D,
        "HOME": 0x24,
        "END": 0x23,
        "PGUP": 0x21,
        "PAGEUP": 0x21,
        "PGDN": 0x22,
        "PAGEDOWN": 0x22,
        "LEFT": 0x25,
        "UP": 0x26,
        "RIGHT": 0x27,
        "DOWN": 0x28,
    }

    def __init__(self) -> None:
        super().__init__()
        self._user32 = None
        self._next_hotkey_id = 1
        self._bindings: dict[str, dict[str, object]] = {}
        self._id_to_name: dict[int, str] = {}
        if sys.platform == "win32":
            import ctypes

            self._user32 = ctypes.windll.user32

    def nativeEventFilter(self, event_type, message):  # type: ignore[override]
        if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return False, 0

        from ctypes import wintypes

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == self.WM_HOTKEY:
            name = self._id_to_name.get(int(msg.wParam))
            if name is None:
                return False, 0
            binding = self._bindings.get(name)
            if binding is None:
                return False, 0
            callback = binding.get("callback")
            if callable(callback):
                callback()
            return True, 0
        return False, 0

    def close(self) -> None:
        for name in list(self._bindings.keys()):
            self.unregister(name)

    def bind(self, name: str, hotkey: str, callback: Callable[[], None], enabled: bool = True) -> str:
        parsed = self._parse_hotkey(hotkey)
        if parsed is None:
            previous = self._bindings.get(name)
            return str(previous.get("hotkey", "F8")) if previous else "F8"

        modifiers, vk, normalized = parsed
        if name in self._bindings:
            self.unregister(name)

        hotkey_id = self._next_hotkey_id
        self._next_hotkey_id += 1
        binding = {
            "id": hotkey_id,
            "hotkey": normalized,
            "modifiers": modifiers,
            "vk": vk,
            "enabled": enabled,
            "callback": callback,
            "registered": False,
        }
        self._bindings[name] = binding
        self._id_to_name[hotkey_id] = name
        if enabled:
            self._register(name)
        return normalized

    def unregister(self, name: str) -> None:
        binding = self._bindings.pop(name, None)
        if binding is None:
            return
        hotkey_id = int(binding["id"])
        self._id_to_name.pop(hotkey_id, None)
        if binding.get("registered") and self._user32 is not None:
            self._user32.UnregisterHotKey(None, hotkey_id)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        binding = self._bindings.get(name)
        if binding is None:
            return False
        currently = bool(binding["enabled"])
        if currently == enabled:
            return True
        binding["enabled"] = enabled
        if enabled:
            return self._register(name)
        self._unregister(name)
        return True

    def is_enabled(self, name: str) -> bool:
        binding = self._bindings.get(name)
        if binding is None:
            return False
        return bool(binding["enabled"])

    def get_hotkey(self, name: str) -> str:
        binding = self._bindings.get(name)
        if binding is None:
            return ""
        return str(binding["hotkey"])

    def _parse_hotkey(self, hotkey: str) -> Optional[tuple[int, int, str]]:
        parts = [p.strip().upper() for p in hotkey.replace("-", "+").split("+") if p.strip()]
        if not parts:
            return None

        modifiers = 0
        key_token: Optional[str] = None
        normalized_parts: list[str] = []

        for part in parts:
            if part in self._MODIFIER_TOKENS:
                flag = self._MODIFIER_TOKENS[part]
                if modifiers & flag:
                    continue
                modifiers |= flag
                if flag == self.MOD_CONTROL:
                    normalized_parts.append("Ctrl")
                elif flag == self.MOD_SHIFT:
                    normalized_parts.append("Shift")
                elif flag == self.MOD_ALT:
                    normalized_parts.append("Alt")
                elif flag == self.MOD_WIN:
                    normalized_parts.append("Win")
                continue
            if key_token is not None:
                return None
            key_token = part

        if key_token is None:
            return None

        vk: Optional[int] = None
        if len(key_token) == 1 and key_token.isalpha():
            vk = ord(key_token)
            normalized_key = key_token
        elif len(key_token) == 1 and key_token.isdigit():
            vk = ord(key_token)
            normalized_key = key_token
        elif key_token.startswith("F") and key_token[1:].isdigit():
            fn = int(key_token[1:])
            if 1 <= fn <= 24:
                vk = 0x70 + fn - 1
                normalized_key = f"F{fn}"
            else:
                return None
        elif key_token in self._KEY_TOKENS:
            vk = self._KEY_TOKENS[key_token]
            pretty = {
                "PGUP": "PgUp",
                "PAGEUP": "PgUp",
                "PGDN": "PgDn",
                "PAGEDOWN": "PgDn",
            }.get(key_token, key_token.title())
            normalized_key = pretty
        else:
            return None

        normalized_parts.append(normalized_key)
        normalized = "+".join(normalized_parts)
        return modifiers, vk, normalized

    def _register(self, name: str) -> bool:
        binding = self._bindings.get(name)
        if binding is None or self._user32 is None:
            return False
        hotkey_id = int(binding["id"])
        modifiers = int(binding["modifiers"])
        vk = int(binding["vk"])
        binding["registered"] = bool(
            self._user32.RegisterHotKey(
                None,
                hotkey_id,
                modifiers | self.MOD_NOREPEAT,
                vk,
            )
        )
        return bool(binding["registered"])

    def _unregister(self, name: str) -> None:
        binding = self._bindings.get(name)
        if binding is None:
            return
        if binding.get("registered") and self._user32 is not None:
            self._user32.UnregisterHotKey(None, int(binding["id"]))
        binding["registered"] = False


def _create_qapp() -> QApplication:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ShastasProjector.App")

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setWindowIcon(_build_app_icon())

    return app


def _build_app_icon() -> QIcon:
    app_dir = Path(__file__).resolve().parent
    preferred_icon_path = app_dir / "resources" / "projectoricon.png"
    if preferred_icon_path.exists():
        pix = QPixmap(str(preferred_icon_path))
        if not pix.isNull():
            return QIcon(pix)

    fallback_icon_path = app_dir / "resources" / "shastas_projector.png"
    if fallback_icon_path.exists():
        pix = QPixmap(str(fallback_icon_path))
        if not pix.isNull():
            return QIcon(pix)
    return _build_fallback_s_icon()


def _build_fallback_s_icon() -> QIcon:
    size = 256
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor("#0f1722"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(8, 8, size - 16, size - 16)

    painter.setPen(QColor("#66d0ff"))
    font = QFont("Segoe UI", 150, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignCenter, "S")
    painter.end()
    return QIcon(pix)


def main() -> None:
    app = _create_qapp()
    app.setQuitOnLastWindowClosed(False)

    config: AppConfig = load_config()
    hotkey_manager: Optional[WindowsHotkeyManager] = None
    tray: Optional[QSystemTrayIcon] = None

    def on_config_changed(new_config: AppConfig) -> None:
        save_config(new_config)

    def on_hotkey_changed(hotkey: str) -> str:
        if hotkey_manager is None:
            return hotkey
        return hotkey_manager.bind("chat_focus", hotkey, panel.focus_chat_input_hotkey, config.focus_hotkey_enabled)

    def on_hotkey_enabled_changed(enabled: bool) -> bool:
        if hotkey_manager is None:
            return enabled
        hotkey_manager.set_enabled("chat_focus", enabled)
        return hotkey_manager.is_enabled("chat_focus")

    def on_overlay_hotkey_changed(overlay_id: str, hotkey: str) -> str:
        if hotkey_manager is None:
            return hotkey
        key = f"overlay:{overlay_id}"
        if not hotkey:
            hotkey_manager.unregister(key)
            return ""
        return hotkey_manager.bind(
            key,
            hotkey,
            lambda oid=overlay_id: panel.toggle_overlay_visibility_by_id(oid),
            True,
        )

    def show_panel() -> None:
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def request_quit() -> None:
        if tray is not None:
            tray.hide()
        panel.prepare_for_quit()
        app.quit()

    panel = ControlPanel(
        config,
        on_config_changed,
        on_hotkey_changed,
        on_hotkey_enabled_changed,
        on_overlay_hotkey_changed,
        request_quit,
    )
    panel.resize(640, 480)
    panel.show()
    if sys.platform == "win32":
        hotkey_manager = WindowsHotkeyManager()
        app.installNativeEventFilter(hotkey_manager)

        config.chat_hotkey = hotkey_manager.bind(
            "chat_focus",
            config.chat_hotkey,
            panel.focus_chat_input_hotkey,
            config.focus_hotkey_enabled,
        )
        config.focus_hotkey_enabled = hotkey_manager.is_enabled("chat_focus")

        for overlay_cfg in config.overlays:
            if overlay_cfg.toggle_hotkey:
                overlay_cfg.toggle_hotkey = hotkey_manager.bind(
                    f"overlay:{overlay_cfg.id}",
                    overlay_cfg.toggle_hotkey,
                    lambda oid=overlay_cfg.id: panel.toggle_overlay_visibility_by_id(oid),
                    True,
                )
        panel.set_hotkey_text(config.chat_hotkey)
        panel.set_focus_hotkey_enabled(config.focus_hotkey_enabled)
        save_config(config)

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(app)
        icon = app.windowIcon()
        if icon.isNull():
            icon = QIcon(str(Path(__file__).resolve().parent / "resources" / "shastas_projector.png"))
        tray.setIcon(icon)
        tray.setToolTip("Shastas Projector")

        menu = QMenu()
        action_show = menu.addAction("Open Control Panel")
        action_hide = menu.addAction("Hide Control Panel")
        menu.addSeparator()
        action_quit = menu.addAction("Quit")

        action_show.triggered.connect(show_panel)
        action_hide.triggered.connect(panel.hide)
        action_quit.triggered.connect(request_quit)
        tray.setContextMenu(menu)

        def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                if panel.isVisible():
                    panel.hide()
                else:
                    show_panel()

        tray.activated.connect(on_tray_activated)
        tray.show()

    exit_code = app.exec()
    if hotkey_manager is not None:
        hotkey_manager.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

