# Instalación, actualización y desinstalación

Ambas vías se **prueban en cada versión** en contenedores limpios de GitHub Actions: se instala de verdad y se ejecuta `oweecapture --comprobar`. Solo Linux.

## Debian, Ubuntu, Deepin, Mint y derivadas (.deb)

Probado en Debian 12 y 13 y en Ubuntu 24.04 y 25.10.

1. Descarga `oweecapture_<versión>_all.deb` de la [última versión](../../../releases/latest). Junto a él hay un archivo `SHA256SUMS` por si quieres verificarlo: `sha256sum -c SHA256SUMS`.
2. Instálalo:
   ```bash
   sudo apt install ./oweecapture_<versión>_all.deb
   ```
3. Comprueba: `oweecapture --version`.

**Dónde se instala:** el código en `/usr/lib/oweecapture` y el lanzador en `/usr/bin/oweecapture`. Si tu sistema no trae PySide6 (por ejemplo Ubuntu 24.04), la instalación crea un entorno propio en `/opt/oweecapture/venv` y lo baja de PyPI (unos 100 MB, hace falta internet).

## Fedora, Arch/Manjaro, openSUSE y cualquier otra (install.sh)

Descarga `oweecapture-<versión>-fuente.tar.gz` de la release (o clona el repositorio), descomprime y, dentro de la carpeta:

```bash
./install.sh --dependencias
```

- Instala en **tu carpeta personal** (`~/.local`), sin tocar el sistema.
- `--dependencias` instala con tu gestor (apt, dnf, pacman o zypper) los paquetes del sistema: GStreamer, ffmpeg, PipeWire, portal… Te enseña la orden y **pregunta antes de usar `sudo`**. Con `--si` no pregunta (para scripts).
- Termina ejecutando `oweecapture --comprobar`, que dice qué falta.
- Otras opciones: `--prefijo DIR` (instalar en otra carpeta) y `--ayuda`.

**Fedora:** no incluye los codificadores H.264 ni AAC por licencias. Activa [RPM Fusion](https://rpmfusion.org/Configuration) e instala: `sudo dnf install gstreamer1-plugins-ugly gstreamer1-libav ffmpeg --allowerasing`.

**Distribución desconocida:** el script lo dice y lista lo que necesitas a mano: Python 3.11 o posterior con venv, PyGObject, dbus-python, GStreamer (base, good, bad, ugly, libav, pipewire), ffmpeg, PipeWire y xdg-desktop-portal.

## Comprobar que todo está bien

```bash
oweecapture --version      # versión instalada
oweecapture --comprobar    # arranca Qt sin pantalla y dice qué falta (ffmpeg, plugins de GStreamer…)
```

## Actualizar

- **.deb:** instala el nuevo encima: `sudo apt install ./oweecapture_<nueva>_all.deb`. Esto **no borra** el programa (arreglado en la 0.1.5).
- **install.sh:** descarga la versión nueva y vuelve a ejecutar `./install.sh`.
- **Después, cierra y vuelve a abrir el programa.** La copia que ya estaba abierta sigue con el código viejo en memoria: «Acerca de» mostrará la versión antigua hasta que la reinicies. Con el icono de la bandeja → *Salir*, o `oweecapture --quit`, y abre de nuevo.
- Si estás en KDE y la versión nueva trae un atajo nuevo, la tecla solo queda asignada tras abrir el programa **dos veces**.

## Desinstalar

- **.deb:** `sudo apt remove oweecapture` (o `purge`). Borra el programa y el entorno propio de `/opt/oweecapture`; tu configuración y tus vídeos no se tocan.
- **install.sh:** `./install.sh --desinstalar` (solo quita lo que puso el script).
- Si quieres quitarlo todo: borra `~/.config/oweecapture` (ajustes), `~/.cache/oweecapture` (registros) y `~/.local/share/oweecapture` (motor de subtítulos, si lo instalaste, unos 620 MB) y el archivo `~/.config/autostart/oweecapture.desktop`.
