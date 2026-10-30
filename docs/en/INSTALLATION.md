[Español](../es/INSTALACION.md) · **English** · [Home](../../README.md)

# Installation, update and uninstall

Both ways are **tested on every release** in clean GitHub Actions containers: it is really installed and `oweecapture --comprobar` (the self-check) is run. Linux only.

## Debian, Ubuntu, Deepin, Mint and derivatives (.deb)

Tested on Debian 12 and 13 and on Ubuntu 24.04 and 25.10.

1. Download `oweecapture_<version>_all.deb` from the [latest release](../../../../releases/latest). Next to it there is a `SHA256SUMS` file in case you want to verify it: `sha256sum -c SHA256SUMS`.
2. Install it:
   ```bash
   sudo apt install ./oweecapture_<version>_all.deb
   ```
3. Check: `oweecapture --version`.

**Where it is installed:** the code in `/usr/lib/oweecapture` and the launcher in `/usr/bin/oweecapture`. If your system does not provide PySide6 (for example Ubuntu 24.04), the installation creates a private environment in `/opt/oweecapture/venv` and downloads it from PyPI (about 100 MB, internet required).

## Fedora, Arch/Manjaro, openSUSE and any other (install.sh)

Download `oweecapture-<version>-fuente.tar.gz` ("fuente" = source) from the release (or clone the repository), unpack it and, inside the folder:

```bash
./install.sh --dependencias
```

- It installs in **your home folder** (`~/.local`), without touching the system.
- `--dependencias` (dependencies) installs, with your package manager (apt, dnf, pacman or zypper), the system packages: GStreamer, ffmpeg, PipeWire, portal… It shows you the command and **asks before using `sudo`**. With `--si` (yes) it does not ask (for scripts).
- It finishes by running `oweecapture --comprobar`, which tells you what is missing.
- Other options: `--prefijo DIR` (install in another folder) and `--ayuda` (help).

**Fedora:** it does not include the H.264 and AAC encoders because of licensing. Enable [RPM Fusion](https://rpmfusion.org/Configuration) and install: `sudo dnf install gstreamer1-plugins-ugly gstreamer1-libav ffmpeg --allowerasing`.

**Unknown distribution:** the script says so and lists what you need by hand: Python 3.11 or later with venv, PyGObject, dbus-python, GStreamer (base, good, bad, ugly, libav, pipewire), ffmpeg, PipeWire and xdg-desktop-portal.

## Check that everything is fine

```bash
oweecapture --version      # installed version
oweecapture --comprobar    # starts Qt without a screen and says what is missing (ffmpeg, GStreamer plugins…)
```

## Update

- **.deb:** install the new one over it: `sudo apt install ./oweecapture_<new>_all.deb`. This **does not delete** the program (fixed in 0.1.5).
- **install.sh:** download the new version and run `./install.sh` again.
- **Afterwards, close and reopen the program.** The copy that was already open keeps the old code in memory: "Acerca de" (About) will show the old version until you restart it. Use the tray icon → *Salir* (Quit), or `oweecapture --quit`, and open it again.
- On KDE, if the new version brings a new shortcut, the key is only assigned after opening the program **twice**.

## Uninstall

- **.deb:** `sudo apt remove oweecapture` (or `purge`). It removes the program and the private environment in `/opt/oweecapture`; your settings and videos are not touched.
- **install.sh:** `./install.sh --desinstalar` (only removes what the script installed).
- To remove everything: delete `~/.config/oweecapture` (settings), `~/.cache/oweecapture` (logs), `~/.local/share/oweecapture` (subtitle engine, if you installed it, about 620 MB) and the file `~/.config/autostart/oweecapture.desktop`.
