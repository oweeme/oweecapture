# ¿En qué lenguaje y con qué biblioteca gráfica?

Pregunta: ¿seguir con Python + GTK, pasar a Qt o usar Rust? Respuesta corta al final; primero los criterios y los datos.

## Qué hace de verdad el programa (esto decide casi todo)
Un grabador de pantalla tiene dos mitades muy distintas:
1. **Tubería de vídeo y audio**: obtener fotogramas del compositor, convertirlos, codificarlos (H.264, VP9, AV1), mezclar audio y escribir el archivo. Aquí el trabajo pesado lo hacen **bibliotecas en C** (GStreamer, FFmpeg, PipeWire, x264). El lenguaje de tu programa solo *orquesta*; si nunca toca los píxeles, no es el cuello de botella.
2. **Interfaz y control**: ventana principal, barra de control mientras grabas, editor de capturas (dibujar), burbuja de cámara, superposición para dibujar, atajos, notificaciones. Aquí pesan la comodidad del toolkit, la memoria y el arranque.

Hoy la mitad 1 son **procesos externos** (`wf-recorder`, `pw-record`, `ffmpeg`, `grim`, `slurp`) y la mitad 2 es Python con GTK4 (842 líneas). Funciona, pero depende de herramientas que solo existen en compositores wlroots.

## Opciones

| | A. Python + GTK4 | B. Python + Qt6 (PySide6) | C. Rust + GTK4 (gtk4-rs, libadwaita) | D. Rust + Slint / iced / egui | E. C++ + Qt6 |
|---|---|---|---|---|---|
| Ya lo tienes | sí (842 líneas) | no | no | no | no |
| Tubería GStreamer / PipeWire | PyGObject: sencillo | GStreamer vía PyGObject (mezclar GTK y Qt no conviene) o QtMultimedia | `gstreamer-rs`, `pipewire-rs`, `ashpd` (portales): muy buenos | los mismos crates | API nativa; la mejor documentada (OBS, Spectacle) |
| Memoria en reposo (orden de magnitud) | ~70–80 MB (medido: el panel Python con GTK4 en OweeLinux ronda 75 MB) | similar o mayor | ~15–30 MB | ~10–40 MB | ~25–40 MB |
| Arranque | ~0,3–0,8 s | ~0,5–1 s | <0,2 s | <0,2 s | ~0,3 s |
| Distribución | necesita Python y `python3-gi` en el sistema; Flatpak lo resuelve | PySide6 pesa >100 MB si va por pip | un binario (más las bibliotecas GTK) | un binario | un binario |
| Superposiciones en Wayland (burbuja, dibujar, barra flotante) | `gtk4-layer-shell` (solo wlroots) | LayerShellQt (KDE) | `gtk4-layer-shell` (solo wlroots) | según biblioteca; limitado | LayerShellQt |
| Seguridad de memoria / hilos | un error de hilos cuelga la interfaz; sin tipos fuertes | igual | el compilador evita carreras de datos y fugas típicas: ideal para un proceso que graba horas | igual | manual |
| Velocidad de desarrollo para ti | la más alta | alta | media (más verboso; GTK en Rust tiene curva) | media | baja |
| Pruebas automáticas | fáciles | fáciles | muy buenas (cargo test) | buenas | trabajosas |
| Comunidad de grabadores en Linux | Kooha usa Rust+GTK4 | – | **Kooha, Cap** (Rust) | – | OBS, Spectacle, SimpleScreenRecorder |

(Los datos de memoria y arranque son órdenes de magnitud, no mediciones de este proyecto; la tabla de medidas propias va en el hito M1 del plan.)

## Lo que importa más que el lenguaje: el *backend* de captura
Hoy se usa `wlr-screencopy` (vía `wf-recorder` y `grim`). **Solo funciona en compositores wlroots** (labwc, sway, Hyprland…). En GNOME y KDE Plasma en Wayland la única vía permitida es el **portal `xdg-desktop-portal` (ScreenCast) + PipeWire**. Si quieres que el programa lo use cualquiera, el backend de portal es obligatorio, y es independiente del lenguaje: en Rust se hace con `ashpd` y `pipewire-rs`; en Python con `dbus` y PyGObject + `pipewiresrc` de GStreamer.

## Decisión recomendada
**Destino final: Rust para el núcleo y GTK4 con libadwaita para la interfaz (opción C).** Motivos: proceso de larga duración con hilos (grabar horas sin fugas ni bloqueos), binario único y arranque rápido, el mejor soporte de portales y PipeWire, y es el camino de los grabadores modernos de Linux. Tú ya programas en Rust y Python, así que no hay un lenguaje desconocido.

**Camino: no reescribir ahora.** Hacerlo en tres etapas para no perder lo que ya funciona:
1. **Etapa 1 (Python + GTK4, ahora):** cambiar el *backend* a portal + PipeWire + GStreamer, que es el cambio que da más valor (GNOME y KDE) y el que tiene más incertidumbre técnica. Si funciona en Python, funcionará en Rust. Python sirve aquí como prototipo rápido porque no toca los fotogramas.
2. **Etapa 2 (núcleo en Rust):** cuando el diseño esté estable, pasar la tubería, la grabación por segmentos, la recuperación y la API D-Bus a un *crate* `screencapture-core`, con un binario de línea de órdenes y un servicio. La interfaz Python sigue usándolo por D-Bus.
3. **Etapa 3 (interfaz en Rust):** pasar la interfaz a `gtk4-rs` + libadwaita si el consumo de memoria y la distribución lo justifican.

**Por qué no Qt:** en OweeLinux y en la mayoría de escritorios ligeros la pila ya es GTK; mezclar Qt añade decenas de MB; las superposiciones en Wayland están mejor resueltas en GTK con `gtk4-layer-shell`. Qt sería la elección si el objetivo principal fuera KDE.

**Por qué no quedarse en Python para siempre:** no porque Python sea lento (no toca los fotogramas), sino por el binario único, la memoria en reposo, el arranque y las garantías de hilos en un programa que debe sobrevivir a grabaciones de horas.

**Cuándo cambiaría esta recomendación:** si el tiempo disponible es muy limitado, quedarse en Python + GTK4 con backend de portal es una opción válida y entrega valor antes; si el objetivo principal fuera KDE, Qt6 (C++ o Rust con `cxx-qt`) ganaría.
