"""Ventana principal de Screencapture con Qt6 (PySide6): grabar la pantalla por el portal, burbuja de cámara y modo presentación. Ejecutar: python3 -m screencapture.qtapp"""
import subprocess, sys
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from . import burbuja, core, kwin, portal, presentacion
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
        self.camara = QCheckBox(_("Cámara en burbuja")); self.camara.setChecked(self.cfg["camera"]); self.camara.toggled.connect(self.cambiar_camara)
        form.addRow(_("Calidad"), self.calidad); form.addRow(self.sistema); form.addRow(self.mic); form.addRow(self.camara); lay.addLayout(form)
        self.boton = QPushButton(_("Grabar")); self.boton.clicked.connect(self.alternar); self.pres = QPushButton(_("Modo presentación")); self.pres.clicked.connect(self.presentacion)
        self.estado = QLabel(""); self.estado.setWordWrap(True); [lay.addWidget(w) for w in (self.boton, self.pres, self.estado)]
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tic)
        kwin.mantener_encima([burbuja_titulo(), presentacion.T_DIBUJO, presentacion.T_CONTROLES])
        if self.camara.isChecked(): self.cambiar_camara(True)

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
        self.guardar(); self.boton.setEnabled(False); self.estado.setText(_("Eligiendo la pantalla…"))
        self.grab.iniciar(self.cfg["quality"], self.cfg["fps"], self.cfg["audio_system"], self.cfg["audio_mic"], self.al_empezar, self.al_fallar)

    def al_empezar(self): self.boton.setText(_("Detener")); self.boton.setEnabled(True); self.reloj.start(500); self.tic()
    def al_fallar(self, mensaje): self.reloj.stop(); self.boton.setText(_("Grabar")); self.boton.setEnabled(True); self.estado.setText(mensaje)
    def tic(self): s = self.grab.segundos(); self.estado.setText(_("Grabando… {0}", f"{s // 60:02d}:{s % 60:02d}"))

    def parar(self):
        self.reloj.stop(); self.boton.setEnabled(False); self.estado.setText(_("Guardando…")); self.grab.detener(lambda ruta, err: self.puente.terminado.emit(ruta, err))

    def al_terminar(self, ruta, err):
        self.boton.setText(_("Grabar")); self.boton.setEnabled(True)
        if err: self.estado.setText(err); return
        self.estado.setText(_("Guardado: ") + ruta)
        subprocess.Popen(["notify-send", "-i", "screencapture", _("Grabación guardada"), ruta], stderr=subprocess.DEVNULL) if core.have("notify-send") else None

    def closeEvent(self, e):
        self.guardar()
        if self.grab.corriendo: self.grab.detener(lambda ruta, err: None)
        kwin.descargar_todo(); QApplication.quit()

def burbuja_titulo(): return burbuja.TITULO

def main():
    app = QApplication(sys.argv); app.setApplicationName("screencapture"); app.setDesktopFileName("screencapture"); v = Ventana(); v.show(); sys.exit(app.exec())

if __name__ == "__main__": main()
