from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from .base_overlay import BaseOverlayWindow, OverlayDragHandle


class _OverlayWebPage(QWebEnginePage):
    """Web page that suppresses JS console output so third-party page errors don't flood the terminal."""

    def javaScriptConsoleMessage(
        self,
        level: "QWebEnginePage.JavaScriptConsoleMessageLevel",
        message: str,
        line_number: int,
        source_id: str,
    ) -> None:
        # Suppress: React #418, TikTok connector errors, etc. come from the loaded page, not our app.
        pass


class WebOverlayWindow(BaseOverlayWindow):
    """Overlay window that hosts a QWebEngineView."""

    def __init__(self, url: str, opacity: float = 0.8, locked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(opacity=opacity, locked=locked, parent=parent)

        self._url = url
        self._zoom = 1.0
        self._web_view = QWebEngineView(self)
        page = _OverlayWebPage(QWebEngineProfile.defaultProfile(), self._web_view)
        page.setBackgroundColor(QColor(0, 0, 0, 0))
        self._web_view.setPage(page)
        self._web_view.setMouseTracking(True)
        self._web_view.installEventFilter(self)
        self._web_view.setAttribute(Qt.WA_TranslucentBackground, True)
        self._web_view.setStyleSheet("background: transparent;")
        self._web_view.loadFinished.connect(self._on_load_finished)

        root_layout = QVBoxLayout()
        m = BaseOverlayWindow.RESIZE_MARGIN
        root_layout.setContentsMargins(m, m, m, m)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._web_view)
        self.setLayout(root_layout)

        self._drag_handle = OverlayDragHandle(self, parent=self)
        self._drag_handle.move(m + 6, m + 6)
        self._drag_handle.raise_()

        self.load_url(url)
        self._raise_chrome()

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
        self._raise_chrome()
        if hasattr(self, "_drag_handle") and self._drag_handle is not None:
            m = BaseOverlayWindow.RESIZE_MARGIN
            self._drag_handle.move(m + 6, m + 6)
            self._drag_handle.raise_()

    def _raise_chrome(self) -> None:
        """Keep drag handle above the web view so it receives clicks."""
        if hasattr(self, "_drag_handle") and self._drag_handle is not None:
            self._drag_handle.raise_()

    def _apply_interaction_state(self) -> None:
        super()._apply_interaction_state()
        interactive = not self._locked and not self.is_click_through()
        if hasattr(self, "_drag_handle") and self._drag_handle is not None:
            self._drag_handle.setEnabled(interactive)
            self._drag_handle.setVisible(interactive)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._raise_chrome()

    def pan_content(self, dx: int, dy: int) -> None:
        """Pan the web page by (dx, dy) pixels. Ctrl+drag inside overlay to use."""
        self._web_view.page().runJavaScript(f"window.scrollBy({dx}, {dy})")

    def fit_to_overlay(self) -> None:
        """Scroll to top and reset view so content fits in the overlay."""
        self._web_view.page().runJavaScript("window.scrollTo(0, 0)")
        if self.on_state_changed:
            self.on_state_changed()

    @property
    def url(self) -> str:
        return self._url

