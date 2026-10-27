"""Burbuja de cámara flotante (PySide6 + GStreamer) con efectos: forma (círculo o cuadrado redondeado), color del borde, espejo, brillo y contraste, y recorte del fondo verde o azul (croma). Arrastrar: botón izquierdo; tamaño: rueda; cerrar: clic derecho o Esc.
Queda dentro de la grabación porque la dibuja el compositor.
En KDE se mantiene encima con `kwin.mantener_encima`; en otros escritorios es una ventana normal."""
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

TITULO = "Screencapture — burbuja de cámara"
TAMANOS = [120, 180, 240, 320]
FORMAS = [("circulo", "Círculo"), ("cuadrado", "Cuadrado redondeado")]
BORDES = [("#2A9D8F", "Verde azulado"), ("#FFFFFF", "Blanco"), ("#E63946", "Rojo"), ("#2A7FFF", "Azul"), ("#FFD60A", "Amarillo"), ("", "Sin borde")]
FONDOS = [("", "Sin recorte"), ("green", "Fondo verde"), ("blue", "Fondo azul")]
OPCIONES = {"forma": "circulo", "borde": "#2A9D8F", "espejo": False, "brillo": 0, "contraste": 100, "fondo": ""}       # brillo -50…50 y contraste 50…150 (en %)

def limpiar(o):
    """Opciones válidas a partir de lo que haya en la configuración (valores desconocidos o fuera de rango vuelven al valor por defecto)."""
    o = {**OPCIONES, **{k: v for k, v in (o or {}).items() if k in OPCIONES}}
    if o["forma"] not in dict(FORMAS): o["forma"] = OPCIONES["forma"]
    if o["borde"] not in dict(BORDES): o["borde"] = OPCIONES["borde"]
    if o["fondo"] not in dict(FONDOS): o["fondo"] = ""
    o["brillo"] = max(-50, min(50, int(o["brillo"]))); o["contraste"] = max(50, min(150, int(o["contraste"]))); o["espejo"] = bool(o["espejo"]); return o

def descripcion(origen, o):
    """Tubería de GStreamer: recorte cuadrado, brillo y contraste (`videobalance`) y recorte del fondo (`alpha`, siempre presente para poder activarlo en vivo), con salida BGRA al `appsink`."""
    return (f"{origen} ! videoconvert ! aspectratiocrop aspect-ratio=1/1 ! videoscale ! video/x-raw,width=320,height=320 ! videoconvert ! videobalance name=balance brightness={o['brillo'] / 100:.2f} contrast={o['contraste'] / 100:.2f} ! "
            f"videoconvert ! alpha name=croma method={o['fondo'] or 'set'} angle=25 noise-level=3 ! videoconvert ! video/x-raw,format=BGRA ! appsink name=sal emit-signals=false max-buffers=1 drop=true sync=false")

class Burbuja(QWidget):
    def __init__(self, dispositivo="/dev/video0", prueba=False, alcerrar=None, opciones=None):
        self.alcerrar = alcerrar; self.o = limpiar(opciones)
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setWindowTitle(TITULO)
        self.lado = TAMANOS[1]; self.setFixedSize(self.lado, self.lado); self.imagen = None
        Gst.init(None)
        origen = "videotestsrc is-live=true pattern=ball" if prueba else f"v4l2src device={dispositivo}"
        self.pipe = Gst.parse_launch(descripcion(origen, self.o))
        self.sal = self.pipe.get_by_name("sal"); self.pipe.set_state(Gst.State.PLAYING)
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tomar_cuadro); self.reloj.start(33)

    def aplicar(self, opciones):
        """Cambia los efectos en vivo (brillo, contraste y recorte van a la tubería; forma, borde y espejo se aplican al dibujar)."""
        self.o = limpiar(opciones); b = self.pipe.get_by_name("balance"); b.set_property("brightness", self.o["brillo"] / 100); b.set_property("contrast", self.o["contraste"] / 100)
        self.pipe.get_by_name("croma").set_property("method", {"": 0, "green": 1, "blue": 2}[self.o["fondo"]]); self.update()

    def tomar_cuadro(self):
        muestra = self.sal.emit("try-pull-sample", 0)
        if not muestra: return
        ok, info = muestra.get_buffer().map(Gst.MapFlags.READ)
        if ok:
            self.imagen = QImage(bytes(info.data), 320, 320, 320 * 4, QImage.Format_ARGB32).copy(); muestra.get_buffer().unmap(info)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform); r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        img = self.imagen.mirrored(True, False) if self.imagen and self.o["espejo"] else self.imagen
        if self.o["fondo"]:                                                      # con recorte del fondo solo se ve a la persona, sin forma ni borde
            if img: p.drawImage(r, img)
            return
        forma = QPainterPath(); forma.addEllipse(r) if self.o["forma"] == "circulo" else forma.addRoundedRect(r, self.width() * 0.14, self.width() * 0.14)
        p.setClipPath(forma)
        if img: p.drawImage(r, img)
        else: p.fillPath(forma, QColor("#102019"))
        p.setClipping(False)
        if self.o["borde"]: p.setPen(QPen(QColor(self.o["borde"]), 3)); p.drawPath(forma)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.windowHandle().startSystemMove()      # en Wayland el cliente no mueve su ventana: se lo pide al compositor
        elif e.button() == Qt.RightButton: self.close()

    def wheelEvent(self, e):
        i = TAMANOS.index(self.lado) + (1 if e.angleDelta().y() > 0 else -1); self.lado = TAMANOS[max(0, min(len(TAMANOS) - 1, i))]; self.setFixedSize(self.lado, self.lado)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.close()

    def closeEvent(self, e): self.pipe.set_state(Gst.State.NULL); self.reloj.stop(); self.alcerrar and self.alcerrar()

