[Español](../es/DESARROLLO.md) · **English** · [Home](../../README.md)

# Development

## Run from the source

```bash
PYTHONPATH=src python3 -m oweecapture.qtapp                      # main window
PYTHONPATH=src python3 -m oweecapture.qtapp --segundo-plano      # tray and shortcuts only
```

System dependencies: see [INSTALLATION.md](INSTALLATION.md) (`./install.sh --dependencias` installs them). On KDE, the desktop gives the application its own identity (needed for the portal and shortcuts) if it is launched from the menu or with:

```bash
systemd-run --user --quiet --collect --unit=app-oweecapture-$RANDOM python3 -m oweecapture.qtapp --segundo-plano
```

## Tests

```bash
python3 tests/ejecutar.py        # the runner exits with the real result
```

They are screenless tests (Qt in `offscreen` mode) and include a fake portal and a fake KWin to check that the application opens even if the desktop is incomplete (the Deepin case), GStreamer pipeline tests and `.deb` package tests. **Every fix for a real bug should come with a test that fails with the old code.**

`tests/ejecutar.py` ends the process with `os._exit` using the test result: with the PyPI Qt, a normal shutdown can abort due to memory corruption on exit, and that would falsify the result.

## Structure (`src/oweecapture/`)

| Module | What it does |
|---|---|
| `qtapp.py` | Main window, tray, shortcuts, `--version`, `--comprobar` |
| `portal.py` | Recording: ScreenCast portal + PipeWire, or `ximagesrc` on X11; GStreamer pipelines, pause, clips |
| `captura.py` | Screenshots through the portal |
| `atajos.py` | Global shortcuts (GlobalShortcuts portal) |
| `servicio.py` | Single instance over D-Bus; commands `--record`, `--shot`, `--present`, `--camera`, `--quit` |
| `kwin.py` | Everything done with KWin: cursor, windows, always-on-top, exclude from capture |
| `directo.py`, `ruido_vivo.py` | RTMP streaming with reconnection; live noise-free microphone |
| `audio.py`, `efectos.py` | Audio mixing and filters; zoom and halo at the end |
| `herramientas.py`, `ventana_herramientas.py`, `reproductor.py` | Trim, vertical, silences and their window with preview |
| `subtitulos.py`, `transcriptor.py` | Local subtitles with faster-whisper |
| `entrada.py`, `efectos_pantalla.py` | Clicks and keys on screen |
| `marco.py`, `selector.py`, `burbuja.py`, `presentacion.py` | Windows over the screen |
| `core.py`, `clips.py`, `inicio.py`, `autor.py`, `i18n.py` | Settings, recovery, clips, autostart, author data, translations |

## Things that are hard to discover

- **Every portal call can fail** (the desktop does not offer GlobalShortcuts, ScreenCast…). `dbus.DBusException`, `TypeError` and `ValueError` are caught and a warning is shown; startup is never allowed to crash.
- **KWin does not exist outside KDE:** `kwin.disponible()` checks that the service really exists before using it.
- **Qt on X11 needs xcb libraries** and, with Deepin's `dxcb` platform, `xcb` is forced (`_plataforma()` in `qtapp.py`).
- **New shortcuts on KDE:** they only get a key on the second start.
- **An upgraded `.deb` runs the old package's `postrm` after unpacking the new one:** that is why the code lives in `/usr/lib/oweecapture` and `postrm` only acts on `remove` and `purge`.
- **With the PyPI Qt** tests can fail because of the shutdown; see `tests/ejecutar.py`.
- **Delete only what the test creates:** never "the newest video" in `Videos`; only paths the test itself printed.

## Build the .deb

```bash
bash packaging/crear_deb.sh      # leaves dist/oweecapture_<version>_all.deb
```

The version comes from `src/oweecapture/__init__.py`. The script rejects an invalid version and a description with non-ASCII characters (it breaks `apt`).

## Release a version

1. Bump the number in **two** places: `src/oweecapture/__init__.py` (`__version__`) and `src/oweecapture/autor.py` (`VERSION`).
2. Add the entry to [CHANGELOG.md](../../CHANGELOG.md) and [CHANGELOG.es.md](../../CHANGELOG.es.md).
3. Tests green, `git commit`, `git push origin main`.
4. Tag and push: `git tag -a vX.Y.Z -m "OweeCapture X.Y.Z" && git push origin vX.Y.Z`.
5. The **Lanzamiento** (release) workflow (`.github/workflows/lanzamiento.yml`) runs the tests, builds the `.deb` and the source, tests the installation on several distributions and publishes the release with `SHA256SUMS`.

## Continuous integration (`.github/workflows/`)

- `ci.yml`: tests on every push.
- `instaladores.yml`: really installs in containers — `.deb` on Debian 12/13 and Ubuntu 24.04/25.10; `install.sh` on Ubuntu, Fedora, Arch and openSUSE; **update over the latest published version** and over a broken environment; a real Qt window with a virtual screen (Xvfb).
- `lanzamiento.yml`: when a `v*` tag is created.

## Conventions

- Code and messages in Spanish; interface texts go through `_()` (translations in `locales/`).
- Commit messages in Spanish, with no tool attributions or co-authors.
- The logo is generated with `python3 tools/generar_logo.py` (SVG and PNG from 16 to 512 px).
