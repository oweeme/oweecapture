#!/usr/bin/env bash
# Instalador universal de OweeCapture para Linux (Debian/Ubuntu/Deepin/Mint, Fedora, Arch/Manjaro, openSUSE y derivadas).
# Instala en tu carpeta personal (sin tocar el sistema): un entorno de Python propio con PySide6 de PyPI, el comando `oweecapture`, el lanzador y los iconos.
# Las dependencias del SISTEMA (GStreamer, ffmpeg, PipeWire, portal...) las instala tu gestor de paquetes: este script te dice cuales y solo las instala si se lo pides.
#
#   ./install.sh                      instala en ~/.local (pregunta antes de usar sudo)
#   ./install.sh --dependencias       ademas instala las dependencias del sistema con tu gestor de paquetes
#   ./install.sh --dependencias --si  igual, sin preguntar (para scripts y contenedores)
#   ./install.sh --prefijo DIR        en otra carpeta (por defecto ~/.local)
#   ./install.sh --desinstalar        quita lo que instalo este script (solo eso)
set -euo pipefail

PREFIJO="${HOME}/.local"; DEPS=0; SI=0; QUITAR=0
while [ $# -gt 0 ]; do case "$1" in
    --dependencias) DEPS=1 ;; --si) SI=1 ;; --desinstalar) QUITAR=1 ;;
    --prefijo) PREFIJO="${2:?falta la carpeta}"; shift ;;
    -h|--ayuda) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opcion desconocida: $1 (usa --ayuda)" >&2; exit 2 ;;
esac; shift; done

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$PREFIJO/share/oweecapture"; BIN="$PREFIJO/bin/oweecapture"; ESC="$PREFIJO/share/applications/oweecapture.desktop"

if [ "$QUITAR" = 1 ]; then
    rm -rf "$APP" "$BIN" "$ESC" "$PREFIJO"/share/icons/hicolor/*/apps/oweecapture.{png,svg}
    echo "OweeCapture desinstalado de $PREFIJO (la configuracion en ~/.config/oweecapture no se toca)."; exit 0
fi

# --- 1. distribucion y paquetes del sistema ---
. /etc/os-release 2>/dev/null || true
FAM="${ID:-}${ID_LIKE:+ $ID_LIKE}"; NOTA=""
case " $FAM " in
    *" debian "*|*" ubuntu "*|*" deepin "*|*" linuxmint "*) GESTOR=apt
        PAQ="python3 python3-venv python3-gi python3-dbus gir1.2-gstreamer-1.0 gstreamer1.0-pipewire gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav ffmpeg pipewire xdg-desktop-portal libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3"
        INSTALAR="apt-get install -y --no-install-recommends" ;;
    *" fedora "*|*" rhel "*|*" centos "*) GESTOR=dnf
        PAQ="python3 python3-gobject python3-dbus gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-bad-free pipewire-gstreamer pipewire xdg-desktop-portal mesa-libGL mesa-libEGL libxkbcommon fontconfig dbus-libs ffmpeg-free"
        INSTALAR="dnf install -y"
        NOTA="Fedora no incluye los codificadores H.264 y AAC (licencias). Para grabar y transmitir activa RPM Fusion (https://rpmfusion.org/Configuration) e instala:  sudo dnf install gstreamer1-plugins-ugly gstreamer1-libav ffmpeg --allowerasing" ;;
    *" arch "*|*" manjaro "*|*" endeavouros "*) GESTOR=pacman
        PAQ="python python-gobject python-dbus gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav gst-plugin-pipewire ffmpeg pipewire xdg-desktop-portal mesa libxkbcommon fontconfig dbus"
        INSTALAR="pacman -S --noconfirm --needed" ;;
    *" suse "*|*" opensuse "*|*" sles "*) GESTOR=zypper
        PAQ="python3 python3-pip python3-gobject python3-dbus-python gstreamer gstreamer-plugins-base gstreamer-plugins-good gstreamer-plugins-bad gstreamer-plugins-ugly gstreamer-plugins-libav gstreamer-plugin-pipewire ffmpeg pipewire xdg-desktop-portal Mesa-libGL1 Mesa-libEGL1 libxkbcommon0 fontconfig libdbus-1-3 libglib-2_0-0 libgobject-2_0-0 libgthread-2_0-0 libgio-2_0-0"
        INSTALAR="zypper --non-interactive install" ;;
    *) GESTOR=""; PAQ=""; INSTALAR="" ;;
esac

if [ -z "$GESTOR" ]; then
    echo "No reconozco tu distribucion (${ID:-?}). Instala a mano: Python 3.11+ con venv, PyGObject, dbus-python, GStreamer (base, good, bad, ugly, libav, pipewire), ffmpeg, PipeWire y xdg-desktop-portal; despues vuelve a ejecutar este script." >&2
elif [ "$DEPS" = 1 ]; then
    CMD="$INSTALAR $PAQ"; [ "$(id -u)" = 0 ] || CMD="sudo $CMD"
    echo "Dependencias del sistema ($GESTOR):"; echo "  $CMD"
    if [ "$SI" = 0 ]; then read -r -p "Ejecutarlo ahora? [s/N] " r; [[ "$r" =~ ^[sSyY] ]] || { echo "Cancelado: nada se instalo."; exit 1; }; fi
    [ "$GESTOR" = apt ] && { [ "$(id -u)" = 0 ] && apt-get update -qq || sudo apt-get update -qq; }
    $CMD
else
    echo "Si falta alguna dependencia del sistema, instalalas con tu gestor ($GESTOR):"; echo "  $( [ "$(id -u)" = 0 ] || echo sudo ) $INSTALAR $PAQ"; echo "  (o vuelve a ejecutar con --dependencias)"; echo
fi

# --- 2. entorno propio con PySide6 de PyPI (ve los paquetes del sistema: gi, dbus) ---
command -v python3 >/dev/null || { echo "Falta python3." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || { echo "Hace falta Python 3.11 o posterior (tienes $(python3 -V))." >&2; exit 1; }
rm -rf "$APP/venv"; mkdir -p "$APP"
python3 -m venv --system-site-packages "$APP/venv" || { echo "No se pudo crear el entorno de Python (en Debian/Ubuntu falta python3-venv)." >&2; exit 1; }
echo "Instalando PySide6 desde PyPI (unos 100 MB)..."
"$APP/venv/bin/pip" install --quiet --disable-pip-version-check PySide6-Essentials

# --- 3. el programa, las traducciones, el comando, el lanzador y los iconos ---
rm -rf "$APP/lib"; mkdir -p "$APP/lib" "$PREFIJO/bin" "$PREFIJO/share/applications"
cp -r "$RAIZ/src/oweecapture" "$APP/lib/oweecapture"; find "$APP/lib" -name __pycache__ -type d -prune -exec rm -rf {} +
rm -rf "$APP/locales"; cp -r "$RAIZ/locales" "$APP/locales"          # i18n.py las busca en ../../locales desde el paquete
cat > "$BIN" <<EOF
#!/bin/sh
export PYTHONPATH="$APP/lib\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$APP/venv/bin/python" -m oweecapture.qtapp "\$@"
EOF
chmod 755 "$BIN"
sed "s|^Exec=oweecapture|Exec=$BIN|" "$RAIZ/data/oweecapture.desktop" > "$ESC"          # el comando y las acciones del lanzador (--shot, --record...) apuntan al comando instalado
install -Dm644 "$RAIZ/data/icons/oweecapture.svg" "$PREFIJO/share/icons/hicolor/scalable/apps/oweecapture.svg"
for n in 16 24 32 48 64 128 256 512; do install -Dm644 "$RAIZ/data/icons/oweecapture-$n.png" "$PREFIJO/share/icons/hicolor/${n}x${n}/apps/oweecapture.png"; done
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$PREFIJO/share/applications" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f "$PREFIJO/share/icons/hicolor" 2>/dev/null || true

# --- 4. autocomprobacion ---
echo; echo "Comprobando la instalacion..."
if "$BIN" --comprobar; then
    [ -n "$NOTA" ] && { echo; echo "AVISO: $NOTA"; }
    echo; echo "Listo. Ejecuta: $BIN"; case ":$PATH:" in *":$PREFIJO/bin:"*) ;; *) echo "(anade $PREFIJO/bin a tu PATH para usar solo 'oweecapture')" ;; esac
else
    echo; echo "La instalacion termino, pero faltan dependencias del sistema (ver arriba). Instalalas y ejecuta:  $BIN --comprobar" >&2; exit 1
fi
