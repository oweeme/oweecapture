# Cambios por versión

## 0.1.9
- Los menús desplegables del icono de la bandeja ya no salen en la grabación (KDE).

## 0.1.8
- Burbuja de la cámara: se puede **quitar y volver a poner mientras grabas** (icono de la bandeja, `Ctrl+Alt+C` o `oweecapture --camera`).
- La **barra del modo presentación no sale en el vídeo**: se ve en tu pantalla, pero se excluye de la grabación y del directo (KDE con KWin 6.4 o posterior).

## 0.1.7
- Al pulsar Detener, el marco amarillo y los resaltados desaparecen al instante (antes esperaban a que terminara de guardar).
- La reducción de calidad en segundo plano es más rápida.

## 0.1.6
- **Grabar en sesiones X11** (Deepin): captura directa de pantalla sin portal. Antes la grabación se cortaba al instante con «El portal de pantalla falló».

## 0.1.5
- **Actualizar ya no deja el programa sin archivos** (fallo visto en Deepin): el código vive en `/usr/lib/oweecapture` y el `postrm` solo borra al quitar o purgar el paquete.

## 0.1.4
- El entorno propio con PySide6 ve siempre el paquete: Python del sistema, `.pth` y lanzador a prueba de fallos.
- Se retira el entorno propio viejo cuando el sistema ya trae PySide6.

## 0.1.3
- La aplicación abre aunque el portal y KWin estén incompletos (Deepin): antes fallaba al arrancar.

## 0.1.2
- Qt abre ventanas en X11: bibliotecas xcb obligatorias, registro de arranque (`arranque.log`) y prueba con pantalla virtual.

## 0.1.1
- **Instalador universal**: `.deb` que trae su PySide6 si el sistema no lo tiene, `install.sh` para Fedora, Arch y openSUSE, y pruebas de instalación en cada distribución.
- Arreglada la descripción del `.deb` y quitada la dependencia de QtDBus, que rompía la instalación en Deepin.

## 0.1.0
- Primera versión pública con el nombre **OweeCapture**, con paquete `.deb` y pruebas automáticas en GitHub Actions: grabación por portal + PipeWire, capturas, zoom a demanda y halo, mezclador de audio y reducción de ruido, directo RTMP con reconexión, clips, herramientas de vídeo (recortar, vertical, silencios), subtítulos locales, grabación vertical con marco arrastrable, clics y teclas en pantalla, modo presentación, burbuja de cámara con efectos, inicio con el escritorio.
