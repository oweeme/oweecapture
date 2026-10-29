#!/usr/bin/env bash
# Construye el paquete .deb de OweeCapture (Debian, Ubuntu, KDE neon, Mint, Deepin…): arquitectura «all» (solo Python), sin compilar nada.
# Uso: packaging/crear_deb.sh [versión]      →  dist/oweecapture_<versión>_all.deb
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"; cd "$RAIZ"
VERSION="${1:-$(python3 -c 'import re,sys; print(re.search(r"__version__ = \"([^\"]+)\"", open("src/oweecapture/__init__.py").read()).group(1))')}"; VERSION="${VERSION#v}"
[[ "$VERSION" =~ ^[0-9][0-9A-Za-z.+~-]*$ ]] || { echo "versión no válida: $VERSION" >&2; exit 1; }
PKG="oweecapture_${VERSION}_all"; B="$(mktemp -d)/$PKG"; trap 'rm -rf "$(dirname "$B")"' EXIT
mkdir -p "$B/DEBIAN" "$B/usr/lib/oweecapture" "$B/usr/bin" "$B/usr/share/applications" "$B/usr/share/oweecapture/locales" "$B/usr/share/icons/hicolor/scalable/apps" "$B/usr/share/doc/oweecapture"

# código (sin cachés) en /usr/lib/oweecapture, una carpeta propia: el postrm de las versiones <= 0.1.4 borraba /usr/lib/python3/dist-packages/oweecapture al ACTUALIZAR y dpkg lo ejecuta después de desempaquetar la nueva
#   versión, así que el programa desaparecía. Fuera de dist-packages ese borrado ya no le alcanza.
cp -r src/oweecapture "$B/usr/lib/oweecapture/oweecapture"; find "$B" -name __pycache__ -type d -prune -exec rm -rf {} +
# comando
cat > "$B/usr/bin/oweecapture" <<'EOF'
#!/bin/sh
# Si el instalador tuvo que crear un entorno propio con PySide6 (la distribucion no lo empaqueta), se usa ese; si no, el Python del sistema.
# Desde el menu no hay terminal: los errores de arranque (p. ej. a Qt le falta una biblioteca) se guardan en ~/.cache/oweecapture/arranque.log
if [ ! -t 2 ]; then d="${XDG_CACHE_HOME:-$HOME/.cache}/oweecapture"; mkdir -p "$d" 2>/dev/null && exec 2>>"$d/arranque.log"; fi
export PYTHONPATH="/usr/lib/oweecapture${PYTHONPATH:+:$PYTHONPATH}"          # el programa vive en /usr/lib/oweecapture
V=/opt/oweecapture/venv/bin/python
if [ -x "$V" ] && "$V" -c "import oweecapture, PySide6.QtWidgets" >/dev/null 2>&1; then exec "$V" -m oweecapture.qtapp "$@"; fi          # un entorno roto no impide arrancar: se cae al Python del sistema
exec /usr/bin/python3 -m oweecapture.qtapp "$@"
EOF
chmod 755 "$B/usr/bin/oweecapture"
# lanzador, iconos, traducciones, licencia y documentación
install -m 644 data/oweecapture.desktop "$B/usr/share/applications/oweecapture.desktop"
install -m 644 data/icons/oweecapture.svg "$B/usr/share/icons/hicolor/scalable/apps/oweecapture.svg"
for n in 16 24 32 48 64 128 256 512; do mkdir -p "$B/usr/share/icons/hicolor/${n}x${n}/apps"; install -m 644 "data/icons/oweecapture-$n.png" "$B/usr/share/icons/hicolor/${n}x${n}/apps/oweecapture.png"; done
install -m 644 locales/*.json "$B/usr/share/oweecapture/locales/"
install -m 644 LICENSE "$B/usr/share/doc/oweecapture/copyright"; install -m 644 README.md "$B/usr/share/doc/oweecapture/README.md"
find "$B" -type d -exec chmod 755 {} +

TAM=$(du -sk --exclude=DEBIAN "$B" | cut -f1)
cat > "$B/DEBIAN/control" <<EOF
Package: oweecapture
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Maintainer: Hector Martinez <hector@oweeme.com>
Homepage: https://oweeme.com
Installed-Size: $TAM
Depends: python3 (>= 3.11), python3-venv, python3-gi, python3-dbus, gir1.2-gstreamer-1.0, gstreamer1.0-pipewire, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-ugly, gstreamer1.0-libav, ffmpeg, pipewire, xdg-desktop-portal, libgl1, libegl1, libxkbcommon0, libfontconfig1, libdbus-1-3, libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libwayland-client0, libwayland-cursor0, libwayland-egl1
Recommends: python3-pyside6.qtcore, python3-pyside6.qtgui, python3-pyside6.qtwidgets, xdg-desktop-portal-kde | xdg-desktop-portal-gnome | xdg-desktop-portal-wlr, libnotify-bin
Description: screenshots, screen recording, live streaming and video tools
 OweeCapture takes screenshots and records the screen (with system audio, microphone and webcam) on Wayland through the desktop portal. It streams live over RTMP (YouTube, TikTok, Twitch) with a local copy and automatic reconnection, and includes tools to publish videos: vertical 9:16, trimming, silence cutting and local automatic subtitles.
EOF
cat > "$B/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    PY=/usr/bin/python3; [ -x "$PY" ] || PY=python3          # SIEMPRE el Python del sistema: un python3 de /usr/local o de pyenv/conda no ve los paquetes de la distribucion (gi, dbus, oweecapture)
    rm -rf /usr/lib/python3/dist-packages/oweecapture          # restos de versiones <= 0.1.4, que instalaban aqui
    $PY -m compileall -q /usr/lib/oweecapture/oweecapture >/dev/null 2>&1 || true
    # PySide6: si la distribucion no lo empaqueta (Ubuntu 24.04, algunas Deepin...), se instala de PyPI en un entorno propio (unos 100 MB); el comando lo usa solo
    if ! $PY -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
        echo "oweecapture: esta distribucion no trae PySide6; se instala desde PyPI (unos 100 MB) en /opt/oweecapture/venv" >&2
        if $PY -m venv --system-site-packages /opt/oweecapture/venv >/dev/null 2>&1 && /opt/oweecapture/venv/bin/pip install --quiet --disable-pip-version-check PySide6-Essentials; then
            # el entorno debe ver los paquetes de la distribucion (oweecapture, gi, dbus) aunque su Python no incluya dist-packages por defecto; al final del sys.path, para que PySide6 de PyPI mande
            SP=$(/opt/oweecapture/venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])") && echo /usr/lib/python3/dist-packages > "$SP/oweecapture-sistema.pth"
            echo "oweecapture: PySide6 instalado" >&2
        else
            rm -rf /opt/oweecapture
            echo "oweecapture: NO se pudo instalar PySide6 (falta red?). Instalalo a mano: /usr/bin/python3 -m venv --system-site-packages /opt/oweecapture/venv && /opt/oweecapture/venv/bin/pip install PySide6-Essentials" >&2
        fi
    else
        rm -rf /opt/oweecapture          # el sistema ya trae PySide6: un entorno propio de una instalacion anterior sobra (y podria estar roto)
    fi
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true
fi
exit 0
EOF
cat > "$B/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
# SOLO al quitar el paquete (remove/purge). En una actualizacion dpkg ejecuta el postrm de la version vieja DESPUES de desempaquetar la nueva:
# borrar aqui el programa lo dejaba sin archivos (el fallo de las versiones <= 0.1.4).
case "$1" in
    remove|purge)
        rm -rf /usr/lib/oweecapture /opt/oweecapture
        command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || true ;;
esac
exit 0
EOF
chmod 755 "$B/DEBIAN/postinst" "$B/DEBIAN/postrm"
if LC_ALL=C grep -nP '[^\x00-\x7F]' "$B/DEBIAN/control" >/dev/null; then echo "el archivo control tiene caracteres no ASCII: algunos instaladores (p. ej. el de Deepin) los muestran rotos" >&2; exit 1; fi
mkdir -p dist; dpkg-deb --root-owner-group -Zxz -b "$B" "dist/$PKG.deb" >/dev/null; echo "dist/$PKG.deb"
