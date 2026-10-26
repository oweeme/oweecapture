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


## Actualización (26 de octubre): objetivo GNOME, KDE, Deepin y, más adelante, Windows
Con ese objetivo cambia el peso de las preguntas, y **mi recomendación cambia: quedarse en Python ahora**.

**1. El lenguaje no resuelve lo difícil.** Cada plataforma necesita su propio sistema de captura, escrito en el lenguaje que sea:
| Escritorio | Cómo se captura | Estado en el proyecto |
|---|---|---|
| wlroots (labwc, sway, Hyprland) | `wlr-screencopy` | hecho |
| GNOME y KDE Plasma (Wayland) | portal `xdg-desktop-portal` (ScreenCast) + PipeWire | por hacer (hito M2) |
| X11 (GNOME/KDE en X11 y, según la versión, Deepin) | `x11grab` de FFmpeg o `ximagesrc` de GStreamer | por hacer, es lo más fácil |
| Windows | `ddagrab` / `gdigrab` de FFmpeg o *Windows Graphics Capture* | por hacer, más adelante |
Deepin: hay que **comprobar** qué sesión usa la versión que se quiera soportar (según mi información, DDE 23 usa X11 por defecto y está incorporando Wayland; no lo he verificado aquí).
FFmpeg ya sabe capturar en X11 y en Windows, así que un backend basado en FFmpeg cubre esos dos casos desde Python sin escribir código específico de cada sistema.

**2. Lo que sí pesa es la biblioteca gráfica, no Python contra Rust.** GTK4 en Windows es incómodo de empaquetar; Qt (PySide6) se instala en Windows con `pip` y se ve nativo en KDE y Deepin (que usan Qt), aunque en GNOME se vea algo ajeno. Si Windows y Deepin son objetivos reales, **Qt6 con PySide6 es una opción seria**; si el objetivo principal es GNOME y las distribuciones ligeras, GTK4. Hay que decidirlo antes de crecer la interfaz.

**3. Ventajas de seguir en Python (hoy):** ya funciona; se prueba y se cambia en minutos; PyGObject orquesta GStreamer y FFmpeg sin tocar los fotogramas, así que el rendimiento no lo limita Python; menos riesgo de reescribir mientras la arquitectura aún cambia.
**4. Inconvenientes de Python (reales):** hay que empaquetar el intérprete y las bibliotecas (Flatpak y AppImage lo resuelven en Linux; en Windows es trabajoso); unos 70–80 MB en reposo con GTK4; arranque más lento; un error de hilos se descubre en ejecución, no al compilar.
**5. Cuándo sí pasar a Rust:** cuando una **medición** lo pida (memoria en reposo, arranque, fallos de hilos en grabaciones largas), cuando se quiera un único binario para Windows/macOS, o cuando el núcleo ya sea estable. Se pasa **el núcleo primero** (un servicio con API D-Bus y una biblioteca) y la interfaz puede seguir en Python/Qt. Hacerlo antes sería reescribir algo que todavía cambia.

**Decisión actual:** Python. Aislar el núcleo (sin imports de interfaz) con **backends intercambiables** (wlroots, portal+PipeWire, X11/FFmpeg, Windows/FFmpeg), medir en el hito M1, y decidir Qt o GTK4 y Rust con datos.

## Una sola aplicación para KDE y GNOME
Una aplicación hecha con Qt funciona en GNOME, y una hecha con GTK funciona en KDE: el toolkit es una biblioteca, no depende del escritorio. Lo que cambia entre escritorios no es la aplicación sino unas pocas piezas del sistema, que hay que aislar en módulos intercambiables:
| Pieza | KDE Plasma | GNOME | Qué hacer |
|---|---|---|---|
| Captura de pantalla (Wayland) | portal ScreenCast + PipeWire | igual | un solo backend para los dos |
| Superposiciones (burbuja de cámara, dibujar sobre la pantalla, barra flotante) | `layer-shell` (soportado) | **no soporta `layer-shell`** | es el punto difícil: alternativa por escritorio y documentar los límites |
| Atajos globales | portal GlobalShortcuts / KDE | portal GlobalShortcuts / configuración de GNOME | usar el portal; si no, órdenes de línea para asignarlas a mano |
| Icono en la bandeja | StatusNotifier | necesita una extensión | no depender de él |
| Aspecto | Qt nativo | GTK nativo | con el otro toolkit se ve algo ajeno (tema, diálogos de archivo); se mitiga con Flatpak y estilos |
| Dependencias | Qt ya instalado | GTK ya instalado | Flatpak incluye lo que falte |
Conclusión: **una sola aplicación y un solo toolkit** es viable. Los límites reales están en las superposiciones de GNOME, no en la elección Qt o GTK.


## Decisión final (26 de octubre)
El autor usa KDE: **Python con Qt6 (PySide6, LGPLv3)**. El proyecto es GPL-3.0-or-later, compatible con la licencia libre de Qt, y no hace falta licencia comercial. Detalle y riesgos del paso de GTK4 a Qt en el hito M0.6 de `PLAN.md`; el riesgo principal son las superposiciones sin marco en Wayland, que en KDE necesitan `LayerShellQt`.
