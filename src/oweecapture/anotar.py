"""Anotar una captura antes de guardarla: la imagen queda congelada a pantalla completa, la zona elegida se ve clara y el resto oscurecido, y se dibuja encima con las mismas herramientas del modo presentación (lápiz, resaltador, flecha, marco, elipse, texto).
Intro o ✓ acepta (el resultado es la zona recortada con lo dibujado) y Esc o ✕ cancela."""
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .presentacion import Dibujo, pintar_elemento

VERDE = QColor("#2A9D8F")

def componer(img, zona, trazos):
    """Recorta `zona` (coordenadas lógicas de la pantalla; None = toda la imagen) de `img` y pinta encima los `trazos`. Respeta la escala de pantalla (HiDPI) de la imagen."""
    f = img.devicePixelRatio() or 1; z = zona if zona else QRect(0, 0, round(img.width() / f), round(img.height() / f))
    r = QRect(round(z.x() * f), round(z.y() * f), round(z.width() * f), round(z.height() * f)).intersected(img.rect()); sal = img.copy(r); sal.setDevicePixelRatio(1.0)
    p = QPainter(sal); p.setRenderHint(QPainter.Antialiasing); p.scale(f, f); p.translate(-r.x() / f, -r.y() / f)
    for t in trazos: pintar_elemento(p, t, img)
    p.end(); return sal

class Anotador(Dibujo):
    """`listo(QImage | None)` se llama una sola vez: la imagen final si se aceptó, None si se canceló."""
    def __init__(self, fondo, zona, listo):
        super().__init__(incrustada=True); self.fondo = fondo; self.zona = zona; self.listo = listo; self.terminado = False
        self.setAttribute(Qt.WA_TranslucentBackground, False); self.setFocusPolicy(Qt.StrongFocus); self.barra.agregar_aceptar(self.aceptar); self.setCursor(Qt.CrossCursor)

    def aceptar(self):
        if self.terminado: return
        self.cerrar_editor(); self.terminado = True; res = componer(self.fondo, self.zona, self.trazos); self.close(); self.listo(res)

    def closeEvent(self, e):
        if not self.terminado: self.terminado = True; self.listo(None)
        super().closeEvent(e)

    def colocar_barra(self):
        """La barra va justo debajo de la zona (o encima si no cabe) y se puede arrastrar; si ya se movió a mano no se vuelve a colocar."""
        b = self.barra
        if b.movida: return
        b.adjustSize(); z = self.zona or self.rect(); x = max(8, min(self.width() - b.width() - 8, z.center().x() - b.width() // 2))
        y = z.bottom() + 12 if z.bottom() + 12 + b.height() < self.height() else (z.top() - b.height() - 12 if z.top() - b.height() - 12 >= 0 else self.height() - b.height() - 12)
        b.move(QPoint(x, y)); b.raise_()
    def showEvent(self, e): super().showEvent(e); self.colocar_barra(); self.barra.show(); self.setFocus()
    def resizeEvent(self, e): super().resizeEvent(e); self.colocar_barra()

    def paintEvent(self, e):
        p = QPainter(self); p.drawImage(self.rect(), self.fondo); z = self.zona
        if z:
            sombra = QColor(0, 0, 0, 120)
            for r in (QRect(0, 0, self.width(), z.top()), QRect(0, z.bottom() + 1, self.width(), self.height()), QRect(0, z.top(), z.left(), z.height()), QRect(z.right() + 1, z.top(), self.width(), z.height())): p.fillRect(r, sombra)
            p.setPen(QPen(VERDE, 2)); p.drawRect(z)
        p.end(); super().paintEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.editor is None: self.aceptar()
        else: super().keyPressEvent(e)
