<p align="center"><img src="data/icons/oweecapture-128.png" alt="Logo de OweeCapture: una koi dentro de una lente circular" width="128"></p>

# OweeCapture

Grabadora de pantalla, capturas, directos y herramientas de vídeo para Linux, pensada para quien hace **tutoriales y contenido** (YouTube, TikTok, Shorts, Reels, WhatsApp).

- **Graba** la pantalla, una zona o en vertical 9:16, con audio del sistema, micrófono y burbuja de cámara.
- **Transmite en directo** por RTMP a YouTube, TikTok, Twitch u otro servidor, guardando una copia local.
- **Ayuda a explicar**: zoom con una tecla, clips de los últimos segundos, modo presentación para dibujar sobre la pantalla, clics y teclas en pantalla.
- **Termina el vídeo**: recortar, cortar silencios, pasar a vertical y subtítulos automáticos (todo en tu equipo, nada sale a internet).

Autor: Hector Martinez · [hector@oweeme.com](mailto:hector@oweeme.com) · https://oweeme.com · Licencia GPL-3.0-or-later.

## Empezar en 3 pasos

1. **Instala** (Debian, Ubuntu, Deepin, Mint): descarga el `.deb` de la [última versión](../../releases/latest) y ejecuta `sudo apt install ./oweecapture_<versión>_all.deb`.
   Otras distribuciones (Fedora, Arch, openSUSE…): [docs/INSTALACION.md](docs/INSTALACION.md).
2. **Ábrela** desde el menú de aplicaciones («OweeCapture») y comprueba con `oweecapture --version`.
3. **Graba**: pulsa *Grabar*, elige la zona y listo. Se guarda en `Vídeos/Screen Recordings`.

Para que los atajos respondan desde que arranca el escritorio, activa «Iniciar OweeCapture al abrir la sesión» en la pestaña *Grabar*.

## Atajos

| Atajo | Orden (para escritorios sin atajos globales) | Qué hace |
|---|---|---|
| `Ctrl+Alt+R` | `oweecapture --record` | Empezar / detener la grabación |
| `Ctrl+Alt+S` | `oweecapture --shot` | Captura de pantalla |
| `Ctrl+Alt+P` | — | Pausar / continuar |
| `Ctrl+Alt+Z` | — | Acercar / alejar (zoom) mientras grabas |
| `Ctrl+Alt+G` | — | Guardar un clip de los últimos segundos |
| `Ctrl+Alt+D` | `oweecapture --present` | Modo presentación (dibujar en pantalla) |
| `Ctrl+Alt+C` | `oweecapture --camera` | Quitar / poner la burbuja de la cámara mientras grabas |
| — | `oweecapture --quit` | Cerrar el programa |

## Documentación

| Quiero… | Lee |
|---|---|
| Aprender a usarla, tarea por tarea | [docs/GUIA.md](docs/GUIA.md) |
| Instalar, actualizar o desinstalar | [docs/INSTALACION.md](docs/INSTALACION.md) |
| Arreglar un problema (no graba, no abre, sin atajos…) | [docs/PROBLEMAS.md](docs/PROBLEMAS.md) |
| Ver qué funciona en cada escritorio | [docs/ESCRITORIOS.md](docs/ESCRITORIOS.md) |
| Ver qué cambió en cada versión | [CHANGELOG.md](CHANGELOG.md) |
| Programar, probar y publicar versiones | [docs/DESARROLLO.md](docs/DESARROLLO.md) |

Otros documentos del proyecto: [PLAN.md](PLAN.md) (hoja de ruta) y [docs/DECISION-LENGUAJE.md](docs/DECISION-LENGUAJE.md) (por qué Python y Qt).

## Estado

Versión 0.1.x. **Probada de verdad en KDE Plasma 6 (Wayland)**, donde todo funciona. En **Deepin (X11)** funciona la captura de pantalla y la grabación; en **GNOME** aún no está probada. **Windows y Android no están soportados** (ver [docs/ESCRITORIOS.md](docs/ESCRITORIOS.md)).
