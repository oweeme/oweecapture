"""Efectos dibujados SOBRE la pantalla mientras se graba o se transmite: ondas en los clics del ratón y las teclas pulsadas en una pastilla abajo. Como se dibujan sobre el escritorio, salen en el vídeo (y en el directo) dentro de la zona grabada.
Ventana a pantalla completa, transparente y que deja pasar todos los clics (como el modo presentación). Solo se repinta mientras hay algo que mostrar: en reposo no gasta CPU."""
import time
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

TITULO = "OweeCapture — efectos"
COLORES = {"izquierdo": "#FFD60A", "derecho": "#FF5C45", "central": "#2A9D8F"}
DURACION_ONDA = 0.6; DURACION_TECLA = 1.8; FUNDIDO = 0.4; MAX_TECLAS = 3

def onda(edad, boton="izquierdo"):
    """(radio, opacidad) de una onda `edad` (0–1) a lo largo de su vida: crece desacelerando y se desvanece. None cuando termina."""
    if edad >= 1: return None
    return 14 + 46 * (1 - (1 - edad) ** 2), 1 - edad

def opacidad_tecla(edad):
    """Opacidad de una tecla mostrada `edad` segundos: plena casi todo el tiempo y desvanece en los últimos FUNDIDO segundos. None cuando termina."""
    if edad >= DURACION_TECLA: return None
    return 1.0 if edad < DURACION_TECLA - FUNDIDO else (DURACION_TECLA - edad) / FUNDIDO

class Superposicion(QWidget):
    def __init__(self, zona=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool); self.zona = zona; self.ondas = []; self.teclas = []
        self.setAttribute(Qt.WA_TranslucentBackground); self.setAttribute(Qt.WA_ShowWithoutActivating); self.setWindowTitle(TITULO)
        self.reloj = QTimer(self); self.reloj.setInterval(16); self.reloj.timeout.connect(self.avanzar)

    def mostrar(self): self.showFullScreen(); self.windowHandle().setFlag(Qt.WindowTransparentForInput, True)          # los clics pasan a las ventanas de debajo

    def clic(self, pos, boton="izquierdo"):
        """Añade una onda en `pos` (QPointF, coordenadas de la pantalla)."""
        self.ondas.append((QPointF(pos), boton, time.time())); self.reloj.start(); self.update()
    def tecla(self, texto):
        self.teclas = (self.teclas + [(texto, time.time())])[-MAX_TECLAS:]; self.reloj.start(); self.update()

    def avanzar(self):
        """Quita lo que ya terminó y para el reloj si no queda nada (sin trabajo en reposo)."""
        ahora = time.time(); self.ondas = [o for o in self.ondas if onda((ahora - o[2]) / DURACION_ONDA)]; self.teclas = [t for t in self.teclas if opacidad_tecla(ahora - t[1]) is not None]
        if not (self.ondas or self.teclas): self.reloj.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setCompositionMode(QPainter.CompositionMode_Source); p.fillRect(self.rect(), Qt.transparent); p.setCompositionMode(QPainter.CompositionMode_SourceOver); ahora = time.time()
        for pos, boton, t0 in self.ondas:
            v = onda((ahora - t0) / DURACION_ONDA)
            if not v: continue
            r, a = v; c = QColor(COLORES.get(boton, "#FFD60A")); relleno = QColor(c); relleno.setAlphaF(0.28 * a); c.setAlphaF(a); p.setBrush(relleno); p.setPen(QPen(c, 5)); p.drawEllipse(pos, r, r)
        area = QRectF(self.zona) if self.zona is not None else QRectF(self.rect()); f = QFont(); f.setBold(True); f.setPixelSize(26); p.setFont(f); fm = p.fontMetrics(); y = area.bottom() - 28
        for texto, t0 in reversed(self.teclas):                                                      # la más reciente abajo; las anteriores suben
            a = opacidad_tecla(ahora - t0)
            if a is None: continue
            w = fm.horizontalAdvance(texto) + 36; h = fm.height() + 14; caja = QRectF(area.center().x() - w / 2, y - h, w, h); fondo = QColor(16, 32, 25, int(225 * a)); p.setPen(Qt.NoPen); p.setBrush(fondo); p.drawRoundedRect(caja, 12, 12)
            borde = QColor("#2A9D8F"); borde.setAlphaF(a); p.setPen(QPen(borde, 2)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(caja, 12, 12); blanco = QColor("white"); blanco.setAlphaF(a); p.setPen(blanco); p.drawText(caja, Qt.AlignCenter, texto); y -= h + 8
