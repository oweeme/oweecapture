# Desarrollo

## Ejecutar desde el código

```bash
PYTHONPATH=src python3 -m oweecapture.qtapp                      # ventana principal
PYTHONPATH=src python3 -m oweecapture.qtapp --segundo-plano      # solo bandeja y atajos
```

Dependencias del sistema: ver [INSTALACION.md](INSTALACION.md) (`./install.sh --dependencias` las instala). Para KDE, el escritorio da identidad propia a la aplicación (necesaria para el portal y los atajos) si se lanza desde el menú o con:

```bash
systemd-run --user --quiet --collect --unit=app-oweecapture-$RANDOM python3 -m oweecapture.qtapp --segundo-plano
```

## Pruebas

```bash
python3 tests/ejecutar.py        # el ejecutor sale con el resultado real
```

Son pruebas sin pantalla (Qt en modo `offscreen`) e incluyen un portal y un KWin falsos para comprobar que la aplicación abre aunque el escritorio esté incompleto (caso Deepin), pruebas de tuberías de GStreamer y del paquete `.deb`. **Toda corrección de un fallo real debería llevar una prueba que falle con el código viejo.**

`tests/ejecutar.py` termina el proceso con `os._exit` con el resultado de las pruebas: con el Qt de PyPI, el cierre normal puede abortar por corrupción de memoria al salir, y eso falsearía el resultado.

## Estructura (`src/oweecapture/`)

| Módulo | Qué hace |
|---|---|
| `qtapp.py` | Ventana principal, bandeja, atajos, `--version`, `--comprobar` |
| `portal.py` | Grabación: portal ScreenCast + PipeWire, o `ximagesrc` en X11; tuberías de GStreamer, pausa, clips |
| `captura.py` | Capturas de pantalla por el portal |
| `atajos.py` | Atajos globales (portal GlobalShortcuts) |
| `servicio.py` | Una sola instancia por D-Bus; órdenes `--record`, `--shot`, `--present`, `--camera`, `--quit` |
| `kwin.py` | Todo lo que se hace con KWin: cursor, ventanas, siempre-encima, excluir de la captura |
| `directo.py`, `ruido_vivo.py` | Directo RTMP con reconexión; micrófono sin ruido en vivo |
| `audio.py`, `efectos.py` | Mezcla de audio y filtros; zoom y halo al terminar |
| `herramientas.py`, `ventana_herramientas.py`, `reproductor.py` | Recortar, vertical, silencios y su ventana con vista previa |
| `subtitulos.py`, `transcriptor.py` | Subtítulos locales con faster-whisper |
| `entrada.py`, `efectos_pantalla.py` | Clics y teclas en pantalla |
| `marco.py`, `selector.py`, `burbuja.py`, `presentacion.py` | Ventanas sobre la pantalla |
| `core.py`, `clips.py`, `inicio.py`, `autor.py`, `i18n.py` | Configuración, recuperación, clips, autoarranque, datos del autor, traducciones |

## Cosas que cuestan descubrir

- **Toda llamada al portal puede fallar** (el escritorio no ofrece GlobalShortcuts, ScreenCast…). Se capturan `dbus.DBusException`, `TypeError` y `ValueError` y se avisa, nunca se deja caer el arranque.
- **KWin no existe fuera de KDE:** `kwin.disponible()` comprueba que el servicio exista de verdad antes de usarlo.
- **Qt en X11 necesita bibliotecas xcb** y, con la plataforma `dxcb` de Deepin, se fuerza `xcb` (`_plataforma()` en `qtapp.py`).
- **Atajos nuevos en KDE:** solo quedan con tecla en el segundo arranque.
- **Un `.deb` actualizado ejecuta el `postrm` del paquete viejo después de desempaquetar el nuevo:** por eso el código vive en `/usr/lib/oweecapture` y el `postrm` solo actúa en `remove` y `purge`.
- **Con el Qt de PyPI** pueden fallar las pruebas por el cierre; ver `tests/ejecutar.py`.
- **Borrar solo lo que crea la prueba:** nunca «el vídeo más reciente» de `Vídeos`; solo rutas que la propia prueba imprimió.

## Construir el .deb

```bash
bash packaging/crear_deb.sh      # deja dist/oweecapture_<versión>_all.deb
```

La versión sale de `src/oweecapture/__init__.py`. El script rechaza una versión inválida y una descripción con caracteres no ASCII (rompe `apt`).

## Publicar una versión

1. Sube el número en **dos** sitios: `src/oweecapture/__init__.py` (`__version__`) y `src/oweecapture/autor.py` (`VERSION`).
2. Añade la entrada al [CHANGELOG.md](../CHANGELOG.md).
3. Pruebas en verde, `git commit`, `git push origin main`.
4. Etiqueta y sube: `git tag -a vX.Y.Z -m "OweeCapture X.Y.Z" && git push origin vX.Y.Z`.
5. El flujo **Lanzamiento** (`.github/workflows/lanzamiento.yml`) pasa las pruebas, construye el `.deb` y el código fuente, prueba la instalación en varias distribuciones y publica la release con `SHA256SUMS`.

## Integración continua (`.github/workflows/`)

- `ci.yml`: pruebas en cada subida.
- `instaladores.yml`: instala de verdad en contenedores — `.deb` en Debian 12/13 y Ubuntu 24.04/25.10; `install.sh` en Ubuntu, Fedora, Arch y openSUSE; **actualización encima de la última versión publicada** y encima de un entorno roto; ventana Qt real con pantalla virtual (Xvfb).
- `lanzamiento.yml`: al crear una etiqueta `v*`.

## Convenciones

- Código y mensajes en español; los textos de la interfaz pasan por `_()` (traducciones en `locales/`).
- Confirmaciones de cambios en español, sin atribuciones de herramientas ni coautores.
- El logo se genera con `python3 tools/generar_logo.py` (SVG y PNG de 16 a 512 px).
