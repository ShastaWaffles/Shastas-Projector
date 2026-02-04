from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QLineEdit,
    QSlider,
    QFileDialog,
    QMessageBox,
    QFormLayout,
    QToolButton,
    QSpinBox,
    QGroupBox,
    QSplitter,
    QKeySequenceEdit,
)

from overlay_app.models.config import AppConfig, OverlayConfig, ThemeType
from overlay_app.overlays.image_overlay import ImageOverlayWindow
from overlay_app.overlays.web_overlay import WebOverlayWindow


class OverlayListItemWidget(QWidget):
    """Row widget: overlay name + visible/locked/click-through buttons."""

    def __init__(
        self,
        name: str,
        visible: bool,
        locked: bool,
        click_through: bool,
        on_visible_toggled,
        on_locked_toggled,
        on_click_through_toggled,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._name_label = QLabel(name)

        self._btn_visible = QToolButton()
        self._btn_visible.setCheckable(True)
        self._btn_visible.setChecked(visible)
        self._btn_visible.setText("V")
        self._btn_visible.setToolTip("Toggle visibility")
        self._btn_visible.toggled.connect(on_visible_toggled)

        self._btn_locked = QToolButton()
        self._btn_locked.setCheckable(True)
        self._btn_locked.setChecked(locked)
        self._btn_locked.setText("L")
        self._btn_locked.setToolTip("Toggle lock")
        self._btn_locked.toggled.connect(on_locked_toggled)

        self._btn_click_through = QToolButton()
        self._btn_click_through.setCheckable(True)
        self._btn_click_through.setChecked(click_through)
        self._btn_click_through.setText("C")
        self._btn_click_through.setToolTip("Toggle click-through")
        self._btn_click_through.toggled.connect(on_click_through_toggled)

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self._name_label)
        layout.addStretch(1)
        layout.addWidget(self._btn_visible)
        layout.addWidget(self._btn_locked)
        layout.addWidget(self._btn_click_through)
        self.setLayout(layout)

    def set_name(self, name: str) -> None:
        self._name_label.setText(name)

    def set_visible(self, visible: bool) -> None:
        self._btn_visible.blockSignals(True)
        self._btn_visible.setChecked(visible)
        self._btn_visible.blockSignals(False)

    def set_locked(self, locked: bool) -> None:
        self._btn_locked.blockSignals(True)
        self._btn_locked.setChecked(locked)
        self._btn_locked.blockSignals(False)

    def set_click_through(self, click_through: bool) -> None:
        self._btn_click_through.blockSignals(True)
        self._btn_click_through.setChecked(click_through)
        self._btn_click_through.blockSignals(False)


class ControlPanel(QWidget):
    """Main control window for managing overlays."""

    def __init__(
        self,
        app_config: AppConfig,
        on_config_changed: Callable[[AppConfig], None],
        on_hotkey_changed: Optional[Callable[[str], str]] = None,
        on_focus_hotkey_enabled_changed: Optional[Callable[[bool], bool]] = None,
        on_overlay_hotkey_changed: Optional[Callable[[str, str], str]] = None,
        on_quit_requested: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.setWindowTitle("Shastas Projector")
        self._config = app_config
        self._on_config_changed = on_config_changed
        self._hotkey_apply_callback = on_hotkey_changed
        self._hotkey_enabled_callback = on_focus_hotkey_enabled_changed
        self._overlay_hotkey_callback = on_overlay_hotkey_changed
        self._on_quit_requested = on_quit_requested
        self._allow_close = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._flush_config)
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(3000)
        self._topmost_timer.timeout.connect(self._refresh_overlay_topmost)
        self._topmost_timer.start()
        self._is_loading_selection = False

        self._overlay_windows: Dict[str, QWidget] = {}
        self._row_widgets: Dict[str, OverlayListItemWidget] = {}
        self._config_by_id: Dict[str, OverlayConfig] = {}

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._name_edit = QLineEdit()
        self._source_edit = QLineEdit()
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(50, 200)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(150, 5000)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(150, 5000)
        self._btn_fit_content = QPushButton("Fit to Content")
        self._btn_reload = QPushButton("Reload Overlay")
        self._btn_fit_content.setEnabled(False)
        self._btn_reload.setEnabled(False)

        self._btn_add_web = QPushButton("Add Web Overlay")
        self._btn_add_image = QPushButton("Add Image Overlay")
        self._btn_delete = QPushButton("Delete Overlay")

        self._btn_lock_all = QPushButton("Lock All")
        self._btn_unlock_all = QPushButton("Unlock All")
        self._btn_hide_all = QPushButton("Hide All")
        self._btn_show_all = QPushButton("Show All")
        self._btn_click_all = QPushButton("Click-Through All")
        self._btn_interact_all = QPushButton("Interactive All")
        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setMaximumSequenceLength(1)
        self._hotkey_edit.setKeySequence(QKeySequence(self._config.chat_hotkey))
        self._overlay_hotkey_edit = QKeySequenceEdit()
        self._overlay_hotkey_edit.setMaximumSequenceLength(1)
        self._btn_clear_overlay_hotkey = QPushButton("Clear")
        self._btn_clear_overlay_hotkey.setFixedWidth(58)
        self._btn_hotkey_enabled = QToolButton()
        self._btn_hotkey_enabled.setCheckable(True)
        self._btn_hotkey_enabled.setChecked(self._config.focus_hotkey_enabled)
        self._hotkey_hint = QLabel("")
        self._btn_theme_dark = QPushButton("Dark")
        self._btn_theme_light = QPushButton("Light")
        self._btn_quit = QPushButton("Quit App")
        self._btn_theme_dark.setCheckable(True)
        self._btn_theme_light.setCheckable(True)
        self._btn_theme_dark.setFixedWidth(58)
        self._btn_theme_light.setFixedWidth(58)
        self._chat_focus_overlay_id: Optional[str] = None
        self._chat_focus_was_click_through = False

        self._build_layout()
        self._connect_signals()
        self._load_from_config()
        self._update_hotkey_enabled_button(self._config.focus_hotkey_enabled)
        self._apply_theme(self._config.theme)
        self._sync_theme_buttons(self._config.theme)
        self._update_hotkey_hint(self._config.chat_hotkey)

    def _build_layout(self) -> None:
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        splitter = QSplitter(Qt.Horizontal, self)
        main_layout.addWidget(splitter)

        left_container = QWidget(self)
        left = QVBoxLayout()
        left_container.setLayout(left)
        left.addWidget(QLabel("Overlays"))
        left.addWidget(self._list)

        add_row = QHBoxLayout()
        add_row.addWidget(self._btn_add_web)
        add_row.addWidget(self._btn_add_image)
        left.addLayout(add_row)
        left.addWidget(self._btn_delete)

        global_row1 = QHBoxLayout()
        global_row1.addWidget(self._btn_lock_all)
        global_row1.addWidget(self._btn_unlock_all)
        left.addLayout(global_row1)

        global_row2 = QHBoxLayout()
        global_row2.addWidget(self._btn_hide_all)
        global_row2.addWidget(self._btn_show_all)
        left.addLayout(global_row2)

        global_row3 = QHBoxLayout()
        global_row3.addWidget(self._btn_click_all)
        global_row3.addWidget(self._btn_interact_all)
        left.addLayout(global_row3)
        splitter.addWidget(left_container)

        right_container = QWidget(self)
        right = QVBoxLayout()
        right_container.setLayout(right)

        # Brand block (keep original artwork in panel)
        brand_block = QVBoxLayout()
        brand_block.setSpacing(1)
        brand_block.setContentsMargins(0, 0, 0, 0)

        icon_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setFixedSize(180, 180)
        app_dir = Path(__file__).resolve().parents[1]
        icon_path = app_dir / "resources" / "shastas_projector.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                icon_label.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_row.addStretch(1)
        icon_row.addWidget(icon_label)
        icon_row.addStretch(1)
        brand_block.addLayout(icon_row)

        meta_row = QVBoxLayout()
        meta_row.setSpacing(1)
        meta_row.setContentsMargins(0, 0, 0, 6)

        version_label = QLabel("v1.0")
        version_label.setAlignment(Qt.AlignCenter)
        meta_row.addWidget(version_label)

        created_label = QLabel("Created by ShastaWaffles")
        created_label.setAlignment(Qt.AlignCenter)
        meta_row.addWidget(created_label)

        copyright_label = QLabel("Copyright 2026")
        copyright_label.setAlignment(Qt.AlignCenter)
        meta_row.addWidget(copyright_label)

        repo_label = QLabel(
            '<a href="https://github.com/ShastaWaffles/Shastas-Projector">GitHub Project</a>'
        )
        repo_label.setAlignment(Qt.AlignCenter)
        repo_label.setOpenExternalLinks(True)
        repo_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        repo_label.setToolTip("Open repository")
        meta_row.addWidget(repo_label)

        brand_block.addLayout(meta_row)
        right.addLayout(brand_block)

        form_group = QGroupBox("Selected Overlay")
        form = QFormLayout()
        form.addRow("Name:", self._name_edit)
        form.addRow("URL / Image Path:", self._source_edit)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Width:"))
        size_row.addWidget(self._width_spin)
        size_row.addWidget(QLabel("Height:"))
        size_row.addWidget(self._height_spin)
        form.addRow("Size:", size_row)
        form.addRow("Zoom (%):", self._zoom_slider)
        overlay_hotkey_row = QHBoxLayout()
        overlay_hotkey_row.addWidget(self._overlay_hotkey_edit)
        overlay_hotkey_row.addWidget(self._btn_clear_overlay_hotkey)
        form.addRow("Toggle hotkey:", overlay_hotkey_row)
        form_group.setLayout(form)
        right.addWidget(form_group)

        right.addWidget(QLabel("Opacity (20-100%)"))
        right.addWidget(self._opacity_slider)
        action_row = QHBoxLayout()
        action_row.addWidget(self._btn_fit_content)
        action_row.addWidget(self._btn_reload)
        right.addLayout(action_row)

        hotkey_group = QGroupBox("Hotkey")
        hotkey_form = QFormLayout()
        hotkey_form.addRow("Chat focus:", self._hotkey_edit)
        hotkey_form.addRow("Enabled:", self._btn_hotkey_enabled)
        hotkey_group.setLayout(hotkey_form)
        right.addWidget(hotkey_group)

        self._hotkey_hint.setStyleSheet("color: #9fb7c8;")
        right.addWidget(self._hotkey_hint)

        theme_row = QHBoxLayout()
        theme_row.addStretch(1)
        theme_row.addWidget(self._btn_theme_dark)
        theme_row.addWidget(self._btn_theme_light)
        theme_row.addWidget(self._btn_quit)
        right.addLayout(theme_row)
        right.addStretch(1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def _connect_signals(self) -> None:
        self._list.currentItemChanged.connect(self._on_selection_changed)

        self._btn_add_web.clicked.connect(self._on_add_web)
        self._btn_add_image.clicked.connect(self._on_add_image)
        self._btn_delete.clicked.connect(self._on_delete_selected)

        self._btn_lock_all.clicked.connect(lambda: self._set_all_locked(True))
        self._btn_unlock_all.clicked.connect(lambda: self._set_all_locked(False))
        self._btn_hide_all.clicked.connect(lambda: self._set_all_visible(False))
        self._btn_show_all.clicked.connect(lambda: self._set_all_visible(True))
        self._btn_click_all.clicked.connect(lambda: self._set_all_click_through(True))
        self._btn_interact_all.clicked.connect(lambda: self._set_all_click_through(False))

        self._name_edit.editingFinished.connect(self._apply_detail_changes)
        self._source_edit.editingFinished.connect(self._apply_detail_changes)
        self._opacity_slider.valueChanged.connect(self._apply_detail_changes)
        self._zoom_slider.valueChanged.connect(self._apply_detail_changes)
        self._width_spin.valueChanged.connect(self._on_size_changed)
        self._height_spin.valueChanged.connect(self._on_size_changed)
        self._btn_fit_content.clicked.connect(self._on_fit_content_clicked)
        self._btn_reload.clicked.connect(self._on_reload_clicked)
        self._hotkey_edit.keySequenceChanged.connect(self._on_hotkey_changed)
        self._overlay_hotkey_edit.keySequenceChanged.connect(self._on_overlay_hotkey_changed)
        self._btn_clear_overlay_hotkey.clicked.connect(self._on_clear_overlay_hotkey)
        self._btn_hotkey_enabled.toggled.connect(self._on_focus_hotkey_enabled_toggled)
        self._btn_theme_dark.clicked.connect(lambda: self._set_theme_from_ui("dark"))
        self._btn_theme_light.clicked.connect(lambda: self._set_theme_from_ui("light"))
        self._btn_quit.clicked.connect(self._on_quit_clicked)

    def _load_from_config(self) -> None:
        for overlay_cfg in self._config.overlays:
            self._config_by_id[overlay_cfg.id] = overlay_cfg
            self._create_overlay_window(overlay_cfg)
            self._add_list_item(overlay_cfg)
            if overlay_cfg.toggle_hotkey and self._overlay_hotkey_callback is not None:
                overlay_cfg.toggle_hotkey = self._overlay_hotkey_callback(overlay_cfg.id, overlay_cfg.toggle_hotkey)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _schedule_config_save(self) -> None:
        self._save_timer.start()

    def _flush_config(self) -> None:
        self._on_config_changed(self._config)

    def _update_hotkey_hint(self, hotkey_text: str) -> None:
        if self._config.focus_hotkey_enabled:
            self._hotkey_hint.setText(
                f"Hotkey: {hotkey_text} chat focus (press again to restore click-through)"
            )
        else:
            self._hotkey_hint.setText("Hotkey focus is disabled")

    def set_hotkey_text(self, hotkey_text: str) -> None:
        self._hotkey_edit.blockSignals(True)
        self._hotkey_edit.setKeySequence(QKeySequence(hotkey_text))
        self._hotkey_edit.blockSignals(False)
        self._update_hotkey_hint(hotkey_text)

    def set_focus_hotkey_enabled(self, enabled: bool) -> None:
        self._btn_hotkey_enabled.blockSignals(True)
        self._btn_hotkey_enabled.setChecked(enabled)
        self._btn_hotkey_enabled.blockSignals(False)
        self._update_hotkey_enabled_button(enabled)
        self._update_hotkey_hint(self._config.chat_hotkey)

    def _update_hotkey_enabled_button(self, enabled: bool) -> None:
        self._btn_hotkey_enabled.setText("On" if enabled else "Off")
        self._btn_hotkey_enabled.setToolTip("Enable or disable global chat-focus hotkey")

    def _sync_theme_buttons(self, theme: ThemeType) -> None:
        self._btn_theme_dark.blockSignals(True)
        self._btn_theme_light.blockSignals(True)
        self._btn_theme_dark.setChecked(theme == "dark")
        self._btn_theme_light.setChecked(theme == "light")
        self._btn_theme_dark.blockSignals(False)
        self._btn_theme_light.blockSignals(False)

        if theme == "dark":
            self._btn_theme_dark.setEnabled(False)
            self._btn_theme_light.setEnabled(True)
        else:
            self._btn_theme_dark.setEnabled(True)
            self._btn_theme_light.setEnabled(False)

    def _apply_theme(self, theme: ThemeType) -> None:
        if theme == "light":
            self.setStyleSheet(
                """
                QWidget { color: #1b2430; background-color: #edf1f7; }
                QGroupBox {
                    background-color: #f7f9fd;
                    border: 1px solid #cfd7e3;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 3px;
                    color: #2b3b4f;
                }
                QLineEdit, QSpinBox, QListWidget, QKeySequenceEdit {
                    background-color: #ffffff;
                    border: 1px solid #c3cddd;
                    border-radius: 6px;
                    padding: 4px;
                    selection-background-color: #4a8df8;
                    selection-color: #ffffff;
                }
                QPushButton, QToolButton {
                    background-color: #ffffff;
                    border: 1px solid #bac6d9;
                    border-radius: 6px;
                    padding: 4px 8px;
                }
                QPushButton:hover, QToolButton:hover { background-color: #edf3ff; }
                QPushButton:checked, QToolButton:checked {
                    background-color: #d9e7ff;
                    border-color: #8db1ef;
                }
                """
            )
        else:
            self.setStyleSheet("")

    def _create_overlay_window(self, cfg: OverlayConfig) -> None:
        if cfg.type == "web":
            win = WebOverlayWindow(url=cfg.source, opacity=cfg.opacity, locked=cfg.locked)
            win.set_zoom(cfg.zoom)
        else:
            win = ImageOverlayWindow(image_path=cfg.source, opacity=cfg.opacity, locked=cfg.locked)

        win.setWindowTitle(cfg.name or cfg.id)
        win.setGeometry(cfg.x, cfg.y, cfg.width, cfg.height)
        win.set_click_through(cfg.click_through)
        if cfg.visible:
            win.show()
            if hasattr(win, "ensure_topmost"):
                win.ensure_topmost()

        def on_state_changed() -> None:
            self._update_config_from_window(cfg.id)
            self._schedule_config_save()

        win.on_state_changed = on_state_changed
        self._overlay_windows[cfg.id] = win

    def _add_list_item(self, cfg: OverlayConfig) -> None:
        item = QListWidgetItem()
        widget = OverlayListItemWidget(
            name=cfg.name or cfg.id,
            visible=cfg.visible,
            locked=cfg.locked,
            click_through=cfg.click_through,
            on_visible_toggled=lambda checked, oid=cfg.id: self._on_row_visible_toggled(oid, checked),
            on_locked_toggled=lambda checked, oid=cfg.id: self._on_row_locked_toggled(oid, checked),
            on_click_through_toggled=lambda checked, oid=cfg.id: self._on_row_click_through_toggled(oid, checked),
        )
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, cfg.id)
        self._list.addItem(item)
        self._list.setItemWidget(item, widget)
        self._row_widgets[cfg.id] = widget

    def _get_selected_id(self) -> Optional[str]:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _find_config(self, overlay_id: str) -> Optional[OverlayConfig]:
        return self._config_by_id.get(overlay_id)

    def _on_selection_changed(self, current: QListWidgetItem, _prev: QListWidgetItem) -> None:
        self._is_loading_selection = True
        overlay_id = current.data(Qt.UserRole) if current else None
        if overlay_id is None:
            self._name_edit.blockSignals(True)
            self._source_edit.blockSignals(True)
            self._opacity_slider.blockSignals(True)
            self._zoom_slider.blockSignals(True)
            self._width_spin.blockSignals(True)
            self._height_spin.blockSignals(True)
            self._overlay_hotkey_edit.blockSignals(True)

            self._name_edit.clear()
            self._source_edit.clear()
            self._opacity_slider.setValue(80)
            self._zoom_slider.setValue(100)
            self._width_spin.setValue(450)
            self._height_spin.setValue(700)
            self._overlay_hotkey_edit.setKeySequence(QKeySequence())

            self._name_edit.blockSignals(False)
            self._source_edit.blockSignals(False)
            self._opacity_slider.blockSignals(False)
            self._zoom_slider.blockSignals(False)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)
            self._overlay_hotkey_edit.blockSignals(False)
            self._btn_fit_content.setEnabled(False)
            self._btn_reload.setEnabled(False)
            self._overlay_hotkey_edit.setEnabled(False)
            self._btn_clear_overlay_hotkey.setEnabled(False)
            self._is_loading_selection = False
            return

        cfg = self._find_config(overlay_id)
        if not cfg:
            self._is_loading_selection = False
            return

        self._name_edit.blockSignals(True)
        self._source_edit.blockSignals(True)
        self._opacity_slider.blockSignals(True)
        self._zoom_slider.blockSignals(True)
        self._width_spin.blockSignals(True)
        self._height_spin.blockSignals(True)
        self._overlay_hotkey_edit.blockSignals(True)

        self._name_edit.setText(cfg.name)
        self._source_edit.setText(cfg.source)
        self._opacity_slider.setValue(int(cfg.opacity * 100))
        self._zoom_slider.setValue(int(cfg.zoom * 100))
        self._width_spin.setValue(cfg.width)
        self._height_spin.setValue(cfg.height)
        self._overlay_hotkey_edit.setKeySequence(QKeySequence(cfg.toggle_hotkey))

        self._name_edit.blockSignals(False)
        self._source_edit.blockSignals(False)
        self._opacity_slider.blockSignals(False)
        self._zoom_slider.blockSignals(False)
        self._width_spin.blockSignals(False)
        self._height_spin.blockSignals(False)
        self._overlay_hotkey_edit.blockSignals(False)

        self._btn_fit_content.setEnabled(cfg.type == "image")
        self._btn_reload.setEnabled(cfg.type == "web")
        self._overlay_hotkey_edit.setEnabled(True)
        self._btn_clear_overlay_hotkey.setEnabled(bool(cfg.toggle_hotkey))
        self._is_loading_selection = False

    def _on_add_web(self) -> None:
        new_id = str(uuid.uuid4())
        cfg = OverlayConfig(
            id=new_id,
            name="Web Overlay",
            type="web",
            source="",
            click_through=False,
        )
        self._config.overlays.append(cfg)
        self._config_by_id[cfg.id] = cfg
        self._create_overlay_window(cfg)
        self._add_list_item(cfg)
        self._list.setCurrentRow(self._list.count() - 1)
        self._schedule_config_save()

    def _on_add_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if not path:
            return

        new_id = str(uuid.uuid4())
        cfg = OverlayConfig(
            id=new_id,
            name="Image Overlay",
            type="image",
            source=path,
            click_through=False,
        )
        self._config.overlays.append(cfg)
        self._config_by_id[cfg.id] = cfg
        self._create_overlay_window(cfg)
        self._add_list_item(cfg)
        self._list.setCurrentRow(self._list.count() - 1)
        self._schedule_config_save()

    def _on_delete_selected(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return

        reply = QMessageBox.question(
            self,
            "Delete Overlay",
            "Delete selected overlay?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._config.overlays = [c for c in self._config.overlays if c.id != overlay_id]
        cfg = self._config_by_id.get(overlay_id)
        if cfg and cfg.toggle_hotkey and self._overlay_hotkey_callback is not None:
            self._overlay_hotkey_callback(overlay_id, "")
        self._config_by_id.pop(overlay_id, None)

        win = self._overlay_windows.pop(overlay_id, None)
        if win:
            win.close()

        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
        self._row_widgets.pop(overlay_id, None)
        if self._chat_focus_overlay_id == overlay_id:
            self._chat_focus_overlay_id = None
            self._chat_focus_was_click_through = False

        self._schedule_config_save()

    def _apply_detail_changes(self) -> None:
        if self._is_loading_selection:
            return
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return

        cfg = self._find_config(overlay_id)
        if not cfg:
            return

        cfg.name = self._name_edit.text().strip() or cfg.name
        new_source = self._source_edit.text().strip()
        old_source = cfg.source
        cfg.source = new_source
        cfg.opacity = max(0.2, min(1.0, self._opacity_slider.value() / 100.0))
        cfg.zoom = max(0.5, min(2.0, self._zoom_slider.value() / 100.0))

        row_widget = self._row_widgets.get(overlay_id)
        if row_widget is not None:
            row_widget.set_name(cfg.name)

        win = self._overlay_windows.get(overlay_id)
        if win:
            win.setWindowTitle(cfg.name or cfg.id)
            if new_source != old_source:
                if isinstance(win, WebOverlayWindow) and cfg.type == "web":
                    win.load_url(cfg.source)
                elif isinstance(win, ImageOverlayWindow) and cfg.type == "image":
                    win.load_image(cfg.source)

            if isinstance(win, WebOverlayWindow):
                win.set_zoom(cfg.zoom)

            win.set_overlay_opacity(cfg.opacity)

        self._schedule_config_save()

    def _set_all_locked(self, locked: bool) -> None:
        for cfg in self._config.overlays:
            cfg.locked = locked
            win = self._overlay_windows.get(cfg.id)
            if win:
                win.set_locked(locked)
            row = self._row_widgets.get(cfg.id)
            if row:
                row.set_locked(locked)
        self._schedule_config_save()

    def _set_all_visible(self, visible: bool) -> None:
        for cfg in self._config.overlays:
            cfg.visible = visible
            win = self._overlay_windows.get(cfg.id)
            if win:
                if visible:
                    win.show()
                    if hasattr(win, "ensure_topmost"):
                        win.ensure_topmost()
                else:
                    win.hide()
            row = self._row_widgets.get(cfg.id)
            if row:
                row.set_visible(visible)
        self._schedule_config_save()

    def _set_all_click_through(self, click_through: bool) -> None:
        for cfg in self._config.overlays:
            cfg.click_through = click_through
            win = self._overlay_windows.get(cfg.id)
            if win:
                win.set_click_through(click_through)
            row = self._row_widgets.get(cfg.id)
            if row:
                row.set_click_through(click_through)
        self._schedule_config_save()

    def _on_row_visible_toggled(self, overlay_id: str, visible: bool) -> None:
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return
        cfg.visible = visible
        if visible:
            win.show()
            if hasattr(win, "ensure_topmost"):
                win.ensure_topmost()
        else:
            win.hide()
        self._schedule_config_save()

    def _on_row_locked_toggled(self, overlay_id: str, locked: bool) -> None:
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return
        cfg.locked = locked
        win.set_locked(locked)
        self._schedule_config_save()

    def _on_row_click_through_toggled(self, overlay_id: str, click_through: bool) -> None:
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return
        cfg.click_through = click_through
        win.set_click_through(click_through)
        self._schedule_config_save()

    def _update_config_from_window(self, overlay_id: str) -> None:
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return

        g = win.geometry()
        cfg.x, cfg.y, cfg.width, cfg.height = g.x(), g.y(), g.width(), g.height()
        # keep size controls in sync
        if overlay_id == self._get_selected_id():
            self._width_spin.blockSignals(True)
            self._height_spin.blockSignals(True)
            self._width_spin.setValue(cfg.width)
            self._height_spin.setValue(cfg.height)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)

    def _on_size_changed(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return

        new_w = self._width_spin.value()
        new_h = self._height_spin.value()
        geom = win.geometry()
        geom.setWidth(new_w)
        geom.setHeight(new_h)
        win.setGeometry(geom)

        cfg.width = new_w
        cfg.height = new_h
        self._schedule_config_save()

    def _on_reload_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        win = self._overlay_windows.get(overlay_id)
        if isinstance(win, WebOverlayWindow):
            win.reload()

    def _on_hotkey_changed(self, sequence: QKeySequence) -> None:
        hotkey_text = sequence.toString(QKeySequence.PortableText).strip()
        if not hotkey_text:
            return

        applied_hotkey = hotkey_text
        if self._hotkey_apply_callback is not None:
            applied_hotkey = self._hotkey_apply_callback(hotkey_text)

        if not applied_hotkey:
            applied_hotkey = self._config.chat_hotkey or "F8"

        if applied_hotkey != hotkey_text:
            self._hotkey_edit.blockSignals(True)
            self._hotkey_edit.setKeySequence(QKeySequence(applied_hotkey))
            self._hotkey_edit.blockSignals(False)

        if self._config.chat_hotkey != applied_hotkey:
            self._config.chat_hotkey = applied_hotkey
            self._schedule_config_save()

        self._update_hotkey_hint(applied_hotkey)

    def _on_focus_hotkey_enabled_toggled(self, enabled: bool) -> None:
        applied = enabled
        if self._hotkey_enabled_callback is not None:
            applied = self._hotkey_enabled_callback(enabled)
        self._update_hotkey_enabled_button(applied)
        if applied != enabled:
            self._btn_hotkey_enabled.blockSignals(True)
            self._btn_hotkey_enabled.setChecked(applied)
            self._btn_hotkey_enabled.blockSignals(False)
        if self._config.focus_hotkey_enabled != applied:
            self._config.focus_hotkey_enabled = applied
            self._schedule_config_save()
        self._update_hotkey_hint(self._config.chat_hotkey)

    def _set_theme_from_ui(self, theme: ThemeType) -> None:
        self._apply_theme(theme)
        self._sync_theme_buttons(theme)
        if self._config.theme != theme:
            self._config.theme = theme
            self._schedule_config_save()

    def _on_overlay_hotkey_changed(self, sequence: QKeySequence) -> None:
        if self._is_loading_selection:
            return
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        cfg = self._find_config(overlay_id)
        if not cfg:
            return

        hotkey_text = sequence.toString(QKeySequence.PortableText).strip()
        applied = hotkey_text
        if self._overlay_hotkey_callback is not None:
            applied = self._overlay_hotkey_callback(overlay_id, hotkey_text)

        if applied != hotkey_text:
            self._overlay_hotkey_edit.blockSignals(True)
            self._overlay_hotkey_edit.setKeySequence(QKeySequence(applied))
            self._overlay_hotkey_edit.blockSignals(False)

        cfg.toggle_hotkey = applied
        self._btn_clear_overlay_hotkey.setEnabled(bool(applied))
        self._schedule_config_save()

    def _on_clear_overlay_hotkey(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        cfg = self._find_config(overlay_id)
        if not cfg:
            return
        if self._overlay_hotkey_callback is not None:
            self._overlay_hotkey_callback(overlay_id, "")
        cfg.toggle_hotkey = ""
        self._overlay_hotkey_edit.blockSignals(True)
        self._overlay_hotkey_edit.setKeySequence(QKeySequence())
        self._overlay_hotkey_edit.blockSignals(False)
        self._btn_clear_overlay_hotkey.setEnabled(False)
        self._schedule_config_save()

    def toggle_overlay_visibility_by_id(self, overlay_id: str) -> None:
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return
        cfg.visible = not cfg.visible
        if cfg.visible:
            win.show()
            if hasattr(win, "ensure_topmost"):
                win.ensure_topmost()
        else:
            win.hide()
        row = self._row_widgets.get(overlay_id)
        if row:
            row.set_visible(cfg.visible)
        self._schedule_config_save()

    def _refresh_overlay_topmost(self) -> None:
        for cfg in self._config.overlays:
            if not cfg.visible:
                continue
            win = self._overlay_windows.get(cfg.id)
            if win:
                if hasattr(win, "ensure_topmost"):
                    win.ensure_topmost()

    def _on_fit_content_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        win = self._overlay_windows.get(overlay_id)
        if isinstance(win, ImageOverlayWindow):
            win.fit_to_content()
            self._update_config_from_window(overlay_id)
            self._schedule_config_save()

    def focus_chat_input_hotkey(self) -> None:
        if not self._config.focus_hotkey_enabled:
            return
        target_id = self._get_selected_id()
        if target_id is None:
            for cfg in self._config.overlays:
                if cfg.type == "web" and cfg.visible:
                    target_id = cfg.id
                    break
        if target_id is None:
            return

        cfg = self._find_config(target_id)
        win = self._overlay_windows.get(target_id)
        if not cfg or not isinstance(win, WebOverlayWindow):
            return

        # Toggle behavior: second press exits chat mode and restores click-through.
        if self._chat_focus_overlay_id == target_id:
            if self._chat_focus_was_click_through:
                cfg.click_through = True
                win.set_click_through(True)
                row = self._row_widgets.get(target_id)
                if row:
                    row.set_click_through(True)
                self._schedule_config_save()
            self._chat_focus_overlay_id = None
            self._chat_focus_was_click_through = False
            return

        self._chat_focus_overlay_id = target_id
        self._chat_focus_was_click_through = cfg.click_through
        if cfg.click_through:
            cfg.click_through = False
            win.set_click_through(False)
            row = self._row_widgets.get(target_id)
            if row:
                row.set_click_through(False)
            self._schedule_config_save()

        if not cfg.visible:
            cfg.visible = True
            win.show()
            if hasattr(win, "ensure_topmost"):
                win.ensure_topmost()
            row = self._row_widgets.get(target_id)
            if row:
                row.set_visible(True)
            self._schedule_config_save()

        win.focus_chat_input()

    def prepare_for_quit(self) -> None:
        self._allow_close = True
        self.close()

    def _on_quit_clicked(self) -> None:
        if self._on_quit_requested is not None:
            self._on_quit_requested()
            return
        self.prepare_for_quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close:
            self.hide()
            event.ignore()
            return
        self._topmost_timer.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_config()
        return super().closeEvent(event)

