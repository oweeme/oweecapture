"""Ventana principal de Screencapture con Qt6 (PySide6): grabar la pantalla por el portal, burbuja de cámara y modo presentación. Ejecutar: python3 -m screencapture.qtapp"""
import os, signal, subprocess, sys
from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from . import atajos, burbuja, captura, core, kwin, portal, presentacion, selector
from .i18n import _

CALIDADES = [("original", _("Original")), ("buena", _("Buena")), ("media", _("Intermedia (recomendada)")), ("ligera", _("Básica (WhatsApp, Telegram)"))]

class Puente(QObject):
    """Los avisos del hilo que convierte a MP4 vuelven al hilo de la interfaz por una señal de Qt."""
    terminado = Signal(object, object)

class Ventana(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Screencapture"); self.cfg = core.load_cfg(); self.grab = portal.Grabador(); self.burbuja = None; self.dibujo = None
        self.puente = Puente(); self.puente.terminado.connect(self.al_terminar); lay = QVBoxLayout(self); form = QFormLayout()
        self.calidad = QComboBox(); [self.calidad.addItem(t, k) for k, t in CALIDADES]; self.calidad.setCurrentIndex(max(0, self.calidad.findData(self.cfg["quality"])))
        self.sistema = QCheckBox(_("Audio del sistema")); self.sistema.setChecked(self.cfg["audio_system"]); self.mic = QCheckBox(_("Micrófono")); self.mic.setChecked(self.cfg["audio_mic"])
        self.camara = QCheckBox(_("Cámara en burbuja (mientras se graba)")); self.camara.setChecked(self.cfg["camera"]); self.camara.toggled.connect(lambda on: self.cambiar_camara(on and self.grab.corriendo))
        form.addRow(_("Calidad"), self.calidad); form.addRow(self.sistema); form.addRow(self.mic); form.addRow(self.camara); lay.addLayout(form)
        self.boton = QPushButton(_("Grabar")); self.boton.clicked.connect(self.alternar); self.pres = QPushButton(_("Modo presentación")); self.pres.clicked.connect(self.presentacion)
        self.cap = QPushButton(_("Captura de pantalla")); self.cap.clicked.connect(self.captura)
        self.pausa = QPushButton(_("Pausar")); self.pausa.setEnabled(False); self.pausa.clicked.connect(self.pausar)
        self.estado = QLabel(""); self.estado.setWordWrap(True); [lay.addWidget(w) for w in (self.boton, self.pausa, self.cap, self.pres, self.estado)]
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tic)
        kwin.mantener_encima([burbuja_titulo(), presentacion.T_DIBUJO, presentacion.T_CONTROLES, selector.TITULO]); self.selector = None
        self.tray = bandeja(self)
        self.atajos = atajos.Atajos(); self.atajos.activado.connect(self.atajo); self.atajos.fallo.connect(lambda m: self.estado.setText(_("Atajos no disponibles: ") + m)); self.atajos.iniciar()

    def atajo(self, que):
        if que == "captura": self.captura()
        elif que == "grabar": self.alternar()

    def con_selector(self, fondo, al_elegir):
        """Muestra el selector (sobre `fondo` congelado, o sobre el escritorio en vivo si es None) y llama a `al_elegir(zona | None)`; Esc cancela."""
        if self.selector: return
        self.selector = selector.Selector(fondo); self.selector.elegido.connect(lambda z: (setattr(self, "selector", None), al_elegir(z)))
        self.selector.cancelado.connect(lambda: (setattr(self, "selector", None), self.estado.setText(_("Cancelado.")), self.boton.setEnabled(True), self.mostrar())); self.selector.showFullScreen()

    def esconder(self, despues):
        """Oculta esta ventana para que no salga en la captura o la grabación y sigue pasado un instante (el compositor tarda un cuadro en retirarla)."""
        self.was_visible = self.isVisible(); self.hide(); QTimer.singleShot(350, despues)
    def mostrar(self):
        if getattr(self, "was_visible", False): self.show()

    def captura(self): self.esconder(lambda: captura.tomar(self.captura_lista, self.captura_fallo))
    def captura_fallo(self, m): self.mostrar(); self.estado.setText(m)
    def captura_lista(self, img): self.con_selector(img, lambda z: self.captura_guardar(img, z))
    def captura_guardar(self, img, zona):
        self.mostrar()
        try:
            r = zona if zona else QRect(0, 0, img.width(), img.height()); f = img.devicePixelRatio() or 1; r = QRect(int(r.x() * f), int(r.y() * f), int(r.width() * f), int(r.height() * f))
            ruta = captura.guardar(img.copy(r)); self.estado.setText(_("Captura guardada y copiada: ") + ruta)
            subprocess.Popen(["notify-send", "-i", "screencapture", _("Captura guardada"), ruta], stderr=subprocess.DEVNULL) if core.have("notify-send") else None
        except Exception as e: self.estado.setText(str(e))

    def guardar(self):
        self.cfg.update(quality=self.calidad.currentData(), audio_system=self.sistema.isChecked(), audio_mic=self.mic.isChecked(), camera=self.camara.isChecked()); core.save_cfg(self.cfg)

    def cambiar_camara(self, on):
        if on and not self.burbuja:
            ok, motivo = True, ""
            self.burbuja = burbuja.Burbuja(alcerrar=lambda: (setattr(self, "burbuja", None), self.camara.setChecked(False))); self.burbuja.show()
        elif not on and self.burbuja: b, self.burbuja = self.burbuja, None; b.alcerrar = None; b.close()

    def presentacion(self):
        if self.dibujo: return
        self.dibujo = presentacion.Dibujo(alcerrar=lambda: setattr(self, "dibujo", None)); self.dibujo.showFullScreen(); self.dibujo.barra.show()

    def alternar(self):
        if self.grab.corriendo: self.parar()
        else: self.empezar()

    def empezar(self):
        """Pide la zona (o pantalla completa) sobre el escritorio en vivo y empieza a grabar; el mismo atajo vuelve a llamar a alternar() y detiene."""
        self.guardar(); self.boton.setEnabled(False); self.esconder(lambda: self.con_selector(None, self.empezar_en))
    def empezar_en(self, zona):
        self.estado.setText(_("Eligiendo la pantalla…"))              # la ventana sigue oculta: no debe salir en el vídeo
        self.grab.iniciar(self.cfg["quality"], self.cfg["fps"], self.cfg["audio_system"], self.cfg["audio_mic"], self.al_empezar, self.al_fallar, zona, lambda ruta, err: self.puente.terminado.emit(ruta, err))

    def al_empezar(self):
        self.boton.setText(_("Detener")); self.boton.setEnabled(True); self.pausa.setEnabled(True); self.reloj.start(500)
        if self.camara.isChecked(): self.cambiar_camara(True)          # la burbuja vive solo mientras se graba
        self.tic()
    def al_fallar(self, mensaje): self.fin_grabacion(); self.estado.setText(mensaje); self.mostrar()
    def fin_grabacion(self):
        self.reloj.stop(); self.cambiar_camara(False); self.boton.setText(_("Grabar")); self.boton.setEnabled(True); self.pausa.setEnabled(False); self.pausa.setText(_("Pausar")); self.refrescar_bandeja()

    def tic(self):
        s = self.grab.segundos(); t = f"{s // 60:02d}:{s % 60:02d}"; self.estado.setText((_("En pausa… {0}") if self.grab.pausada else _("Grabando… {0}")).replace("{0}", t)); self.refrescar_bandeja(t)

    def pausar(self):
        """Pausa o reanuda; el archivo sigue siendo uno solo."""
        if not self.grab.corriendo: return
        (self.grab.reanudar if self.grab.pausada else self.grab.pausar)(); self.pausa.setText(_("Continuar") if self.grab.pausada else _("Pausar")); self.tic()

    def refrescar_bandeja(self, tiempo=""):
        """El icono de la bandeja muestra el estado (rojo grabando, naranja en pausa) y su menú ofrece detener y pausar sin ventana."""
        g, p = self.grab.corriendo, self.grab.pausada
        self.tray.setIcon(icono_estado("pausa" if p else "grabando") if g else icono()); self.tray.setToolTip(("Screencapture — " + (_("En pausa") if p else _("Grabando")) + " " + tiempo) if g else "Screencapture")
        self.acc["grabar"].setText(_("Detener la grabación") if g else _("Grabar")); self.acc["pausa"].setVisible(g); self.acc["pausa"].setText(_("Continuar") if p else _("Pausar"))

    def parar(self):
        self.reloj.stop(); self.boton.setEnabled(False); self.pausa.setEnabled(False); self.estado.setText(_("Guardando…")); self.grab.detener(lambda ruta, err: self.puente.terminado.emit(ruta, err))
        self.cambiar_camara(False); self.refrescar_bandeja()

    def al_terminar(self, ruta, err):
        self.fin_grabacion(); self.mostrar()          # también llega aquí si la captura se cortó desde el indicador del escritorio
        if err: self.estado.setText(err); return
        self.estado.setText(_("Guardado: ") + ruta)
        subprocess.Popen(["notify-send", "-i", "screencapture", _("Grabación guardada"), ruta], stderr=subprocess.DEVNULL) if core.have("notify-send") else None

    def closeEvent(self, e): e.ignore(); self.hide()            # cerrar la ventana la oculta; los atajos siguen activos y se sale desde la bandeja
    def salir(self):
        self.guardar()
        if self.grab.corriendo: self.grab.detener(lambda ruta, err: None)
        self.cambiar_camara(False); kwin.descargar_todo(); QApplication.quit()

def burbuja_titulo(): return burbuja.TITULO

def icono():
    """Icono del tema si está instalado; si no, el SVG del repositorio."""
    i = QIcon.fromTheme("screencapture")
    return i if not i.isNull() else QIcon(os.path.join(os.path.dirname(__file__), "..", "..", "data", "icons", "screencapture.svg"))

def icono_estado(estado):
    """Círculo rojo (grabando) o naranja con barras (en pausa), dibujado a mano para no depender del tema de iconos."""
    pm = QPixmap(64, 64); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
    p.setBrush(QColor("#F4A261" if estado == "pausa" else "#E63946")); p.drawEllipse(6, 6, 52, 52)
    if estado == "pausa": p.setBrush(Qt.white); p.drawRect(21, 20, 8, 24); p.drawRect(35, 20, 8, 24)
    p.end(); return QIcon(pm)

def bandeja(v):
    """Icono en la bandeja (StatusNotifier en KDE): captura, grabar o detener, pausar, abrir la ventana y salir, sin necesidad de ventana."""
    t = QSystemTrayIcon(icono(), v); m = QMenu(); v.acc = {}
    v.acc["captura"] = m.addAction(_("Captura de pantalla"), v.captura); v.acc["grabar"] = m.addAction(_("Grabar"), v.alternar)
    v.acc["pausa"] = m.addAction(_("Pausar"), v.pausar); v.acc["pausa"].setVisible(False)
    m.addAction(_("Abrir ventana"), v.show); m.addSeparator(); m.addAction(_("Salir"), v.salir)
    t.setContextMenu(m); t.setToolTip("Screencapture"); t.activated.connect(lambda r: (m.popup(QCursor.pos()) if v.grab.corriendo else v.show()) if r == QSystemTrayIcon.Trigger else None); t.show(); return t

def main():
    signal.signal(signal.SIGINT, lambda *a: QApplication.quit())                  # Ctrl+C en la terminal cierra la aplicación
    app = QApplication(sys.argv); app.setApplicationName("screencapture"); app.setDesktopFileName("screencapture"); app.setQuitOnLastWindowClosed(False); v = Ventana()
    pulso = QTimer(); pulso.start(300); pulso.timeout.connect(lambda: None)         # deja que Python atienda las señales mientras Qt espera
    if "--segundo-plano" not in sys.argv: v.show()          # con --segundo-plano solo atiende a los atajos
    sys.exit(app.exec())

if __name__ == "__main__": main()
