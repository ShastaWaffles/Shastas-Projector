from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget, QSizeGrip
from PySide6.QtWebEngineWidgets import QWebEngineView

from .base_overlay import BaseOverlayWindow, OverlayDragHeader


class WebOverlayWindow(BaseOverlayWindow):
    """Overlay window that hosts a QWebEngineView."""

    def __init__(self, url: str, opacity: float = 0.8, locked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(opacity=opacity, locked=locked, parent=parent)

        self._url = url
        self._zoom = 1.0
        self._web_view = QWebEngineView(self)
        self._web_view.setMouseTracking(True)
        self._web_view.installEventFilter(self)
        self._web_view.setAttribute(Qt.WA_TranslucentBackground, True)
        self._web_view.setStyleSheet("background: transparent;")
        self._web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self._web_view.loadFinished.connect(self._on_load_finished)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._web_view)
        self.setLayout(root_layout)

        header = OverlayDragHeader(self, parent=self)
        self.register_header_widget(header)

        self._size_grip = QSizeGrip(self)
        self.register_resize_handle_widget(self._size_grip)

        self.load_url(url)
        self._position_chrome()

    def load_url(self, url: str) -> None:
        self._url = url
        if url:
            self._web_view.setUrl(QUrl.fromUserInput(url))
        else:
            self._web_view.setHtml(
                """
                <html>
                  <body style="margin:0;display:flex;align-items:center;justify-content:center;
                               background:#121212;color:#c4c4c4;font-family:sans-serif;">
                    Overlay URL is empty
                  </body>
                </html>
                """
            )

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        page_url = self._web_view.url().toString().lower()
        if "sleepychat" not in page_url:
            return
        self._web_view.page().runJavaScript(
            """
            (() => {
              const styleId = "__sp_transparency_fix__";
              let style = document.getElementById(styleId);
              if (!style) {
                style = document.createElement("style");
                style.id = styleId;
                document.head.appendChild(style);
              }
              style.textContent = `
                html, body { background: transparent !important; }
                #root, .app, main { background: transparent !important; }
              `;
            })();
            """
        )

    def reload(self) -> None:
        self._web_view.reload()

    def focus_chat_input(self) -> None:
        self.raise_()
        self.activateWindow()
        self._web_view.setFocus()
        self._web_view.page().runJavaScript(
            """
            (() => {
              const selectors = [
                'textarea[placeholder*="Send a message"]',
                'textarea[placeholder*="command"]',
                'textarea[placeholder*="message"]',
                'input[placeholder*="Send a message"]',
                'input[placeholder*="command"]',
                'input[placeholder*="message"]',
                'textarea',
                'input[type="text"]',
                '[contenteditable="true"]'
              ];
              const focusInDoc = (doc) => {
                if (!doc) return false;
                let target = null;
                for (const s of selectors) {
                  target = doc.querySelector(s);
                  if (target) break;
                }
                if (!target) {
                  const editables = Array.from(doc.querySelectorAll('input, textarea, [contenteditable="true"]'))
                    .filter((el) => !el.disabled);
                  target = editables.length ? editables[0] : null;
                }
                if (!target) return false;
                target.focus({ preventScroll: true });
                if (typeof target.click === 'function') target.click();
                target.dispatchEvent(new Event('input', { bubbles: true }));
                if (typeof target.setSelectionRange === 'function' && typeof target.value === 'string') {
                  const end = target.value.length;
                  target.setSelectionRange(end, end);
                }
                return true;
              };

              if (focusInDoc(document)) return true;
              const iframes = Array.from(document.querySelectorAll('iframe'));
              for (const iframe of iframes) {
                try {
                  if (focusInDoc(iframe.contentDocument)) return true;
                } catch (e) {}
              }
              return false;
            })();
            """
        )

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.5, min(2.0, zoom))
        self._web_view.setZoomFactor(self._zoom)
        if self.on_state_changed:
            self.on_state_changed()

    def zoom(self) -> float:
        return self._zoom

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_chrome()

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

    @property
    def url(self) -> str:
        return self._url

