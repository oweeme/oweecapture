# Solución de problemas

**Primero, dos comprobaciones que resuelven la mayoría de los casos:**

```bash
oweecapture --version      # ¿qué versión es la instalada?
oweecapture --comprobar    # ¿qué falta en el sistema?
```

Y mira los registros (se explican abajo): `~/.cache/oweecapture/arranque.log` y `~/.cache/oweecapture/error.log`.

## «Acerca de» muestra una versión vieja

Acabas de actualizar, pero sigue abierta la copia anterior (se arranca con la sesión y se queda en memoria). Ciérrala y abre de nuevo:

```bash
oweecapture --quit
```

o icono de la bandeja → *Salir*. Si no responde, localiza el proceso con `pgrep -f oweecapture.qtapp` y ciérralo con `kill <número>`. Para volver a abrirlo sin que dependa de la terminal:

```bash
systemd-run --user --quiet --collect --unit=app-oweecapture-$RANDOM /usr/bin/oweecapture --segundo-plano
```

> No lances el programa con `--scope` en una terminal y luego pulses `Ctrl+C`: lo cierra.

## No abre nada (ni ventana ni icono)

1. Ábrelo desde una terminal: `oweecapture`. El error sale ahí.
2. Si lo lanzas desde el menú no hay terminal; mira `~/.cache/oweecapture/arranque.log`. **Ese archivo se va acumulando**: lo que ves al final es lo último, pero puede haber errores de intentos viejos arriba. Para empezar limpio: `: > ~/.cache/oweecapture/arranque.log`.
3. Errores típicos:
   - `No module named 'oweecapture'`: instalación incompleta o rota por una versión antigua. Con el `.deb`: `sudo apt purge oweecapture` y vuelve a instalar la última versión.
   - `Could not find the Qt platform plugin "dxcb"` (Deepin): se corrige desde la 0.1.3; actualiza.
   - `No module named 'PySide6'` o `libxcb…`: falta una biblioteca del sistema; ejecuta `oweecapture --comprobar`.

## Grabar no funciona o se corta al instante

- **Mensaje «El portal de pantalla falló»** (escritorios con X11, como Deepin): usa la versión **0.1.6 o posterior**, que graba sin portal en sesiones X11. Comprueba tu sesión con `echo $XDG_SESSION_TYPE` (`x11` o `wayland`).
- **KDE/GNOME (Wayland):** hace falta `xdg-desktop-portal` con el módulo de tu escritorio (`xdg-desktop-portal-kde` o `xdg-desktop-portal-gnome`) y PipeWire. Al grabar por primera vez, el escritorio muestra un aviso de permiso de compartir pantalla; hay que aceptarlo.
- **Se corta y el vídeo sale vacío o no se guarda nada:** mira el final de `~/.cache/oweecapture/error.log`. Pásalo si abres una incidencia.
- **Aparece «Guardando…» mucho rato:** con zoom o halo, el vídeo se reescribe al terminar (~0,8 s por segundo grabado). Con calidad *WhatsApp*, la reducción posterior va en segundo plano y el vídeo ya se puede abrir.
- **Poco espacio:** no graba con menos de 1 GB libre.

## No hay atajos globales

Mensaje: «Tu escritorio no ofrece atajos globales a las aplicaciones». Es normal en **Deepin** y en **GNOME anterior a la 48**. La aplicación funciona igual; crea los atajos en los ajustes de teclado de tu escritorio, asignando estas órdenes:

| Orden | Hace |
|---|---|
| `oweecapture --record` | Grabar / detener |
| `oweecapture --shot` | Captura de pantalla |
| `oweecapture --present` | Modo presentación |
| `oweecapture --camera` | Quitar / poner la burbuja de cámara |
| `oweecapture --quit` | Cerrar |

Si la tecla que quieres ya la usa el sistema (en Deepin `Ctrl+Alt+R` es su grabador), elige otra, p. ej. `Ctrl+Alt+Shift+R`. Activa también «Iniciar OweeCapture al abrir la sesión» para que atienda las órdenes desde que arranca el escritorio.

**En KDE, un atajo nuevo no tiene tecla:** tras instalar una versión con un atajo nuevo (por ejemplo `Ctrl+Alt+C` en la 0.1.8), KDE solo le asigna la tecla en el **segundo** arranque. Cierra el programa y ábrelo dos veces.

## El zoom o el halo no hacen nada

- Solo funcionan en **KDE Plasma** (necesitan KWin); en otros escritorios las opciones aparecen desactivadas.
- El zoom solo se aplica si pulsas `Ctrl+Alt+Z` durante la grabación; si no lo pulsas, el vídeo queda sin zoom. Mira el icono de la bandeja: cambia a lupa mientras está activo.
- Se aplica **al terminar** la grabación, no en vivo en el vídeo.

## Los clics y las teclas no aparecen

Tu usuario debe estar en el grupo `input`: `sudo usermod -aG input $USER` y **cierra la sesión y vuelve a entrar** (con reiniciar el programa no basta). Comprueba con `groups`.

## La barra del modo presentación o los menús salen en el vídeo

La exclusión de la grabación funciona solo en **KDE con KWin 6.4 o posterior**. En otros escritorios no hay forma de ocultar una ventana; graba solo una zona y deja la barra fuera de ella.

## Directo

- **«No se pudo conectar con el servidor»:** revisa la dirección del servidor y la clave; vuelve a copiarlas de la plataforma, sin espacios.
- **Se corta y vuelve:** es la reconexión automática; la copia local sigue grabándose. El estado se ve en la ventana.
- **El micrófono sin ruido no aparece:** falta el módulo echo-cancel de PipeWire; se transmite con el micrófono normal y te avisa.
- **Fedora:** sin RPM Fusion no hay H.264/AAC (ver [INSTALACION.md](INSTALACION.md)).

## Subtítulos

- Piden descargar el motor la primera vez (unos 620 MB; hace falta internet solo para eso).
- Para quitarlo y recuperar el espacio: borra `~/.local/share/oweecapture/voz` y `~/.local/share/oweecapture/modelos`.

## GNOME

Aún no está probado. Hay que saber que: el icono de la bandeja solo se ve con la extensión *AppIndicator*, los atajos globales solo existen desde GNOME 48 (antes, crea los tuyos), y no se pueden dejar ventanas siempre encima ni ocultarlas de la grabación.

## Pedir ayuda

Abre una incidencia en el repositorio con: tu distribución y escritorio, `echo $XDG_SESSION_TYPE`, `oweecapture --version`, y el final de `error.log` y `arranque.log`. **Revisa antes de pegar** que no haya claves de directo: no se guardan en los registros, pero conviene mirar.
