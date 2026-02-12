
![Shastas Projector](screenshots/shastas_projector.png)

# Shasta's Projector (v2.0.0)

A cross-platform desktop overlay app for streamers who want chat and visual widgets **on top of their game** without keeping a browser open.

Built for streamers who play in borderless or windowed fullscreen and want a lightweight, always-on-top overlay that stays out of the way during gameplay.


---
## Features of v2.0.0

- Region screen capture overlays
- Window capture overlays
- Window picker for selecting app/game windows
- Window crop picker for precise capture areas
- Overlay profiles (create, rename, delete, switch)
- Move overlays between profiles
- Duplicate overlays quickly
- Per-overlay controls:
  - Visibility
  - Lock / unlock
  - Click-through
  - Opacity
  - Zoom
  - Size / position
- Per-overlay visibility hotkeys
- Chat focus hotkey
- Click-through toggle hotkey
- macOS global hotkey support
- Improved system tray controls (open/hide/quit)
- Cross-platform support for Windows and macOS
- Cross-platform CI builds (Windows + macOS)
- PyInstaller packaging improvements for multi-OS builds
- Starts clean on first run (no default overlays)
- Simplified UI (removed overlay notes system)

---

## Best Use for Streamers

This app is designed for **borderless or windowed fullscreen** workflows so chat and overlays can stay visible over games.

⚠️ **Important:**  
True **exclusive fullscreen** in some games (including Minecraft) can bypass desktop overlays due to OS/GPU behavior.  
For reliable overlays, use **borderless** or **windowed fullscreen** modes.

---

## Screenshots / Demo

<img width="1095" height="698" alt="image" src="https://github.com/user-attachments/assets/5b8332f9-5871-41f3-a87c-fb6fa37d9dae" />

<img width="390" height="424" alt="image" src="https://github.com/user-attachments/assets/645b9501-daf9-4653-a022-435f9a25fe93" />


![Empty Overlay Screenshot](screenshots/projector-empty-overlay.png)

![Sleepychat Minecraft Overlay Example](screenshots/sleepychat-overlay-example.png)


---

## Requirements

- Python 3.10+ (3.11+ recommended)
- Dependencies listed in `requirements.txt`

---

## Local Run

```bash
pip install -r requirements.txt
python -m overlay_app.app
```

## Packaging (PyInstaller)

Build on each OS natively:
- Windows build on Windows
- macOS build on macOS
- Linux build on Linux

Install build tooling:

```bash
pip install -r requirements.txt pyinstaller
```

### Windows

```powershell
pyinstaller --name "ShastasProjector" --windowed --onedir `
  --icon overlay_app/resources/projectoricon.png `
  --add-data "overlay_app/resources;overlay_app/resources" `
  -m overlay_app.app
```

### macOS / Linux

```bash
pyinstaller --name "ShastasProjector" --windowed --onedir \
  --icon overlay_app/resources/projectoricon.png \
  --add-data "overlay_app/resources:overlay_app/resources" \
  -m overlay_app.app
```

Output is created in `dist/ShastasProjector/`.

## Project Structure

```text
overlay_app/
  app.py
  models/
  overlays/
  ui/
  resources/
```

## License

MIT License

Copyright (c) 2026 ShastaWaffles

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...

