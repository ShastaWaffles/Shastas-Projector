import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Literal

from appdirs import user_config_dir


OverlayType = Literal["web", "image"]


ThemeType = Literal["dark", "light"]


@dataclass
class OverlayConfig:
    id: str
    name: str
    type: OverlayType
    source: str  # URL for web, file path for image
    x: int = 100
    y: int = 100
    width: int = 450
    height: int = 700
    opacity: float = 0.8
    zoom: float = 1.0
    toggle_hotkey: str = ""
    click_through: bool = False
    locked: bool = False
    visible: bool = True


@dataclass
class AppConfig:
    overlays: List[OverlayConfig]
    chat_hotkey: str = "F8"
    focus_hotkey_enabled: bool = True
    theme: ThemeType = "dark"


APP_NAME = "ShastasProjector"
APP_AUTHOR = "ShastasProjector"


def _config_path() -> Path:
    base = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        default_overlay = OverlayConfig(
            id="default-sleepychat",
            name="Sleepychat",
            type="web",
            source="",
        )
        return AppConfig(overlays=[default_overlay])

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AppConfig(overlays=[])

    overlays: List[OverlayConfig] = []
    for item in data.get("overlays", []):
        try:
            overlay_type = item.get("type", "web")
            if overlay_type not in ("web", "image"):
                overlay_type = "web"

            opacity = float(item.get("opacity", 0.8))
            opacity = max(0.2, min(1.0, opacity))

            zoom = float(item.get("zoom", 1.0))
            zoom = max(0.5, min(2.0, zoom))

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
                )
            )
        except Exception:
            continue

    chat_hotkey = str(data.get("chat_hotkey", "F8")).strip() or "F8"
    focus_hotkey_enabled = bool(data.get("focus_hotkey_enabled", True))
    theme = str(data.get("theme", "dark")).strip().lower()
    if theme not in ("dark", "light"):
        theme = "dark"
    return AppConfig(
        overlays=overlays,
        chat_hotkey=chat_hotkey,
        focus_hotkey_enabled=focus_hotkey_enabled,
        theme=theme,  # type: ignore[arg-type]
    )


def save_config(config: AppConfig) -> None:
    path = _config_path()
    serializable = {
        "overlays": [asdict(o) for o in config.overlays],
        "chat_hotkey": config.chat_hotkey,
        "focus_hotkey_enabled": config.focus_hotkey_enabled,
        "theme": config.theme,
    }
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

