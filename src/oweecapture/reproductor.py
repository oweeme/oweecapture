"""Reproductor de vídeo mínimo para la vista previa (PySide6 + GStreamer): los fotogramas salen de un `appsink` y se dibujan en una etiqueta, igual que la burbuja de cámara, así que no hace falta QtMultimedia (que no siempre está instalado).
Reproducir/pausar, barra de posición con arrastre, saltar a un instante, reproducir solo un tramo y una guía opcional de recorte vertical 9:16 dibujada encima."""
import os
import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from . import herramientas

class Reproductor(QWidget):
    posicion = Signal(float)           # segundo actual (cada vez que cambia)

    def __init__(self, silencioso=False, padre=None):
        super().__init__(padre); Gst.init(None); self.silencioso = silencioso; self.pipe = None; self.sal = None; self.dur = 0.0; self.pos = 0.0; self.imagen = None; self.hasta = None; self.arrastrando = False; self.guia = None; self.reproduciendo = False
        self.pantalla = QLabel(); self.pantalla.setMinimumSize(360, 203); self.pantalla.setAlignment(Qt.AlignCenter); self.pantalla.setStyleSheet("background: #000;")
        self.boton = QPushButton("▶"); self.boton.setFixedWidth(40); self.boton.clicked.connect(self.alternar); self.barra = QSlider(Qt.Horizontal); self.barra.setRange(0, 1000); self.tiempo = QLabel("0:00 / 0:00"); self.tiempo.setMinimumWidth(90)
        self.barra.sliderPressed.connect(lambda: setattr(self, "arrastrando", True)); self.barra.sliderReleased.connect(self.soltado); self.barra.sliderMoved.connect(lambda v: self.ir_a(v / 1000 * self.dur))
        fila = QHBoxLayout(); [fila.addWidget(x) for x in (self.boton, self.barra, self.tiempo)]; lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.pantalla, 1); lay.addLayout(fila)
        self.reloj = QTimer(self); self.reloj.setInterval(33); self.reloj.timeout.connect(self.tic); self.habilitar(False)

    def habilitar(self, si): self.boton.setEnabled(si); self.barra.setEnabled(si)

    def cargar(self, ruta):
        """Abre `ruta` en pausa, mostrando el primer fotograma. Una ruta vacía o inexistente deja el reproductor vacío."""
        self.detener(); self.dur = 0.0; self.pos = 0.0; self.imagen = None; self.hasta = None; self.pantalla.clear(); self.actualizar_tiempo(); self.barra.setValue(0)
        if not (ruta and os.path.isfile(ruta)): self.habilitar(False); return
        self.pipe = Gst.ElementFactory.make("playbin", None); self.pipe.set_property("uri", GLib.filename_to_uri(os.path.abspath(ruta), None))
        bin_ = Gst.parse_bin_from_description("videoconvert ! video/x-raw,format=BGRx ! appsink name=sal emit-signals=false max-buffers=1 drop=true sync=true", True); self.pipe.set_property("video-sink", bin_); self.sal = bin_.get_by_name("sal")
        if self.silencioso: mudo = Gst.ElementFactory.make("fakesink", None); mudo.set_property("sync", True); self.pipe.set_property("audio-sink", mudo)          # sin salida de audio (pruebas); con sync para que marque el ritmo como una tarjeta de sonido
        self.pipe.set_state(Gst.State.PAUSED); self.reproduciendo = False; self.boton.setText("▶"); self.habilitar(True); self.reloj.start()

    def detener(self):
        self.reloj.stop()
        if self.pipe is not None: self.pipe.set_state(Gst.State.NULL); self.pipe = None; self.sal = None
        self.reproduciendo = False; self.boton.setText("▶")

    def alternar(self):
        if self.pipe is None: return
        if self.reproduciendo: self.pausar()
        else:
            if self.dur and self.pos >= self.dur - 0.2: self.ir_a(0.0)
            self.reproducir()

    def reproducir(self):
        if self.pipe is not None: self.pipe.set_state(Gst.State.PLAYING); self.reproduciendo = True; self.boton.setText("⏸")
    def pausar(self):
        if self.pipe is not None: self.pipe.set_state(Gst.State.PAUSED); self.reproduciendo = False; self.boton.setText("▶"); self.hasta = None

    def ir_a(self, t):
        """Salta al segundo `t` (con precisión de fotograma) y deja ese fotograma a la vista."""
        if self.pipe is None: return
        t = max(0.0, min(t, self.dur or t)); self.pipe.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, int(t * Gst.SECOND)); self.pos = t; self.actualizar_tiempo()

    def ver_tramo(self, inicio, fin):
        """Reproduce de `inicio` a `fin` y se detiene sola al llegar."""
        if self.pipe is None or fin <= inicio: return
        self.ir_a(inicio); self.hasta = fin; self.reproducir()

    def soltado(self): self.arrastrando = False; self.ir_a(self.barra.value() / 1000 * self.dur)

    def segundos(self):
        """Posición actual (s): la que informa GStreamer si hay, y si no la última conocida."""
        if self.pipe is not None:
            ok, p = self.pipe.query_position(Gst.Format.TIME)
            if ok: self.pos = p / Gst.SECOND
        return self.pos

    def tic(self):
        """Cada 33 ms: toma el fotograma nuevo (si hay), actualiza la barra y el tiempo, y para si se llegó al final del tramo."""
        if self.pipe is None: return
        if not self.dur:
            ok, d = self.pipe.query_duration(Gst.Format.TIME)
            if ok and d > 0: self.dur = d / Gst.SECOND; self.actualizar_tiempo()
        muestra = (self.sal.emit("try-pull-preroll", 0) if not self.reproduciendo else None) or self.sal.emit("try-pull-sample", 0)          # en pausa el fotograma está como «preroll» (y pedir antes la muestra lo gastaría)
        if muestra:
            st = muestra.get_caps().get_structure(0); w, h = st.get_value("width"), st.get_value("height"); ok, info = muestra.get_buffer().map(Gst.MapFlags.READ)
            if ok: self.imagen = QImage(bytes(info.data), w, h, w * 4, QImage.Format_RGB32).copy(); muestra.get_buffer().unmap(info); self.pintar()
        t = self.segundos()
        if not self.arrastrando and self.dur: self.barra.setValue(int(t / self.dur * 1000))
        self.actualizar_tiempo(); self.posicion.emit(t)
        if self.hasta is not None and t >= self.hasta: self.pausar()
        elif self.reproduciendo and self.dur and t >= self.dur - 0.05: self.pausar()

    def actualizar_tiempo(self): self.tiempo.setText(f"{herramientas.a_texto(self.pos)} / {herramientas.a_texto(self.dur)}")

    def poner_guia(self, posicion):
        """Dibuja encima la ventana vertical 9:16 que quedaría con `posicion` (0 = izquierda, 1 = derecha); None la quita."""
        self.guia = posicion; self.pintar()

    def resizeEvent(self, e): super().resizeEvent(e); self.pintar()

    def pintar(self):
        if self.imagen is None: return
        pm = QPixmap.fromImage(self.imagen).scaled(self.pantalla.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if self.guia is not None and pm.width() * 16 > pm.height() * 9:                                  # solo si el vídeo es más ancho que 9:16 (si no, no hay nada que recortar)
            p = QPainter(pm); w = pm.height() * 9 / 16; x = max(0.0, min(1.0, self.guia)) * (pm.width() - w); sombra = QColor(0, 0, 0, 150)
            p.fillRect(QRectF(0, 0, x, pm.height()), sombra); p.fillRect(QRectF(x + w, 0, pm.width() - x - w, pm.height()), sombra); p.setPen(QPen(QColor("#2A9D8F"), 2)); p.drawRect(QRectF(x, 1, w, pm.height() - 2)); p.end()
        self.pantalla.setPixmap(pm)

    def closeEvent(self, e): self.detener(); super().closeEvent(e)
