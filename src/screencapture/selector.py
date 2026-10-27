"""Selector de zona a pantalla completa: arrastrar para elegir una zona, Enter o Espacio para toda la pantalla, Esc o clic derecho para cancelar.
Con `fondo` (una captura ya tomada) la imagen queda congelada debajo, como Spectacle o Flameshot; sin `fondo` solo oscurece el escritorio en vivo (se usa antes de grabar).
`elegido(QRect | None)`: la zona en píxeles de la pantalla, o None si se pidió toda la pantalla. `cancelado()`: no se eligió nada."""
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .i18n import _

TITULO = "Screencapture — selector"
VERDE = QColor("#2A9D8F"); MIN = 8      # lado mínimo para que un clic suelto no cuente como zona

class Selector(QWidget):
    elegido = Signal(object); cancelado = Signal()

    def __init__(self, fondo=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.fondo = fondo; self.a = None; self.b = None; self.hecho = False
        self.setAttribute(Qt.WA_TranslucentBackground, fondo is None); self.setWindowTitle(TITULO); self.setMouseTracking(True); self.setCursor(Qt.CrossCursor)

    def zona(self):
        if not (self.a and self.b): return None
        r = QRect(self.a, self.b).normalized(); return QRect(r.left(), r.top(), max(1, r.width() - 1), max(1, r.height() - 1))      # QRect(a, b) incluye ambos extremos: un píxel de más

    def paintEvent(self, _e):
        p = QPainter(self); z = self.zona()
        if self.fondo: p.drawImage(self.rect(), self.fondo)
        sombra = QColor(0, 0, 0, 120)
        if z and z.width() >= MIN and z.height() >= MIN:
            for r in (QRect(0, 0, self.width(), z.top()), QRect(0, z.bottom() + 1, self.width(), self.height()), QRect(0, z.top(), z.left(), z.height()), QRect(z.right() + 1, z.top(), self.width(), z.height())):
                p.fillRect(r, sombra)
            p.setPen(QPen(VERDE, 2)); p.drawRect(z)
            p.setFont(QFont(self.font().family(), 10)); txt = f"{z.width()} × {z.height()}"; w = p.fontMetrics().horizontalAdvance(txt) + 14
            y = z.top() - 26 if z.top() > 30 else z.top() + 6; p.fillRect(QRect(z.left(), y, w, 22), VERDE); p.setPen(Qt.white); p.drawText(QRect(z.left(), y, w, 22), Qt.AlignCenter, txt)
        else:
            p.fillRect(self.rect(), sombra)
            p.setPen(Qt.white); p.setFont(QFont(self.font().family(), 13))
            p.drawText(self.rect(), Qt.AlignCenter, _("Arrastra para elegir una zona\nEnter o Espacio: pantalla completa · Esc: cancelar"))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.a = self.b = e.position().toPoint(); self.update()
        elif e.button() == Qt.RightButton: self.terminar(None, True)
    def mouseMoveEvent(self, e):
        if self.a and e.buttons() & Qt.LeftButton: self.b = e.position().toPoint(); self.update()
    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.a: return
        z = self.zona(); self.a = self.b = None
        if z and z.width() >= MIN and z.height() >= MIN: self.terminar(z)
        else: self.update()
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space): self.terminar(None)
        elif e.key() == Qt.Key_Escape: self.terminar(None, True)

    def terminar(self, zona, cancelar=False):
        if self.hecho: return
        self.hecho = True; self.close(); (self.cancelado.emit() if cancelar else self.elegido.emit(zona))
