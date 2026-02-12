import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from appdirs import user_config_dir


OverlayType = Literal["web", "image", "screen"]


@dataclass
class CaptureRect:
    """Screen rectangle: x, y, width, height (in screen coordinates)."""
    x: int
    y: int
    width: int
    height: int

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int, int, int]) -> "CaptureRect":
        return cls(x=t[0], y=t[1], width=t[2], height=t[3])


ThemeType = Literal["dark", "light", "ember", "sea", "emerald", "cherry", "pastel", "neon", "late", "fire", "galaxy", "ducky"]


@dataclass
class OverlayConfig:
    id: str
    name: str
    type: OverlayType
    source: str  # URL for web, file path for image, display text for screen
    x: int = 100
    y: int = 100
    width: int = 450
    height: int = 700
    opacity: float = 1.0
    zoom: float = 1.0
    toggle_hotkey: str = ""
    click_through: bool = False
    locked: bool = False
    visible: bool = True
    # Screen capture (only when type == "screen")
    capture_mode: Literal["region", "window"] = "region"
    capture_rect: Optional[CaptureRect] = None  # region rect or crop within window
    window_handle: int = 0
    window_title: str = ""


@dataclass
class OverlayProfile:
    id: str
    name: str
    overlays: List[OverlayConfig]


@dataclass
class AppConfig:
    profiles: List[OverlayProfile]
    active_profile_id: str = "default"
    chat_hotkey: str = ""
    focus_hotkey_enabled: bool = False
    click_through_hotkey: str = ""
    theme: ThemeType = "dark"
    keep_control_panel_on_top: bool = False


APP_NAME = "ShastasProjector"
APP_AUTHOR = "ShastasProjector"


def _config_path() -> Path:
    base = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        return AppConfig(
            profiles=[OverlayProfile(id="default", name="Default", overlays=[])],
            active_profile_id="default",
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AppConfig(
            profiles=[OverlayProfile(id="default", name="Default", overlays=[])],
            active_profile_id="default",
        )

    def _parse_overlays(items) -> List[OverlayConfig]:
        overlays: List[OverlayConfig] = []
        for item in items or []:
            try:
                overlay_type = item.get("type", "web")
                if overlay_type not in ("web", "image", "screen"):
                    overlay_type = "web"

                opacity = float(item.get("opacity", 1.0))
                opacity = max(0.2, min(1.0, opacity))

                zoom = float(item.get("zoom", 1.0))
                zoom = max(0.5, min(3.0, zoom))

                capture_rect: Optional[CaptureRect] = None
                if overlay_type == "screen":
                    cr = item.get("capture_rect")
                    if cr and isinstance(cr, dict):
                        capture_rect = CaptureRect(
                            x=int(cr.get("x", 0)),
                            y=int(cr.get("y", 0)),
                            width=max(1, int(cr.get("width", 400))),
                            height=max(1, int(cr.get("height", 300))),
                        )

                overlays.append(
                    OverlayConfig(
                        id=item["id"],
                        name=item.get("name", item["id"]),
                        type=overlay_type,
                        source=item.get("source", ""),
                        x=int(item.get("x", 100)),
                        y=int(item.get("y", 100)),
                        width=int(item.get("width", 450)),
                        height=int(item.get("height", 700)),
                        opacity=opacity,
                        zoom=zoom,
                        toggle_hotkey=str(item.get("toggle_hotkey", "")).strip(),
                        click_through=bool(item.get("click_through", False)),
                        locked=bool(item.get("locked", False)),
                        visible=bool(item.get("visible", True)),
                        capture_mode=str(item.get("capture_mode", "region")) if overlay_type == "screen" else "region",
                        capture_rect=capture_rect,
                        window_handle=int(item.get("window_handle", 0)) if overlay_type == "screen" else 0,
                        window_title=str(item.get("window_title", "") or ""),
                    )
                )
            except Exception:
                continue
        return overlays

    profiles: List[OverlayProfile] = []
    if isinstance(data.get("profiles"), list):
        for prof in data.get("profiles", []):
            try:
                prof_id = str(prof.get("id", "") or "").strip() or "default"
                name = str(prof.get("name", "Default") or "Default").strip()
                overlays = _parse_overlays(prof.get("overlays", []))
                profiles.append(OverlayProfile(id=prof_id, name=name, overlays=overlays))
            except Exception:
                continue

    if not profiles:
        legacy_overlays = _parse_overlays(data.get("overlays", []))
        profiles = [OverlayProfile(id="default", name="Default", overlays=legacy_overlays)]

    active_profile_id = str(data.get("active_profile_id", "default") or "default").strip()
    if not any(p.id == active_profile_id for p in profiles):
        active_profile_id = profiles[0].id if profiles else "default"

    chat_hotkey = str(data.get("chat_hotkey", "")).strip()
    # Legacy default was F8; clear it so the user can set their own hotkey
    if chat_hotkey == "F8":
        chat_hotkey = ""
    focus_hotkey_enabled = bool(data.get("focus_hotkey_enabled", False))
    click_through_hotkey = str(data.get("click_through_hotkey", "")).strip()
    theme = str(data.get("theme", "dark")).strip().lower()
    if theme not in ("dark", "light", "ember", "sea", "emerald", "cherry", "pastel", "neon", "late", "fire", "galaxy", "ducky"):
        theme = "dark"
    keep_control_panel_on_top = bool(data.get("keep_control_panel_on_top", False))
    return AppConfig(
        profiles=profiles,
        active_profile_id=active_profile_id,
        chat_hotkey=chat_hotkey,
        focus_hotkey_enabled=focus_hotkey_enabled,
        click_through_hotkey=click_through_hotkey,
        theme=theme,  # type: ignore[arg-type]
        keep_control_panel_on_top=keep_control_panel_on_top,
    )


def save_config(config: AppConfig) -> None:
    path = _config_path()
    serializable = {
        "profiles": [asdict(p) for p in config.profiles],
        "active_profile_id": config.active_profile_id,
        "chat_hotkey": config.chat_hotkey,
        "focus_hotkey_enabled": config.focus_hotkey_enabled,
        "click_through_hotkey": config.click_through_hotkey,
        "theme": config.theme,
        "keep_control_panel_on_top": config.keep_control_panel_on_top,
    }
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
