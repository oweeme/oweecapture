# Screencapture

Capturas de pantalla con editor de anotaciones, grabación de vídeo con audio del sistema, micrófono y cámara, y modo presentación para dibujar sobre la pantalla. Pensado para Wayland, poco consumo de CPU y vídeos pequeños (niveles de calidad: original, buena, intermedia y básica para WhatsApp y Telegram).

**Estado:** versión 0.1, extraída de la «Capturadora» de OweeLinux. Hoy funciona en compositores basados en wlroots (labwc, sway, Hyprland, River…). El plan para llegar a GNOME y KDE está en [PLAN.md](PLAN.md).

## Qué hace hoy
- `screencapture --shot [full|region]`: captura inmediata y editor (lápiz, resaltador, flecha, rectángulo, elipse, texto, números, pixelar; deshacer y rehacer; guardar, guardar como y copiar).
- `screencapture --record [full|region]`: empieza a grabar (otra vez = parar). Audio del sistema y micrófono, burbuja de cámara arrastrable, calidad en cuatro niveles (la reducción se hace al terminar, en segundo plano y con prioridad baja).
- `screencapture --present`: dibuja sobre la pantalla (lápiz, resaltador, halo del puntero).
- Si la aplicación se cierra a mitad de una grabación, «Detener» o abrir la aplicación guarda lo que se grabó.

## Dependencias (sistema)
`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-gtk4layershell-1.0` (o `libgtk4-layer-shell`), `grim`, `slurp`, `wf-recorder`, `ffmpeg`, `pipewire` (`pw-record`, `wpctl`), `wl-clipboard`, `libnotify-bin`. En Debian/Ubuntu: `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-gtk4layershell-1.0 grim slurp wf-recorder ffmpeg pipewire-bin wl-clipboard libnotify-bin`.

## Ejecutar desde el código
```bash
cd screencapture
PYTHONPATH=src python3 -m screencapture            # ventana principal
PYTHONPATH=src python3 -m screencapture --shot region
python3 -m unittest discover -s tests               # pruebas sin interfaz
```

## Licencia
GPL-3.0-or-later (ver `LICENSE`). Autor: Hector Martinez.
