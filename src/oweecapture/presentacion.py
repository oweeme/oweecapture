"""Modo presentación: dibujar sobre la pantalla con una barra de iconos (PySide6): lápiz, resaltador, flecha, marco rectangular, elipse y texto, con colores y tres grosores, deshacer, borrar y «pasar clics» (el escritorio responde como siempre y los dibujos siguen visibles).
Atajos en la ventana de dibujo: 1 lápiz · 2 resaltador · 3 flecha · 4 marco · 5 elipse · 6 texto · Ctrl+Z deshacer · C borrar todo · Espacio dibujar/pasar clics · Esc salir.
La barra de controles es hija de la ventana de dibujo (KWin la mantiene encima). Los iconos se dibujan a mano con QPainter: no dependen del tema de iconos del escritorio."""
import math
from PySide6.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QToolButton, QWidget

from .i18n import _

T_DIBUJO, T_CONTROLES = "OweeCapture — dibujo", "OweeCapture — controles"
HERRAMIENTAS = [("lapiz", "Lápiz"), ("resaltador", "Resaltador"), ("flecha", "Flecha"), ("marco", "Marco (rectángulo)"), ("elipse", "Elipse"), ("texto", "Texto")]
COLORES = ["#E63946", "#FFD60A", "#2A9D8F", "#2A7FFF", "#FFFFFF", "#111111"]
GROSORES = [3, 6, 10]                          # trazo en píxeles (el resaltador es 4 veces más ancho; el texto sube de 18 a 28 y 42 px)
TEXTO_PX = [18, 28, 42]

def cabeza_de_flecha(a, b, ancho):
    """Triángulo de la punta de una flecha de `a` hacia `b` (con `ancho` de trazo): su largo crece con el grosor para que se vea en los tres tamaños."""
    largo = max(16.0, ancho * 4.5); ang = math.atan2(b.y() - a.y(), b.x() - a.x()); abre = math.radians(26)
    return QPolygonF([b, QPointF(b.x() - largo * math.cos(ang - abre), b.y() - largo * math.sin(ang - abre)), QPointF(b.x() - largo * math.cos(ang + abre), b.y() - largo * math.sin(ang + abre))])

def pintar_elemento(p, e):
    """Dibuja un elemento (un dict con `t` = tipo, `c` = color, `w` = grosor y los datos de su tipo) con el pintor `p`."""
    t, color, w = e["t"], QColor(e["c"]), e["w"]; p.setBrush(Qt.NoBrush)
    if t in ("lapiz", "resaltador"):
        if t == "resaltador": color = QColor(color.red(), color.green(), color.blue(), 110); w *= 4
        p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.drawPath(e["ruta"])
    elif t == "flecha":
        p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap)); cab = cabeza_de_flecha(e["a"], e["b"], w); base = (cab[1] + cab[2]) / 2; p.drawLine(QLineF(e["a"], base)); p.setBrush(color); p.setPen(QPen(color, 1)); p.drawPolygon(cab)
    elif t in ("marco", "elipse"):
        p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); r = QRectF(e["a"], e["b"]).normalized()
        p.drawRoundedRect(r, 6, 6) if t == "marco" else p.drawEllipse(r)
    elif t == "texto":
        f = QFont(); f.setBold(True); f.setPixelSize(TEXTO_PX[min(GROSORES.index(w) if w in GROSORES else 1, 2)]); ruta = QPainterPath(); ruta.addText(e["a"], f, e["texto"])
        p.strokePath(ruta, QPen(QColor(0, 0, 0, 190), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.fillPath(ruta, color)            # contorno oscuro: se lee sobre cualquier fondo

class Dibujo(QWidget):
    def __init__(self, alcerrar=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint); self.alcerrar = alcerrar
        self.setAttribute(Qt.WA_TranslucentBackground); self.setWindowTitle(T_DIBUJO); self.setMouseTracking(True)
        self.trazos = []; self.actual = None; self.herramienta = "lapiz"; self.color = COLORES[0]; self.grosor = GROSORES[1]; self.puntero = None; self.dibujando = True; self.editor = None
        self.barra = Controles(self)
        self.setCursor(Qt.CrossCursor)

    def modo(self, dibujar):
        """Dibujar: la ventana recibe el ratón. Pasar clics: la región de entrada queda vacía y el escritorio responde como siempre (los dibujos siguen visibles)."""
        self.cerrar_editor(); self.dibujando = dibujar; self.windowHandle().setFlag(Qt.WindowTransparentForInput, not dibujar); self.puntero = None if not dibujar else self.puntero
        self.barra.actualizar(); self.update()

    def closeEvent(self, e): self.barra.close(); self.alcerrar and self.alcerrar()
    def herramienta_es(self, h): self.cerrar_editor(); self.herramienta = h; self.modo(True); self.barra.actualizar()
    def color_es(self, c): self.color = c; self.barra.actualizar()
    def grosor_es(self, g): self.grosor = g; self.barra.actualizar()
    def deshacer(self): self.cerrar_editor(); self.trazos and self.trazos.pop(); self.update()
    def borrar(self): self.cerrar_editor(); self.trazos.clear(); self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for e in self.trazos + ([self.actual] if self.actual else []): pintar_elemento(p, e)
        if self.puntero and self.dibujando and self.herramienta not in ("texto",):                  # halo alrededor del puntero (solo se conoce su posición mientras se dibuja)
            p.setPen(QPen(QColor(255, 214, 10, 200), 3)); p.setBrush(QColor(255, 214, 10, 45)); p.drawEllipse(self.puntero, 26, 26)

    # --- texto: un cuadro de edición sobre la pantalla; Intro lo fija y Esc lo cancela ---
    def abrir_editor(self, pos):
        self.cerrar_editor(); px = TEXTO_PX[GROSORES.index(self.grosor)]; ed = QLineEdit(self); ed.setPlaceholderText(_("Escribe y pulsa Intro")); ed.setFixedWidth(340)
        ed.setStyleSheet(f"QLineEdit {{ background: rgba(16,32,25,230); color: {self.color}; border: 2px solid #2A9D8F; border-radius: 8px; padding: 4px 8px; font-size: {px}px; font-weight: bold; }}")
        ed.move(int(pos.x()), int(pos.y() - ed.sizeHint().height() / 2)); ed.returnPressed.connect(lambda: self.fijar_texto(pos)); ed.show(); ed.setFocus(); self.editor = ed
    def fijar_texto(self, pos):
        ed = self.editor
        if ed is None: return
        texto = ed.text().strip(); self.cerrar_editor()
        if texto: self.trazos.append({"t": "texto", "c": self.color, "w": self.grosor, "a": QPointF(pos.x() + 4, pos.y() + TEXTO_PX[GROSORES.index(self.grosor)] * 0.35), "texto": texto}); self.update()
    def cerrar_editor(self):
        ed, self.editor = self.editor, None
        if ed is not None: ed.hide(); ed.deleteLater()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton: return
        pos = e.position()
        if self.herramienta == "texto": self.abrir_editor(pos); return
        self.cerrar_editor(); base = {"t": self.herramienta, "c": self.color, "w": self.grosor}
        if self.herramienta in ("lapiz", "resaltador"): ruta = QPainterPath(pos); ruta.lineTo(pos + QPointF(0.01, 0)); self.actual = {**base, "ruta": ruta}
        else: self.actual = {**base, "a": QPointF(pos), "b": QPointF(pos)}
        self.update()
    def mouseMoveEvent(self, e):
        self.puntero = e.position()
        if self.actual:
            if "ruta" in self.actual: self.actual["ruta"].lineTo(e.position())
            else: self.actual["b"] = QPointF(e.position())
        self.update()
    def mouseReleaseEvent(self, e):
        if self.actual:
            a = self.actual; self.actual = None
            if "ruta" in a or QLineF(a["a"], a["b"]).length() >= 4: self.trazos.append(a)          # un clic suelto no deja una figura de tamaño cero
            self.update()
    def leaveEvent(self, _e): self.puntero = None; self.update()
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape: self.close() if self.editor is None else self.cerrar_editor()
        elif Qt.Key_1 <= k <= Qt.Key_6: self.herramienta_es(HERRAMIENTAS[k - Qt.Key_1][0])
        elif k == Qt.Key_C: self.borrar()
        elif k == Qt.Key_Z and e.modifiers() & Qt.ControlModifier: self.deshacer()
        elif k == Qt.Key_Space: self.modo(not self.dibujando)

def icono(nombre, color="#e8f3ef", lado=28):
    """Icono de la barra, dibujado a mano (sin depender del tema de iconos)."""
    pm = QPixmap(lado, lado); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing); c = QColor(color); pen = QPen(c, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin); p.setPen(pen); p.setBrush(Qt.NoBrush); s = lado / 28
    def L(x1, y1, x2, y2): p.drawLine(QLineF(x1 * s, y1 * s, x2 * s, y2 * s))
    if nombre == "lapiz": L(6, 22, 20, 8); L(20, 8, 23, 11); L(23, 11, 9, 25); L(6, 22, 5, 26); L(5, 26, 9, 25)
    elif nombre == "resaltador": p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 150), 9 * s, Qt.SolidLine, Qt.FlatCap)); L(7, 20, 21, 20); p.setPen(pen); L(5, 10, 16, 6); L(16, 6, 22, 12); L(22, 12, 14, 16); L(14, 16, 5, 10)
    elif nombre == "flecha": L(5, 23, 21, 7); p.setBrush(c); p.drawPolygon(cabeza_de_flecha(QPointF(5 * s, 23 * s), QPointF(23 * s, 5 * s), 2.4))
    elif nombre == "marco": p.drawRoundedRect(QRectF(4 * s, 7 * s, 20 * s, 15 * s), 3 * s, 3 * s)
    elif nombre == "elipse": p.drawEllipse(QRectF(4 * s, 7 * s, 20 * s, 15 * s))
    elif nombre == "texto": f = QFont(); f.setBold(True); f.setPixelSize(int(22 * s)); p.setFont(f); p.drawText(QRectF(0, 0, lado, lado), Qt.AlignCenter, "T")
    elif nombre == "deshacer": ruta = QPainterPath(QPointF(9 * s, 11 * s)); ruta.cubicTo(QPointF(24 * s, 5 * s), QPointF(26 * s, 22 * s), QPointF(12 * s, 22 * s)); p.drawPath(ruta); L(9, 11, 9, 5); L(9, 11, 15, 11)
    elif nombre == "borrar": L(7, 9, 21, 9); L(11, 9, 11, 6); L(11, 6, 17, 6); L(17, 6, 17, 9); p.drawRoundedRect(QRectF(9 * s, 9 * s, 10 * s, 14 * s), 2 * s, 2 * s); L(12.5, 12, 12.5, 20); L(15.5, 12, 15.5, 20)
    elif nombre == "clics": p.setBrush(c); p.drawPolygon(QPolygonF([QPointF(8 * s, 4 * s), QPointF(8 * s, 21 * s), QPointF(13 * s, 16.5 * s), QPointF(17 * s, 24 * s), QPointF(20 * s, 22.5 * s), QPointF(16 * s, 15 * s), QPointF(22 * s, 15 * s)]))
    elif nombre == "salir": L(7, 7, 21, 21); L(21, 7, 7, 21)
    elif nombre.startswith("g"): r = {"g0": 2.5, "g1": 4.5, "g2": 7.0}[nombre] * s; p.setBrush(c); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(lado / 2, lado / 2), r, r)
    elif nombre.startswith("#"): p.setBrush(QColor(nombre)); p.setPen(QPen(QColor("#e8f3ef"), 1.6)); p.drawEllipse(QRectF(5 * s, 5 * s, 18 * s, 18 * s))
    p.end(); return QIcon(pm)

class Controles(QWidget):
    """Barra de iconos: ventana propia, hija (transitoria) de la de dibujo, así KWin la mantiene siempre por encima de ella y sigue recibiendo clics en modo «pasar clics». Se arrastra desde cualquier parte vacía."""
    def __init__(self, dibujo):
        super().__init__(dibujo, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint); self.d = dibujo; self.setWindowTitle(T_CONTROLES)
        self.setStyleSheet("QWidget#fondo { background: #102019; border: 2px solid #2A9D8F; border-radius: 12px; } QToolButton { background: #1c3a31; border: 2px solid transparent; border-radius: 8px; padding: 3px; } QToolButton:hover { background: #24493d; } QToolButton:checked { background: #2A9D8F; } QFrame#sep { background: #2A9D8F; }")
        self.setObjectName("fondo"); self.setAttribute(Qt.WA_StyledBackground); lay = QHBoxLayout(self); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(5); self.bots = {}
        def boton(clave, ico, tip, accion, marcable=False):
            b = QToolButton(); b.setIcon(ico); b.setIconSize(QSize(28, 28)); b.setToolTip(tip); b.setCheckable(marcable); b.setAutoRaise(False); b.clicked.connect(lambda _c=False, a=accion: a()); lay.addWidget(b); self.bots[clave] = b
        def separador(): f = QFrame(); f.setObjectName("sep"); f.setFixedSize(2, 30); lay.addWidget(f)
        for i, (clave, nombre) in enumerate(HERRAMIENTAS): boton(clave, icono(clave), f"{_(nombre)}  ({i + 1})", lambda c=clave: self.d.herramienta_es(c), True)
        separador()
        for c in COLORES: boton(c, icono(c), _("Color"), lambda c=c: self.d.color_es(c), True)
        separador()
        for i, g in enumerate(GROSORES): boton(f"g{i}", icono(f"g{i}"), _("Grosor"), lambda g=g: self.d.grosor_es(g), True)
        separador()
        boton("deshacer", icono("deshacer"), _("Deshacer  (Ctrl+Z)"), self.d.deshacer); boton("borrar", icono("borrar"), _("Borrar todo  (C)"), self.d.borrar)
        boton("clics", icono("clics"), _("Pasar clics: usar el escritorio sin salir (Espacio)"), lambda: self.d.modo(not self.d.dibujando), True); boton("salir", icono("salir", "#ff8a8a"), _("Salir  (Esc)"), self.d.close)
        self.actualizar()
    def actualizar(self):
        for h, _n in HERRAMIENTAS: self.bots[h].setChecked(self.d.herramienta == h and self.d.dibujando)
        for c in COLORES: self.bots[c].setChecked(self.d.color == c)
        for i, g in enumerate(GROSORES): self.bots[f"g{i}"].setChecked(self.d.grosor == g)
        self.bots["clics"].setChecked(not self.d.dibujando)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.windowHandle().startSystemMove()
