[Español](CHANGELOG.es.md) · **English**

# Changelog

## 0.1.9
- The pop-up menus of the tray icon no longer appear in the recording (KDE).

## 0.1.8
- Camera bubble: it can be **hidden and shown again while recording** (tray icon, `Ctrl+Alt+C` or `oweecapture --camera`).
- The **presentation-mode toolbar does not appear in the video**: you see it on your screen, but it is excluded from recordings and streams (KDE with KWin 6.4 or later).

## 0.1.7
- When you press Stop, the yellow frame and the highlights disappear immediately (before, they waited until saving finished).
- The background quality reduction is faster.

## 0.1.6
- **Recording on X11 sessions** (Deepin): direct screen capture without a portal. Before, recording stopped instantly with "El portal de pantalla falló" (the screen portal failed).

## 0.1.5
- **Updating no longer leaves the program without files** (bug seen on Deepin): the code lives in `/usr/lib/oweecapture` and `postrm` only deletes things on remove or purge.

## 0.1.4
- The private environment with PySide6 always sees the package: system Python, `.pth` file and a failure-proof launcher.
- The old private environment is removed when the system already provides PySide6.

## 0.1.3
- The application opens even if the portal and KWin are incomplete (Deepin): before, it failed at startup.

## 0.1.2
- Qt opens windows on X11: xcb libraries are now required, startup log (`arranque.log`) and a test with a virtual screen.

## 0.1.1
- **Universal installer**: a `.deb` that brings its own PySide6 if the system has none, `install.sh` for Fedora, Arch and openSUSE, and installation tests on each distribution.
- Fixed the `.deb` description and removed the QtDBus dependency, which broke installation on Deepin.

## 0.1.0
- First public version under the name **OweeCapture**, with a `.deb` package and automated tests on GitHub Actions: recording through portal + PipeWire, screenshots, on-demand zoom and cursor halo, audio mixer and noise reduction, RTMP streaming with reconnection, clips, video tools (trim, vertical, silences), local subtitles, vertical recording with a draggable frame, clicks and keys on screen, presentation mode, camera bubble with effects, start with the desktop.
