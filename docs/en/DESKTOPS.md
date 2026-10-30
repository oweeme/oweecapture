[Español](../es/ESCRITORIOS.md) · **English** · [Home](../../README.md)

# What works on each desktop

Real status, tested or not. "Untested" means the code exists but nobody has used it on that desktop.

| Feature | KDE Plasma 6 (Wayland) | Deepin (X11) | GNOME | Windows |
|---|---|---|---|---|
| Open the application | Yes | Yes | Untested | No |
| Screenshot | Yes | Yes | Untested | No |
| Record screen or region | Yes (portal + PipeWire) | Yes (direct X11 capture, since 0.1.6) | Untested | No |
| System audio and microphone | Yes | Untested | Untested | No |
| Global shortcuts | Yes | No: create your own with the `--record`, `--shot`… commands | Only GNOME 48 or later; before that, manual shortcuts | No |
| Automatic zoom and cursor halo | Yes | No (needs KWin) | No | No |
| Yellow frame and vertical 9:16 | Yes | Untested | Untested | No |
| Camera bubble | Yes | Untested | Untested | No |
| Keep the presentation toolbar and tray menus out of the recording | Yes (KWin 6.4 or later) | No | No | No |
| RTMP live streaming | Yes | Untested | Untested | No |
| Video tools and subtitles | Yes | Untested | Untested | No |
| Tray icon | Yes | Yes | Needs the AppIndicator extension | No |

## Why it changes from one desktop to another

- **Wayland (KDE, GNOME):** an application cannot capture the screen by itself; it asks the desktop's *portal* (xdg-desktop-portal), which shows its own permission prompt and delivers a PipeWire stream.
- **X11 (Deepin, others):** that portal does not exist. Since 0.1.6 OweeCapture detects the X11 session and captures the screen directly with GStreamer.
- **Global shortcuts:** KDE offers them to applications; Deepin and older GNOME do not. There they are created in the desktop's own keyboard settings, assigning one of the commands (`oweecapture --record`, etc.).
- **Automatic zoom, hiding windows from the recording:** they depend on KWin, KDE's window manager.

## Windows

There is no installer yet, and one cannot be faked: most of the capture depends on Linux components. Each has a Windows equivalent, but it must be rewritten and tested on a real Windows:

| Piece | On Linux | On Windows |
|---|---|---|
| Screen capture | portal + PipeWire (or `ximagesrc`) | GStreamer `d3d11screencapturesrc` or ffmpeg `ddagrab` |
| Audio | PipeWire | `wasapi2src` (system audio through loopback) |
| Global shortcuts | portal / KGlobalAccel | `RegisterHotKey` |
| Hide windows from the recording | KWin | `SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE` |
| Installer | `.deb`, `install.sh` | `.exe` with PyInstaller |

The Qt interface, streaming, video tools and subtitles would be reused as they are. Planned order: 1) video tools and subtitles, 2) recording and shortcuts, 3) streaming and camera, 4) installer. Someone with Windows is needed to test each phase.

## Android

No. This application depends on Linux desktop components. A mobile version would be a new project.
