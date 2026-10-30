[Español](../es/PROBLEMAS.md) · **English** · [Home](../../README.md)

# Troubleshooting

**First, two checks that solve most cases:**

```bash
oweecapture --version      # which version is installed?
oweecapture --comprobar    # what is missing from the system?
```

And look at the logs (explained below): `~/.cache/oweecapture/arranque.log` and `~/.cache/oweecapture/error.log`.

## "Acerca de" (About) shows an old version

You just updated, but the previous copy is still open (it starts with the session and stays in memory). Close it and open again:

```bash
oweecapture --quit
```

or tray icon → *Salir* (Quit). If it does not respond, find the process with `pgrep -f oweecapture.qtapp` and close it with `kill <number>`. To open it again without depending on the terminal:

```bash
systemd-run --user --quiet --collect --unit=app-oweecapture-$RANDOM /usr/bin/oweecapture --segundo-plano
```

> Do not launch the program with `--scope` in a terminal and then press `Ctrl+C`: it closes it.

## Nothing opens (no window, no icon)

1. Open it from a terminal: `oweecapture`. The error shows there.
2. If you launch it from the menu there is no terminal; look at `~/.cache/oweecapture/arranque.log`. **That file accumulates**: what you see at the end is the latest, but there can be errors from old attempts above. To start clean: `: > ~/.cache/oweecapture/arranque.log`.
3. Typical errors:
   - `No module named 'oweecapture'`: incomplete installation or broken by an old version. With the `.deb`: `sudo apt purge oweecapture` and install the latest version again.
   - `Could not find the Qt platform plugin "dxcb"` (Deepin): fixed since 0.1.3; update.
   - `No module named 'PySide6'` or `libxcb…`: a system library is missing; run `oweecapture --comprobar`.

## Recording does not work or stops instantly

- **Message "El portal de pantalla falló"** (the screen portal failed) (X11 desktops such as Deepin): use version **0.1.6 or later**, which records without a portal on X11 sessions. Check your session with `echo $XDG_SESSION_TYPE` (`x11` or `wayland`).
- **KDE/GNOME (Wayland):** you need `xdg-desktop-portal` with your desktop's module (`xdg-desktop-portal-kde` or `xdg-desktop-portal-gnome`) and PipeWire. The first time you record, the desktop shows a screen-sharing permission prompt; you must accept it.
- **It stops and the video is empty or nothing is saved:** look at the end of `~/.cache/oweecapture/error.log`. Include it if you open an issue.
- **"Guardando…" (Saving) lasts a long time:** with zoom or halo, the video is rewritten at the end (~0.8 s per second recorded). With *WhatsApp* quality, the later reduction runs in the background and the video can already be opened.
- **Low disk space:** it does not record with less than 1 GB free.

## No global shortcuts

Message: "Tu escritorio no ofrece atajos globales a las aplicaciones" (your desktop does not offer global shortcuts to applications). This is normal on **Deepin** and on **GNOME before 48**. The application works the same; create the shortcuts in your desktop's keyboard settings, assigning these commands:

| Command | Does |
|---|---|
| `oweecapture --record` | Record / stop |
| `oweecapture --shot` | Screenshot |
| `oweecapture --present` | Presentation mode |
| `oweecapture --camera` | Hide / show the camera bubble |
| `oweecapture --quit` | Quit |

If the key you want is already used by the system (on Deepin `Ctrl+Alt+R` is its recorder), choose another, e.g. `Ctrl+Alt+Shift+R`. Also enable "Iniciar OweeCapture al abrir la sesión" (start with the session) so it handles the commands from the moment the desktop starts.

**On KDE, a new shortcut has no key:** after installing a version with a new shortcut (for example `Ctrl+Alt+C` in 0.1.8), KDE only assigns the key on the **second** start. Close the program and open it twice.

## Zoom or halo do nothing

- They only work on **KDE Plasma** (they need KWin); on other desktops the options appear disabled.
- Zoom is only applied if you press `Ctrl+Alt+Z` during the recording; if you do not press it, the video has no zoom. Look at the tray icon: it changes to a magnifier while active.
- It is applied **when the recording ends**, not live in the video.

## Clicks and keys do not appear

Your user must be in the `input` group: `sudo usermod -aG input $USER` and **log out and back in** (restarting the program is not enough). Check with `groups`.

## The presentation toolbar or menus appear in the video

Exclusion from the recording only works on **KDE with KWin 6.4 or later**. On other desktops there is no way to hide a window; record only a region and keep the toolbar outside it.

## Live streaming

- **"No se pudo conectar con el servidor"** (could not connect to the server): check the server address and the key; copy them again from the platform, without spaces.
- **It drops and comes back:** that is the automatic reconnection; the local copy keeps recording. The status is shown in the window.
- **The noise-free microphone does not appear:** the PipeWire echo-cancel module is missing; it streams with the normal microphone and tells you.
- **Fedora:** without RPM Fusion there is no H.264/AAC (see [INSTALLATION.md](INSTALLATION.md)).

## Subtitles

- They ask to download the engine the first time (about 620 MB; internet is only needed for that).
- To remove it and recover the space: delete `~/.local/share/oweecapture/voz` and `~/.local/share/oweecapture/modelos`.

## GNOME

Still untested. Things to know: the tray icon is only visible with the *AppIndicator* extension, global shortcuts only exist since GNOME 48 (before that, create your own), and windows cannot be kept always on top or hidden from the recording.

## Asking for help

Open an issue in the repository with: your distribution and desktop, `echo $XDG_SESSION_TYPE`, `oweecapture --version`, and the end of `error.log` and `arranque.log`. **Review before pasting** that there are no stream keys: they are not stored in the logs, but it is worth checking.
