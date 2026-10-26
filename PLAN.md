# Plan de Screencapture

Documento de planificación. Fecha: 26 de octubre de 2026. Autor del proyecto: Hector Martinez. Licencia prevista: GPL-3.0-or-later.
Las decisiones de lenguaje y biblioteca gráfica están razonadas en [docs/DECISION-LENGUAJE.md](docs/DECISION-LENGUAJE.md). Las estimaciones de tiempo son orientativas (una persona, tiempo parcial) y se revisan al terminar cada hito.

## 1. Visión
Una grabadora y capturadora de pantalla para Linux que **cualquiera pueda usar sin restricciones**, que **no cuelgue el equipo**, que **ocupe poco** y que **genere vídeos pequeños** listos para compartir. Pensada para quien enseña, hace tutoriales, sube a YouTube o TikTok, o manda vídeos por WhatsApp y Telegram.

**A quién sirve primero:** estudiantes y docentes (dibujar sobre la pantalla, explicar), creadores de contenido (cámara en burbuja, audio del sistema y micrófono) y usuarios de equipos modestos (poca CPU y memoria).

**Qué la distingue** (a verificar con una comparación real en el hito M0.5): vídeos pequeños con un solo selector de calidad, recuperación de grabaciones cortadas, modo presentación para dibujar, y funcionamiento fluido en equipos de 4 a 16 GB. Interfaz en 19 idiomas desde el principio (ya traducida).

## 2. Punto de partida (lo que ya existe)
Código extraído de la «Capturadora» de OweeLinux: `src/screencapture/` (≈840 líneas de Python con GTK4), 91 textos traducidos a 19 idiomas en `locales/`, 9 pruebas sin interfaz.

| Función | Cómo se hace hoy | Límite |
|---|---|---|
| Captura | `grim` + `slurp` | solo compositores wlroots |
| Grabación | `wf-recorder` (x264) + `pw-record` (audio) + `ffmpeg` (mezcla) | solo wlroots; procesos sueltos; sin pausa |
| Calidades | original, buena, intermedia (720p), básica (720p a 20 fps) | tabla fija; sin estimación de tamaño; la reducción es posterior |
| Cámara | burbuja con `gtk4-layer-shell` | solo wlroots |
| Presentación | superposición para dibujar con `gtk4-layer-shell` | solo wlroots |
| Editor | cairo: lápiz, resaltador, flecha, rectángulo, elipse, texto, números, pixelar | sin recorte, sin desenfoque, sin capas |
| Seguridad ante fallos | límites de memoria con `systemd-run`, cierre paciente, recuperación de grabaciones huérfanas y restos | recupera lo grabado, pero no graba en segmentos |
| Integración | archivo de estado + acciones D-Bus para el panel de OweeLinux | específica de OweeLinux |

**Medidas disponibles** (de OweeLinux, no de este proyecto): una grabación de 62 MB bajó a 12 MB con la calidad intermedia (captura de pantalla del propio autor); una prueba con vídeo sintético de 60 s dio 19,0 → 7,5 MB (720p) y 4,5 MB (720p a 20 fps). Un caso real de 5 minutos de grabación quedó sin guardar cuando el sistema cerró la aplicación (probable falta de memoria): de ahí la prioridad de la fiabilidad.

## 3. Requisitos (lo que has pedido hasta ahora)
1. Grabar la pantalla completa o una zona, con audio del sistema y micrófono.
2. Compresión fuerte con **cuatro niveles** y la opción de WhatsApp/Telegram.
3. Cámara en una burbuja redonda que se arrastra y cambia de tamaño; que se apague al terminar.
4. Dibujar sobre la pantalla (modo presentación) mientras se graba, sin que los controles salgan en el vídeo.
5. Capturas con editor y avisos claros al guardar o copiar.
6. Poder **detener siempre** y **no perder** lo grabado.
7. Poco consumo en equipos modestos (HP con AMD A12 y 16 GB; también 4 GB).
8. Directos para YouTube y TikTok y un avatar (mencionado; fase posterior).

## 4. Arquitectura objetivo
```
                         ┌──────────────── interfaz (GTK4) ─────────────────┐
                         │ ventana principal · barra de control · editor      │
                         │ burbuja de cámara · superposición de dibujo        │
                         └───────────────▲──────────────────────────────────┘
                                         │ D-Bus (org.screencapture.Service)
┌──────────────── screencapture-core (servicio + biblioteca) ─────────────────────────────┐
│ Capture        Encoder          Audio             Camera          Storage / Recovery    │
│  · portal+PipeWire  · GStreamer     · PipeWire         · PipeWire       · segmentos MKV     │
│    (GNOME, KDE,      (x264, VA-API,   (sistema + mic,    / v4l2          · reanudar tras    │
│    sway, labwc)      NVENC, VP9, AV1)  mezcla, nivel)                      caídas            │
│  · wlr-screencopy   · perfiles de    · sincronía A/V                    · límites de disco  │
│    (vía rápida)       calidad                                                              │
│  · X11 (opcional)   Postproceso: reducción en segundo plano, recorte sin recodificar, GIF   │
└────────────────────────────────────────────────────────────────────────────────────────┘
        integraciones opcionales: atajos globales (portal GlobalShortcuts), notificaciones, paneles
```
Principios:
- **El núcleo no sabe de ventanas.** Se controla por D-Bus y línea de órdenes (`screencapture-ctl start|stop|pause|status`), así lo usan la interfaz, los atajos y cualquier panel.
- **Grabar en segmentos** (Matroska o MP4 fragmentado): si todo se cae, el archivo hasta ese instante es válido.
- **Todo proceso externo con tiempo límite y nunca en el hilo de la interfaz** (ya se hace hoy).
- **Ninguna telemetría.** No se envía nada a ningún sitio.

## 5. Hoja de ruta
Cada hito termina con algo que se puede probar y con criterios de aceptación medibles.

### M0 — Extracción (hecho)
Proyecto aparte, sin dependencias de OweeLinux, 19 idiomas, pruebas básicas. **Criterio:** `python3 -m unittest discover -s tests` pasa.
**M0.5 — Comparación:** probar Spectacle, Kooha, OBS, SimpleScreenRecorder y Flameshot en la misma máquina y anotar qué hace mejor cada uno (tamaño de archivo, CPU, facilidad). Define la ventaja real. *(1 semana)*

### M1 — Fiabilidad (2–3 semanas)
- Grabación en **segmentos** y recuperación automática al abrir.
- **Pausa y reanudar.** Aviso cuando queda poco disco o memoria; parada ordenada antes de que el sistema mate el proceso.
- Pruebas de integración con un compositor sin pantalla (`WLR_BACKENDS=headless` con labwc o sway) y una prueba automática de «matar el programa a mitad» 100 veces: **0 grabaciones perdidas**.
- Tabla de medidas propias: CPU, memoria y MB por minuto en cada calidad (1080p y 720p) en el HP de 16 GB y en una VM.

### M2 — Funcionar en cualquier escritorio Wayland (4–6 semanas)
- Backend **portal ScreenCast + PipeWire + GStreamer**; conservar `wlr-screencopy` como vía rápida en wlroots.
- Las superposiciones (burbuja, dibujo) sin `layer-shell` en GNOME y KDE: ventana siempre visible con la API disponible, o integración con la extensión del escritorio; documentar lo que no sea posible.
- Selección de zona sin `slurp`. **Criterio:** graba en GNOME, KDE Plasma, sway y labwc; una grabación de 30 min sin pérdidas.
- Es el hito con **más incertidumbre**: validar primero con un prototipo de 2 días en GNOME y KDE.

### M3 — Calidad y audio (3–4 semanas)
- Codificación por hardware (VA-API, NVENC) con vuelta a x264 si falla; VP9 y AV1 como opciones libres de patentes.
- **Perfiles de destino:** WhatsApp (límite de tamaño), YouTube 1080p, TikTok vertical 9:16, GIF/WebP animado. Estimación de tamaño antes de grabar.
- Audio: mezcla con niveles por fuente, reducción de ruido del micrófono, sincronía comprobada.

### M4 — Editor (3–4 semanas)
Capturas: recortar, desenfocar, texto con fondo, copiar texto de la imagen (OCR opcional). Vídeo: **recortar el principio y el final sin recodificar**, extraer fotograma, GIF.

### M5 — Directos y avatar (6+ semanas, a decidir)
Salida RTMP/SRT a YouTube y TikTok con escena (pantalla + cámara + avatar). **Decisión pendiente:** es el terreno de OBS; solo merece la pena si M0.5 muestra un hueco claro (por ejemplo, directos ligeros en equipos modestos).

### M6 — Publicación (3 semanas)
Paquetes **Flatpak (Flathub)**, `.deb` y AppImage; página web y documentación; CI en GitHub Actions (pruebas y empaquetado); versión 1.0.

### M7 — Núcleo en Rust (opcional, 8–12 semanas)
Pasar el núcleo a un *crate* `screencapture-core` (`gstreamer-rs`, `pipewire-rs`, `ashpd`) y, si compensa, la interfaz a `gtk4-rs` + libadwaita. Se hace **después** de M2, cuando la arquitectura ya está probada.

## 6. Cómo se prueba
- **Unitarias** (sin interfaz): tabla de calidades, mezcla, nombres de archivo, traducciones, recuperación.
- **Integración** con compositor sin pantalla (sway o labwc en modo headless) para grabar de verdad y comprobar duración, códec y tamaño con `ffprobe`.
- **Manual en VM y en equipos reales**: HP A12 (16 GB), una laptop con NVIDIA y una Intel. El arnés de QEMU de OweeLinux (`boot-shot.py`: capturas, teclado, ratón y arrastre) sirve para pruebas de interfaz.
- **Prueba de caídas:** `kill -9` a mitad de la grabación, disco lleno, memoria baja.

## 7. Métricas de éxito
| Métrica | Objetivo |
|---|---|
| CPU grabando 1080p a 24–30 fps en el HP A12 | menos del 25 % (con VA-API) |
| Memoria del servicio de grabación | menos de 150 MB; sin crecimiento en 1 hora |
| Tamaño en calidad intermedia | ≤ 1/4 del original en pantalla de escritorio (el caso real medido: 62 → 12 MB) |
| Arranque de la interfaz | menos de 1 s |
| Grabaciones perdidas tras caídas simuladas | 0 de 100 |
| Escritorios soportados | GNOME, KDE Plasma, sway, labwc, Hyprland |

## 8. Riesgos
| Riesgo | Mitigación |
|---|---|
| El portal pide confirmación en cada grabación | usar el *restore token* del portal para recordar la elección |
| Sin `layer-shell` en GNOME/KDE no hay burbuja ni dibujo flotante | hito M2: alternativa por escritorio; documentar límites |
| Sincronía de audio y vídeo | GStreamer con una sola línea de tiempo; pruebas con claqueta |
| Patentes de H.264/AAC | ofrecer VP9/Opus y AV1 libres; H.264 por defecto por compatibilidad |
| Controladores de GPU (NVIDIA, AMD antiguos) | vuelta automática a x264 por CPU |
| Alcance (directos, avatar, editor de vídeo) | cerrar M1–M3 antes; M5 solo si hay hueco |
| Nombre `screencapture` | no hay paquete de Debian con ese nombre; en macOS existe una orden del sistema con ese nombre (no afecta a Linux); revisar antes de publicar |

## 9. Estructura del repositorio
```
screencapture/
  PLAN.md  README.md  LICENSE  pyproject.toml
  src/screencapture/   core.py  app.py  editor.py  overlay.py  camera.py  i18n.py
  locales/             19 idiomas (JSON: español → traducción)
  data/                icono y archivo .desktop
  tests/               pruebas
  docs/                DECISION-LENGUAJE.md
```
Convenciones: commits claros y sin atribuciones de herramientas ni coautores; textos de la interfaz en español dentro de `_()` y catálogos aparte; nada de código específico de un escritorio dentro del núcleo (las integraciones son módulos opcionales).

## 10. Primeras dos semanas (orden de trabajo)
1. Instalar y probar la competencia (M0.5) y escribir 10 líneas de conclusiones.
2. Prototipo de **portal + PipeWire + GStreamer** en GNOME y KDE (un script de 100 líneas que grabe 10 s a MP4): decide el riesgo de M2.
3. Compositor sin pantalla para pruebas de integración (labwc o sway headless) y primera prueba de «matar a mitad».
4. Diseño de la grabación por segmentos (formato y recuperación) y empezar M1.
5. Crear el repositorio en GitHub (sin coautores) cuando quieras publicarlo; hasta entonces vive solo en tu máquina.

## 11. Decisiones que dependen de ti
1. ¿Prioridad: poder usarla en GNOME/KDE (M2) o pulir primero lo que ya funciona en wlroots (M1 y M3)?
2. ¿Directos y avatar entran en la 1.0 o después?
3. ¿Interfaz con libadwaita (estilo GNOME) o con tema propio (como en OweeLinux)?
4. ¿Qué equipos reales son tu referencia (HP A12 y Dell con NVIDIA)?
5. ¿Publicar ya el repositorio o esperar a M1?
