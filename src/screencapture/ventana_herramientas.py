"""Ventana «Herramientas de vídeo»: elige un vídeo (por defecto el último grabado) y crea una versión recortada, vertical 9:16 para Shorts, TikTok y Reels y/o sin silencios. Siempre escribe archivos nuevos al lado del original."""
import glob, os, subprocess, tempfile, threading
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
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
        self.recorte = QCheckBox(_("Recortar el principio y el final")); self.t_ini = QLineEdit("0:00"); self.t_fin = QLineEdit(); self.exacto = QCheckBox(_("Corte exacto (más lento: recodifica)")); self.exacto.setChecked(True)
        self.m_ini = QLabel(); self.m_fin = QLabel(); [m.setFixedSize(240, 135) for m in (self.m_ini, self.m_fin)]; [m.setAlignment(Qt.AlignCenter) for m in (self.m_ini, self.m_fin)]; self.dur = 0.0
        tiempos = QHBoxLayout(); [tiempos.addWidget(x) for x in (QLabel(_("Inicio")), self.t_ini, QLabel(_("Fin")), self.t_fin)]; minis = QHBoxLayout(); minis.addWidget(self.m_ini); minis.addWidget(self.m_fin)
        self.panel_recorte = [self.t_ini, self.t_fin, self.exacto, self.m_ini, self.m_fin]; self.recorte.toggled.connect(self.recorte_cambia); [t.editingFinished.connect(self.miniaturas) for t in (self.t_ini, self.t_fin)]; self.archivo.editingFinished.connect(self.cargar)
        lay.addWidget(self.recorte); lay.addLayout(tiempos); lay.addWidget(self.exacto); lay.addLayout(minis)
        self.vertical = QCheckBox(_("Vertical 9:16 (YouTube Shorts, TikTok, Reels)")); self.vertical.setChecked(True); self.modo = QComboBox(); [self.modo.addItem(_(t), k) for k, t in herramientas.MODOS]
        self.pos = QSlider(Qt.Horizontal); self.pos.setRange(0, 100); self.pos.setValue(50); self.etq_pos = QLabel(_("Parte que queda: centro")); self.pos.valueChanged.connect(self.pos_cambia); self.modo.currentIndexChanged.connect(self.modo_cambia)
        self.silencios = QCheckBox(_("Cortar los silencios")); self.sens = QComboBox(); [self.sens.addItem(_(t), k) for k, t, _u, _m in herramientas.SILENCIOS]; self.sens.setCurrentIndex(1)
        for w in (self.vertical, self.modo, self.etq_pos, self.pos, self.silencios, self.sens): lay.addWidget(w)
        self.vertical.toggled.connect(self.modo_cambia); self.silencios.toggled.connect(self.sens.setEnabled); self.sens.setEnabled(False); self.modo_cambia(); self.cargar(); self.recorte_cambia()
        self.barra = QProgressBar(); self.barra.setRange(0, 1); self.barra.setTextVisible(False); self.estado = QLabel(""); self.estado.setWordWrap(True)
        botones = QHBoxLayout(); self.crear = QPushButton(_("Crear")); self.crear.clicked.connect(self.empezar); self.cancelar = QPushButton(_("Cancelar")); self.cancelar.setEnabled(False); self.cancelar.clicked.connect(self.parar)
        self.carpeta = QPushButton(_("Abrir carpeta")); self.carpeta.setEnabled(False); self.carpeta.clicked.connect(self.abrir_carpeta); [botones.addWidget(x) for x in (self.crear, self.cancelar, self.carpeta)]
        [lay.addWidget(x) for x in (self.barra, self.estado)]; lay.addLayout(botones); self.resultado = None; self.setMinimumWidth(460)

    def cargar(self):
        """Lee la duración del vídeo elegido y pone el fin por defecto al final."""
        m = herramientas.medidas(self.archivo.text().strip()) if os.path.isfile(self.archivo.text().strip()) else None
        self.dur = m[3] if m else 0.0; self.t_ini.setText("0:00"); self.t_fin.setText(herramientas.a_texto(self.dur) if self.dur else ""); self.miniaturas()
    def recorte_cambia(self):
        [w.setEnabled(self.recorte.isChecked()) for w in self.panel_recorte]
        if self.recorte.isChecked(): self.miniaturas()
    def tiempo(self, campo, por_defecto):
        try: return herramientas.a_segundos(campo.text())
        except ValueError: return por_defecto
    def miniaturas(self):
        """Fotogramas de los instantes de inicio y fin elegidos, para ver dónde se corta."""
        ruta = self.archivo.text().strip()
        if not (self.recorte.isChecked() and os.path.isfile(ruta) and self.dur): self.m_ini.clear(); self.m_fin.clear(); return
        with tempfile.TemporaryDirectory() as d:
            for etiqueta, t in ((self.m_ini, self.tiempo(self.t_ini, 0.0)), (self.m_fin, max(0.0, self.tiempo(self.t_fin, self.dur) - 0.1))):
                png = herramientas.fotograma(ruta, min(t, self.dur), os.path.join(d, "f.png"))
                if png: etiqueta.setPixmap(QPixmap(png).scaled(240, 135, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else: etiqueta.setText(_("(sin imagen)"))

    def modo_cambia(self):
        recorte = self.vertical.isChecked() and self.modo.currentData() == "recorte"; self.modo.setEnabled(self.vertical.isChecked()); self.pos.setEnabled(recorte); self.etq_pos.setEnabled(recorte)
    def pos_cambia(self, v): self.etq_pos.setText(_("Parte que queda: ") + (_("izquierda") if v < 20 else _("derecha") if v > 80 else _("centro") if 40 <= v <= 60 else f"{v} %"))

    def elegir(self):
        r, _f = QFileDialog.getOpenFileName(self, _("Elegir un vídeo"), os.path.dirname(self.archivo.text()) or core.DIR_VID, _("Vídeos") + " (*.mp4 *.mkv *.mov *.webm)")
        if r: self.archivo.setText(r); self.cargar()

    def empezar(self):
        ruta = self.archivo.text().strip()
        if not os.path.isfile(ruta): self.estado.setText(_("Elige un vídeo que exista.")); return
        if not (self.recorte.isChecked() or self.vertical.isChecked() or self.silencios.isChecked()): self.estado.setText(_("Marca al menos una herramienta.")); return
        try: ini = herramientas.a_segundos(self.t_ini.text()); fin = herramientas.a_segundos(self.t_fin.text())
        except ValueError: ini = fin = 0.0
        if self.recorte.isChecked() and fin - ini < 0.3: self.estado.setText(_("Pon tiempos válidos, como 0:05 y 1:30 (el fin debe ser mayor que el inicio).")); return
        self.control = herramientas.Control(); self.crear.setEnabled(False); self.cancelar.setEnabled(True); self.carpeta.setEnabled(False); self.barra.setRange(0, 0); self.estado.setText(_("Procesando… (puede tardar según la duración)"))
        opciones = dict(recorte=self.recorte.isChecked(), ini=ini, fin=fin, exacto=self.exacto.isChecked(), vertical=self.vertical.isChecked(), modo=self.modo.currentData(), pos=self.pos.value() / 100, silencios=self.silencios.isChecked(), sens=self.sens.currentData())
        self.hilo = threading.Thread(target=lambda: self.aviso.terminado.emit(*self.trabajo(ruta, opciones, self.control)), daemon=True); self.hilo.start()

    @staticmethod
    def trabajo(ruta, o, control):
        """Corre en un hilo: (ruta final, error). Orden: recortar → cortar silencios → vertical; el nombre acumula lo aplicado y los archivos intermedios se borran."""
        base = os.path.splitext(ruta)[0]; actual = ruta; sufijo = ""; intermedios = []
        def paso(res):
            nonlocal actual
            if res[1]: [herramientas._borrar(i) for i in intermedios]; return res[1]
            if actual != ruta: intermedios.append(actual)
            actual = res[0]; return None
        if o["recorte"]:
            sufijo += "-recorte"; err = paso(herramientas.recortar(actual, base + sufijo + ".mp4", o["ini"], o["fin"], o["exacto"], control))
            if err: return None, err
        if o["silencios"]:
            _i, _t, umbral, minimo = next(x for x in herramientas.SILENCIOS if x[0] == o["sens"]); sufijo += "-sin-silencios"; err = paso(herramientas.cortar_silencios(actual, base + sufijo + ".mp4", umbral, minimo, control)[:2])
            if err: return None, err
        if o["vertical"]:
            sufijo += "-vertical"; err = paso(herramientas.vertical(actual, base + sufijo + ".mp4", o["modo"], o["pos"], control))
            if err: return None, err
        [herramientas._borrar(i) for i in intermedios]; return actual, None

    def parar(self):
        if self.control: self.control.cancelar()

    def al_terminar(self, ruta, err):
        self.barra.setRange(0, 1); self.crear.setEnabled(True); self.cancelar.setEnabled(False)
        if err: self.estado.setText(err); return
        self.resultado = ruta; self.carpeta.setEnabled(True); d = core.duration(ruta); nota = _(" Dura más de 1 min: comprueba el límite de la plataforma.") if d > 60 else ""
        self.estado.setText(_("Listo: ") + ruta + nota)

    def abrir_carpeta(self):
        if self.resultado: subprocess.Popen(["xdg-open", os.path.dirname(self.resultado)], stderr=subprocess.DEVNULL)
