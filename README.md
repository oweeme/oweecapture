# Screencapture

Capturas de pantalla con editor de anotaciones, grabación de vídeo con audio del sistema, micrófono y cámara, y modo presentación para dibujar sobre la pantalla. Pensado para Wayland, poco consumo de CPU y vídeos pequeños (niveles de calidad: original, buena, intermedia y básica para WhatsApp y Telegram).

**Estado:** versión 0.1, extraída de la «Capturadora» de OweeLinux. Hoy funciona en compositores basados en wlroots (labwc, sway, Hyprland, River…). El plan para llegar a GNOME y KDE está en [PLAN.md](PLAN.md).

## Qué hace hoy (interfaz Qt, probada en KDE neon con Plasma 6 en Wayland)
- `Ctrl+Alt+S` o `screencapture --shot`: captura por el portal del escritorio, con selector de zona (arrastrar; Enter o Espacio para toda la pantalla; Esc cancela). Se guarda en Imágenes/Screenshots y se copia al portapapeles.
- `Ctrl+Alt+R` o `screencapture --record`: elige la zona y empieza a grabar; otra vez para detener. Audio del sistema y micrófono, cuatro niveles de calidad (la reducción se hace al terminar, en segundo plano), pausa y continuar desde el icono de la bandeja. La ventana se oculta mientras se graba.
- **Zoom a demanda** (1,5×, 2× o 2,5×): mientras grabas, `Ctrl+Alt+Z` acerca (centrado en el cursor, que el zoom sigue) y otra vez aleja, con transición suave; y **halo en el puntero**. Se aplican al terminar la grabación (se reescribe el vídeo: unos 0,8 s por segundo de grabación en 1080p). Solo en KDE Plasma, donde KWin entrega la posición del cursor; en otros escritorios las opciones aparecen desactivadas. Resaltar los clics y mostrar las teclas queda pendiente: necesita permiso de lectura de `/dev/input` (grupo `input`).
- **Mezclador de audio**: el sistema y el micrófono se graban en pistas separadas y al guardar se mezclan con el volumen de cada fuente (0–200 %) y, si quieres, reducción de ruido del micrófono: *suave* (filtro de graves y resta del ruido de fondo, unos 7 dB menos de ruido) o *fuerte* (además una puerta de ruido que cierra el micrófono entre frases; puede cortar finales de palabra muy bajos). Medido con ruido rosa realista; la voz casi no cambia.
- **Transmitir en directo** por RTMP a YouTube, TikTok, Twitch u otro servidor (panel «Transmitir en directo»): pegas la clave de transmisión de la plataforma (no hace falta iniciar sesión ni usar su API), eliges 480p, 720p o 1080p y se emite pantalla + burbuja de cámara + audio (sistema y micrófono con su volumen) con una copia local en MP4 por si se corta la conexión. La clave solo se guarda si marcas «Recordar» (archivo de configuración con permisos 0600) y nunca aparece en mensajes ni en el registro. En directo no hay pausa ni zoom, y la reducción de ruido del micrófono solo existe al grabar. Medido en un portátil de 4 núcleos: 720p a 3000 kbps con mucho movimiento, 30 fps estables y ~1,6 núcleos. TikTok exige cumplir sus requisitos para transmitir desde un ordenador con clave.
- **Clips de los últimos segundos** (`Ctrl+Alt+G`, 15, 30, 60 o 120 s): mientras grabas o transmites, guarda aparte lo último que pasó (en `Videos/Screen Recordings/Clips`) sin parar nada y sin gastar CPU extra, porque se corta de la copia que ya se está escribiendo. Empieza hasta 2 s antes de lo pedido (fotograma clave anterior). No funciona en pausa ni si no hay una grabación en curso.
- **Herramientas de vídeo** (botón en la ventana o «Herramientas de vídeo…» en la bandeja; abre con tu última grabación): **recortar el principio y el final** (con miniaturas de los fotogramas de inicio y fin, corte exacto o rápido sin recodificar), **vertical 9:16** (1080×1920) para YouTube Shorts, TikTok y Reels, con el vídeo entero sobre un fondo desenfocado o recortado a vertical eligiendo qué parte queda; y **cortar silencios** (suave, normal o fuerte) para tutoriales. Se pueden combinar (recortar → silencios → vertical); siempre crean un archivo nuevo al lado del original, se pueden cancelar y no pisan nada. Medido: el vertical con fondo desenfocado tarda ~0,5 s por cada segundo de vídeo en un portátil de 4 núcleos. Revisa el límite de duración vigente de cada plataforma.
- Burbuja de cámara redonda y arrastrable, solo mientras se graba. `screencapture --present`: dibujar sobre la pantalla (lápiz, resaltador, halo) con «pasar clics».
  Efectos de la cámara (panel «Efectos de la cámara», en vivo): forma (círculo o cuadrado redondeado), color del borde, espejo, brillo, contraste y **recorte del fondo verde o azul** (solo se ve a la persona).
- Una sola instancia: `screencapture --quit` la cierra; `--segundo-plano` arranca solo con el icono de la bandeja y los atajos.
- Pendiente: editor de capturas en Qt (el de GTK4 sigue en el repositorio pero no funciona en KDE), elegir una ventana, GNOME.

## Dependencias (sistema)
`python3-pyside6.qtwidgets`, `python3-pyside6.qtgui`, `python3-pyside6.qtdbus`, `python3-gi`, `python3-dbus`, `gstreamer1.0-pipewire`, `gstreamer1.0-plugins-ugly` (x264), `ffmpeg`, `pipewire`, `xdg-desktop-portal` con el módulo de su escritorio, `libnotify-bin`. En KDE hace falta instalar `data/screencapture.desktop` en `~/.local/share/applications/`: el portal solo atiende a una aplicación con su archivo `.desktop`.

## Ejecutar desde el código
```bash
PYTHONPATH=src python3 -m screencapture.qtapp                      # ventana principal
PYTHONPATH=src python3 -m screencapture.qtapp --segundo-plano      # solo bandeja y atajos
python3 -m unittest discover -s tests                              # pruebas sin interfaz
```
Para que el escritorio le dé identidad propia (necesaria para el portal) se lanza desde el menú de aplicaciones o con `systemd-run --user --scope --unit=app-screencapture-1 ...`.

## Licencia
GPL-3.0-or-later (ver `LICENSE`). Autor: Hector Martinez.
