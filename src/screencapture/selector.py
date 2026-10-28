"""Selector de zona a pantalla completa: arrastrar para elegir una zona, Enter o Espacio para toda la pantalla, Esc o clic derecho para cancelar. Tecla V: marco vertical 9:16 (para TikTok y Shorts) que sigue al ratón, con la rueda cambia de tamaño y un clic lo fija.
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

    def __init__(self, fondo=None, ventanas=(), vertical=False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.vertical = vertical; self.escala = 0.92; self.centro = QPoint(0, 0); self.fondo = fondo; self.a = None; self.b = None; self.hecho = False; self.sobre = None
        self.ventanas = [(QRect(v["x"], v["y"], v["w"], v["h"]), v["c"]) for v in ventanas]      # de abajo arriba: la última es la que está encima
        self.setAttribute(Qt.WA_TranslucentBackground, fondo is None); self.setWindowTitle(TITULO); self.setMouseTracking(True); self.setCursor(Qt.CrossCursor)

    def showEvent(self, e): self.centro = self.rect().center(); super().showEvent(e)

    def ventana_en(self, punto):
        """La ventana de más arriba bajo el puntero: (QRect, título) o None."""
        return next((v for v in reversed(self.ventanas) if v[0].contains(punto)), None)

    def marco_vertical(self):
        """El marco 9:16 centrado en el ratón, dentro de la pantalla: alto = `escala` de la pantalla, ancho = 9/16 del alto exacto (medidas pares, como pide H.264)."""
        h = max(16, int(self.height() * self.escala) // 16 * 16); w = h * 9 // 16          # alto múltiplo de 16: el ancho sale exacto (y par) y la proporción es 9:16 de verdad
        return QRect(max(0, min(self.width() - w, self.centro.x() - w // 2)), max(0, min(self.height() - h, self.centro.y() - h // 2)), w, h)

    def zona(self):
        if not (self.a and self.b): return None
        r = QRect(self.a, self.b).normalized(); return QRect(r.left(), r.top(), max(1, r.width() - 1), max(1, r.height() - 1))      # QRect(a, b) incluye ambos extremos: un píxel de más

    def paintEvent(self, _e):
        p = QPainter(self); z = self.zona()
        if self.fondo: p.drawImage(self.rect(), self.fondo)
        sombra = QColor(0, 0, 0, 120)
        if self.vertical: self.pintar_vertical(p, sombra); return
        if z and z.width() >= MIN and z.height() >= MIN:
            for r in (QRect(0, 0, self.width(), z.top()), QRect(0, z.bottom() + 1, self.width(), self.height()), QRect(0, z.top(), z.left(), z.height()), QRect(z.right() + 1, z.top(), self.width(), z.height())):
                p.fillRect(r, sombra)
            p.setPen(QPen(VERDE, 2)); p.drawRect(z)
            p.setFont(QFont(self.font().family(), 10)); txt = f"{z.width()} × {z.height()}"; w = p.fontMetrics().horizontalAdvance(txt) + 14
            y = z.top() - 26 if z.top() > 30 else z.top() + 6; p.fillRect(QRect(z.left(), y, w, 22), VERDE); p.setPen(Qt.white); p.drawText(QRect(z.left(), y, w, 22), Qt.AlignCenter, txt)
        else:
            p.fillRect(self.rect(), sombra)
            if self.sobre:                                                            # ventana bajo el puntero: se muestra sin sombra y con borde
                r, titulo = self.sobre; r = r.intersected(self.rect())
                if self.fondo: p.drawImage(r, self.fondo, r)
                else: p.setCompositionMode(QPainter.CompositionMode_Clear); p.fillRect(r, Qt.transparent); p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                p.setPen(QPen(VERDE, 3)); p.drawRect(r.adjusted(1, 1, -2, -2)); p.setFont(QFont(self.font().family(), 10)); txt = f"{titulo[:60]}  {r.width()} × {r.height()}"; w = p.fontMetrics().horizontalAdvance(txt) + 14
                y = r.top() + 8; p.fillRect(QRect(r.left() + 8, y, w, 22), VERDE); p.setPen(Qt.white); p.drawText(QRect(r.left() + 8, y, w, 22), Qt.AlignCenter, txt)
            else:
                p.setPen(Qt.white); p.setFont(QFont(self.font().family(), 13))
                p.drawText(self.rect(), Qt.AlignCenter, _("Arrastra para elegir una zona · Clic en una ventana para elegirla\nEnter o Espacio: pantalla completa · V: marco vertical 9:16 · Esc: cancelar"))

    def pintar_vertical(self, p, sombra):
        z = self.marco_vertical()
        for r in (QRect(0, 0, self.width(), z.top()), QRect(0, z.bottom() + 1, self.width(), self.height()), QRect(0, z.top(), z.left(), z.height()), QRect(z.right() + 1, z.top(), self.width(), z.height())): p.fillRect(r, sombra)
        p.setPen(QPen(VERDE, 3)); p.drawRect(z); p.setFont(QFont(self.font().family(), 10)); txt = f"{z.width()} × {z.height()}  ·  vertical 9:16"; w = p.fontMetrics().horizontalAdvance(txt) + 14
        y = z.top() + 8; p.fillRect(QRect(z.left() + 8, y, w, 22), VERDE); p.setPen(Qt.white); p.drawText(QRect(z.left() + 8, y, w, 22), Qt.AlignCenter, txt)
        p.setFont(QFont(self.font().family(), 12)); p.drawText(QRect(0, self.height() - 60, self.width(), 40), Qt.AlignCenter, _("Mueve el ratón para colocar el marco · Rueda: tamaño · Clic: elegir · V: zona libre · Esc: cancelar"))

    def wheelEvent(self, e):
        if self.vertical: self.escala = max(0.3, min(1.0, self.escala + (0.04 if e.angleDelta().y() > 0 else -0.04))); self.update()

    def mousePressEvent(self, e):
        if self.vertical and e.button() == Qt.LeftButton: self.terminar(self.marco_vertical()); return
        if e.button() == Qt.LeftButton: self.a = self.b = e.position().toPoint(); self.update()
        elif e.button() == Qt.RightButton: self.terminar(None, True)
    def mouseMoveEvent(self, e):
        if self.vertical: self.centro = e.position().toPoint(); self.update(); return
        if self.a and e.buttons() & Qt.LeftButton: self.b = e.position().toPoint(); self.update()
        else:
            nueva = self.ventana_en(e.position().toPoint())
            if nueva != self.sobre: self.sobre = nueva; self.update()
    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.a: return
        z = self.zona(); self.a = self.b = None
        if z and z.width() >= MIN and z.height() >= MIN: self.terminar(z)
        elif self.sobre: self.terminar(self.sobre[0].intersected(self.rect()))      # clic suelto sobre una ventana: se elige entera
        else: self.update()
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_V: self.vertical = not self.vertical; self.update()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space): self.terminar(None)
        elif e.key() == Qt.Key_Escape: self.terminar(None, True)

    def terminar(self, zona, cancelar=False):
        if self.hecho: return
        self.hecho = True; self.close(); (self.cancelado.emit() if cancelar else self.elegido.emit(zona))
