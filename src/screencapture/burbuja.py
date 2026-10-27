"""Burbuja de cámara redonda y flotante (PySide6 + GStreamer). Arrastrar: botón izquierdo; tamaño: rueda; cerrar: clic derecho o Esc. Queda dentro de la grabación porque la dibuja el compositor.
En KDE se mantiene encima con `kwin.mantener_encima`; en otros escritorios es una ventana normal."""
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

TITULO = "Screencapture — burbuja de cámara"
TAMANOS = [120, 180, 240, 320]

class Burbuja(QWidget):
    def __init__(self, dispositivo="/dev/video0", prueba=False, alcerrar=None):
        self.alcerrar = alcerrar
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setWindowTitle(TITULO)
        self.lado = TAMANOS[1]; self.setFixedSize(self.lado, self.lado); self.imagen = None
        Gst.init(None)
        origen = "videotestsrc is-live=true pattern=ball" if prueba else f"v4l2src device={dispositivo}"
        self.pipe = Gst.parse_launch(f"{origen} ! videoconvert ! aspectratiocrop aspect-ratio=1/1 ! videoscale ! video/x-raw,format=BGRx,width=320,height=320 ! appsink name=sal emit-signals=false max-buffers=1 drop=true sync=false")
        self.sal = self.pipe.get_by_name("sal"); self.pipe.set_state(Gst.State.PLAYING)
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tomar_cuadro); self.reloj.start(33)

    def tomar_cuadro(self):
        muestra = self.sal.emit("try-pull-sample", 0)
        if not muestra: return
        ok, info = muestra.get_buffer().map(Gst.MapFlags.READ)
        if ok:
            self.imagen = QImage(bytes(info.data), 320, 320, 320 * 4, QImage.Format_RGB32).copy(); muestra.get_buffer().unmap(info)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4); forma = QPainterPath(); forma.addEllipse(r)
        p.setClipPath(forma)
        if self.imagen: p.drawImage(r, self.imagen)
        else: p.fillPath(forma, QColor("#102019"))
        p.setClipping(False); p.setPen(QPen(QColor("#2A9D8F"), 3)); p.drawEllipse(r)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.windowHandle().startSystemMove()      # en Wayland el cliente no mueve su ventana: se lo pide al compositor
        elif e.button() == Qt.RightButton: self.close()

    def wheelEvent(self, e):
        i = TAMANOS.index(self.lado) + (1 if e.angleDelta().y() > 0 else -1); self.lado = TAMANOS[max(0, min(len(TAMANOS) - 1, i))]; self.setFixedSize(self.lado, self.lado)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.close()

    def closeEvent(self, e): self.pipe.set_state(Gst.State.NULL); self.reloj.stop(); self.alcerrar and self.alcerrar()

