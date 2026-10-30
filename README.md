[Español](README.es.md) · **English**

<p align="center"><img src="data/icons/oweecapture-128.png" alt="OweeCapture logo: a koi inside a round lens" width="128"></p>

# OweeCapture

Screen recorder, screenshots, live streaming and video tools for Linux, made for people who create **tutorials and content** (YouTube, TikTok, Shorts, Reels, WhatsApp).

- **Records** the screen, a region, or vertical 9:16, with system audio, microphone and a camera bubble.
- **Streams live** over RTMP to YouTube, TikTok, Twitch or any server, keeping a local copy.
- **Helps you explain**: one-key zoom, clips of the last few seconds, presentation mode to draw on the screen, clicks and keys shown on screen.
- **Finishes the video**: trim, cut silences, convert to vertical and automatic subtitles (all on your computer, nothing is sent to the internet).

Author: Hector Martinez · [hector@oweeme.com](mailto:hector@oweeme.com) · https://oweeme.com · License GPL-3.0-or-later.

> **The application interface is currently in Spanish** (its translation catalogs cover only a few messages). In this documentation, button and option names are written as they appear on screen, followed by an English translation the first time. The documentation is available in English and Spanish.

## Get started in 3 steps

1. **Install** (Debian, Ubuntu, Deepin, Mint): download the `.deb` from the [latest release](../../releases/latest) and run `sudo apt install ./oweecapture_<version>_all.deb`.
   Other distributions (Fedora, Arch, openSUSE…): [docs/en/INSTALLATION.md](docs/en/INSTALLATION.md).
2. **Open it** from the applications menu ("OweeCapture") and check with `oweecapture --version`.
3. **Record**: press *Grabar* (Record), pick the region, done. Videos are saved in `Videos/Screen Recordings`.

To make the shortcuts work from the moment the desktop starts, enable "Iniciar OweeCapture al abrir la sesión" (start with the session) in the *Grabar* tab.

## Shortcuts

| Shortcut | Command (for desktops without global shortcuts) | What it does |
|---|---|---|
| `Ctrl+Alt+R` | `oweecapture --record` | Start / stop recording |
| `Ctrl+Alt+S` | `oweecapture --shot` | Screenshot |
| `Ctrl+Alt+P` | — | Pause / resume |
| `Ctrl+Alt+Z` | — | Zoom in / out while recording |
| `Ctrl+Alt+G` | — | Save a clip of the last few seconds |
| `Ctrl+Alt+D` | `oweecapture --present` | Presentation mode (draw on screen) |
| `Ctrl+Alt+C` | `oweecapture --camera` | Hide / show the camera bubble while recording |
| — | `oweecapture --quit` | Quit the program |

## Documentation

| I want to… | Read |
|---|---|
| Learn to use it, task by task | [docs/en/GUIDE.md](docs/en/GUIDE.md) |
| Install, update or uninstall | [docs/en/INSTALLATION.md](docs/en/INSTALLATION.md) |
| Fix a problem (won't record, won't open, no shortcuts…) | [docs/en/TROUBLESHOOTING.md](docs/en/TROUBLESHOOTING.md) |
| See what works on each desktop | [docs/en/DESKTOPS.md](docs/en/DESKTOPS.md) |
| See what changed in each version | [CHANGELOG.md](CHANGELOG.md) |
| Develop, test and release versions | [docs/en/DEVELOPMENT.md](docs/en/DEVELOPMENT.md) |

Other project documents (Spanish only): [PLAN.md](PLAN.md) (roadmap) and [docs/DECISION-LENGUAJE.md](docs/DECISION-LENGUAJE.md) (why Python and Qt).

## Status

Version 0.1.x. **Really tested on KDE Plasma 6 (Wayland)**, where everything works. On **Deepin (X11)** screenshots and recording work; **GNOME** is untested. **Windows and Android are not supported** (see [docs/en/DESKTOPS.md](docs/en/DESKTOPS.md)).
