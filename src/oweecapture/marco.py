"""Marco que muestra, mientras se graba o se transmite, qué parte de la pantalla entra en el vídeo, y que se puede arrastrar durante la grabación (como la burbuja de cámara): `movida(QRect)` avisa de la nueva zona.
Se dibuja SOLO por fuera de la zona (una línea de 4 px y un asa), así que no sale en la grabación: el portal entrega la pantalla entera y se recorta la zona.
Es una ventana a pantalla completa y transparente; su máscara de entrada solo cubre la línea y el asa, así que el resto de la pantalla sigue recibiendo los clics."""
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QRegion
from PySide6.QtWidgets import QWidget

TITULO = "OweeCapture — marco"
GROSOR = 4; COLOR = QColor("#FFD60A"); ASA = (150, 24)          # tamaño del asa (ancho, alto)
TEXTO = "⠿ arrastra para mover"

def segmentos(zona, ancho, alto):
    """Los cuatro rectángulos de la línea que rodea `zona` por fuera (recortados a la pantalla). Ninguno toca el interior de la zona."""
    z = zona; g = GROSOR; pantalla = QRect(0, 0, ancho, alto)
    return [r.intersected(pantalla) for r in (QRect(z.left() - g, z.top() - g, z.width() + 2 * g, g), QRect(z.left() - g, z.bottom() + 1, z.width() + 2 * g, g), QRect(z.left() - g, z.top(), g, z.height()), QRect(z.right() + 1, z.top(), g, z.height()))]

def asa(zona, ancho, alto):
    """El rectángulo del asa: pegado por fuera al borde de arriba de la zona (o al de abajo si arriba no cabe) y centrado. None si no cabe en ninguno de los dos (zona casi a pantalla completa)."""
    w, h = ASA; x = max(0, min(ancho - w, zona.center().x() - w // 2))
    for y in (zona.top() - GROSOR - h, zona.bottom() + 1 + GROSOR):
        if 0 <= y and y + h <= alto: return QRect(x, y, w, h)
    return None

def mover(zona, delta, ancho, alto):
    """`zona` desplazada `delta` (QPoint) sin salirse de la pantalla."""
    return QRect(max(0, min(ancho - zona.width(), zona.x() + delta.x())), max(0, min(alto - zona.height(), zona.y() + delta.y())), zona.width(), zona.height())

class Marco(QWidget):
    movida = Signal(object)

    def __init__(self, zona):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool); self.zona = QRect(zona); self.arrastre = None
        self.setAttribute(Qt.WA_TranslucentBackground); self.setAttribute(Qt.WA_ShowWithoutActivating); self.setWindowTitle(TITULO); self.setCursor(Qt.SizeAllCursor)

    def mostrar(self): self.showFullScreen(); self.windowHandle(); self.mascara()

    def zonas_activas(self):
        """Lo que se puede agarrar para mover el marco: la línea y el asa."""
        return segmentos(self.zona, self.width(), self.height()) + ([a] if (a := asa(self.zona, self.width(), self.height())) else [])

    def mascara(self):
        """Solo la línea y el asa reciben el ratón; el resto de la pantalla queda libre (los clics pasan a las ventanas de debajo)."""
        r = QRegion()
        for z in self.zonas_activas(): r = r.united(QRegion(z))
        self.windowHandle().setMask(r)          # a nivel de la ventana de plataforma: en Wayland es solo la región de entrada. Con QWidget.setMask también se recortaría lo que se pinta y las líneas viejas no se borrarían (estela)

    def paintEvent(self, _e):
        p = QPainter(self); p.setCompositionMode(QPainter.CompositionMode_Source); p.fillRect(self.rect(), Qt.transparent); p.setCompositionMode(QPainter.CompositionMode_SourceOver)          # borra lo dibujado antes: sin esto el marco deja una estela al moverse
        for r in segmentos(self.zona, self.width(), self.height()): p.fillRect(r, COLOR)
        a = asa(self.zona, self.width(), self.height())
        if a:
            p.setPen(Qt.NoPen); p.setBrush(COLOR); p.drawRoundedRect(a, 6, 6); p.setPen(QColor("#222222")); p.setFont(QFont(self.font().family(), 9, QFont.Bold)); p.drawText(a, Qt.AlignCenter, TEXTO)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.arrastre = (e.position().toPoint(), QRect(self.zona))          # dónde se agarró y cuál era la zona entonces
    def mouseMoveEvent(self, e):
        if self.arrastre is None: return
        inicio, zona0 = self.arrastre; nueva = mover(zona0, e.position().toPoint() - inicio, self.width(), self.height())
        if nueva != self.zona: self.zona = nueva; self.mascara(); self.update(); self.movida.emit(QRect(nueva))
    def mouseReleaseEvent(self, e): self.arrastre = None
