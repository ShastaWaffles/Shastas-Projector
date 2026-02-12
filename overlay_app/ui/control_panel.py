from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

from PySide6.QtCore import QEvent, QSize, QTimer, Qt, QEventLoop, QUrl
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QKeySequence, QPixmap, QResizeEvent, QDesktopServices, QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QMenu,
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
    QInputDialog,
    QMessageBox,
    QFormLayout,
    QToolButton,
    QSpinBox,
    QSplitter,
    QKeySequenceEdit,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
)

from overlay_app.models.config import AppConfig, OverlayConfig, OverlayProfile, CaptureRect, ThemeType
from overlay_app.overlays.image_overlay import ImageOverlayWindow
from overlay_app.overlays.screen_capture_overlay import ScreenCaptureOverlay
from overlay_app.overlays.web_overlay import WebOverlayWindow
from overlay_app.ui.region_picker import RegionPickerOverlay
from overlay_app.ui.window_picker import WindowPickerDialog
from overlay_app.ui.window_crop_picker import WindowCropPickerDialog

# Minimal dark theme: near-black, dark gray panels, soft purple accent
CONTROL_PANEL_DARK_QSS = """
    QWidget { background-color: #0B0D10; color: #E7EAF0; }
    QLabel { color: #E7EAF0; font-size: 14px; background: transparent; }
    QLabel[class="muted"] { color: #AAB2C0; font-size: 12px; }
    QLabel[class="section"] { color: #8B5CF6; font-size: 12px; font-weight: bold; margin-top: 6px; margin-bottom: 2px; letter-spacing: 0.5px; }
    QListWidget {
        background-color: #0B0D10; border: 1px solid #2a3140; border-radius: 12px;
        padding: 6px; outline: none;
    }
    QListWidget::item {
        padding: 0; margin: 2px; background: transparent; border-radius: 10px;
    }
    QListWidget::item:selected {
        background-color: rgba(139, 92, 246, 0.16);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-radius: 10px;
    }
    QListWidget::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.05); border-radius: 10px;
    }
    QLineEdit, QSpinBox, QKeySequenceEdit, QPlainTextEdit {
        background-color: #0B0D10; color: #E7EAF0; border: 1px solid #2a3140;
        border-radius: 8px; padding: 8px 12px; min-height: 24px; font-size: 14px;
    }
    QLineEdit:focus, QSpinBox:focus, QKeySequenceEdit:focus { border-color: #8B5CF6; }
    QSlider::groove:horizontal {
        height: 6px; background: #242C3A; border-radius: 3px;
    }
    QSlider::handle:horizontal {
        width: 14px; margin: -4px 0; background: #8B5CF6; border-radius: 7px;
    }
    QSlider::handle:horizontal:hover { background: #9d7af0; }
    QPushButton {
        background-color: #111318; color: #E7EAF0; border: 1px solid #2a3140;
        border-radius: 10px; padding: 8px 14px; min-height: 24px; font-size: 13px;
    }
    QPushButton:hover { background-color: #1e2430; border-color: #8B5CF6; color: #E7EAF0; }
    QPushButton:pressed { background-color: #242C3A; }
    QPushButton:disabled { color: #6b7280; }
    QPushButton[class="primary"] {
        background-color: #8B5CF6; border-color: #8B5CF6; color: #E7EAF0;
    }
    QPushButton[class="primary"]:hover {
        background-color: #9d7af0; border-color: #9d7af0; color: #E7EAF0;
    }
    QPushButton[class="primary"]:pressed { background-color: #7c3aed; border-color: #7c3aed; }
    QPushButton[class="primary"]:disabled { background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }
    QPushButton[class="action-primary"] {
        background-color: #eab308; border-color: #eab308; color: #0f0f14;
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }
    QPushButton[class="action-primary"]:hover {
        background-color: #facc15; border-color: #facc15;
    }
    QPushButton[class="action-primary"]:pressed { background-color: #ca8a04; border-color: #ca8a04; }
    QPushButton[class="action-primary"]:disabled { background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }
    QPushButton[class="action-secondary"] {
        background-color: rgba(168, 85, 247, 0.08);
        border: 1px solid rgba(168, 85, 247, 0.45);
        color: #f5f3ff;
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }
    QPushButton[class="action-secondary"]:hover {
        background-color: rgba(168, 85, 247, 0.16);
        border-color: rgba(168, 85, 247, 0.7);
    }
    QPushButton[class="action-secondary"]:pressed {
        background-color: rgba(168, 85, 247, 0.24);
    }
    QPushButton[class="action-secondary"]:disabled {
        background-color: rgba(168, 85, 247, 0.04);
        border-color: rgba(168, 85, 247, 0.2);
        color: #6b7280;
    }
    QPushButton[class="action-primary"] {
        background-color: #8B5CF6; border-color: #8B5CF6; color: #E7EAF0;
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }
    QPushButton[class="action-primary"]:hover {
        background-color: #9d7af0; border-color: #9d7af0;
    }
    QPushButton[class="action-primary"]:pressed { background-color: #7c3aed; border-color: #7c3aed; }
    QPushButton[class="action-primary"]:disabled { background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }
    QPushButton[class="action-secondary"] {
        background-color: rgba(139, 92, 246, 0.08);
        border: 1px solid rgba(139, 92, 246, 0.45);
        color: #E7EAF0;
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }
    QPushButton[class="action-secondary"]:hover {
        background-color: rgba(139, 92, 246, 0.16);
        border-color: rgba(139, 92, 246, 0.7);
    }
    QPushButton[class="action-secondary"]:pressed {
        background-color: rgba(139, 92, 246, 0.24);
    }
    QPushButton[class="action-secondary"]:disabled {
        background-color: rgba(139, 92, 246, 0.04);
        border-color: rgba(139, 92, 246, 0.2);
        color: #6b7280;
    }
    QPushButton[class="subtle"] { background: transparent; border: none; color: #AAB2C0; }
    QPushButton[class="subtle"]:hover { color: #8B5CF6; }
    QPushButton[class="destructive"]:hover { border-color: #c62828; color: #ef5350; }
    QPushButton[class="compact"] { font-size: 12px; padding: 6px 12px; min-height: 22px; }
    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QTabWidget::pane {
        border: 1px solid #2a3140;
        border-radius: 12px; background: #0B0D10;
        margin-top: 6px; padding: 12px 14px 18px 14px;
    }
    QTabBar {
        background: #111318;
        border: 1px solid #2a3140;
        border-radius: 12px;
        padding: 4px;
    }
    QTabBar::tab {
        background: transparent; color: #AAB2C0;
        padding: 8px 16px; margin-right: 4px;
        border: none;
        border-radius: 8px; font-size: 13px;
    }
    QTabBar::tab:selected {
        background: #8B5CF6; color: #E7EAF0;
    }
    QTabBar::tab:hover:!selected {
        background: #1a1f2e; color: #E7EAF0;
    }
    QMenu {
        background-color: #111318;
        color: #E7EAF0;
        border: 1px solid #2a3140;
        padding: 4px 0;
    }
    QMenu::item {
        padding: 6px 14px;
        background: transparent;
    }
    QMenu::item:selected {
        background-color: #8B5CF6;
        color: #E7EAF0;
    }
    QFrame#HeroHeader {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba(139, 92, 246, 0.06), stop: 0.65 rgba(139, 92, 246, 0.03), stop: 1 rgba(139, 92, 246, 0.14));
        border: 1px solid #2a3140;
        border-radius: 14px;
    }
    QLabel#HeaderIcon {
        background: transparent;
        border: none;
        padding: 0;
    }
    QLabel[class="header-title"] {
        font-size: 16px;
        font-weight: 700;
        margin: 0;
        padding: 0;
    }
    QLabel[class="header-subtitle"] {
        font-size: 11px;
        color: #AAB2C0;
        margin: -2px 0 0 0;
        padding: 0;
    }
    QLabel[class="header-meta"] {
        font-size: 11px;
        color: #AAB2C0;
    }
    QFrame#HeaderGlow {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba(139, 92, 246, 0.0), stop: 0.5 rgba(139, 92, 246, 0.45), stop: 1 rgba(139, 92, 246, 0.0));
        border-radius: 1px;
    }
    QPushButton[class="header-cta"] {
        background-color: #111318;
        border: 1px solid #8B5CF6;
        color: #E7EAF0;
        border-radius: 10px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton[class="header-cta"]:hover {
        background-color: #1e2430;
        border-color: #9d7af0;
    }
    QPushButton[class="header-cta"]:pressed {
        background-color: #242C3A;
        border-color: #7c3aed;
    }
"""


def _hex_to_rgba_015(hex_color: str) -> str:
    """Convert #RRGGBB to 'r, g, b' for rgba(r, g, b, 0.15)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "139, 92, 246"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"


def _theme_qss(
    bg: str,
    bg_panel: str,
    border: str,
    border_light: str,
    accent: str,
    accent_hover: str,
    accent_pressed: str,
    text: str,
    text_muted: str,
) -> str:
    """Build full QSS for a dark theme with given palette."""
    rgba = _hex_to_rgba_015(accent)
    return f"""
    QWidget {{ background-color: {bg}; color: {text}; }}
    QLabel {{ color: {text}; font-size: 14px; background: transparent; }}
    QLabel[class="muted"] {{ color: {text_muted}; font-size: 12px; }}
    QLabel[class="section"] {{ color: {accent}; font-size: 12px; font-weight: bold; margin-top: 6px; margin-bottom: 2px; letter-spacing: 0.5px; }}
    QListWidget {{
        background-color: {bg}; border: 1px solid {border}; border-radius: 12px;
        padding: 6px; outline: none;
    }}
    QListWidget::item {{
        padding: 0; margin: 2px; background: transparent; border-radius: 10px;
    }}
    QListWidget::item:selected {{
        background-color: rgba({rgba}, 0.16);
        border: 1px solid rgba({rgba}, 0.35);
        border-radius: 10px;
    }}
    QListWidget::item:hover:!selected {{
        background-color: rgba(255, 255, 255, 0.06); border-radius: 10px;
    }}
    QLineEdit, QSpinBox, QKeySequenceEdit, QPlainTextEdit {{
        background-color: {bg}; color: {text}; border: 1px solid {border};
        border-radius: 8px; padding: 8px 12px; min-height: 24px; font-size: 14px;
    }}
    QLineEdit:focus, QSpinBox:focus, QKeySequenceEdit:focus {{ border-color: {accent}; }}
    QSlider::groove:horizontal {{
        height: 6px; background: {border_light}; border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 14px; margin: -4px 0; background: {accent}; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {accent_hover}; }}
    QPushButton {{
        background-color: {bg_panel}; color: {text}; border: 1px solid {border};
        border-radius: 10px; padding: 8px 14px; min-height: 24px; font-size: 13px;
    }}
    QPushButton:hover {{ background-color: {border_light}; border-color: {accent}; color: {text}; }}
    QPushButton:pressed {{ background-color: {border}; }}
    QPushButton:disabled {{ color: #6b7280; }}
    QPushButton[class="primary"] {{
        background-color: {accent}; border-color: {accent}; color: #E7EAF0;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {accent_hover}; border-color: {accent_hover}; color: #E7EAF0;
    }}
    QPushButton[class="primary"]:pressed {{ background-color: {accent_pressed}; border-color: {accent_pressed}; }}
    QPushButton[class="primary"]:disabled {{ background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }}
    QPushButton[class="action-primary"] {{
        background-color: {accent}; border-color: {accent}; color: #E7EAF0;
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }}
    QPushButton[class="action-primary"]:hover {{
        background-color: {accent_hover}; border-color: {accent_hover};
    }}
    QPushButton[class="action-primary"]:pressed {{ background-color: {accent_pressed}; border-color: {accent_pressed}; }}
    QPushButton[class="action-primary"]:disabled {{ background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }}
    QPushButton[class="action-secondary"] {{
        background-color: rgba({rgba}, 0.08);
        border: 1px solid rgba({rgba}, 0.45);
        color: {text};
        border-radius: 12px; padding: 8px 16px; font-weight: 600;
    }}
    QPushButton[class="action-secondary"]:hover {{
        background-color: rgba({rgba}, 0.16);
        border-color: rgba({rgba}, 0.7);
    }}
    QPushButton[class="action-secondary"]:pressed {{
        background-color: rgba({rgba}, 0.24);
    }}
    QPushButton[class="action-secondary"]:disabled {{
        background-color: rgba({rgba}, 0.04);
        border-color: rgba({rgba}, 0.2);
        color: #6b7280;
    }}
    QPushButton[class="subtle"] {{ background: transparent; border: none; color: {text_muted}; }}
    QPushButton[class="subtle"]:hover {{ color: {accent}; }}
    QPushButton[class="destructive"]:hover {{ border-color: #c62828; color: #ef5350; }}
    QPushButton[class="compact"] {{ font-size: 12px; padding: 6px 12px; min-height: 22px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 12px; background: {bg};
        margin-top: 6px; padding: 12px 14px 18px 14px;
    }}
    QTabBar {{
        background: {bg_panel};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 4px;
    }}
    QTabBar::tab {{
        background: transparent; color: {text_muted};
        padding: 8px 16px; margin-right: 4px;
        border: none;
        border-radius: 8px; font-size: 13px;
    }}
    QTabBar::tab:selected {{
        background: {accent}; color: #E7EAF0;
    }}
    QTabBar::tab:hover:!selected {{
        background: {border_light}; color: {text};
    }}
    QMenu {{
        background-color: {bg_panel};
        color: {text};
        border: 1px solid {border};
        padding: 4px 0;
    }}
    QMenu::item {{
        padding: 6px 14px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background-color: {accent_hover};
        color: #E7EAF0;
    }}
    QFrame#HeroHeader {{
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba({rgba}, 0.06), stop: 0.65 rgba({rgba}, 0.03), stop: 1 rgba({rgba}, 0.14));
        border: 1px solid {border};
        border-radius: 14px;
    }}
    QLabel#HeaderIcon {{
        background: transparent;
        border: none;
        padding: 0;
    }}
    QLabel[class="header-title"] {{
        font-size: 16px;
        font-weight: 700;
        margin: 0;
        padding: 0;
    }}
    QLabel[class="header-subtitle"] {{
        font-size: 11px;
        color: {text_muted};
        margin: -2px 0 0 0;
        padding: 0;
    }}
    QLabel[class="header-meta"] {{
        font-size: 11px;
        color: {text_muted};
    }}
    QFrame#HeaderGlow {{
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba({rgba}, 0.0), stop: 0.5 rgba({rgba}, 0.45), stop: 1 rgba({rgba}, 0.0));
        border-radius: 1px;
    }}
    QPushButton[class="header-cta"] {{
        background-color: {bg_panel};
        border: 1px solid {accent};
        color: {text};
        border-radius: 10px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton[class="header-cta"]:hover {{
        background-color: {border_light};
        border-color: {accent_hover};
    }}
    QPushButton[class="header-cta"]:pressed {{
        background-color: {border};
        border-color: {accent_pressed};
    }}
    """


# Full theme QSS: Ember (reds/oranges), Sea (blues), Emerald (greens)
CONTROL_PANEL_EMBER_QSS = _theme_qss(
    bg="#1a0f0a",
    bg_panel="#251510",
    border="#3d2318",
    border_light="#4a2a1c",
    accent="#ea580c",
    accent_hover="#f97316",
    accent_pressed="#c2410c",
    text="#fef3e8",
    text_muted="#d4a574",
)
CONTROL_PANEL_SEA_QSS = _theme_qss(
    bg="#0a0f14",
    bg_panel="#0f1820",
    border="#1e3a4a",
    border_light="#243d52",
    accent="#0284c7",
    accent_hover="#0ea5e9",
    accent_pressed="#0369a1",
    text="#e8f4fc",
    text_muted="#7dd3fc",
)
CONTROL_PANEL_EMERALD_QSS = _theme_qss(
    bg="#0a100d",
    bg_panel="#0f1812",
    border="#1a2e24",
    border_light="#234a36",
    accent="#059669",
    accent_hover="#10b981",
    accent_pressed="#047857",
    text="#e8f5f0",
    text_muted="#6ee7b7",
)
CONTROL_PANEL_CHERRY_QSS = _theme_qss(
    bg="#1a0a12",
    bg_panel="#251018",
    border="#3d1a2a",
    border_light="#4a2438",
    accent="#db2777",
    accent_hover="#ec4899",
    accent_pressed="#be185d",
    text="#fdf2f8",
    text_muted="#f9a8d4",
)
CONTROL_PANEL_PASTEL_QSS = _theme_qss(
    bg="#221e28",
    bg_panel="#2a2532",
    border="#3d3548",
    border_light="#4a4058",
    accent="#a78bfa",
    accent_hover="#c4b5fd",
    accent_pressed="#8b5cf6",
    text="#f5f3ff",
    text_muted="#c4b5fd",
)
CONTROL_PANEL_NEON_QSS = _theme_qss(
    bg="#0d0208",
    bg_panel="#1a0510",
    border="#3d0a20",
    border_light="#5c1530",
    accent="#ff006e",
    accent_hover="#ff2d92",
    accent_pressed="#c71585",
    text="#ffe4ec",
    text_muted="#ff85c1",
)
CONTROL_PANEL_DUCKY_QSS = _theme_qss(
    # Much brighter, more yellow overall
    bg="#11100a",            # dark but with a warm yellow tint
    bg_panel="#1b1809",      # slightly brighter panel
    border="#4b3f16",        # warm golden-brown border
    border_light="#5b4c1a",  # lighter border for hovers
    accent="#fde047",        # very bright yellow
    accent_hover="#facc15",  # strong ducky yellow
    accent_pressed="#eab308",# deeper pressed yellow
    text="#fefce8",          # soft off‑white
    text_muted="#fef9c3",    # pale yellow for muted text
)
# Fashionably Late: rainbow theme — each accent role gets a different color (ROYGBV)
CONTROL_PANEL_LATE_QSS = """
    QWidget { background-color: #0f0f14; color: #f5f3ff; }
    QLabel { color: #f5f3ff; font-size: 14px; background: transparent; }
    QLabel[class="muted"] { color: #a1a1aa; font-size: 12px; }
    QLabel[class="section"] { color: #ef4444; font-size: 12px; font-weight: bold; margin-top: 6px; margin-bottom: 2px; letter-spacing: 0.5px; }
    QListWidget {
        background-color: #0f0f14; border: 1px solid #27272a; border-radius: 12px;
        padding: 6px; outline: none;
    }
    QListWidget::item {
        padding: 0; margin: 2px; background: transparent; border-radius: 10px;
    }
    QListWidget::item:selected {
        background-color: rgba(34, 197, 94, 0.16);
        border: 1px solid rgba(34, 197, 94, 0.35);
        border-radius: 10px;
    }
    QListWidget::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.06); border-radius: 10px;
    }
    QLineEdit, QSpinBox, QKeySequenceEdit, QPlainTextEdit {
        background-color: #0f0f14; color: #f5f3ff; border: 1px solid #27272a;
        border-radius: 8px; padding: 8px 12px; min-height: 24px; font-size: 14px;
    }
    QLineEdit:focus, QSpinBox:focus, QKeySequenceEdit:focus { border-color: #8b5cf6; }
    QSlider::groove:horizontal {
        height: 6px; background: #27272a; border-radius: 3px;
    }
    QSlider::handle:horizontal {
        width: 14px; margin: -4px 0; background: #f97316; border-radius: 7px;
    }
    QSlider::handle:horizontal:hover { background: #fb923c; }
    QPushButton {
        background-color: #18181b; color: #f5f3ff; border: 1px solid #27272a;
        border-radius: 10px; padding: 8px 14px; min-height: 24px; font-size: 13px;
    }
    QPushButton:hover { background-color: #27272a; border-color: #8b5cf6; color: #f5f3ff; }
    QPushButton:pressed { background-color: #3f3f46; }
    QPushButton:disabled { color: #6b7280; }
    QPushButton[class="primary"] {
        background-color: #eab308; border-color: #eab308; color: #0f0f14;
    }
    QPushButton[class="primary"]:hover {
        background-color: #facc15; border-color: #facc15; color: #0f0f14;
    }
    QPushButton[class="primary"]:pressed { background-color: #ca8a04; border-color: #ca8a04; }
    QPushButton[class="primary"]:disabled { background-color: #3f3f46; border-color: #3f3f46; color: #6b7280; }
    QPushButton[class="subtle"] { background: transparent; border: none; color: #a1a1aa; }
    QPushButton[class="subtle"]:hover { color: #8b5cf6; }
    QPushButton[class="destructive"]:hover { border-color: #c62828; color: #ef5350; }
    QPushButton[class="compact"] { font-size: 12px; padding: 6px 12px; min-height: 22px; }
    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QTabWidget::pane {
        border: 1px solid #27272a;
        border-radius: 12px; background: #0f0f14;
        margin-top: 6px; padding: 12px 14px 18px 14px;
    }
    QTabBar {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 4px;
    }
    QTabBar::tab {
        background: transparent; color: #a1a1aa;
        padding: 8px 16px; margin-right: 4px;
        border: none;
        border-radius: 8px; font-size: 13px;
    }
    QTabBar::tab:selected {
        background: #3b82f6; color: #E7EAF0;
    }
    QTabBar::tab:hover:!selected {
        background: #27272a; color: #f5f3ff;
    }
    QFrame#HeroHeader {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba(168, 85, 247, 0.06), stop: 0.65 rgba(168, 85, 247, 0.03), stop: 1 rgba(168, 85, 247, 0.14));
        border: 1px solid #27272a;
        border-radius: 14px;
    }
    QLabel#HeaderIcon {
        background: transparent;
        border: none;
        padding: 0;
    }
    QLabel[class="header-title"] {
        font-size: 16px;
        font-weight: 700;
        margin: 0;
        padding: 0;
    }
    QLabel[class="header-subtitle"] {
        font-size: 11px;
        color: #a1a1aa;
        margin: -2px 0 0 0;
        padding: 0;
    }
    QLabel[class="header-meta"] {
        font-size: 11px;
        color: #a1a1aa;
    }
    QFrame#HeaderGlow {
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba(168, 85, 247, 0.0), stop: 0.5 rgba(168, 85, 247, 0.45), stop: 1 rgba(168, 85, 247, 0.0));
        border-radius: 1px;
    }
    QPushButton[class="header-cta"] {
        background-color: #18181b;
        border: 1px solid #a855f7;
        color: #f5f3ff;
        border-radius: 10px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton[class="header-cta"]:hover {
        background-color: #27272a;
        border-color: #c084fc;
    }
    QPushButton[class="header-cta"]:pressed {
        background-color: #3f3f46;
        border-color: #a855f7;
    }
    """

# Fire Nation: red theme throughout
CONTROL_PANEL_FIRE_QSS = _theme_qss(
    bg="#140808",
    bg_panel="#220a0a",
    border="#3d1515",
    border_light="#5c2020",
    accent="#dc2626",
    accent_hover="#f87171",
    accent_pressed="#b91c1c",
    text="#fef2f2",
    text_muted="#fca5a5",
)

# Galaxy: deep space purples and blues
CONTROL_PANEL_GALAXY_QSS = _theme_qss(
    bg="#0d0a14",
    bg_panel="#151020",
    border="#2a2040",
    border_light="#3a3050",
    accent="#7c3aed",
    accent_hover="#a78bfa",
    accent_pressed="#5b21b6",
    text="#f5f3ff",
    text_muted="#a78bfa",
)

# Per-theme colors for widgets that use setStyleSheet (list item icons, badge, etc.)
THEME_COLORS: dict[ThemeType, tuple[str, str, str, str]] = {
    "dark": ("#8B5CF6", "#9d7af0", "#AAB2C0", "139, 92, 246"),
    "light": ("#6366f1", "#818cf8", "#64748b", "99, 102, 241"),
    "ember": ("#ea580c", "#f97316", "#d4a574", "234, 88, 12"),
    "sea": ("#0284c7", "#0ea5e9", "#7dd3fc", "2, 132, 199"),
    "emerald": ("#059669", "#10b981", "#6ee7b7", "5, 150, 105"),
    "cherry": ("#db2777", "#ec4899", "#f9a8d4", "219, 39, 119"),
    "pastel": ("#a78bfa", "#c4b5fd", "#c4b5fd", "167, 139, 250"),
    "neon": ("#ff006e", "#ff2d92", "#ff85c1", "255, 0, 110"),
    "late": ("#a855f7", "#c084fc", "#c4b5fd", "168, 85, 247"),
    "fire": ("#dc2626", "#f87171", "#fca5a5", "220, 38, 38"),
    "galaxy": ("#7c3aed", "#a78bfa", "#a78bfa", "124, 58, 237"),
    # Ducky: lots of bright yellow for icons/badges/accents
    "ducky": ("#fde047", "#facc15", "#fef9c3", "253, 224, 71"),
}


def _section_header(text: str) -> QLabel:
    out = QLabel(text)
    out.setProperty("class", "section")
    return out


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setProperty("class", "divider")
    line.setFixedHeight(1)
    return line


def _header_icon_pixmap() -> QPixmap:
    base = Path(__file__).resolve().parent.parent
    for name in ("shastas_projector.png", "projectoricon.png"):
        path = base / "resources" / name
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                return pix
    return QPixmap()


# Font Awesome 6/7 solid (fa-solid-900) Unicode PUA codepoints
FA_EYE = "\uf06e"
FA_EYE_SLASH = "\uf070"
FA_LOCK = "\uf023"
FA_UNLOCK = "\uf09c"
FA_HAND_POINTER = "\uf25a"
FA_BORDER_NONE = "\uf850"
FA_TRASH_CAN = "\uf2ed"
# Type icons: web=globe, image=image, region=object-group (solid), window=window-maximize (regular)
FA_GLOBE = "\uf0ac"
FA_IMAGE = "\uf03e"
FA_OBJECT_GROUP = "\uf247"
FA_WINDOW_MAXIMIZE = "\uf2d0"
FA_TOGGLE_ON = "\uf205"
FA_TOGGLE_OFF = "\uf204"
# Gear for Settings: FA classic solid gear is f013, but FA7 Free-Solid-900.otf may map it to arrow.
# Use Unicode GEAR (U+2699) with default font so a gear always displays.
GEAR_CHAR = "\u2699"

_FONT_AWESOME_FAMILY: Optional[str] = None
_FONT_AWESOME_REGULAR_FAMILY: Optional[str] = None


def _load_font_awesome() -> Optional[str]:
    """Load Font Awesome Solid from overlay_app/resources/fonts. Returns family name or None."""
    global _FONT_AWESOME_FAMILY
    if _FONT_AWESOME_FAMILY is not None:
        return _FONT_AWESOME_FAMILY
    base = Path(__file__).resolve().parent.parent
    fonts_dir = base / "resources" / "fonts"
    # Prefer Solid font (exact names first, then any *Solid*900*)
    candidates = [
        fonts_dir / "Font Awesome 7 Free-Solid-900.otf",
        fonts_dir / "fa-solid-900.otf",
        fonts_dir / "fa-solid-900.ttf",
        base / "resources" / "fa-solid-900.ttf",
    ]
    for path in candidates:
        if path.exists():
            fid = QFontDatabase.addApplicationFont(str(path))
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    _FONT_AWESOME_FAMILY = families[0]
                    return _FONT_AWESOME_FAMILY
    # Fallback: any font in fonts/ whose name suggests Solid 900
    if fonts_dir.exists():
        for path in fonts_dir.iterdir():
            if path.suffix.lower() in (".otf", ".ttf") and "solid" in path.stem.lower() and "900" in path.stem:
                fid = QFontDatabase.addApplicationFont(str(path))
                if fid != -1:
                    families = QFontDatabase.applicationFontFamilies(fid)
                    if families:
                        _FONT_AWESOME_FAMILY = families[0]
                        return _FONT_AWESOME_FAMILY
    return None


def _load_font_awesome_regular() -> Optional[str]:
    """Load Font Awesome Regular from overlay_app/resources/fonts. Returns family name or None."""
    global _FONT_AWESOME_REGULAR_FAMILY
    if _FONT_AWESOME_REGULAR_FAMILY is not None:
        return _FONT_AWESOME_REGULAR_FAMILY
    base = Path(__file__).resolve().parent.parent
    fonts_dir = base / "resources" / "fonts"
    candidates = [
        fonts_dir / "Font Awesome 7 Free-Regular-400.otf",
        fonts_dir / "fa-regular-400.otf",
        fonts_dir / "fa-regular-400.ttf",
    ]
    for path in candidates:
        if path.exists():
            fid = QFontDatabase.addApplicationFont(str(path))
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    _FONT_AWESOME_REGULAR_FAMILY = families[0]
                    return _FONT_AWESOME_REGULAR_FAMILY
    if fonts_dir.exists():
        for path in fonts_dir.iterdir():
            if path.suffix.lower() in (".otf", ".ttf") and "regular" in path.stem.lower() and "400" in path.stem and "solid" not in path.stem.lower():
                fid = QFontDatabase.addApplicationFont(str(path))
                if fid != -1:
                    families = QFontDatabase.applicationFontFamilies(fid)
                    if families:
                        _FONT_AWESOME_REGULAR_FAMILY = families[0]
                        return _FONT_AWESOME_REGULAR_FAMILY
    return None


# Explicit point sizes for icon fonts; QFont(family) uses pointSize -1 by default and triggers Qt warning on setFont/hover.
_ICON_FONT_POINT_SIZE = 10


def _icon_font() -> QFont:
    """QFont for Font Awesome icons; use constructor with point size so Qt never sees -1."""
    fa = _load_font_awesome()
    if fa:
        f = QFont(fa, _ICON_FONT_POINT_SIZE)
    else:
        f = QFont()
        f.setPointSize(_ICON_FONT_POINT_SIZE)
    return f


def _icon_font_regular() -> QFont:
    """QFont for Font Awesome Regular (e.g. window-maximize). Use constructor with point size so Qt never sees -1."""
    fa = _load_font_awesome_regular()
    if fa:
        f = QFont(fa, _ICON_FONT_POINT_SIZE)
    else:
        f = QFont()
        f.setPointSize(_ICON_FONT_POINT_SIZE)
    return f


def _type_icon_char(overlay_type: str, capture_mode: str = "region") -> str:
    """Return Font Awesome character for overlay type: web=globe, image=image, region=object-group, window=window-maximize."""
    if overlay_type == "web":
        return FA_GLOBE
    if overlay_type == "image":
        return FA_IMAGE
    if overlay_type == "screen":
        return FA_OBJECT_GROUP if capture_mode == "region" else FA_WINDOW_MAXIMIZE
    return FA_GLOBE


def _type_icon_use_regular(overlay_type: str, capture_mode: str = "region") -> bool:
    """True if this type icon uses the Regular font (window-maximize)."""
    return overlay_type == "screen" and capture_mode == "window"


THEME_DISPLAY_ORDER: list[tuple[str, ThemeType]] = [
    ("Dark", "dark"),
    ("Light", "light"),
    ("Ember", "ember"),
    ("Sea Blue", "sea"),
    ("Emerald", "emerald"),
    ("Cherry Blossom", "cherry"),
    ("Pastel Dreams", "pastel"),
    ("Neon Pink", "neon"),
    ("Fashionably Late", "late"),
    ("Fire Nation", "fire"),
    ("Galaxy", "galaxy"),
    ("Ducky", "ducky"),
]


class SettingsDialog(QDialog):
    """Popup for app settings (theme, panel behavior, etc.)."""

    def __init__(
        self,
        current_theme: ThemeType,
        on_theme_changed: Callable[[ThemeType], None],
        keep_on_top: bool,
        on_keep_on_top_changed: Callable[[bool], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        self.setMaximumSize(600, 500)
        self._on_theme_changed = on_theme_changed
        self._on_keep_on_top_changed = on_keep_on_top_changed

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Theme selector
        self._theme_combo = QComboBox()
        theme_values = [t[1] for t in THEME_DISPLAY_ORDER]
        self._theme_combo.addItems([t[0] for t in THEME_DISPLAY_ORDER])
        idx = theme_values.index(current_theme) if current_theme in theme_values else 0
        self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        form.addRow("Theme", self._theme_combo)

        # Panel behavior
        self._keep_on_top_checkbox = QCheckBox("Keep control panel on top")
        self._keep_on_top_checkbox.setChecked(keep_on_top)
        self._keep_on_top_checkbox.toggled.connect(self._on_keep_on_top_toggled)
        form.addRow("Control panel", self._keep_on_top_checkbox)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.setMinimumWidth(280)

    def _on_theme_selected(self, index: int) -> None:
        theme_values = [t[1] for t in THEME_DISPLAY_ORDER]
        if 0 <= index < len(theme_values):
            self._on_theme_changed(theme_values[index])

    def _on_keep_on_top_toggled(self, checked: bool) -> None:
        self._on_keep_on_top_changed(checked)


class OverlayListItemWidget(QWidget):
    """Row widget: type icon + overlay name + subtitle + trash + visible/locked/click-through icon buttons."""

    _ICON_STYLE = (
        "QToolButton { color: #AAB2C0; border: none; background: transparent; min-width: 24px; min-height: 24px; } "
        "QToolButton:checked { color: #8B5CF6; } "
        "QToolButton:hover { color: #E7EAF0; }"
    )

    def __init__(
        self,
        overlay_id: str,
        name: str,
        subtitle: str,
        overlay_type: str,
        capture_mode: str,
        visible: bool,
        locked: bool,
        click_through: bool,
        on_visible_toggled,
        on_locked_toggled,
        on_click_through_toggled,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._overlay_id = overlay_id
        self._visible = visible
        self._locked = locked
        self._click_through = click_through
        icon_font = _icon_font()
        type_char = _type_icon_char(overlay_type, capture_mode)
        use_regular = _type_icon_use_regular(overlay_type, capture_mode)
        type_font = _icon_font_regular() if use_regular else icon_font

        self._type_icon_label = QLabel(type_char)
        self._type_icon_label.setFont(type_font)
        self._type_icon_label.setStyleSheet("color: #8B5CF6; min-width: 20px;")
        self._type_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._type_icon_label.setFixedWidth(24)

        self._full_name = name
        self._full_subtitle = subtitle
        self._name_label = QLabel(name)
        self._name_label.setStyleSheet("font-weight: bold;")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setProperty("class", "muted")
        # Explicit font with positive point size so stylesheet/hover never triggers QFont::setPointSize(-1) warning
        sub_font = QFont()
        sub_font.setPointSize(11)
        self._subtitle_label.setFont(sub_font)
        self._subtitle_label.setStyleSheet("color: #AAB2C0; font-weight: normal;")
        self._subtitle_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._detail_tooltip = ""  # set via set_detail_tooltip(); full URL/region on hover

        self._btn_visible = QToolButton()
        self._btn_visible.setCheckable(True)
        self._btn_visible.setChecked(visible)
        self._btn_visible.setFont(icon_font)
        self._btn_visible.setStyleSheet(self._ICON_STYLE)
        self._btn_visible.setToolTip("Toggle visibility")
        self._btn_visible.setFixedWidth(28)
        self._btn_visible.toggled.connect(on_visible_toggled)
        self._btn_visible.toggled.connect(self._update_icons)

        self._btn_locked = QToolButton()
        self._btn_locked.setCheckable(True)
        self._btn_locked.setChecked(locked)
        self._btn_locked.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._btn_locked.setFont(icon_font)
        self._btn_locked.setStyleSheet(self._ICON_STYLE)
        self._btn_locked.setToolTip("Lock movement / Unlock movement")
        self._btn_locked.setFixedWidth(28)
        self._btn_locked.toggled.connect(on_locked_toggled)
        self._btn_locked.toggled.connect(self._update_icons)

        self._btn_click_through = QToolButton()
        self._btn_click_through.setCheckable(True)
        self._btn_click_through.setChecked(click_through)
        self._btn_click_through.setFont(icon_font)
        self._btn_click_through.setStyleSheet(self._ICON_STYLE)
        self._btn_click_through.setToolTip("Toggle click-through")
        self._btn_click_through.setFixedWidth(28)
        self._btn_click_through.toggled.connect(on_click_through_toggled)
        self._btn_click_through.toggled.connect(self._update_icons)

        self._update_icons()

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.addWidget(self._name_label)
        text_col.addWidget(self._subtitle_label)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        layout.addWidget(self._type_icon_label)
        layout.addLayout(text_col)
        layout.addStretch(1)
        layout.addSpacing(8)
        layout.addWidget(self._btn_visible)
        layout.addWidget(self._btn_locked)
        layout.addWidget(self._btn_click_through)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        """Fixed height so list rows don't stretch; comfortable for name + sub row."""
        return QSize(200, 52)

    def _update_icons(self) -> None:
        self._btn_visible.setText(FA_EYE if self._btn_visible.isChecked() else FA_EYE_SLASH)
        self._btn_locked.setText(FA_LOCK if self._btn_locked.isChecked() else FA_UNLOCK)
        self._btn_click_through.setText(FA_BORDER_NONE if self._btn_click_through.isChecked() else FA_HAND_POINTER)

    def set_name(self, name: str) -> None:
        self._full_name = name
        self._update_elided_text()

    def set_subtitle(self, subtitle: str) -> None:
        self._full_subtitle = subtitle
        self._update_elided_text()

    def set_detail_tooltip(self, tooltip: str) -> None:
        """Full detail (URL, region coords, window title) shown on hover over sub row."""
        self._detail_tooltip = tooltip or ""
        self._subtitle_label.setToolTip(self._detail_tooltip)

    def _update_elided_text(self) -> None:
        from PySide6.QtGui import QFontMetrics
        w = self.width()
        # Row width for text: name gets full line, subtitle (sub row) gets same width, truncated
        text_width = max(60, w - 120)
        fm_name = QFontMetrics(self._name_label.font())
        fm_sub = QFontMetrics(self._subtitle_label.font())
        # Show name in full when there's space; only elide when very narrow
        self._name_label.setText(fm_name.elidedText(self._full_name, Qt.TextElideMode.ElideRight, text_width))
        # Sub row: show part of link/region; full detail on hover (tooltip set by set_detail_tooltip)
        self._subtitle_label.setText(fm_sub.elidedText(self._full_subtitle, Qt.TextElideMode.ElideRight, text_width))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def set_visible(self, visible: bool) -> None:
        self._btn_visible.blockSignals(True)
        self._btn_visible.setChecked(visible)
        self._btn_visible.blockSignals(False)
        self._update_icons()

    def set_locked(self, locked: bool) -> None:
        self._btn_locked.blockSignals(True)
        self._btn_locked.setChecked(locked)
        self._btn_locked.blockSignals(False)
        self._update_icons()

    def set_click_through(self, click_through: bool) -> None:
        self._btn_click_through.blockSignals(True)
        self._btn_click_through.setChecked(click_through)
        self._btn_click_through.blockSignals(False)
        self._update_icons()

    def set_tools_visible(self, visible: bool) -> None:
        """Show or hide the overlay tools (visibility, lock, click-through)."""
        self._btn_visible.setVisible(visible)
        self._btn_locked.setVisible(visible)
        self._btn_click_through.setVisible(visible)

    def update_theme_colors(self, accent: str, accent_hover: str, text_muted: str) -> None:
        """Update inline styles to match current theme (called when panel theme changes)."""
        self._type_icon_label.setStyleSheet(f"color: {accent}; min-width: 20px;")
        self._subtitle_label.setStyleSheet(f"color: {text_muted}; font-weight: normal;")
        icon_style = (
            f"QToolButton {{ color: {text_muted}; border: none; background: transparent; min-width: 24px; min-height: 24px; }} "
            f"QToolButton:checked {{ color: {accent}; }} "
            f"QToolButton:hover {{ color: {accent_hover}; }}"
        )
        lock_style = (
            f"QToolButton {{ color: {text_muted}; border: none; background: transparent; min-width: 24px; min-height: 24px; }} "
            f"QToolButton:checked {{ color: {accent}; }} "
            f"QToolButton:hover {{ color: {accent_hover}; }}"
        )
        self._btn_visible.setStyleSheet(icon_style)
        self._btn_locked.setStyleSheet(lock_style)
        self._btn_click_through.setStyleSheet(icon_style)


class ControlPanel(QWidget):
    """Main control window for managing overlays."""

    def __init__(
        self,
        app_config: AppConfig,
        on_config_changed: Callable[[AppConfig], None],
        on_hotkey_changed: Optional[Callable[[str], str]] = None,
        on_focus_hotkey_enabled_changed: Optional[Callable[[bool], bool]] = None,
        on_overlay_hotkey_changed: Optional[Callable[[str, str], str]] = None,
        on_click_through_hotkey_changed: Optional[Callable[[str], str]] = None,
        on_quit_requested: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.setWindowTitle("Shastas Projector")
        self._config = app_config
        self._on_config_changed = on_config_changed
        self._hotkey_apply_callback = on_hotkey_changed
        self._hotkey_enabled_callback = on_focus_hotkey_enabled_changed
        self._overlay_hotkey_callback = on_overlay_hotkey_changed
        self._click_through_hotkey_callback = on_click_through_hotkey_changed
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
        self._apply_panel_on_top(self._config.keep_control_panel_on_top)
        # Ensure close button is always enabled (Windows can grey it out otherwise)
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self._is_loading_selection = False

        self._overlay_windows: Dict[str, QWidget] = {}
        self._row_widgets: Dict[str, OverlayListItemWidget] = {}
        self._config_by_id: Dict[str, OverlayConfig] = {}
        self._global_hotkeys_supported = sys.platform in ("win32", "darwin")

        self._list = QListWidget()
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setAlternatingRowColors(False)
        self._list.setUniformItemSizes(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setDragEnabled(True)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_overlay_list_context_menu)
        self._profile_combo = QComboBox()
        self._btn_new_profile = QPushButton("New")
        self._btn_rename_profile = QPushButton("Rename")
        self._btn_delete_profile = QPushButton("Delete")
        for btn in (self._btn_new_profile, self._btn_rename_profile, self._btn_delete_profile):
            btn.setProperty("class", "compact")
        self._name_edit = QLineEdit()
        self._source_edit = QLineEdit()
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(50, 300)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(150, 5000)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(150, 5000)
        self._btn_fit_content = QPushButton("Fit to Content")
        self._btn_reload = QPushButton("Reload Overlay")
        self._btn_fit_content.setProperty("class", "action-secondary")
        self._btn_reload.setProperty("class", "action-primary")
        self._btn_fit_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_reload.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_fit_content.setFixedHeight(42)
        self._btn_reload.setFixedHeight(42)
        self._btn_fit_content.setEnabled(False)
        self._btn_reload.setEnabled(False)

        self._btn_repick_region = QPushButton("Re-pick region")
        self._btn_repick_window = QPushButton("Re-pick window")
        self._btn_crop_window = QPushButton("Crop window…")
        self._capture_x_spin = QSpinBox()
        self._capture_x_spin.setRange(-10000, 10000)
        self._capture_y_spin = QSpinBox()
        self._capture_y_spin.setRange(-10000, 10000)
        self._capture_w_spin = QSpinBox()
        self._capture_w_spin.setRange(1, 4096)
        self._capture_h_spin = QSpinBox()
        self._capture_h_spin.setRange(1, 4096)

        self._btn_add_web = QPushButton("Add Web Overlay")
        self._btn_add_image = QPushButton("Add Image Overlay")
        self._btn_add_region = QPushButton("Add Region Overlay")
        self._btn_add_window = QPushButton("Add Window Overlay")

        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setMaximumSequenceLength(1)
        self._hotkey_edit.setKeySequence(QKeySequence(self._config.chat_hotkey))
        self._overlay_hotkey_edit = QKeySequenceEdit()
        self._overlay_hotkey_edit.setMaximumSequenceLength(1)
        self._btn_clear_overlay_hotkey = QPushButton("Clear")
        self._btn_clear_overlay_hotkey.setFixedWidth(58)
        self._btn_clear_chat_hotkey = QPushButton("Clear")
        self._btn_clear_chat_hotkey.setFixedWidth(58)
        self._hotkey_hint = QLabel("")
        self._click_through_hotkey_edit = QKeySequenceEdit()
        self._click_through_hotkey_edit.setMaximumSequenceLength(1)
        self._click_through_hotkey_edit.setKeySequence(QKeySequence(self._config.click_through_hotkey))
        self._btn_clear_click_through_hotkey = QPushButton("Clear")
        self._btn_clear_click_through_hotkey.setFixedWidth(58)
        self._click_through_hint = QLabel("")
        self._overlay_title_label = QLabel("Select an overlay")
        self._overlay_type_badge = QLabel("")
        self._btn_show_controls = QToolButton()
        self._btn_show_controls.setCheckable(True)
        self._btn_show_controls.setChecked(True)
        self._toggle_tools_label = QLabel("Hide overlay tools")
        self._opacity_value_label = QLabel("Opacity 100%")
        self._zoom_value_label = QLabel("Zoom 100%")
        self._btn_settings = QToolButton()
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._btn_settings.setText(GEAR_CHAR)
        self._btn_settings.setToolTip("Settings")
        # Larger settings wheel: bigger font and button size (use explicit point size to avoid QFont::setPointSize warning)
        gear_font = QFont()
        gear_font.setPointSize(max(1, 16))
        self._btn_settings.setFont(gear_font)
        self._btn_settings.setMinimumSize(40, 40)
        self._btn_settings.setFixedSize(40, 40)
        self._btn_delete_overlay = QPushButton("Delete Overlay")
        self._btn_delete_overlay.setProperty("class", "destructive")
        self._btn_delete_overlay.setStyleSheet(
            "QPushButton { background-color: #c62828; color: #fff; border: 1px solid #b71c1c; font-size: 13px; padding: 8px 14px; min-height: 24px; } "
            "QPushButton:hover { background-color: #d32f2f; border-color: #c62828; } "
            "QPushButton:pressed { background-color: #b71c1c; } "
            "QPushButton:disabled { background-color: #424242; color: #757575; border-color: #424242; }"
        )
        self._btn_delete_overlay.setEnabled(False)
        self._chat_focus_overlay_id: Optional[str] = None
        self._chat_focus_was_click_through = False

        self._build_layout()
        self._configure_hotkey_ui_for_platform()
        self.setMinimumSize(920, 640)
        self.setMaximumSize(1100, 760)
        self._connect_signals()
        self._load_from_config()
        self._apply_theme(self._config.theme)
        self._update_hotkey_hint(self._config.chat_hotkey)
        self._update_click_through_hint(self._config.click_through_hotkey)
        self._btn_clear_click_through_hotkey.setEnabled(bool(self._config.click_through_hotkey))

    def _configure_hotkey_ui_for_platform(self) -> None:
        if self._global_hotkeys_supported:
            return
        note = "Global hotkeys are currently supported on Windows and macOS."
        for widget in (
            self._hotkey_edit,
            self._overlay_hotkey_edit,
            self._click_through_hotkey_edit,
            self._btn_clear_chat_hotkey,
            self._btn_clear_overlay_hotkey,
            self._btn_clear_click_through_hotkey,
        ):
            widget.setEnabled(False)
            widget.setToolTip(note)
        self._hotkey_hint.setText(note)
        self._click_through_hint.setText(note)

    def _build_layout(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        self.setLayout(main_layout)

        # Top header hero: icon + title + subtitle + GitHub call-to-action
        header = QFrame(self)
        header.setObjectName("HeroHeader")
        header_outer = QVBoxLayout()
        header_outer.setContentsMargins(12, 8, 12, 8)
        header_outer.setSpacing(6)
        header.setLayout(header_outer)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.setFixedHeight(150)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        header_icon = QLabel()
        header_icon.setObjectName("HeaderIcon")
        header_icon.setFixedSize(160, 110)
        header_icon.setAlignment(Qt.AlignCenter)
        icon_pix = _header_icon_pixmap()
        if not icon_pix.isNull():
            header_icon.setPixmap(icon_pix.scaled(140, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        header_title = QLabel("Shastas Projector v2.0.0")
        header_title.setProperty("class", "header-title")
        header_subtitle = QLabel("Open Source Python Projector")
        header_subtitle.setProperty("class", "header-subtitle")

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(header_title)
        title_col.addWidget(header_subtitle)
        header_title.setContentsMargins(0, 0, 0, 0)
        header_subtitle.setContentsMargins(0, 0, 0, 0)

        header_meta = QLabel("\u00a9 2026 Shasta Waffles")
        header_meta.setProperty("class", "header-meta")
        header_meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_cta = QPushButton("GitHub Project")
        header_cta.setProperty("class", "header-cta")
        header_cta.setCursor(Qt.PointingHandCursor)
        header_cta.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/ShastaWaffles/Shastas-Projector"))
        )

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_col.addWidget(header_meta, 0, Qt.AlignRight)
        right_col.addWidget(header_cta, 0, Qt.AlignRight)

        header_row.addWidget(header_icon)
        header_row.addLayout(title_col)
        header_row.addStretch(1)
        header_row.addLayout(right_col)

        header_glow = QFrame()
        header_glow.setObjectName("HeaderGlow")
        header_glow.setFixedHeight(2)

        header_outer.addLayout(header_row)
        header_outer.addWidget(header_glow)

        main_layout.addWidget(header)

        # Keep references for responsive header tweaks
        self._header_container = header
        self._header_icon = header_icon
        self._header_icon_pix = icon_pix
        self._header_title = header_title
        self._header_subtitle = header_subtitle
        self._header_meta = header_meta
        self._header_cta = header_cta
        self._header_title_col = title_col
        self._header_right_col = right_col

        splitter = QSplitter(Qt.Horizontal, self)
        main_layout.addWidget(splitter)

        # —— Left: toggle above overlays, then list ——
        left_container = QWidget(self)
        left = QVBoxLayout()
        left.setSpacing(6)
        left_container.setLayout(left)
        self._btn_show_controls.setFont(_icon_font())
        self._btn_show_controls.setText(FA_TOGGLE_ON)
        self._btn_show_controls.setStyleSheet(
            "QToolButton { color: #8B5CF6; border: none; background: transparent; min-width: 28px; min-height: 28px; } "
            "QToolButton:checked { color: #8B5CF6; } QToolButton:hover { color: #9d7af0; }"
        )
        self._toggle_tools_label.setStyleSheet("color: #AAB2C0; font-size: 13px;")
        toggle_row_left = QHBoxLayout()
        toggle_row_left.addWidget(self._btn_show_controls)
        toggle_row_left.addWidget(self._toggle_tools_label)
        toggle_row_left.addStretch(1)
        left.addLayout(toggle_row_left)
        profile_row = QHBoxLayout()
        profile_row.setSpacing(6)
        profile_row.addWidget(QLabel("Profile"))
        profile_row.addWidget(self._profile_combo)
        left.addLayout(profile_row)
        profile_actions = QHBoxLayout()
        profile_actions.setSpacing(6)
        profile_actions.addWidget(self._btn_new_profile)
        profile_actions.addWidget(self._btn_rename_profile)
        profile_actions.addWidget(self._btn_delete_profile)
        left.addLayout(profile_actions)
        left.addWidget(QLabel("Overlays"))
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left.addWidget(self._list)
        add_row1 = QHBoxLayout()
        add_row1.setSpacing(6)
        add_row1.addWidget(self._btn_add_web)
        add_row1.addWidget(self._btn_add_image)
        left.addLayout(add_row1)
        add_row2 = QHBoxLayout()
        add_row2.setSpacing(6)
        add_row2.addWidget(self._btn_add_region)
        add_row2.addWidget(self._btn_add_window)
        left.addLayout(add_row2)
        for btn in (self._btn_add_web, self._btn_add_image, self._btn_add_region, self._btn_add_window):
            btn.setProperty("class", "compact")
        left_container.setMinimumWidth(320)
        splitter.addWidget(left_container)

        # —— Right: overlay title + toggle + tabbed controls (no scroll) ——
        right_inner = QWidget(self)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.setContentsMargins(12, 0, 24, 0)
        right_inner.setLayout(right)

        self._overlay_title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._overlay_type_badge.setStyleSheet(
            "background-color: rgba(139, 92, 246, 0.3); color: #8B5CF6; "
            "padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: bold;"
        )
        title_row = QHBoxLayout()
        title_row.addWidget(self._overlay_title_label)
        title_row.addWidget(self._overlay_type_badge)
        title_row.addStretch(1)
        title_row.addWidget(self._btn_delete_overlay)
        right.addLayout(title_row)
        right.addSpacing(8)
        self._btn_show_controls.toggled.connect(self._on_show_controls_toggled)

        self._controls_container = QWidget(self)
        self._controls_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Policy.Expanding)
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)
        self._controls_container.setLayout(controls_layout)

        tabs = QTabWidget(self)
        self._tab_widget = tabs
        tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Tab: Source
        basic_page = QWidget()
        basic_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        basic_layout = QVBoxLayout()
        basic_layout.setSpacing(2)
        basic_layout.setContentsMargins(2, 2, 2, 2)
        form_basic = QFormLayout()
        form_basic.setVerticalSpacing(2)
        form_basic.addRow("Name", self._name_edit)
        form_basic.addRow("Source", self._source_edit)
        self._name_edit.setMinimumWidth(200)
        self._source_edit.setMinimumWidth(200)
        basic_layout.addLayout(form_basic)
        basic_page.setLayout(basic_layout)
        tabs.addTab(basic_page, "Source")

        # Tab: Display
        size_page = QWidget()
        size_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        size_layout = QVBoxLayout()
        size_layout.setSpacing(12)
        size_layout.setContentsMargins(4, 6, 4, 12)
        size_layout.addWidget(_section_header("SIZE & POSITION"))
        size_row = QHBoxLayout()
        size_row.setSpacing(12)
        size_row.addWidget(QLabel("Width"))
        size_row.addWidget(self._width_spin)
        size_row.addSpacing(16)
        size_row.addWidget(QLabel("Height"))
        size_row.addWidget(self._height_spin)
        size_row.addStretch(1)
        self._width_spin.setMinimumWidth(70)
        self._width_spin.setMaximumWidth(100)
        self._height_spin.setMinimumWidth(70)
        self._height_spin.setMaximumWidth(100)
        size_layout.addLayout(size_row)
        size_layout.addSpacing(4)
        size_layout.addWidget(_section_header("OPACITY & ZOOM"))
        self._opacity_value_label.setMinimumWidth(100)
        size_layout.addWidget(self._opacity_value_label)
        size_layout.addWidget(self._opacity_slider)
        size_layout.addSpacing(4)
        size_layout.addWidget(self._zoom_value_label)
        size_layout.addWidget(self._zoom_slider)
        size_layout.addSpacing(8)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.setContentsMargins(0, 4, 0, 4)
        action_row.addWidget(self._btn_fit_content)
        action_row.addWidget(self._btn_reload)
        size_layout.addLayout(action_row)
        size_layout.addSpacing(12)
        size_page.setLayout(size_layout)
        tabs.addTab(size_page, "Display")

        # Tab: Hotkey
        hotkey_page = QWidget()
        hotkey_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        hotkey_layout = QVBoxLayout()
        hotkey_layout.setSpacing(2)
        hotkey_layout.setContentsMargins(2, 2, 2, 2)
        hotkey_layout.addWidget(_section_header("OVERLAY VISIBILITY HOTKEY"))
        overlay_hotkey_row = QHBoxLayout()
        overlay_hotkey_row.addWidget(self._overlay_hotkey_edit)
        overlay_hotkey_row.addWidget(self._btn_clear_overlay_hotkey)
        hotkey_layout.addLayout(overlay_hotkey_row)
        # Chat input hotkey only for web and window overlays; hide for image/region
        self._chat_input_hotkey_group = QWidget()
        chat_input_layout = QVBoxLayout()
        chat_input_layout.setSpacing(2)
        chat_input_layout.setContentsMargins(0, 0, 0, 0)
        chat_input_layout.addWidget(_section_header("OVERLAY CHAT INPUT HOTKEY"))
        chat_hotkey_row = QHBoxLayout()
        chat_hotkey_row.addWidget(self._hotkey_edit)
        chat_hotkey_row.addWidget(self._btn_clear_chat_hotkey)
        chat_input_layout.addLayout(chat_hotkey_row)
        self._hotkey_hint.setStyleSheet("color: #AAB2C0; font-size: 12px;")
        chat_input_layout.addWidget(self._hotkey_hint)
        self._chat_input_hotkey_group.setLayout(chat_input_layout)
        self._chat_input_hotkey_group.setVisible(False)  # shown only for web/window in _on_selection_changed
        hotkey_layout.addWidget(self._chat_input_hotkey_group)
        hotkey_layout.addWidget(_section_header("OVERLAY CLICK THROUGH"))
        click_through_hotkey_row = QHBoxLayout()
        click_through_hotkey_row.addWidget(self._click_through_hotkey_edit)
        click_through_hotkey_row.addWidget(self._btn_clear_click_through_hotkey)
        hotkey_layout.addLayout(click_through_hotkey_row)
        self._click_through_hint.setStyleSheet("color: #AAB2C0; font-size: 12px;")
        hotkey_layout.addWidget(self._click_through_hint)
        hotkey_page.setLayout(hotkey_layout)
        tabs.addTab(hotkey_page, "Hotkeys")

        # Tab: Capture (shown only for screen overlays)
        screen_capture_wrap = QWidget()
        screen_capture_wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        screen_capture_layout = QVBoxLayout()
        screen_capture_layout.setSpacing(2)
        screen_capture_layout.setContentsMargins(2, 2, 2, 2)
        repick_row = QHBoxLayout()
        repick_row.addWidget(self._btn_repick_region)
        repick_row.addWidget(self._btn_repick_window)
        screen_capture_layout.addLayout(repick_row)
        screen_capture_layout.addWidget(self._btn_crop_window)
        capture_rect_row = QHBoxLayout()
        capture_rect_row.addWidget(QLabel("X"))
        capture_rect_row.addWidget(self._capture_x_spin)
        capture_rect_row.addWidget(QLabel("Y"))
        capture_rect_row.addWidget(self._capture_y_spin)
        screen_capture_layout.addLayout(capture_rect_row)
        capture_size_row = QHBoxLayout()
        capture_size_row.addWidget(QLabel("W"))
        capture_size_row.addWidget(self._capture_w_spin)
        capture_size_row.addWidget(QLabel("H"))
        capture_size_row.addWidget(self._capture_h_spin)
        screen_capture_layout.addLayout(capture_size_row)
        screen_capture_wrap.setLayout(screen_capture_layout)
        self._screen_capture_group = screen_capture_wrap
        self._capture_tab_widget = screen_capture_wrap
        self._capture_tab_title = "Capture"

        controls_layout.addWidget(tabs)
        right.addWidget(self._controls_container)
        right.addStretch(1)
        settings_row = QHBoxLayout()
        settings_row.addStretch(1)
        settings_row.addWidget(self._btn_settings)
        right.addLayout(settings_row)

        right_inner.setMinimumWidth(320)
        splitter.addWidget(right_inner)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def _connect_signals(self) -> None:
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.model().rowsMoved.connect(self._on_overlay_list_reordered)

        self._btn_add_web.clicked.connect(self._on_add_web)
        self._btn_add_image.clicked.connect(self._on_add_image)
        self._btn_add_region.clicked.connect(self._on_add_region)
        self._btn_add_window.clicked.connect(self._on_add_window)

        self._name_edit.editingFinished.connect(self._apply_detail_changes)
        self._source_edit.editingFinished.connect(self._apply_detail_changes)
        self._opacity_slider.valueChanged.connect(self._apply_detail_changes)
        self._zoom_slider.valueChanged.connect(self._apply_detail_changes)
        self._width_spin.valueChanged.connect(self._on_size_changed)
        self._height_spin.valueChanged.connect(self._on_size_changed)
        self._btn_fit_content.clicked.connect(self._on_fit_content_clicked)
        self._btn_reload.clicked.connect(self._on_reload_clicked)
        self._btn_repick_region.clicked.connect(self._on_repick_region_clicked)
        self._btn_repick_window.clicked.connect(self._on_repick_window_clicked)
        self._btn_crop_window.clicked.connect(self._on_crop_window_clicked)
        self._capture_x_spin.valueChanged.connect(self._on_capture_rect_changed)
        self._capture_y_spin.valueChanged.connect(self._on_capture_rect_changed)
        self._capture_w_spin.valueChanged.connect(self._on_capture_rect_changed)
        self._capture_h_spin.valueChanged.connect(self._on_capture_rect_changed)
        self._hotkey_edit.keySequenceChanged.connect(self._on_hotkey_changed)
        self._overlay_hotkey_edit.keySequenceChanged.connect(self._on_overlay_hotkey_changed)
        self._btn_clear_overlay_hotkey.clicked.connect(self._on_clear_overlay_hotkey)
        self._btn_clear_chat_hotkey.clicked.connect(self._on_clear_chat_hotkey)
        self._click_through_hotkey_edit.keySequenceChanged.connect(self._on_click_through_hotkey_changed)
        self._btn_clear_click_through_hotkey.clicked.connect(self._on_clear_click_through_hotkey)
        self._btn_settings.clicked.connect(self._on_settings_clicked)
        self._btn_delete_overlay.clicked.connect(self._on_delete_overlay_clicked)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self._btn_new_profile.clicked.connect(self._on_new_profile_clicked)
        self._btn_rename_profile.clicked.connect(self._on_rename_profile_clicked)
        self._btn_delete_profile.clicked.connect(self._on_delete_profile_clicked)

    def _load_from_config(self) -> None:
        self._refresh_profile_combo()
        self._switch_active_profile(self._config.active_profile_id, save=False)

    def _get_active_profile(self) -> OverlayProfile:
        if not self._config.profiles:
            default_profile = OverlayProfile(id="default", name="Default", overlays=[])
            self._config.profiles.append(default_profile)
            self._config.active_profile_id = default_profile.id
            return default_profile
        for profile in self._config.profiles:
            if profile.id == self._config.active_profile_id:
                return profile
        self._config.active_profile_id = self._config.profiles[0].id
        return self._config.profiles[0]

    def _refresh_profile_combo(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for profile in self._config.profiles:
            self._profile_combo.addItem(profile.name, profile.id)
        active_id = self._config.active_profile_id
        idx = self._profile_combo.findData(active_id)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)

    def _switch_active_profile(self, profile_id: str, save: bool = True) -> None:
        if profile_id == self._config.active_profile_id and self._config_by_id:
            return

        # Tear down current profile overlays
        if self._overlay_hotkey_callback is not None:
            for cfg in self._config_by_id.values():
                if cfg.toggle_hotkey:
                    self._overlay_hotkey_callback(cfg.id, "")
        for win in self._overlay_windows.values():
            win.close()
        self._overlay_windows.clear()
        self._row_widgets.clear()
        self._config_by_id.clear()
        self._list.clear()
        self._chat_focus_overlay_id = None
        self._chat_focus_was_click_through = False

        # Switch active profile
        self._config.active_profile_id = profile_id
        profile = self._get_active_profile()

        # Load overlays for active profile
        for overlay_cfg in profile.overlays:
            self._config_by_id[overlay_cfg.id] = overlay_cfg
            self._create_overlay_window(overlay_cfg)
            self._add_list_item(overlay_cfg)
            if overlay_cfg.toggle_hotkey and self._overlay_hotkey_callback is not None:
                overlay_cfg.toggle_hotkey = self._overlay_hotkey_callback(overlay_cfg.id, overlay_cfg.toggle_hotkey)

        self._refresh_profile_combo()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        if save:
            self._schedule_config_save()

    def _on_profile_selected(self, index: int) -> None:
        profile_id = self._profile_combo.itemData(index)
        if profile_id:
            self._switch_active_profile(str(profile_id), save=True)

    def _on_new_profile_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok:
            return
        name = name.strip() or "New Profile"
        new_profile = OverlayProfile(id=str(uuid.uuid4()), name=name, overlays=[])
        self._config.profiles.append(new_profile)
        self._switch_active_profile(new_profile.id, save=True)

    def _on_rename_profile_clicked(self) -> None:
        profile = self._get_active_profile()
        name, ok = QInputDialog.getText(self, "Rename Profile", "Profile name:", text=profile.name)
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        profile.name = name
        self._refresh_profile_combo()
        self._schedule_config_save()

    def _on_delete_profile_clicked(self) -> None:
        if len(self._config.profiles) <= 1:
            QMessageBox.information(self, "Delete Profile", "You must keep at least one profile.")
            return
        profile = self._get_active_profile()
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Profile")
        msg.setText(f'Delete profile "{profile.name}" and all its overlays?')
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        reply = msg.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._config.profiles = [p for p in self._config.profiles if p.id != profile.id]
        new_active = self._config.profiles[0].id if self._config.profiles else "default"
        self._switch_active_profile(new_active, save=True)

    def _schedule_config_save(self) -> None:
        self._save_timer.start()

    def _flush_config(self) -> None:
        self._on_config_changed(self._config)

    def _apply_panel_on_top(self, keep_on_top: bool) -> None:
        """Apply always-on-top behavior for the control panel window."""
        flags = self.windowFlags()
        if keep_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        # Changing window flags can hide the window; ensure it stays visible.
        if self.isVisible():
            self.show()

    def _raise_overlay_later(self, win: QWidget) -> None:
        """Schedule raise + ensure_topmost so the overlay gets on top after it has a native handle."""

        def _do() -> None:
            if win.isVisible() and hasattr(win, "ensure_topmost"):
                win.raise_()
                win.ensure_topmost()

        QTimer.singleShot(200, _do)

    def _update_hotkey_hint(self, hotkey_text: str) -> None:
        if not self._global_hotkeys_supported:
            self._hotkey_hint.setText("Global hotkeys are currently supported on Windows and macOS.")
            return
        if self._config.focus_hotkey_enabled:
            self._hotkey_hint.setText(
                f"Hotkey: {hotkey_text} focuses chat input (press again to restore)"
            )
        else:
            self._hotkey_hint.setText("Overlay Chat Input Hotkey is disabled")

    def _update_click_through_hint(self, hotkey_text: str) -> None:
        if not self._global_hotkeys_supported:
            self._click_through_hint.setText("Global hotkeys are currently supported on Windows and macOS.")
            return
        if hotkey_text:
            self._click_through_hint.setText(
                f"Hotkey: {hotkey_text} toggles click-through for selected overlay"
            )
        else:
            self._click_through_hint.setText("Overlay Click Through hotkey is not set")

    def set_hotkey_text(self, hotkey_text: str) -> None:
        self._hotkey_edit.blockSignals(True)
        self._hotkey_edit.setKeySequence(QKeySequence(hotkey_text))
        self._hotkey_edit.blockSignals(False)
        self._update_hotkey_hint(hotkey_text)

    def set_focus_hotkey_enabled(self, enabled: bool) -> None:
        self._config.focus_hotkey_enabled = enabled
        self._update_hotkey_hint(self._config.chat_hotkey)

    def _on_settings_clicked(self) -> None:
        dlg = SettingsDialog(
            self._config.theme,
            on_theme_changed=self._set_theme_from_ui,
            keep_on_top=self._config.keep_control_panel_on_top,
            on_keep_on_top_changed=self._on_keep_on_top_setting_changed,
            parent=self,
        )
        dlg.exec()

    def _on_keep_on_top_setting_changed(self, keep_on_top: bool) -> None:
        self._config.keep_control_panel_on_top = keep_on_top
        self._apply_panel_on_top(keep_on_top)
        self._schedule_config_save()

    def _apply_theme(self, theme: ThemeType) -> None:
        if theme == "light":
            self.setStyleSheet(
                """
                QWidget { color: #1b2430; background-color: #edf1f7; }
                QLabel { color: #1b2430; background: transparent; }
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
                QLineEdit, QSpinBox, QListWidget, QKeySequenceEdit, QPlainTextEdit {
                    background-color: #ffffff;
                    border: 1px solid #c3cddd;
                    border-radius: 6px;
                    padding: 4px;
                    selection-background-color: #4a8df8;
                    selection-color: #ffffff;
                }
                QListWidget::item {
                    padding: 0;
                    margin: 2px;
                    border-radius: 10px;
                }
                QListWidget::item:selected {
                    background-color: rgba(99, 102, 241, 0.16);
                    border: 1px solid rgba(99, 102, 241, 0.35);
                }
                QListWidget::item:hover:!selected {
                    background-color: rgba(2, 6, 23, 0.06);
                }
                QTabWidget::pane {
                    border: 1px solid #cfd7e3;
                    border-radius: 12px; background: #f7f9fd;
                    margin-top: 6px; padding: 12px 14px 18px 14px;
                }
                QTabBar {
                    background: #ffffff;
                    border: 1px solid #cfd7e3;
                    border-radius: 12px;
                    padding: 4px;
                }
                QTabBar::tab {
                    background: transparent; color: #64748b;
                    padding: 8px 16px; margin-right: 4px;
                    border: none;
                    border-radius: 8px; font-size: 13px;
                }
                QTabBar::tab:selected {
                    background: #6366f1; color: #ffffff;
                }
                QTabBar::tab:hover:!selected { background: #edf3ff; color: #1b2430; }
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
                QPushButton[class="primary"] {
                    background-color: #6366f1; border-color: #6366f1; color: #ffffff;
                }
                QPushButton[class="primary"]:hover {
                    background-color: #818cf8; border-color: #818cf8; color: #ffffff;
                }
                QPushButton[class="primary"]:pressed { background-color: #4f46e5; border-color: #4f46e5; }
                QPushButton[class="primary"]:disabled { background-color: #c3cddd; border-color: #c3cddd; color: #6b7280; }
                QPushButton[class="action-primary"] {
                    background-color: #6366f1; border-color: #6366f1; color: #ffffff;
                    border-radius: 12px; padding: 8px 16px; font-weight: 600;
                }
                QPushButton[class="action-primary"]:hover {
                    background-color: #818cf8; border-color: #818cf8;
                }
                QPushButton[class="action-primary"]:pressed { background-color: #4f46e5; border-color: #4f46e5; }
                QPushButton[class="action-primary"]:disabled { background-color: #c3cddd; border-color: #c3cddd; color: #6b7280; }
                QPushButton[class="action-secondary"] {
                    background-color: rgba(99, 102, 241, 0.08);
                    border: 1px solid rgba(99, 102, 241, 0.45);
                    color: #1b2430;
                    border-radius: 12px; padding: 8px 16px; font-weight: 600;
                }
                QPushButton[class="action-secondary"]:hover {
                    background-color: rgba(99, 102, 241, 0.16);
                    border-color: rgba(99, 102, 241, 0.7);
                }
                QPushButton[class="action-secondary"]:pressed {
                    background-color: rgba(99, 102, 241, 0.24);
                }
                QPushButton[class="action-secondary"]:disabled {
                    background-color: rgba(99, 102, 241, 0.04);
                    border-color: rgba(99, 102, 241, 0.2);
                    color: #6b7280;
                }
                QFrame#HeroHeader {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 rgba(99, 102, 241, 0.06), stop: 0.65 rgba(99, 102, 241, 0.03), stop: 1 rgba(99, 102, 241, 0.14));
                    border: 1px solid #cfd7e3;
                    border-radius: 14px;
                }
                QLabel#HeaderIcon {
                    background: transparent;
                    border: none;
                    padding: 0;
                }
                QLabel[class="header-title"] {
                    font-size: 16px;
                    font-weight: 700;
                    color: #1b2430;
                    margin: 0;
                    padding: 0;
                }
                QLabel[class="header-subtitle"] {
                    font-size: 11px;
                    color: #64748b;
                    margin: -2px 0 0 0;
                    padding: 0;
                }
                QLabel[class="header-meta"] {
                    font-size: 11px;
                    color: #64748b;
                }
                QFrame#HeaderGlow {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 rgba(99, 102, 241, 0.0), stop: 0.5 rgba(99, 102, 241, 0.35), stop: 1 rgba(99, 102, 241, 0.0));
                    border-radius: 1px;
                }
                QPushButton[class="header-cta"] {
                    background-color: #ffffff;
                    border: 1px solid #6366f1;
                    color: #1b2430;
                    border-radius: 10px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton[class="header-cta"]:hover {
                    background-color: #edf3ff;
                    border-color: #818cf8;
                }
                QPushButton[class="header-cta"]:pressed {
                    background-color: #d9e7ff;
                    border-color: #4f46e5;
                }
                """
            )
        elif theme == "ember":
            self.setStyleSheet(CONTROL_PANEL_EMBER_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "sea":
            self.setStyleSheet(CONTROL_PANEL_SEA_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "emerald":
            self.setStyleSheet(CONTROL_PANEL_EMERALD_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "cherry":
            self.setStyleSheet(CONTROL_PANEL_CHERRY_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "pastel":
            self.setStyleSheet(CONTROL_PANEL_PASTEL_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "neon":
            self.setStyleSheet(CONTROL_PANEL_NEON_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "late":
            self.setStyleSheet(CONTROL_PANEL_LATE_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "fire":
            self.setStyleSheet(CONTROL_PANEL_FIRE_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "galaxy":
            self.setStyleSheet(CONTROL_PANEL_GALAXY_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        elif theme == "ducky":
            self.setStyleSheet(CONTROL_PANEL_DUCKY_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            self.setStyleSheet(CONTROL_PANEL_DARK_QSS)
            self.style().unpolish(self)
            self.style().polish(self)
        self._update_theme_dependent_styles(theme)

    def _update_theme_dependent_styles(self, theme: ThemeType) -> None:
        """Update widgets that use inline setStyleSheet so they match the current theme."""
        colors = THEME_COLORS.get(theme, THEME_COLORS["dark"])
        accent, accent_hover, text_muted, accent_rgba = colors
        self._btn_show_controls.setStyleSheet(
            f"QToolButton {{ color: {accent}; border: none; background: transparent; min-width: 28px; min-height: 28px; }} "
            f"QToolButton:checked {{ color: {accent}; }} QToolButton:hover {{ color: {accent_hover}; }}"
        )
        self._toggle_tools_label.setStyleSheet(f"color: {text_muted}; font-size: 13px;")
        self._overlay_type_badge.setStyleSheet(
            f"background-color: rgba({accent_rgba}, 0.3); color: {accent}; "
            "padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: bold;"
        )
        self._hotkey_hint.setStyleSheet(f"color: {text_muted}; font-size: 12px;")
        self._click_through_hint.setStyleSheet(f"color: {text_muted}; font-size: 12px;")
        for widget in self._row_widgets.values():
            if hasattr(widget, "update_theme_colors"):
                widget.update_theme_colors(accent, accent_hover, text_muted)
        for win in self._overlay_windows.values():
            if hasattr(win, "set_overlay_border_color"):
                win.set_overlay_border_color(accent)

    def _clamp_geometry_to_screen(self, x: int, y: int, w: int, h: int) -> tuple:
        """Return (x, y, w, h) with position clamped so at least part of the window is on-screen."""
        screen = QApplication.primaryScreen()
        if not screen:
            return (x, y, w, h)
        gr = screen.availableGeometry()
        margin = 80
        x = max(gr.x() - w + margin, min(x, gr.right() - margin))
        y = max(gr.y() - h + margin, min(y, gr.bottom() - margin))
        return (x, y, w, h)

    def _create_overlay_window(self, cfg: OverlayConfig) -> None:
        if cfg.type == "web":
            win = WebOverlayWindow(url=cfg.source, opacity=cfg.opacity, locked=cfg.locked)
            win.set_zoom(cfg.zoom)
        elif cfg.type == "screen":
            win = ScreenCaptureOverlay(
                capture_mode=cfg.capture_mode,
                capture_rect=cfg.capture_rect,
                window_handle=cfg.window_handle,
                window_title=cfg.window_title,
                opacity=cfg.opacity,
                locked=cfg.locked,
            )
            win.set_zoom(cfg.zoom)
        else:
            win = ImageOverlayWindow(image_path=cfg.source, opacity=cfg.opacity, locked=cfg.locked)

        win.setWindowTitle(cfg.name or cfg.id)
        x, y, w, h = self._clamp_geometry_to_screen(cfg.x, cfg.y, cfg.width, cfg.height)
        win.setGeometry(x, y, w, h)
        cfg.x, cfg.y, cfg.width, cfg.height = x, y, w, h
        win.set_click_through(cfg.click_through)
        # Respect saved visibility for all overlay types
        if cfg.visible:
            win.show()
            if hasattr(win, "ensure_topmost"):
                win.ensure_topmost()
            self._raise_overlay_later(win)

        def on_state_changed() -> None:
            self._update_config_from_window(cfg.id)
            self._schedule_config_save()

        win.on_state_changed = on_state_changed
        self._overlay_windows[cfg.id] = win
        # Apply current theme border color to overlay
        colors = THEME_COLORS.get(self._config.theme, THEME_COLORS["dark"])
        if hasattr(win, "set_overlay_border_color"):
            win.set_overlay_border_color(colors[0])

    def _overlay_subtitle(self, cfg: OverlayConfig) -> str:
        """Short text for sub row (truncated in UI); full version in tooltip."""
        if cfg.type == "web":
            return cfg.source.strip() or "Web"
        if cfg.type == "image":
            return Path(cfg.source).name if cfg.source else "Image"
        if cfg.type == "screen":
            return cfg.source or ("Region" if cfg.capture_mode == "region" else "Window")
        return cfg.type

    def _overlay_detail_tooltip(self, cfg: OverlayConfig) -> str:
        """Full detail for sub row tooltip (URL, region coords, window title)."""
        if cfg.type == "web":
            return cfg.source.strip() or "Web"
        if cfg.type == "image":
            return cfg.source or "Image"
        if cfg.type == "screen":
            if cfg.capture_mode == "region" and cfg.capture_rect:
                r = cfg.capture_rect
                return f"Region ({r.x}, {r.y}, {r.width}×{r.height})"
            if cfg.capture_mode == "window":
                return f"Window: {cfg.window_title or 'Unknown'}"
            return cfg.source or "Region" if cfg.capture_mode == "region" else "Window"
        return cfg.type

    def _add_list_item(self, cfg: OverlayConfig) -> None:
        item = QListWidgetItem()
        widget = OverlayListItemWidget(
            overlay_id=cfg.id,
            name=cfg.name or cfg.id,
            subtitle=self._overlay_subtitle(cfg),
            overlay_type=cfg.type,
            capture_mode=cfg.capture_mode,
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
        widget.set_detail_tooltip(self._overlay_detail_tooltip(cfg))
        widget.set_tools_visible(self._btn_show_controls.isChecked())
        # Apply current theme colors so new list items match the active theme
        colors = THEME_COLORS.get(self._config.theme, THEME_COLORS["dark"])
        accent, accent_hover, text_muted = colors[0], colors[1], colors[2]
        widget.update_theme_colors(accent, accent_hover, text_muted)

    def _on_overlay_list_reordered(self) -> None:
        """Sync active profile overlay order to match the list order after drag/drop."""
        order_ids = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item:
                oid = item.data(Qt.UserRole)
                if oid:
                    order_ids.append(oid)
        if not order_ids:
            return
        profile = self._get_active_profile()
        id_to_cfg = {c.id: c for c in profile.overlays}
        profile.overlays = [id_to_cfg[oid] for oid in order_ids if oid in id_to_cfg]
        self._schedule_config_save()

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
            self._opacity_slider.setValue(100)
            self._zoom_slider.setValue(100)
            self._width_spin.setValue(450)
            self._height_spin.setValue(700)
            self._overlay_hotkey_edit.setKeySequence(QKeySequence())
            self._overlay_title_label.setText("Select an overlay")
            self._overlay_type_badge.setText("")
            self._overlay_type_badge.setVisible(False)
            self._opacity_value_label.setText("Opacity 100%")
            self._zoom_value_label.setText("Zoom 100%")

            self._name_edit.blockSignals(False)
            self._source_edit.blockSignals(False)
            self._opacity_slider.blockSignals(False)
            self._zoom_slider.blockSignals(False)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)
            self._overlay_hotkey_edit.blockSignals(False)
            self._btn_fit_content.setEnabled(False)
            self._btn_reload.setEnabled(False)
            self._source_edit.setReadOnly(False)
            self._source_edit.setPlaceholderText("")
            self._screen_capture_group.setVisible(False)
            self._overlay_hotkey_edit.setEnabled(False)
            self._btn_clear_overlay_hotkey.setEnabled(False)
            self._update_capture_tab_visibility(None)
            self._btn_delete_overlay.setEnabled(False)
            self._chat_input_hotkey_group.setVisible(False)
            self._is_loading_selection = False
            return

        cfg = self._find_config(overlay_id)
        if not cfg:
            self._chat_input_hotkey_group.setVisible(False)
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
        self._overlay_title_label.setText(cfg.name or cfg.id)
        self._overlay_type_badge.setVisible(True)
        type_badge = {"web": "WEB", "image": "IMAGE", "screen": "REGION CAPTURE" if cfg.capture_mode == "region" else "WINDOW CAPTURE"}
        self._overlay_type_badge.setText(type_badge.get(cfg.type, cfg.type.upper()))
        self._opacity_value_label.setText(f"Opacity {int(cfg.opacity * 100)}%")
        self._zoom_value_label.setText(f"Zoom {int(cfg.zoom * 100)}%")

        self._name_edit.blockSignals(False)
        self._source_edit.blockSignals(False)
        self._opacity_slider.blockSignals(False)
        self._zoom_slider.blockSignals(False)
        self._width_spin.blockSignals(False)
        self._height_spin.blockSignals(False)
        self._overlay_hotkey_edit.blockSignals(False)

        self._btn_fit_content.setEnabled(cfg.type == "image")
        self._btn_reload.setEnabled(cfg.type == "web")
        self._source_edit.setReadOnly(cfg.type == "screen")
        # Overlay Chat Input Hotkey only for web and window overlays
        self._chat_input_hotkey_group.setVisible(
            cfg.type == "web" or (cfg.type == "screen" and cfg.capture_mode == "window")
        )
        if cfg.type == "screen":
            self._source_edit.setPlaceholderText("Region or window (use Re-pick or adjust below)")
            self._screen_capture_group.setVisible(True)
            self._btn_repick_region.setEnabled(cfg.capture_mode == "region")
            self._btn_repick_window.setEnabled(cfg.capture_mode == "window")
            win = self._overlay_windows.get(overlay_id) if overlay_id else None
            is_window_overlay = cfg.capture_mode == "window" and isinstance(win, ScreenCaptureOverlay)
            self._btn_crop_window.setEnabled(is_window_overlay)
            if cfg.capture_mode == "region" and cfg.capture_rect:
                self._capture_x_spin.blockSignals(True)
                self._capture_y_spin.blockSignals(True)
                self._capture_w_spin.blockSignals(True)
                self._capture_h_spin.blockSignals(True)
                self._capture_x_spin.setValue(cfg.capture_rect.x)
                self._capture_y_spin.setValue(cfg.capture_rect.y)
                self._capture_w_spin.setValue(cfg.capture_rect.width)
                self._capture_h_spin.setValue(cfg.capture_rect.height)
                self._capture_x_spin.blockSignals(False)
                self._capture_y_spin.blockSignals(False)
                self._capture_w_spin.blockSignals(False)
                self._capture_h_spin.blockSignals(False)
                self._capture_x_spin.setEnabled(True)
                self._capture_y_spin.setEnabled(True)
                self._capture_w_spin.setEnabled(True)
                self._capture_h_spin.setEnabled(True)
            elif is_window_overlay and win is not None:
                full = win.get_full_window_rect()
                if full:
                    _left, _top, win_w, win_h = full
                    self._capture_w_spin.setRange(1, max(1, win_w))
                    self._capture_h_spin.setRange(1, max(1, win_h))
                    self._capture_x_spin.setRange(0, max(0, win_w - 1))
                    self._capture_y_spin.setRange(0, max(0, win_h - 1))
                self._capture_x_spin.blockSignals(True)
                self._capture_y_spin.blockSignals(True)
                self._capture_w_spin.blockSignals(True)
                self._capture_h_spin.blockSignals(True)
                if cfg.capture_rect:
                    self._capture_x_spin.setValue(cfg.capture_rect.x)
                    self._capture_y_spin.setValue(cfg.capture_rect.y)
                    self._capture_w_spin.setValue(cfg.capture_rect.width)
                    self._capture_h_spin.setValue(cfg.capture_rect.height)
                elif full:
                    self._capture_x_spin.setValue(0)
                    self._capture_y_spin.setValue(0)
                    self._capture_w_spin.setValue(full[2])
                    self._capture_h_spin.setValue(full[3])
                self._capture_x_spin.blockSignals(False)
                self._capture_y_spin.blockSignals(False)
                self._capture_w_spin.blockSignals(False)
                self._capture_h_spin.blockSignals(False)
                self._capture_x_spin.setEnabled(True)
                self._capture_y_spin.setEnabled(True)
                self._capture_w_spin.setEnabled(True)
                self._capture_h_spin.setEnabled(True)
            else:
                self._capture_x_spin.setEnabled(False)
                self._capture_y_spin.setEnabled(False)
                self._capture_w_spin.setEnabled(False)
                self._capture_h_spin.setEnabled(False)
        else:
            self._screen_capture_group.setVisible(False)
        self._update_capture_tab_visibility(overlay_id)
        self._overlay_hotkey_edit.setEnabled(True)
        self._btn_clear_overlay_hotkey.setEnabled(bool(cfg.toggle_hotkey))
        self._btn_delete_overlay.setEnabled(True)
        self._is_loading_selection = False
        # Bring selected overlay to front so the user can see it
        win = self._overlay_windows.get(overlay_id)
        if win and win.isVisible():
            self._raise_overlay_later(win)

    def _on_add_web(self) -> None:
        new_id = str(uuid.uuid4())
        cfg = OverlayConfig(
            id=new_id,
            name="Web Overlay",
            type="web",
            source="",
            click_through=False,
        )
        self._get_active_profile().overlays.append(cfg)
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
        self._get_active_profile().overlays.append(cfg)
        self._config_by_id[cfg.id] = cfg
        self._create_overlay_window(cfg)
        self._add_list_item(cfg)
        self._list.setCurrentRow(self._list.count() - 1)
        self._schedule_config_save()

    def _on_add_region(self) -> None:
        self.hide()
        QTimer.singleShot(300, self._run_region_picker)

    def _run_region_picker(self) -> None:
        picker = RegionPickerOverlay()
        result_holder: list = []

        def on_finished(rect) -> None:
            result_holder.append(rect)
            loop.quit()

        picker.selection_finished.connect(on_finished)
        picker.show_fullscreen()
        loop = QEventLoop()
        loop.exec()
        self.show()
        self.raise_()
        self.activateWindow()

        rect = result_holder[0] if result_holder else None
        if not rect:
            return

        x, y, w, h = rect
        capture_rect = CaptureRect(x=x, y=y, width=w, height=h)
        new_id = str(uuid.uuid4())
        source_text = f"Region ({x},{y}) {w}×{h}"
        cfg = OverlayConfig(
            id=new_id,
            name="Screen region",
            type="screen",
            source=source_text,
            capture_mode="region",
            capture_rect=capture_rect,
            click_through=False,
        )
        self._get_active_profile().overlays.append(cfg)
        self._config_by_id[cfg.id] = cfg
        self._create_overlay_window(cfg)
        self._add_list_item(cfg)
        self._list.setCurrentRow(self._list.count() - 1)
        self._schedule_config_save()

    def _on_repick_region_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        cfg = self._find_config(overlay_id) if overlay_id else None
        if not cfg or cfg.type != "screen" or cfg.capture_mode != "region":
            return
        self.hide()
        QTimer.singleShot(300, lambda: self._run_repick_region(overlay_id))

    def _run_repick_region(self, overlay_id: str) -> None:
        picker = RegionPickerOverlay()
        result_holder: list = []

        def on_finished(rect) -> None:
            result_holder.append(rect)
            loop.quit()

        picker.selection_finished.connect(on_finished)
        picker.show_fullscreen()
        loop = QEventLoop()
        loop.exec()
        self.show()
        self.raise_()
        self.activateWindow()

        rect = result_holder[0] if result_holder else None
        if not rect:
            return
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id) if overlay_id else None
        if not cfg or not isinstance(win, ScreenCaptureOverlay):
            return
        x, y, w, h = rect
        capture_rect = CaptureRect(x=x, y=y, width=w, height=h)
        cfg.capture_rect = capture_rect
        cfg.source = f"Region ({x},{y}) {w}×{h}"
        win.set_capture_region(capture_rect)
        self._capture_x_spin.blockSignals(True)
        self._capture_y_spin.blockSignals(True)
        self._capture_w_spin.blockSignals(True)
        self._capture_h_spin.blockSignals(True)
        self._capture_x_spin.setValue(x)
        self._capture_y_spin.setValue(y)
        self._capture_w_spin.setValue(w)
        self._capture_h_spin.setValue(h)
        self._capture_x_spin.blockSignals(False)
        self._capture_y_spin.blockSignals(False)
        self._capture_w_spin.blockSignals(False)
        self._capture_h_spin.blockSignals(False)
        self._source_edit.setText(cfg.source)
        row = self._row_widgets.get(overlay_id) if overlay_id else None
        if row:
            row.set_subtitle(self._overlay_subtitle(cfg))
            row.set_detail_tooltip(self._overlay_detail_tooltip(cfg))
        self._schedule_config_save()

    def _on_repick_window_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        cfg = self._find_config(overlay_id) if overlay_id else None
        if not cfg or cfg.type != "screen" or cfg.capture_mode != "window":
            return
        dlg = WindowPickerDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        sel = dlg.get_selection()
        if not sel:
            return
        hwnd, title = sel
        cfg.window_handle = hwnd
        cfg.window_title = title
        cfg.source = f"Window: {title[:50]}" + ("…" if len(title) > 50 else "")
        cfg.name = f"Window: {title[:30]}"
        win = self._overlay_windows.get(overlay_id) if overlay_id else None
        if isinstance(win, ScreenCaptureOverlay):
            win.set_capture_window(hwnd, title)
        row = self._row_widgets.get(overlay_id)
        if row:
            row.set_name(cfg.name)
            row.set_subtitle(self._overlay_subtitle(cfg))
            row.set_detail_tooltip(self._overlay_detail_tooltip(cfg))
        self._name_edit.setText(cfg.name)
        self._source_edit.setText(cfg.source)
        self._schedule_config_save()

    def _on_crop_window_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        cfg = self._find_config(overlay_id) if overlay_id else None
        win = self._overlay_windows.get(overlay_id) if overlay_id else None
        if not cfg or cfg.type != "screen" or cfg.capture_mode != "window" or not isinstance(win, ScreenCaptureOverlay):
            return
        window_rect = win.get_full_window_rect()
        if not window_rect:
            return
        initial_crop = win.get_crop_rect()
        dlg = WindowCropPickerDialog(
            self,
            window_rect,
            initial_crop,
            window_title=cfg.window_title or "",
        )
        if dlg.exec() != QDialog.Accepted:
            return
        crop = dlg.get_crop_rect()
        if not crop:
            return
        cfg.capture_rect = crop
        win.set_capture_region(crop)
        self._capture_x_spin.blockSignals(True)
        self._capture_y_spin.blockSignals(True)
        self._capture_w_spin.blockSignals(True)
        self._capture_h_spin.blockSignals(True)
        self._capture_x_spin.setValue(crop.x)
        self._capture_y_spin.setValue(crop.y)
        self._capture_w_spin.setValue(crop.width)
        self._capture_h_spin.setValue(crop.height)
        self._capture_x_spin.blockSignals(False)
        self._capture_y_spin.blockSignals(False)
        self._capture_w_spin.blockSignals(False)
        self._capture_h_spin.blockSignals(False)
        self._schedule_config_save()

    def _on_capture_rect_changed(self) -> None:
        if self._is_loading_selection:
            return
        overlay_id = self._get_selected_id()
        cfg = self._find_config(overlay_id) if overlay_id else None
        win = self._overlay_windows.get(overlay_id) if overlay_id else None
        if not cfg or cfg.type != "screen" or not isinstance(win, ScreenCaptureOverlay):
            return
        x = self._capture_x_spin.value()
        y = self._capture_y_spin.value()
        w = max(1, self._capture_w_spin.value())
        h = max(1, self._capture_h_spin.value())
        capture_rect = CaptureRect(x=x, y=y, width=w, height=h)
        cfg.capture_rect = capture_rect
        if cfg.capture_mode == "region":
            cfg.source = f"Region ({x},{y}) {w}×{h}"
            self._source_edit.setText(cfg.source)
            row = self._row_widgets.get(overlay_id) if overlay_id else None
            if row:
                row.set_subtitle(self._overlay_subtitle(cfg))
                row.set_detail_tooltip(self._overlay_detail_tooltip(cfg))
        win.set_capture_region(capture_rect)
        self._schedule_config_save()

    def _on_add_window(self) -> None:
        dlg = WindowPickerDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        sel = dlg.get_selection()
        if not sel:
            return
        hwnd, title = sel
        new_id = str(uuid.uuid4())
        source_text = f"Window: {title[:50]}" + ("…" if len(title) > 50 else "")
        cfg = OverlayConfig(
            id=new_id,
            name=f"Window: {title[:30]}",
            type="screen",
            source=source_text,
            capture_mode="window",
            window_handle=hwnd,
            window_title=title,
            click_through=False,
        )
        self._get_active_profile().overlays.append(cfg)
        self._config_by_id[cfg.id] = cfg
        self._create_overlay_window(cfg)
        self._add_list_item(cfg)
        self._list.setCurrentRow(self._list.count() - 1)
        self._schedule_config_save()

    def _on_overlay_list_context_menu(self, pos: "QPoint") -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        self._list.setCurrentItem(item)
        overlay_id = item.data(Qt.UserRole)
        if not overlay_id:
            return
        cfg = self._find_config(overlay_id)
        if not cfg:
            return
        menu = QMenu(self)
        act_refresh = menu.addAction("Refresh overlay")
        act_refresh.setEnabled(cfg.type == "web")
        act_duplicate = menu.addAction("Duplicate")
        act_delete = menu.addAction("Delete")
        move_menu = menu.addMenu("Move to profile")
        move_actions: dict[QAction, str] = {}
        for profile in self._config.profiles:
            if profile.id == self._config.active_profile_id:
                continue
            action = move_menu.addAction(profile.name)
            move_actions[action] = profile.id
        move_menu.addSeparator()
        act_move_new = move_menu.addAction("New profile...")
        if cfg.type == "web":
            create_label = "Create new web overlay"
        elif cfg.type == "image":
            create_label = "Create new image overlay"
        elif cfg.type == "screen" and cfg.capture_mode == "region":
            create_label = "Create new region overlay"
        else:
            create_label = "Create new window overlay"
        act_create = menu.addAction(create_label)
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == act_refresh:
            self._on_reload_clicked()
        elif action == act_duplicate:
            self._duplicate_overlay(overlay_id)
        elif action == act_delete:
            self._on_row_delete_clicked(overlay_id)
        elif action in move_actions:
            self._move_overlay_to_profile(overlay_id, move_actions[action])
        elif action == act_move_new:
            name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
            if ok:
                name = name.strip() or "New Profile"
                new_profile = OverlayProfile(id=str(uuid.uuid4()), name=name, overlays=[])
                self._config.profiles.append(new_profile)
                self._move_overlay_to_profile(overlay_id, new_profile.id)
        elif action == act_create:
            if cfg.type == "web":
                self._on_add_web()
            elif cfg.type == "image":
                self._on_add_image()
            elif cfg.type == "screen" and cfg.capture_mode == "region":
                self._on_add_region()
            else:
                self._on_add_window()

    def _move_overlay_to_profile(self, overlay_id: str, target_profile_id: str) -> None:
        if target_profile_id == self._config.active_profile_id:
            return
        current_profile = self._get_active_profile()
        target_profile = next((p for p in self._config.profiles if p.id == target_profile_id), None)
        if not target_profile:
            return
        cfg = self._find_config(overlay_id)
        if not cfg:
            return

        current_profile.overlays = [c for c in current_profile.overlays if c.id != overlay_id]
        target_profile.overlays.append(cfg)

        if self._overlay_hotkey_callback is not None and cfg.toggle_hotkey:
            self._overlay_hotkey_callback(cfg.id, "")

        win = self._overlay_windows.pop(overlay_id, None)
        if win:
            win.close()
        self._config_by_id.pop(overlay_id, None)
        self._row_widgets.pop(overlay_id, None)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.UserRole) == overlay_id:
                self._list.takeItem(i)
                break
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._schedule_config_save()

    def _duplicate_overlay(self, overlay_id: str) -> None:
        cfg = self._find_config(overlay_id)
        if not cfg:
            return
        new_id = str(uuid.uuid4())
        copy_name = (cfg.name or cfg.id) + " (copy)"
        capture_rect = None
        if cfg.capture_rect:
            capture_rect = CaptureRect(
                x=cfg.capture_rect.x,
                y=cfg.capture_rect.y,
                width=cfg.capture_rect.width,
                height=cfg.capture_rect.height,
            )
        new_cfg = OverlayConfig(
            id=new_id,
            name=copy_name,
            type=cfg.type,
            source=cfg.source,
            x=cfg.x,
            y=cfg.y,
            width=cfg.width,
            height=cfg.height,
            opacity=cfg.opacity,
            zoom=cfg.zoom,
            toggle_hotkey="",
            click_through=cfg.click_through,
            locked=cfg.locked,
            visible=cfg.visible,
            capture_mode=cfg.capture_mode,
            capture_rect=capture_rect,
            window_handle=cfg.window_handle,
            window_title=cfg.window_title,
        )
        self._get_active_profile().overlays.append(new_cfg)
        self._config_by_id[new_cfg.id] = new_cfg
        self._create_overlay_window(new_cfg)
        self._add_list_item(new_cfg)
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole) == new_id:
                self._list.setCurrentRow(i)
                break
        self._schedule_config_save()

    def _on_delete_overlay_clicked(self) -> None:
        overlay_id = self._get_selected_id()
        if overlay_id:
            self._on_row_delete_clicked(overlay_id)

    def _on_row_delete_clicked(self, overlay_id: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Overlay")
        msg.setText("Delete this overlay?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        msg.setMaximumSize(500, 400)
        reply = msg.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._delete_overlay_by_id(overlay_id)

    def _delete_overlay_by_id(self, overlay_id: str) -> None:
        profile = self._get_active_profile()
        profile.overlays = [c for c in profile.overlays if c.id != overlay_id]
        cfg = self._config_by_id.get(overlay_id)
        if cfg and cfg.toggle_hotkey and self._overlay_hotkey_callback is not None:
            self._overlay_hotkey_callback(overlay_id, "")
        self._config_by_id.pop(overlay_id, None)

        win = self._overlay_windows.pop(overlay_id, None)
        if win:
            win.close()

        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.UserRole) == overlay_id:
                self._list.takeItem(i)
                break
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
        cfg.zoom = max(0.5, min(3.0, self._zoom_slider.value() / 100.0))

        self._opacity_value_label.setText(f"Opacity {self._opacity_slider.value()}%")
        self._zoom_value_label.setText(f"Zoom {self._zoom_slider.value()}%")
        self._overlay_title_label.setText(cfg.name or cfg.id)

        row_widget = self._row_widgets.get(overlay_id)
        if row_widget is not None:
            row_widget.set_name(cfg.name)
            row_widget.set_subtitle(self._overlay_subtitle(cfg))
            row_widget.set_detail_tooltip(self._overlay_detail_tooltip(cfg))

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
            elif isinstance(win, ScreenCaptureOverlay):
                win.set_zoom(cfg.zoom)

            win.set_overlay_opacity(cfg.opacity)

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
            self._raise_overlay_later(win)
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
        # sync zoom from overlay (e.g. after scroll-wheel zoom)
        if hasattr(win, "_zoom"):
            cfg.zoom = max(0.5, min(3.0, getattr(win, "_zoom", cfg.zoom)))
        elif callable(getattr(win, "zoom", None)):
            cfg.zoom = max(0.5, min(3.0, win.zoom()))
        # keep size and zoom controls in sync
        if overlay_id == self._get_selected_id():
            self._width_spin.blockSignals(True)
            self._height_spin.blockSignals(True)
            self._width_spin.setValue(cfg.width)
            self._height_spin.setValue(cfg.height)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(int(cfg.zoom * 100))
            self._zoom_slider.blockSignals(False)

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
        if not self._global_hotkeys_supported:
            return
        hotkey_text = sequence.toString(QKeySequence.PortableText).strip()
        if not hotkey_text:
            return

        applied_hotkey = hotkey_text
        if self._hotkey_apply_callback is not None:
            applied_hotkey = self._hotkey_apply_callback(hotkey_text)

        if not applied_hotkey:
            applied_hotkey = self._config.chat_hotkey

        if applied_hotkey != hotkey_text:
            self._hotkey_edit.blockSignals(True)
            self._hotkey_edit.setKeySequence(QKeySequence(applied_hotkey))
            self._hotkey_edit.blockSignals(False)

        if self._config.chat_hotkey != applied_hotkey:
            self._config.chat_hotkey = applied_hotkey
            self._config.focus_hotkey_enabled = bool(applied_hotkey)
            self._schedule_config_save()

        self._update_hotkey_hint(applied_hotkey)

    def _set_theme_from_ui(self, theme: ThemeType) -> None:
        self._apply_theme(theme)
        if self._config.theme != theme:
            self._config.theme = theme
            self._schedule_config_save()

    def _on_overlay_hotkey_changed(self, sequence: QKeySequence) -> None:
        if not self._global_hotkeys_supported:
            return
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
        if not self._global_hotkeys_supported:
            return
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

    def _on_clear_chat_hotkey(self) -> None:
        if not self._global_hotkeys_supported:
            return
        self._config.chat_hotkey = ""
        self._config.focus_hotkey_enabled = False
        self._hotkey_edit.blockSignals(True)
        self._hotkey_edit.setKeySequence(QKeySequence())
        self._hotkey_edit.blockSignals(False)
        if self._hotkey_apply_callback is not None:
            self._hotkey_apply_callback("")
        self._update_hotkey_hint("")
        self._schedule_config_save()

    def _on_click_through_hotkey_changed(self, sequence: QKeySequence) -> None:
        if not self._global_hotkeys_supported:
            return
        hotkey_text = sequence.toString(QKeySequence.PortableText).strip()
        applied = hotkey_text
        if self._click_through_hotkey_callback is not None:
            applied = self._click_through_hotkey_callback(hotkey_text) if hotkey_text else self._click_through_hotkey_callback("")
        if applied != hotkey_text and hotkey_text:
            self._click_through_hotkey_edit.blockSignals(True)
            self._click_through_hotkey_edit.setKeySequence(QKeySequence(applied))
            self._click_through_hotkey_edit.blockSignals(False)
        if self._config.click_through_hotkey != applied:
            self._config.click_through_hotkey = applied or ""
            self._schedule_config_save()
        self._btn_clear_click_through_hotkey.setEnabled(bool(applied))
        self._update_click_through_hint(applied or "")

    def _on_clear_click_through_hotkey(self) -> None:
        if not self._global_hotkeys_supported:
            return
        self._config.click_through_hotkey = ""
        self._click_through_hotkey_edit.blockSignals(True)
        self._click_through_hotkey_edit.setKeySequence(QKeySequence())
        self._click_through_hotkey_edit.blockSignals(False)
        if self._click_through_hotkey_callback is not None:
            self._click_through_hotkey_callback("")
        self._btn_clear_click_through_hotkey.setEnabled(False)
        self._update_click_through_hint("")
        self._schedule_config_save()

    def toggle_click_through_hotkey(self) -> None:
        overlay_id = self._get_selected_id()
        if not overlay_id:
            return
        cfg = self._find_config(overlay_id)
        win = self._overlay_windows.get(overlay_id)
        if not cfg or not win:
            return
        cfg.click_through = not cfg.click_through
        win.set_click_through(cfg.click_through)
        row = self._row_widgets.get(overlay_id)
        if row:
            row.set_click_through(cfg.click_through)
        self._schedule_config_save()

    def set_click_through_hotkey_text(self, hotkey_text: str) -> None:
        self._click_through_hotkey_edit.blockSignals(True)
        self._click_through_hotkey_edit.setKeySequence(QKeySequence(hotkey_text))
        self._click_through_hotkey_edit.blockSignals(False)
        self._update_click_through_hint(hotkey_text)
        self._btn_clear_click_through_hotkey.setEnabled(bool(hotkey_text))

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
            self._raise_overlay_later(win)
        else:
            win.hide()
        row = self._row_widgets.get(overlay_id)
        if row:
            row.set_visible(cfg.visible)
        self._schedule_config_save()

    def _refresh_overlay_topmost(self) -> None:
        if self.isVisible():
            return
        for cfg in self._get_active_profile().overlays:
            if not cfg.visible:
                continue
            win = self._overlay_windows.get(cfg.id)
            if win and hasattr(win, "ensure_topmost"):
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
        # Only consider web and window overlays; ignore image and region
        if target_id:
            cfg_sel = self._find_config(target_id)
            if cfg_sel and (
                cfg_sel.type == "image"
                or (cfg_sel.type == "screen" and cfg_sel.capture_mode == "region")
            ):
                target_id = None
        if target_id is None:
            for cfg in self._get_active_profile().overlays:
                if not cfg.visible:
                    continue
                if cfg.type == "web":
                    target_id = cfg.id
                    break
                if cfg.type == "screen" and cfg.capture_mode == "window":
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
        # Persist overlay state (visibility, lock, click-through, etc.) before closing
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_config()
        self.close()

    def _on_quit_clicked(self) -> None:
        if self._on_quit_requested is not None:
            self._on_quit_requested()
            return
        self.prepare_for_quit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_list_row_widths()
        self._update_header_responsive()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._update_list_row_widths)
        QTimer.singleShot(0, self._update_header_responsive)
        QTimer.singleShot(0, self._bring_panel_to_front)

    def _update_header_responsive(self) -> None:
        """Adjust header sizing/visibility so it stays balanced at smaller widths."""
        header = getattr(self, "_header_container", None)
        if header is None:
            return
        w = self.width()
        if w < 900:
            header.setFixedHeight(120)
            self._header_icon.setFixedSize(120, 82)
            if not self._header_icon_pix.isNull():
                self._header_icon.setPixmap(
                    self._header_icon_pix.scaled(104, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            self._header_subtitle.setVisible(False)
        else:
            header.setFixedHeight(150)
            self._header_icon.setFixedSize(160, 110)
            if not self._header_icon_pix.isNull():
                self._header_icon.setPixmap(
                    self._header_icon_pix.scaled(140, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            self._header_subtitle.setVisible(True)

    def _bring_panel_to_front(self) -> None:
        """Raise and activate the control panel so it stays above overlays."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def _update_list_row_widths(self) -> None:
        w = self._list.viewport().width()
        if w > 0:
            for row_widget in self._row_widgets.values():
                row_widget.setMinimumWidth(w)
                row_widget.setMaximumWidth(w)

    def _on_show_controls_toggled(self, checked: bool) -> None:
        self._btn_show_controls.setText(FA_TOGGLE_ON if checked else FA_TOGGLE_OFF)
        self._toggle_tools_label.setText("Hide overlay tools" if checked else "Show overlay tools")
        for row_widget in self._row_widgets.values():
            row_widget.set_tools_visible(checked)

    def _update_capture_tab_visibility(self, overlay_id: Optional[str]) -> None:
        cfg = self._find_config(overlay_id) if overlay_id else None
        is_screen = cfg is not None and cfg.type == "screen"
        idx = self._tab_widget.indexOf(self._capture_tab_widget)
        if is_screen and idx == -1:
            self._tab_widget.insertTab(2, self._capture_tab_widget, self._capture_tab_title)
        elif not is_screen and idx >= 0:
            self._tab_widget.removeTab(idx)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() == Qt.WindowState.WindowMinimized:
                self.setWindowState(Qt.WindowState.WindowNoState)
                self.hide()
                event.accept()
                return
        return super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close:
            self._allow_close = True
            if self._on_quit_requested is not None:
                self._on_quit_requested()
            self._topmost_timer.stop()
            if self._save_timer.isActive():
                self._save_timer.stop()
                self._flush_config()
            return super().closeEvent(event)
        self._topmost_timer.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_config()
        return super().closeEvent(event)
