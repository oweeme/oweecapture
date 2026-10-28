"""Genera el logo de OweeCapture: data/icons/oweecapture.svg y los PNG (16 a 512 px). Una koi (la mascota de Owee) nada dentro de una lente circular; su ojo es el punto rojo de «grabar».
La geometría está UNA vez aquí (en un lienzo de 512×512) y de ella salen el SVG (texto) y los PNG (QPainter, sin necesitar QtSvg ni rsvg). Uso: python3 tools/generar_logo.py"""
import os, sys
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "icons")
VERDE_1, VERDE_2 = "#2B9482", "#145247"       # fondo del círculo: de arriba a la izquierda a abajo a la derecha
CREMA, CORAL, OSCURO, ROJO = "#FFEDB3", "#FF5C45", "#3A2B2A", "#FF3B30"

# Cada forma: lista de comandos ("M", x, y) · ("C", x1, y1, x2, y2, x, y) · ("Z",) en el lienzo de 512×512
CUERPO = [("M", 88, 368), ("C", 112, 432, 238, 440, 322, 378), ("C", 392, 326, 392, 232, 342, 168), ("C", 350, 228, 322, 290, 252, 302), ("C", 188, 312, 114, 300, 88, 368), ("Z",)]
COLA = [("M", 340, 172), ("C", 318, 148, 276, 118, 272, 72), ("C", 294, 84, 308, 94, 316, 108), ("C", 312, 84, 318, 62, 334, 46), ("C", 346, 64, 352, 84, 358, 104), ("C", 368, 92, 384, 86, 396, 86), ("C", 402, 124, 380, 162, 352, 190), ("Z",)]
ALETA = [("M", 322, 382), ("C", 358, 346, 412, 334, 444, 352), ("C", 438, 374, 410, 388, 384, 384), ("C", 366, 392, 344, 392, 322, 382), ("Z",)]
MANCHA_CORAL = [("M", 142, 316), ("C", 190, 302, 238, 300, 272, 284), ("C", 282, 306, 256, 326, 226, 332), ("C", 196, 338, 156, 336, 142, 316), ("Z",)]
MANCHA_OSCURA_1 = [("M", 262, 340), ("C", 290, 330, 322, 344, 320, 372), ("C", 316, 396, 282, 402, 262, 392), ("C", 246, 382, 244, 350, 262, 340), ("Z",)]
MANCHA_OSCURA_2 = [("M", 356, 246), ("C", 376, 252, 384, 290, 372, 328), ("C", 358, 342, 338, 330, 336, 308), ("C", 346, 296, 346, 270, 356, 246), ("Z",)]
OJO = (120, 372, 15); BRILLO = (113, 365, 4.5)
BURBUJAS = [(84, 336, 7), (100, 304, 5), (82, 278, 3.5)]          # suben de la boca de la koi
REFLEJO = [("M", 96, 150), ("C", 112, 118, 138, 94, 170, 80)]          # destello de lente en el borde de arriba a la izquierda

def _d(cmds): return " ".join(" ".join(str(x) for x in c) for c in cmds)           # path de SVG
def _ruta(cmds):
    r = QPainterPath()
    for c in cmds:
        if c[0] == "M": r.moveTo(c[1], c[2])
        elif c[0] == "C": r.cubicTo(c[1], c[2], c[3], c[4], c[5], c[6])
        elif c[0] == "Z": r.closeSubpath()
    return r

def svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <title>OweeCapture</title>
  <defs>
    <linearGradient id="fondo" x1="0.15" y1="0.1" x2="0.85" y2="0.95"><stop offset="0" stop-color="{VERDE_1}"/><stop offset="1" stop-color="{VERDE_2}"/></linearGradient>
    <clipPath id="cuerpo"><path d="{_d(CUERPO)}"/></clipPath>
  </defs>
  <circle cx="256" cy="256" r="248" fill="url(#fondo)"/>
  <circle cx="256" cy="256" r="226" fill="none" stroke="{CREMA}" stroke-opacity="0.35" stroke-width="5"/>
  <path d="{_d(COLA)}" fill="{CORAL}"/>
  <path d="{_d(ALETA)}" fill="{CORAL}"/>
  <path d="{_d(CUERPO)}" fill="{CREMA}"/>
  <g clip-path="url(#cuerpo)"><path d="{_d(MANCHA_CORAL)}" fill="{CORAL}"/><path d="{_d(MANCHA_OSCURA_1)}" fill="{OSCURO}"/><path d="{_d(MANCHA_OSCURA_2)}" fill="{OSCURO}"/></g>
  <path d="{_d(REFLEJO)}" fill="none" stroke="#fff" stroke-opacity="0.38" stroke-width="7" stroke-linecap="round"/>
  {"".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{CREMA}" fill-opacity="0.45"/>' for x, y, r in BURBUJAS)}
  <circle cx="{OJO[0]}" cy="{OJO[1]}" r="{OJO[2]}" fill="{ROJO}"/><circle cx="{BRILLO[0]}" cy="{BRILLO[1]}" r="{BRILLO[2]}" fill="#fff"/>
</svg>
"""

def pintar(lado):
    img = QImage(lado, lado, QImage.Format_ARGB32); img.fill(Qt.transparent); p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); p.scale(lado / 512, lado / 512); p.setPen(Qt.NoPen)
    g = QLinearGradient(QPointF(512 * .15, 512 * .1), QPointF(512 * .85, 512 * .95)); g.setColorAt(0, QColor(VERDE_1)); g.setColorAt(1, QColor(VERDE_2)); p.setBrush(QBrush(g)); p.drawEllipse(QRectF(8, 8, 496, 496))
    anillo = QColor(CREMA); anillo.setAlphaF(0.35); p.setPen(QPen(anillo, 5)); p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(30, 30, 452, 452)); p.setPen(Qt.NoPen)
    for cmds, color in ((COLA, CORAL), (ALETA, CORAL), (CUERPO, CREMA)): p.setBrush(QColor(color)); p.drawPath(_ruta(cmds))
    p.save(); p.setClipPath(_ruta(CUERPO))
    for cmds, color in ((MANCHA_CORAL, CORAL), (MANCHA_OSCURA_1, OSCURO), (MANCHA_OSCURA_2, OSCURO)): p.setBrush(QColor(color)); p.drawPath(_ruta(cmds))
    p.restore(); cb = QColor(CREMA); cb.setAlphaF(0.45); p.setBrush(cb)
    for x, y, r in BURBUJAS: p.drawEllipse(QPointF(x, y), r, r)
    rf = QColor('#ffffff'); rf.setAlphaF(0.38); p.setPen(QPen(rf, 7, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush); p.drawPath(_ruta(REFLEJO)); p.setPen(Qt.NoPen); p.setBrush(QColor(ROJO)); p.drawEllipse(QPointF(OJO[0], OJO[1]), OJO[2], OJO[2]); p.setBrush(QColor("#ffffff")); p.drawEllipse(QPointF(BRILLO[0], BRILLO[1]), BRILLO[2], BRILLO[2]); p.end(); return img

if __name__ == "__main__":
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    os.makedirs(RAIZ, exist_ok=True); open(os.path.join(RAIZ, "oweecapture.svg"), "w").write(svg())
    for n in (16, 24, 32, 48, 64, 128, 256, 512): pintar(n if n >= 48 else n * 4).scaled(n, n, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save(os.path.join(RAIZ, f"oweecapture-{n}.png")) if n < 48 else pintar(n).save(os.path.join(RAIZ, f"oweecapture-{n}.png"))
    print("logo generado en", os.path.abspath(RAIZ))
