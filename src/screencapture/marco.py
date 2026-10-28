"""Marco que muestra, mientras se graba o se transmite, qué parte de la pantalla entra en el vídeo. Se dibuja SOLO por fuera de la zona (una línea de 4 px alrededor), así que no sale en la grabación: el portal entrega la pantalla entera y se recorta la zona.
Ventana a pantalla completa, transparente y que deja pasar los clics (como el modo presentación)."""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

TITULO = "Screencapture — marco"
GROSOR = 4; COLOR = QColor("#FFD60A")

def segmentos(zona, ancho, alto):
    """Los cuatro rectángulos de la línea que rodea `zona` por fuera (recortados a la pantalla). Ninguno toca el interior de la zona."""
    z = zona; g = GROSOR; pantalla = QRect(0, 0, ancho, alto)
    return [r.intersected(pantalla) for r in (QRect(z.left() - g, z.top() - g, z.width() + 2 * g, g), QRect(z.left() - g, z.bottom() + 1, z.width() + 2 * g, g), QRect(z.left() - g, z.top(), g, z.height()), QRect(z.right() + 1, z.top(), g, z.height()))]

class Marco(QWidget):
    def __init__(self, zona):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool); self.zona = QRect(zona)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setAttribute(Qt.WA_ShowWithoutActivating); self.setWindowTitle(TITULO)

    def mostrar(self):
        self.showFullScreen(); self.windowHandle().setFlag(Qt.WindowTransparentForInput, True)         # los clics pasan a las ventanas de debajo

    def paintEvent(self, _e):
        p = QPainter(self)
        for r in segmentos(self.zona, self.width(), self.height()): p.fillRect(r, COLOR)
