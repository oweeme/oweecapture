"""Ventana «Herramientas de vídeo»: elige un vídeo (por defecto el último grabado) y crea una versión vertical 9:16 para Shorts, TikTok y Reels y/o sin silencios. Siempre escribe archivos nuevos al lado del original."""
import glob, os, subprocess, threading
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSlider, QVBoxLayout
from . import core, herramientas
from .i18n import _

def ultimo_video():
    """El vídeo grabado más reciente (carpeta de grabaciones y sus clips), o ''."""
    v = glob.glob(os.path.join(core.DIR_VID, "*.mp4")) + glob.glob(os.path.join(core.DIR_VID, "Clips", "*.mp4"))
    return max(v, key=os.path.getmtime) if v else ""

class Aviso(QObject):
    terminado = Signal(object, object)

class VentanaHerramientas(QDialog):
    def __init__(self, archivo="", padre=None):
        super().__init__(padre); self.setWindowTitle(_("Herramientas de vídeo")); self.control = None; self.hilo = None; self.aviso = Aviso(); self.aviso.terminado.connect(self.al_terminar); lay = QVBoxLayout(self)
        fila = QHBoxLayout(); self.archivo = QLineEdit(archivo or ultimo_video()); b = QPushButton(_("Elegir…")); b.clicked.connect(self.elegir); fila.addWidget(self.archivo); fila.addWidget(b); lay.addWidget(QLabel(_("Vídeo"))); lay.addLayout(fila)
        self.vertical = QCheckBox(_("Vertical 9:16 (YouTube Shorts, TikTok, Reels)")); self.vertical.setChecked(True); self.modo = QComboBox(); [self.modo.addItem(_(t), k) for k, t in herramientas.MODOS]
        self.pos = QSlider(Qt.Horizontal); self.pos.setRange(0, 100); self.pos.setValue(50); self.etq_pos = QLabel(_("Parte que queda: centro")); self.pos.valueChanged.connect(self.pos_cambia); self.modo.currentIndexChanged.connect(self.modo_cambia)
        self.silencios = QCheckBox(_("Cortar los silencios")); self.sens = QComboBox(); [self.sens.addItem(_(t), k) for k, t, _u, _m in herramientas.SILENCIOS]; self.sens.setCurrentIndex(1)
        for w in (self.vertical, self.modo, self.etq_pos, self.pos, self.silencios, self.sens): lay.addWidget(w)
        self.vertical.toggled.connect(self.modo_cambia); self.silencios.toggled.connect(self.sens.setEnabled); self.sens.setEnabled(False); self.modo_cambia()
        self.barra = QProgressBar(); self.barra.setRange(0, 1); self.barra.setTextVisible(False); self.estado = QLabel(""); self.estado.setWordWrap(True)
        botones = QHBoxLayout(); self.crear = QPushButton(_("Crear")); self.crear.clicked.connect(self.empezar); self.cancelar = QPushButton(_("Cancelar")); self.cancelar.setEnabled(False); self.cancelar.clicked.connect(self.parar)
        self.carpeta = QPushButton(_("Abrir carpeta")); self.carpeta.setEnabled(False); self.carpeta.clicked.connect(self.abrir_carpeta); [botones.addWidget(x) for x in (self.crear, self.cancelar, self.carpeta)]
        [lay.addWidget(x) for x in (self.barra, self.estado)]; lay.addLayout(botones); self.resultado = None; self.setMinimumWidth(460)

    def modo_cambia(self):
        recorte = self.vertical.isChecked() and self.modo.currentData() == "recorte"; self.modo.setEnabled(self.vertical.isChecked()); self.pos.setEnabled(recorte); self.etq_pos.setEnabled(recorte)
    def pos_cambia(self, v): self.etq_pos.setText(_("Parte que queda: ") + (_("izquierda") if v < 20 else _("derecha") if v > 80 else _("centro") if 40 <= v <= 60 else f"{v} %"))

    def elegir(self):
        r, _f = QFileDialog.getOpenFileName(self, _("Elegir un vídeo"), os.path.dirname(self.archivo.text()) or core.DIR_VID, _("Vídeos") + " (*.mp4 *.mkv *.mov *.webm)")
        if r: self.archivo.setText(r)

    def empezar(self):
        ruta = self.archivo.text().strip()
        if not os.path.isfile(ruta): self.estado.setText(_("Elige un vídeo que exista.")); return
        if not (self.vertical.isChecked() or self.silencios.isChecked()): self.estado.setText(_("Marca al menos una herramienta.")); return
        self.control = herramientas.Control(); self.crear.setEnabled(False); self.cancelar.setEnabled(True); self.carpeta.setEnabled(False); self.barra.setRange(0, 0); self.estado.setText(_("Procesando… (puede tardar según la duración)"))
        opciones = dict(vertical=self.vertical.isChecked(), modo=self.modo.currentData(), pos=self.pos.value() / 100, silencios=self.silencios.isChecked(), sens=self.sens.currentData())
        self.hilo = threading.Thread(target=lambda: self.aviso.terminado.emit(*self.trabajo(ruta, opciones, self.control)), daemon=True); self.hilo.start()

    @staticmethod
    def trabajo(ruta, o, control):
        """Corre en un hilo: (ruta final, error). Con las dos herramientas, primero se cortan los silencios y sobre ese resultado se hace el vertical (el intermedio se borra)."""
        base = os.path.splitext(ruta)[0]; actual = ruta; intermedio = None
        if o["silencios"]:
            _i, _t, umbral, minimo = next(s for s in herramientas.SILENCIOS if s[0] == o["sens"])
            actual, err, info = herramientas.cortar_silencios(actual, base + "-sin-silencios.mp4", umbral, minimo, control)
            if err: return None, err
            intermedio = actual
        if o["vertical"]:
            final, err = herramientas.vertical(actual, base + ("-sin-silencios" if o["silencios"] else "") + "-vertical.mp4", o["modo"], o["pos"], control)
            if intermedio and final: herramientas._borrar(intermedio)
            return final, err
        return actual, None

    def parar(self):
        if self.control: self.control.cancelar()

    def al_terminar(self, ruta, err):
        self.barra.setRange(0, 1); self.crear.setEnabled(True); self.cancelar.setEnabled(False)
        if err: self.estado.setText(err); return
        self.resultado = ruta; self.carpeta.setEnabled(True); d = core.duration(ruta); nota = _(" Dura más de 1 min: comprueba el límite de la plataforma.") if d > 60 else ""
        self.estado.setText(_("Listo: ") + ruta + nota)

    def abrir_carpeta(self):
        if self.resultado: subprocess.Popen(["xdg-open", os.path.dirname(self.resultado)], stderr=subprocess.DEVNULL)
