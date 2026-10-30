# Qué funciona en cada escritorio

Estado real, probado o no. «Sin probar» significa que el código existe pero nadie lo ha usado en ese escritorio.

| Función | KDE Plasma 6 (Wayland) | Deepin (X11) | GNOME | Windows |
|---|---|---|---|---|
| Abrir la aplicación | Sí | Sí | Sin probar | No |
| Captura de pantalla | Sí | Sí | Sin probar | No |
| Grabar pantalla o zona | Sí (portal + PipeWire) | Sí (captura X11 directa, desde la 0.1.6) | Sin probar | No |
| Audio del sistema y micrófono | Sí | Sin probar | Sin probar | No |
| Atajos globales | Sí | No: crea los tuyos con las órdenes `--record`, `--shot`… | Solo GNOME 48 o posterior; antes, atajos manuales | No |
| Zoom automático y halo en el cursor | Sí | No (necesita KWin) | No | No |
| Marco amarillo y vertical 9:16 | Sí | Sin probar | Sin probar | No |
| Burbuja de cámara | Sí | Sin probar | Sin probar | No |
| Quitar de la grabación la barra del modo presentación y los menús de la bandeja | Sí (KWin 6.4 o posterior) | No | No | No |
| Directo RTMP | Sí | Sin probar | Sin probar | No |
| Herramientas de vídeo y subtítulos | Sí | Sin probar | Sin probar | No |
| Icono en la bandeja | Sí | Sí | Hace falta la extensión AppIndicator | No |

## Por qué cambia de un escritorio a otro

- **Wayland (KDE, GNOME):** una aplicación no puede capturar la pantalla por su cuenta; lo pide al *portal* del escritorio (xdg-desktop-portal), que muestra su propio aviso de permiso y entrega un flujo de PipeWire.
- **X11 (Deepin, otros):** no existe ese portal. Desde la 0.1.6 OweeCapture detecta la sesión X11 y captura la pantalla directamente con GStreamer.
- **Atajos globales:** KDE los ofrece a las aplicaciones; Deepin y GNOME antiguos no. Allí se crean en los ajustes de teclado del propio escritorio, asignando una de las órdenes (`oweecapture --record`, etc.).
- **Zoom automático, ocultar ventanas de la grabación:** dependen de KWin, el gestor de ventanas de KDE.

## Windows

Todavía no hay instalador, y no se puede fingir uno: casi toda la captura depende de piezas de Linux. Cada una tiene un equivalente en Windows, pero hay que reescribirla y probarla en un Windows real:

| Pieza | En Linux | En Windows |
|---|---|---|
| Captura de pantalla | portal + PipeWire (o `ximagesrc`) | `d3d11screencapturesrc` de GStreamer o `ddagrab` de ffmpeg |
| Audio | PipeWire | `wasapi2src` (audio del sistema por «loopback») |
| Atajos globales | portal / KGlobalAccel | `RegisterHotKey` |
| Ocultar ventanas de la grabación | KWin | `SetWindowDisplayAffinity` con `WDA_EXCLUDEFROMCAPTURE` |
| Instalador | `.deb`, `install.sh` | `.exe` con PyInstaller |

Se reutilizarían tal cual la interfaz Qt, el directo, las herramientas de vídeo y los subtítulos. Orden previsto: 1) herramientas de vídeo y subtítulos, 2) grabación y atajos, 3) directo y cámara, 4) instalador. Hace falta alguien con Windows que pruebe cada fase.

## Android

No. Esta aplicación depende de componentes de escritorio Linux. Una versión para móvil sería un proyecto nuevo.
