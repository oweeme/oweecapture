# Guía de uso

Cada apartado responde a «quiero hacer X». Las rutas son las de una instalación normal; las carpetas se llaman según el idioma de tu sistema (aquí `Vídeos` e `Imágenes`).

## La ventana

Tiene tres pestañas: **Grabar**, **Audio y cámara** y **Directo**. Los botones *Grabar* y *Pausar* están siempre abajo. Mientras grabas, la ventana se oculta y todo se maneja desde el **icono de la bandeja** (clic derecho) o con los atajos.

Al lado del botón *Grabar* hay: *Captura de pantalla*, *Modo presentación*, *Herramientas de vídeo* y *Acerca de*.

## Hacer una captura de pantalla

1. `Ctrl+Alt+S` (o el botón *Captura de pantalla*).
2. Arrastra para elegir una zona, o pulsa `Enter` o `Espacio` para toda la pantalla. `Esc` cancela.
3. Queda en `Imágenes/Screenshots` y copiada al portapapeles, lista para pegar.

La primera vez, el escritorio te pide permiso.

## Grabar la pantalla

1. En la pestaña **Grabar** elige:
   - **Zona al grabar:** *Libre* (arrastras una zona o pantalla completa) o *Vertical 9:16* (para TikTok, Shorts y Reels).
   - **Calidad:** *WhatsApp / Telegram* (pequeño y nítido), *YouTube* (buena calidad) o *Máxima* (para editar después).
   - **Fotogramas:** 24, 30 o 60 fps.
   - **Tamaño máximo:** sin límite, 16, 50 o 100 MB.
2. Pulsa **Grabar** (o `Ctrl+Alt+R`) y elige la zona.
3. Para terminar: `Ctrl+Alt+R` de nuevo, o *Detener la grabación* en el icono de la bandeja.
4. El vídeo aparece en `Vídeos/Screen Recordings` con el nombre `grabacion-AAAAMMDD-HHMMSS.mp4`.

**Pausar y continuar:** `Ctrl+Alt+P` o el menú de la bandeja.

**La reducción de calidad ocurre después:** con *WhatsApp / Telegram* el vídeo se guarda al detener y, en segundo plano, se reduce a 720p (puede tardar unos minutos en grabaciones largas; llega un aviso cuando termina y el archivo se reemplaza solo si queda más pequeño). Con *YouTube* o *Máxima* no se reduce.

**Audio:** en la pestaña *Audio y cámara* marca *Audio del sistema* y/o *Micrófono*. Cada fuente va en su propia pista y al guardar se mezclan con el volumen que elijas (0–200 %). Para el micrófono puedes activar la reducción de ruido: *suave* o *fuerte* (la fuerte cierra el micrófono entre frases y puede cortar finales de palabra muy bajos).

**Grabaciones que se cortan:** si el programa o el equipo se cierran, lo grabado no se pierde; se recupera al abrir de nuevo como `grabacion-recuperada-…`.

## Marco amarillo y mover la zona

Mientras grabas una zona, una línea amarilla la rodea **por fuera** (no sale en el vídeo). Con ella puedes **arrastrar la zona mientras grabas**: agarra la línea o el asa «arrastra para mover». Solo la línea recibe el ratón; el resto de la pantalla funciona normal.

## Grabar en vertical (TikTok, Shorts, Reels)

1. En *Zona al grabar* elige **Vertical 9:16**, o pulsa `V` en el selector de zona.
2. Un marco 9:16 sigue al ratón: la **rueda** cambia su tamaño y un **clic** lo fija.
3. Muévelo mientras grabas arrastrando la línea amarilla.

## Zoom mientras grabas

*(Solo KDE Plasma.)* En *Ayudas para tutoriales* elige 1,5×, 2× o 2,5×. Durante la grabación, `Ctrl+Alt+Z` acerca centrado en el cursor y otra vez aleja, con transición suave. El icono de la bandeja cambia a lupa mientras el zoom está activo. El zoom se aplica **al terminar** la grabación (reescribe el vídeo; unos 0,8 s por cada segundo grabado en 1080p), así que la ventana dice «Guardando…» un rato.

Si no pulsas `Ctrl+Alt+Z` en ningún momento, el vídeo queda sin zoom.

**Resaltar el cursor** (un halo alrededor del puntero) se activa en la misma sección.

## Clics y teclas en pantalla

Para mostrar ondas de color en cada clic y una pastilla con las teclas que pulsas:

1. Tu usuario debe estar en el grupo `input` (el sistema no deja leer ratón y teclado de otro modo). En una terminal: `sudo usermod -aG input $USER` y **vuelve a iniciar sesión**.
2. Marca *Resaltar los clics del ratón* y elige en *Mostrar teclas*: *No mostrar*, *Solo atajos y teclas especiales* (Ctrl+C, Intro, Esc…) o *Todo lo que escribo*.

**Privacidad:** solo se lee mientras grabas o transmites, no se guarda nada y por defecto no se muestra lo que escribes. Evita «Todo lo que escribo» si vas a teclear contraseñas.

## Guardar un clip de los últimos segundos

Mientras grabas o transmites, `Ctrl+Alt+G` guarda aparte los últimos 15, 30, 60 o 120 segundos (se elige en *Clip con Ctrl+Alt+G*) en `Vídeos/Screen Recordings/Clips`, sin parar la grabación. Sirve para «eso que acaba de pasar, quiero guardarlo». No funciona en pausa.

## Burbuja de la cámara

1. En *Audio y cámara* marca **Cámara en burbuja**.
2. Al grabar aparece una burbuja redonda que se **arrastra** por la pantalla.
3. **Quitarla y ponerla mientras grabas:** `Ctrl+Alt+C`, o en el icono de la bandeja *Quitar la burbuja de la cámara* / *Poner la burbuja de la cámara*. Quitarla no cambia tu opción: la próxima grabación vuelve a llevarla.
4. En el panel *Efectos de la cámara* (se ve en vivo): forma (círculo o cuadrado redondeado), color del borde, espejo, brillo, contraste y **recorte de fondo verde o azul**.

## Modo presentación: dibujar sobre la pantalla

`Ctrl+Alt+D` (o el botón *Modo presentación*) pone una capa transparente sobre la pantalla y una barra de iconos con: lápiz, resaltador, flecha, marco, elipse y texto (escribes y pulsas `Intro`); 6 colores, 3 grosores, deshacer, borrar y **pasar clics** (usas el escritorio sin salir y lo dibujado sigue visible).

Teclas: `1`–`6` cambian de herramienta, `Ctrl+Z` deshace, `C` borra, `Espacio` alterna pasar clics, `Esc` sale.

**Para que la barra no salga en tus vídeos:** en KDE Plasma (KWin 6.4 o posterior) la barra de iconos se excluye sola de las grabaciones y los directos: tú la ves, el vídeo no. **Lo que dibujas sí sale en el vídeo.** Lo mismo ocurre con los menús desplegables del icono de la bandeja mientras grabas. En otros escritorios no hay forma de ocultar una ventana de la grabación; la alternativa es grabar solo una zona y dejar la barra fuera de ella.

## Transmitir en directo

1. En la plataforma (YouTube, TikTok, Twitch…) obtén la **dirección del servidor** y la **clave de transmisión**. TikTok exige cumplir sus requisitos para transmitir desde un ordenador con clave.
2. Pestaña **Directo**: pega ambas, elige 480p, 720p o 1080p y pulsa *Transmitir en directo*.
3. Se emite pantalla + cámara + audio (sistema y micrófono) y se guarda una **copia local en MP4** por si se corta la conexión.
4. Si se cae la conexión, **reconecta sola** (reintenta a 1, 2, 4, 8, 15 y 30 s); la ventana muestra el estado. Si nunca llega a conectar (dirección o clave mal puestas) avisa a los 3 intentos.

**La clave** solo se guarda si marcas «Recordar» (archivo de configuración con permisos 0600). Nunca aparece en mensajes ni en el registro; el botón *Mostrar* la enseña y se vuelve a tapar solo.

En directo no hay pausa ni zoom. La reducción de ruido del micrófono crea un micrófono virtual «OweeCapture: micrófono sin ruido» (necesita PipeWire con el módulo echo-cancel; si falta, se usa el micrófono normal y se avisa). Pruébalo antes de un directo importante: cómo suena tu voz con el filtro solo se juzga a oído.

## Herramientas de vídeo

Botón *Herramientas de vídeo* en la ventana o en la bandeja; se abre con tu última grabación. **Siempre crean un archivo nuevo al lado del original**, se pueden cancelar y no pisan nada.

- **Recortar** el principio y el final, con miniaturas. En la vista previa, el botón *Aquí* pone el inicio o el fin donde está el vídeo y *▶ Ver el tramo* reproduce justo lo que quedará.
- **Vertical 9:16** (1080×1920) para Shorts, TikTok y Reels: con el vídeo entero sobre un fondo desenfocado, o recortado eligiendo qué parte queda. Revisa el límite de duración de cada plataforma.
- **Cortar silencios** (suave, normal o fuerte): ideal para tutoriales.
- **Subtítulos automáticos**, locales: crean un archivo `.srt` junto al vídeo (sirve en YouTube) y, si quieres, los dibujan en el vídeo estilo TikTok.

Se pueden combinar: recortar → silencios → subtítulos → vertical.

### Subtítulos: la descarga

El motor (faster-whisper, modelo «base») **no viene incluido**: se descarga si lo aceptas, con un botón en las herramientas. **Pesa unos 620 MB** y se instala en `~/.local/share/oweecapture/`; se quita borrando las carpetas `voz/` y `modelos/` de ahí. El audio nunca sale de tu equipo. La calidad con voz real hay que juzgarla a oído.

## Arranque con el escritorio

Activa **Iniciar OweeCapture al abrir la sesión** (pestaña *Grabar*). Crea `~/.config/autostart/oweecapture.desktop`, que arranca solo el icono de la bandeja y los atajos, sin abrir la ventana. Para quitarlo, desmarca la casilla.

## Dónde se guarda todo

| Qué | Dónde |
|---|---|
| Capturas | `Imágenes/Screenshots` |
| Grabaciones | `Vídeos/Screen Recordings/grabacion-….mp4` |
| Clips | `Vídeos/Screen Recordings/Clips` |
| Configuración | `~/.config/oweecapture/config.json` |
| Elección de pantalla recordada | `~/.config/oweecapture/portal.json` |
| Errores de grabación | `~/.cache/oweecapture/error.log` |
| Errores de arranque | `~/.cache/oweecapture/arranque.log` |
| Grabación en curso (temporal) | `~/.cache/oweecapture/rec/` |
| Motor de subtítulos | `~/.local/share/oweecapture/` |
