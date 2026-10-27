"""Modo presentación: dibujar sobre la pantalla (lápiz, resaltador, halo del puntero) con alternancia «dibujar» / «pasar clics» (PySide6).
Atajos en la ventana de dibujo: 1 lápiz · 2 resaltador · Ctrl+Z deshacer · C borrar todo · Espacio dibujar/pasar clics · Esc salir. La barra de controles es hija de la ventana de dibujo (KWin la mantiene encima)."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

T_DIBUJO, T_CONTROLES = "Screencapture — dibujo", "Screencapture — controles"
HERRAMIENTAS = {"lapiz": (QColor(230, 57, 70), 4), "resaltador": (QColor(255, 214, 10, 110), 24)}

class Dibujo(QWidget):
    def __init__(self, alcerrar=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint); self.alcerrar = alcerrar
        self.setAttribute(Qt.WA_TranslucentBackground); self.setWindowTitle(T_DIBUJO); self.setMouseTracking(True)
        self.trazos = []; self.actual = None; self.herramienta = "lapiz"; self.puntero = None; self.dibujando = True
        self.barra = Controles(self)
        self.setCursor(Qt.CrossCursor)

    def modo(self, dibujar):
        """Dibujar: la ventana recibe el ratón. Pasar clics: la región de entrada queda vacía y el escritorio responde como siempre (los trazos siguen visibles)."""
        self.dibujando = dibujar; self.windowHandle().setFlag(Qt.WindowTransparentForInput, not dibujar); self.puntero = None if not dibujar else self.puntero
        self.barra.actualizar(); self.update()

    def closeEvent(self, e): self.barra.close(); self.alcerrar and self.alcerrar()
    def herramienta_es(self, h): self.herramienta = h; self.modo(True); self.barra.actualizar()
    def deshacer(self): self.trazos and self.trazos.pop(); self.update()
    def borrar(self): self.trazos.clear(); self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for color, ancho, ruta in self.trazos + ([self.actual] if self.actual else []):
            p.setPen(QPen(color, ancho, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush); p.drawPath(ruta)
        if self.puntero and self.dibujando:                                                 # halo alrededor del puntero (solo se conoce su posición mientras se dibuja)
            p.setPen(QPen(QColor(255, 214, 10, 200), 3)); p.setBrush(QColor(255, 214, 10, 45)); p.drawEllipse(self.puntero, 26, 26)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            color, ancho = HERRAMIENTAS[self.herramienta]; ruta = QPainterPath(e.position()); ruta.lineTo(e.position() + QPointF(0.01, 0)); self.actual = (color, ancho, ruta); self.update()
    def mouseMoveEvent(self, e):
        self.puntero = e.position()
        if self.actual: self.actual[2].lineTo(e.position())
        self.update()
    def mouseReleaseEvent(self, e):
        if self.actual: self.trazos.append(self.actual); self.actual = None; self.update()
    def leaveEvent(self, _e): self.puntero = None; self.update()
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape: self.close()
        elif k == Qt.Key_1: self.herramienta_es("lapiz")
        elif k == Qt.Key_2: self.herramienta_es("resaltador")
        elif k == Qt.Key_C: self.borrar()
        elif k == Qt.Key_Z and e.modifiers() & Qt.ControlModifier: self.deshacer()
        elif k == Qt.Key_Space: self.modo(not self.dibujando)

class Controles(QWidget):
    """Barra de controles: ventana propia, hija (transitoria) de la de dibujo, así KWin la mantiene siempre por encima de ella y sigue recibiendo clics en modo «pasar clics»."""
    def __init__(self, dibujo):
        super().__init__(dibujo, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint); self.d = dibujo; self.setWindowTitle(T_CONTROLES)
        self.setStyleSheet("QWidget#fondo { background: #102019; border: 2px solid #2A9D8F; border-radius: 12px; } QPushButton { color: #e8f3ef; background: #1c3a31; border: 0; border-radius: 8px; padding: 8px 12px; } QPushButton:checked { background: #2A9D8F; }")
        self.setObjectName("fondo"); self.setAttribute(Qt.WA_StyledBackground); lay = QHBoxLayout(self); lay.setContentsMargins(10, 8, 10, 8)
        self.bots = {}
        for clave, texto, accion, marcable in (("lapiz", "Lápiz", lambda: self.d.herramienta_es("lapiz"), True), ("resaltador", "Resaltador", lambda: self.d.herramienta_es("resaltador"), True),
                                               ("deshacer", "Deshacer", self.d.deshacer, False), ("borrar", "Borrar", self.d.borrar, False),
                                               ("clics", "Pasar clics", lambda: self.d.modo(not self.d.dibujando), True), ("salir", "Salir", self.d.close, False)):
            b = QPushButton(texto); b.setCheckable(marcable); b.clicked.connect(lambda _c=False, a=accion: a()); lay.addWidget(b); self.bots[clave] = b
        self.actualizar()
    def actualizar(self):
        for h in HERRAMIENTAS: self.bots[h].setChecked(self.d.herramienta == h and self.d.dibujando)
        self.bots["clics"].setChecked(not self.d.dibujando)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.windowHandle().startSystemMove()

