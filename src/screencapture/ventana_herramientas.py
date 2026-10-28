"""Ventana «Herramientas de vídeo»: elige un vídeo (por defecto el último grabado) y crea una versión recortada, vertical 9:16 para Shorts, TikTok y Reels y/o sin silencios. Siempre escribe archivos nuevos al lado del original."""
import glob, os, subprocess, threading
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSlider, QVBoxLayout
from . import core, herramientas, reproductor
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
        self.rep = reproductor.Reproductor(); lay.addWidget(self.rep)
        self.recorte = QCheckBox(_("Recortar el principio y el final")); self.t_ini = QLineEdit("0:00"); self.t_fin = QLineEdit(); self.exacto = QCheckBox(_("Corte exacto (más lento: recodifica)")); self.exacto.setChecked(True); self.dur = 0.0
        self.b_ini = QPushButton(_("Aquí")); self.b_fin = QPushButton(_("Aquí")); self.b_ver = QPushButton(_("▶ Ver el tramo")); [b.setToolTip(t) for b, t in ((self.b_ini, _("Poner el inicio en la posición actual de la vista previa")), (self.b_fin, _("Poner el fin en la posición actual de la vista previa")))]
        self.b_ini.clicked.connect(lambda: self.t_ini.setText(herramientas.a_texto(self.rep.segundos()))); self.b_fin.clicked.connect(lambda: self.t_fin.setText(herramientas.a_texto(self.rep.segundos()))); self.b_ver.clicked.connect(self.ver_tramo)
        tiempos = QHBoxLayout(); [tiempos.addWidget(x) for x in (QLabel(_("Inicio")), self.t_ini, self.b_ini, QLabel(_("Fin")), self.t_fin, self.b_fin, self.b_ver)]
        self.panel_recorte = [self.t_ini, self.t_fin, self.exacto, self.b_ini, self.b_fin, self.b_ver]; self.recorte.toggled.connect(self.recorte_cambia); self.archivo.editingFinished.connect(self.cargar)
        lay.addWidget(self.recorte); lay.addLayout(tiempos); lay.addWidget(self.exacto)
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
        """Abre el vídeo elegido en la vista previa, lee su duración y pone el fin por defecto al final."""
        ruta = self.archivo.text().strip(); m = herramientas.medidas(ruta) if os.path.isfile(ruta) else None
        self.dur = m[3] if m else 0.0; self.t_ini.setText("0:00"); self.t_fin.setText(herramientas.a_texto(self.dur) if self.dur else ""); self.rep.cargar(ruta if m else ""); self.modo_cambia()
    def recorte_cambia(self): [w.setEnabled(self.recorte.isChecked()) for w in self.panel_recorte]
    def ver_tramo(self):
        """Reproduce en la vista previa justo el tramo que quedaría con el inicio y el fin escritos."""
        try: ini = herramientas.a_segundos(self.t_ini.text()); fin = herramientas.a_segundos(self.t_fin.text())
        except ValueError: self.estado.setText(_("Pon tiempos válidos, como 0:05 y 1:30.")); return
        if fin <= ini: self.estado.setText(_("El fin debe ser mayor que el inicio.")); return
        self.estado.setText(""); self.rep.ver_tramo(ini, fin)

    def modo_cambia(self):
        recorte = self.vertical.isChecked() and self.modo.currentData() == "recorte"; self.modo.setEnabled(self.vertical.isChecked()); self.pos.setEnabled(recorte); self.etq_pos.setEnabled(recorte); self.rep.poner_guia(self.pos.value() / 100 if recorte else None)          # la guía 9:16 se dibuja sobre la vista previa
    def pos_cambia(self, v): self.rep.poner_guia(v / 100 if self.pos.isEnabled() else None); self.etq_pos.setText(_("Parte que queda: ") + (_("izquierda") if v < 20 else _("derecha") if v > 80 else _("centro") if 40 <= v <= 60 else f"{v} %"))

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
        self.rep.pausar(); self.control = herramientas.Control(); self.crear.setEnabled(False); self.cancelar.setEnabled(True); self.carpeta.setEnabled(False); self.barra.setRange(0, 0); self.estado.setText(_("Procesando… (puede tardar según la duración)"))
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

    def done(self, r): self.rep.detener(); super().done(r)          # al cerrar, la vista previa deja de reproducir
    def closeEvent(self, e): self.rep.detener(); super().closeEvent(e)
