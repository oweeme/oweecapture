"""Ventana principal de OweeCapture con Qt6 (PySide6): grabar la pantalla por el portal, burbuja de cámara y modo presentación. Ejecutar: python3 -m oweecapture.qtapp"""
import os, signal, subprocess, sys
from PySide6.QtCore import QObject, QPointF, QRect, QSize, QTimer, Signal
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QGroupBox, QMenu, QScrollArea, QSystemTrayIcon, QTabWidget, QCheckBox, QComboBox, QFormLayout, QLabel, QHBoxLayout, QLineEdit, QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget
from . import atajos, autor, burbuja, captura, clips, core, directo, efectos_pantalla, entrada, kwin, marco, ventana_herramientas, portal, presentacion, selector, servicio
from .i18n import _

CALIDADES = [("whatsapp", _("WhatsApp / Telegram (pequeño y nítido)")), ("youtube", _("YouTube (buena calidad)")), ("maxima", _("Máxima (edición y efectos)"))]
FOTOGRAMAS = [24, 30, 60]
ZOOMS = [(0, _("Sin zoom")), (1.5, "1,5×"), (2, "2×"), (2.5, "2,5×")]
RUIDOS = [(0, _("Sin reducción")), (1, _("Suave (ventilador, zumbido)")), (2, _("Fuerte (también corta el ruido entre frases)"))]
TECLAS_MODOS = [("no", _("No mostrar teclas")), ("atajos", _("Solo atajos y teclas especiales (Ctrl+C, Intro…)")), ("todo", _("Todo lo que escribo (cuidado con las contraseñas)"))]
FORMATOS = [("libre", _("Libre (arrastrar una zona o pantalla completa)")), ("vertical", _("Vertical 9:16 (TikTok, Shorts, Reels)"))]
LIMITES = [(0, _("Sin límite")), (16, _("16 MB (WhatsApp)")), (50, _("50 MB")), (100, _("100 MB"))]

class Puente(QObject):
    """Los avisos del hilo que convierte a MP4 vuelven al hilo de la interfaz por una señal de Qt."""
    terminado = Signal(object, object); clip_listo = Signal(object, object); entrada = Signal(str, object, object)          # «entrada»: clics y teclas, que llegan desde el hilo lector

class Ventana(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle("OweeCapture"); self.setWindowIcon(icono()); self.cfg = core.load_cfg(); self.grab = portal.Grabador(); self.burbuja = None; self.dibujo = None
        self.puente = Puente(); self.puente.terminado.connect(self.al_terminar); self.puente.clip_listo.connect(self.al_clip); self.puente.entrada.connect(self.al_entrada); self.lector = None; self.sup = None; self.teclas = None; lay = QVBoxLayout(self)
        self.calidad = QComboBox(); [self.calidad.addItem(t, k) for k, t in CALIDADES]; self.calidad.setCurrentIndex(max(0, self.calidad.findData(self.cfg["quality"])))
        self.sistema = QCheckBox(_("Audio del sistema")); self.sistema.setChecked(self.cfg["audio_system"]); self.mic = QCheckBox(_("Micrófono")); self.mic.setChecked(self.cfg["audio_mic"])
        self.camara = QCheckBox(_("Cámara en burbuja (mientras se graba)")); self.camara.setChecked(self.cfg["camera"]); self.camara.toggled.connect(lambda on: self.cambiar_camara(on and self.grab.corriendo))
        self.fps = QComboBox(); [self.fps.addItem(f"{n} fps", n) for n in FOTOGRAMAS]; self.fps.setCurrentIndex(max(0, self.fps.findData(self.cfg["fps"])))
        self.limite = QComboBox(); [self.limite.addItem(t, n) for n, t in LIMITES]; self.limite.setCurrentIndex(max(0, self.limite.findData(self.cfg["max_mb"]))); self.calidad.currentIndexChanged.connect(self.perfil_cambia); self.perfil_cambia()
        self.formato = QComboBox(); [self.formato.addItem(t, k) for k, t in FORMATOS]; self.formato.setCurrentIndex(max(0, self.formato.findData(self.cfg["formato"])))
        self.clip_seg = QComboBox(); [self.clip_seg.addItem(f"{n} s", n) for n in clips.OPCIONES]; self.clip_seg.setCurrentIndex(max(0, self.clip_seg.findData(self.cfg["clip_seg"])))
        self.clics = QCheckBox(_("Resaltar los clics del ratón")); self.clics.setChecked(self.cfg["clics"]); self.teclas_modo = QComboBox(); [self.teclas_modo.addItem(t, k) for k, t in TECLAS_MODOS]; self.teclas_modo.setCurrentIndex(max(0, self.teclas_modo.findData(self.cfg["teclas"])))
        self.ayuda_input = QLabel(_("Para esto hace falta que tu usuario esté en el grupo «input» (el sistema no deja leer el ratón y el teclado de otro modo). En una terminal: sudo usermod -aG input $USER  y vuelve a iniciar sesión. Solo se lee mientras grabas o transmites y no se guarda nada.")); self.ayuda_input.setWordWrap(True); self.ayuda_input.setStyleSheet("color: #d98324;")
        self.clics.toggled.connect(self.actualizar_ayuda_input); self.teclas_modo.currentIndexChanged.connect(self.actualizar_ayuda_input); self.actualizar_ayuda_input()
        self.zoom = QComboBox(); [self.zoom.addItem(t, n) for n, t in ZOOMS]; self.zoom.setCurrentIndex(max(0, self.zoom.findData(self.cfg["zoom"]))); self.halo = QCheckBox(_("Resaltar el cursor")); self.halo.setChecked(self.cfg["halo"])
        self.ruido = QComboBox(); [self.ruido.addItem(t, n) for n, t in RUIDOS]; self.ruido.setCurrentIndex(max(0, self.ruido.findData(self.cfg["ruido"]))); self.mic.toggled.connect(self.ruido.setEnabled); self.ruido.setEnabled(self.mic.isChecked()); self.ruido.setToolTip(_("Al grabar se aplica al guardar el vídeo; en directo se usa el cancelador de ruido de PipeWire (WebRTC), que se activa solo mientras transmites."))
        if not kwin.disponible(): self.zoom.setEnabled(False); self.halo.setEnabled(False); self.zoom.setToolTip(_("Disponible solo en KDE Plasma (necesita leer la posición del cursor).")); self.halo.setToolTip(self.zoom.toolTip())
        def grupo(titulo, *filas):
            """Un cuadro con título y un formulario: cada fila es (etiqueta, widget) o solo un widget."""
            g = QGroupBox(titulo); f = QFormLayout(g)
            for fila in filas: f.addRow(*fila) if isinstance(fila, tuple) else f.addRow(fila)
            return g
        def pagina(*bloques):
            """Una pestaña con scroll vertical: si el contenido no cabe (pantalla pequeña) se desplaza, y nunca deja huecos."""
            w = QWidget(); v = QVBoxLayout(w); [v.addWidget(x) for x in bloques]; v.addStretch(1); sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); sc.setWidget(w); return sc
        efectos = self.efectos_camara(); self.camara.toggled.connect(efectos.setEnabled); efectos.setEnabled(self.camara.isChecked())
        self.pestanas = QTabWidget(); self.pestanas.addTab(pagina(grupo(_("Qué grabar"), (_("Zona al grabar"), self.formato), (_("Calidad"), self.calidad), (_("Fotogramas"), self.fps), (_("Tamaño máximo"), self.limite)),
                                                               grupo(_("Ayudas para tutoriales"), (_("Zoom con Ctrl+Alt+Z"), self.zoom), (_("Clip con Ctrl+Alt+G: últimos"), self.clip_seg), self.halo, self.clics, (_("Mostrar teclas"), self.teclas_modo), self.ayuda_input)), _("Grabar"))
        self.pestanas.addTab(pagina(grupo(_("Audio"), self.sistema, (_("Volumen del sistema"), self.deslizador("vol_sistema", self.sistema)), self.mic, (_("Volumen del micrófono"), self.deslizador("vol_mic", self.mic)), (_("Ruido del micrófono"), self.ruido)),
                                    grupo(_("Cámara"), self.camara), efectos), _("Audio y cámara"))
        self.pestanas.addTab(pagina(self.panel_directo()), _("Directo")); lay.addWidget(self.pestanas, 1)
        self.boton = QPushButton(_("Grabar")); self.boton.clicked.connect(self.alternar); self.pres = QPushButton(_("Modo presentación")); self.pres.clicked.connect(self.presentacion)
        self.cap = QPushButton(_("Captura de pantalla")); self.cap.clicked.connect(self.captura); self.herr = QPushButton(_("Herramientas de vídeo")); self.herr.setToolTip(_("Vertical 9:16, recortar, cortar silencios, vista previa")); self.herr.clicked.connect(self.herramientas); self.ultimo = ""
        self.pausa = QPushButton(_("Pausar")); self.pausa.setEnabled(False); self.pausa.clicked.connect(self.pausar); self.acerca = QPushButton(_("Acerca de")); self.acerca.clicked.connect(self.acerca_de)
        self.estado = QLabel(""); self.estado.setWordWrap(True); self.directo_activo = None; self.zona_grabada = None; self.marco = None; principal = QHBoxLayout(); principal.addWidget(self.boton, 2); principal.addWidget(self.pausa, 1); lay.addLayout(principal); lay.addWidget(self.estado)
        otros = QHBoxLayout(); [otros.addWidget(w) for w in (self.cap, self.pres, self.herr, self.acerca)]; lay.addLayout(otros); self.resize(560, 640)
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tic)
        kwin.mantener_encima([burbuja_titulo(), marco.TITULO, efectos_pantalla.TITULO, presentacion.T_DIBUJO, presentacion.T_CONTROLES, selector.TITULO]); self.selector = None
        self.tray = bandeja(self)
        self.atajos = atajos.Atajos(); self.atajos.activado.connect(self.atajo); self.atajos.fallo.connect(lambda m: self.estado.setText(_("Atajos no disponibles: ") + m))
        if not os.environ.get("OWEECAPTURE_SIN_ATAJOS"): self.atajos.iniciar()          # las pruebas lo desactivan: registrar atajos desde un proceso de prueba los deja en el grupo equivocado de KDE

    def atajo(self, que):
        if que == "captura": self.captura()
        elif que == "grabar": self.alternar()
        elif que == "pausar": self.pausar()
        elif que == "zoom": self.zoom_tecla()
        elif que == "clip": self.clip_tecla()
        elif que == "presentacion": self.presentacion()

    def deslizador(self, clave, casilla):
        """Control de volumen de una fuente (0–200 %), activo solo si la fuente está marcada; el ajuste se aplica al guardar la grabación."""
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); d = QSlider(Qt.Horizontal); d.setRange(0, 200); d.setValue(int(self.cfg[clave])); t = QLabel(f"{d.value()} %"); t.setMinimumWidth(48)
        d.valueChanged.connect(lambda v: t.setText(f"{v} %")); d.setEnabled(casilla.isChecked()); casilla.toggled.connect(d.setEnabled); h.addWidget(d); h.addWidget(t); setattr(self, "_" + clave, d); return w

    def acerca_de(self):
        """Ventana «Acerca de»: versión, autor, correo, sitio web y licencia (los datos están en autor.py)."""
        d = QDialog(self); d.setWindowTitle(_("Acerca de OweeCapture")); v = QVBoxLayout(d); cab = QHBoxLayout(); logo = QLabel(); logo.setPixmap(icono().pixmap(64, 64)); cab.addWidget(logo)
        t = QLabel(f"<h2>OweeCapture {autor.VERSION}</h2>"); cab.addWidget(t, 1); v.addLayout(cab); desc = QLabel(_(autor.DESCRIPCION)); desc.setWordWrap(True); v.addWidget(desc)
        info = QLabel(f"<p><b>{_('Autor')}:</b> {autor.NOMBRE}<br><b>{_('Correo')}:</b> <a href='mailto:{autor.EMAIL}'>{autor.EMAIL}</a><br><b>{_('Sitio web')}:</b> <a href='{autor.WEB}'>{autor.WEB}</a><br><b>{_('Licencia')}:</b> {autor.LICENCIA}</p>")
        info.setOpenExternalLinks(True); info.setTextInteractionFlags(Qt.TextBrowserInteraction); v.addWidget(info); b = QPushButton(_("Cerrar")); b.clicked.connect(d.accept); v.addWidget(b); d.setMinimumWidth(420); d.exec()

    def herramientas(self):
        """Abre las herramientas de vídeo con la última grabación ya elegida."""
        if getattr(self, "ventana_herr", None) and self.ventana_herr.isVisible(): self.ventana_herr.raise_(); self.ventana_herr.activateWindow(); return
        self.ventana_herr = ventana_herramientas.VentanaHerramientas(self.ultimo if self.ultimo and os.path.exists(self.ultimo) else "", self); self.ventana_herr.show()

    def clip_tecla(self):
        """Ctrl+Alt+G mientras se graba o se transmite: guarda aparte los últimos N segundos (los que se hayan elegido) sin parar nada."""
        n = self.clip_seg.currentData()
        if not self.grab.clip(n, lambda ruta, err: self.puente.clip_listo.emit(ruta, err)):
            if not self.grab.corriendo: self.estado.setText(_("Los clips se guardan mientras grabas o transmites: empieza una grabación primero.")); self.avisar("OweeCapture", self.estado.text())
            else: self.estado.setText(_("No se puede guardar un clip en pausa."))
            return
        self.avisar("OweeCapture", _("Guardando un clip de los últimos {0} s…").replace("{0}", str(n)))
    def al_clip(self, ruta, err):
        if err: self.estado.setText(err); self.avisar("OweeCapture", err); return
        self.estado.setText(_("Clip guardado: ") + ruta); self.avisar(_("Clip guardado"), ruta)

    def zoom_tecla(self):
        """Ctrl+Alt+Z mientras se graba: acerca (centrado en el cursor) o aleja; el efecto se aplica al terminar la grabación."""
        r = self.grab.alternar_zoom()
        if r is None: self.estado.setText(_("El zoom solo funciona grabando (sin pausa) y con un nivel de zoom elegido.")) if not self.grab.corriendo else None; return
        texto = _("Zoom: acercado (se aplica al terminar)") if r else _("Zoom: alejado"); self.estado.setText(texto); self.avisar("OweeCapture", texto); self.refrescar_bandeja()

    def avisar(self, titulo, texto):
        """Aviso del escritorio: con `notify-send` si está instalado y, si no, el globo de la bandeja (así siempre se ve algo)."""
        if core.have("notify-send"): subprocess.Popen(["notify-send", "-i", "oweecapture", titulo, texto], stderr=subprocess.DEVNULL)
        else: self.tray.showMessage(titulo, texto, QSystemTrayIcon.Information, 2500)

    def con_selector(self, fondo, al_elegir, vertical=False):
        """Muestra el selector (sobre `fondo` congelado, o sobre el escritorio en vivo si es None) y llama a `al_elegir(zona | None)`; Esc cancela."""
        if self.selector: return
        self.selector = True                                                      # reserva: evita abrir dos selectores mientras KWin responde
        kwin.listar_ventanas(lambda ventanas: self.mostrar_selector(fondo, ventanas, al_elegir, vertical))
    def mostrar_selector(self, fondo, ventanas, al_elegir, vertical=False):
        self.selector = selector.Selector(fondo, ventanas, vertical); self.selector.elegido.connect(lambda z: (setattr(self, "selector", None), al_elegir(z)))
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
            self.avisar(_("Captura guardada"), ruta)
        except Exception as e: self.estado.setText(str(e))

    def perfil_cambia(self):
        """El tope de tamaño solo se aplica a los perfiles que reducen al terminar (WhatsApp / Telegram); YouTube y Máxima conservan lo grabado."""
        self.limite.setEnabled(core.QUALITY[self.calidad.currentData()][2] is not None)

    def sin_clave(self, texto):
        """Quita la clave de transmisión de cualquier mensaje que se muestre."""
        return directo.ocultar(str(texto), self.d_clave.text().strip())

    def guardar(self):
        self.cfg.update(clics=self.clics.isChecked(), teclas=self.teclas_modo.currentData(), formato=self.formato.currentData(), clip_seg=self.clip_seg.currentData(), directo_plataforma=self.d_plat.currentData(), directo_url=self.d_url.text().strip(), directo_clave=self.d_clave.text().strip() if self.d_recordar.isChecked() else "", directo_recordar=self.d_recordar.isChecked(), directo_calidad=self.d_calidad.currentData(), quality=self.calidad.currentData(), fps=self.fps.currentData(), max_mb=self.limite.currentData() if self.limite.isEnabled() else 0, audio_system=self.sistema.isChecked(), audio_mic=self.mic.isChecked(), camera=self.camara.isChecked(), zoom=self.zoom.currentData(), halo=self.halo.isChecked(), vol_sistema=self._vol_sistema.value(), vol_mic=self._vol_mic.value(), ruido=self.ruido.currentData(), **{"cam_" + k: v for k, v in self.opciones_camara().items()}); core.save_cfg(self.cfg)

    def efectos_camara(self):
        """Panel plegable con los efectos de la burbuja (forma, borde, espejo, brillo, contraste, fondo); los cambios se ven al instante en la burbuja si está abierta."""
        panel = QWidget(); f = QFormLayout(panel); f.setContentsMargins(18, 0, 0, 0); self.cam = {}
        def combo(clave, opciones):
            c = QComboBox(); [c.addItem(_(t), k) for k, t in opciones]; c.setCurrentIndex(max(0, c.findData(self.cfg[clave]))); c.currentIndexChanged.connect(self.camara_cambia); self.cam[clave] = c; return c
        def desliz(clave, a, b, texto):
            w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); d = QSlider(Qt.Horizontal); d.setRange(a, b); d.setValue(int(self.cfg[clave])); t = QLabel(texto(d.value())); t.setMinimumWidth(48)
            d.valueChanged.connect(lambda v: (t.setText(texto(v)), self.camara_cambia())); h.addWidget(d); h.addWidget(t); self.cam[clave] = d; return w
        f.addRow(_("Forma"), combo("cam_forma", burbuja.FORMAS)); f.addRow(_("Borde"), combo("cam_borde", burbuja.BORDES)); self.espejo = QCheckBox(_("Espejo (como un espejo)")); self.espejo.setChecked(self.cfg["cam_espejo"]); self.espejo.toggled.connect(self.camara_cambia); f.addRow(self.espejo)
        f.addRow(_("Brillo"), desliz("cam_brillo", -50, 50, lambda v: f"{v:+d}")); f.addRow(_("Contraste"), desliz("cam_contraste", 50, 150, lambda v: f"{v} %")); f.addRow(_("Recortar el fondo"), combo("cam_fondo", burbuja.FONDOS))
        g = QGroupBox(_("Efectos de la cámara")); QVBoxLayout(g).addWidget(panel); return g

    def panel_directo(self):
        """Transmitir en directo por RTMP (YouTube, TikTok, Twitch u otro servidor): servidor, clave de transmisión y calidad. La clave se guarda solo si se marca «Recordar»."""
        panel = QWidget(); f = QFormLayout(panel); f.setContentsMargins(18, 0, 0, 0)
        self.d_plat = QComboBox(); [self.d_plat.addItem(n, i) for i, n, _u in directo.PLATAFORMAS]; self.d_plat.setCurrentIndex(max(0, self.d_plat.findData(self.cfg["directo_plataforma"])))
        self.d_url = QLineEdit(self.cfg["directo_url"] or self.url_plataforma()); self.d_url.setPlaceholderText("rtmp://…")
        self.d_clave = QLineEdit(self.cfg["directo_clave"]); self.d_clave.setEchoMode(QLineEdit.Password); self.d_clave.setPlaceholderText(_("Clave de transmisión (no la muestres a nadie)"))
        self.d_recordar = QCheckBox(_("Recordar la clave en este equipo")); self.d_recordar.setChecked(self.cfg["directo_recordar"])
        self.d_calidad = QComboBox(); [self.d_calidad.addItem(t, i) for i, t, _a, _k in directo.CALIDADES]; self.d_calidad.setCurrentIndex(max(0, self.d_calidad.findData(self.cfg["directo_calidad"])))
        self.d_plat.currentIndexChanged.connect(lambda: self.d_url.setText(self.url_plataforma()))
        self.b_directo = QPushButton(_("Transmitir en directo")); self.b_directo.clicked.connect(self.transmitir)
        f.addRow(_("Plataforma"), self.d_plat); f.addRow(_("Servidor"), self.d_url); self.ver_clave = QToolButton(); self.ver_clave.setText(_("Mostrar")); self.ver_clave.setCheckable(True); self.ver_clave.setToolTip(_("Mostrar u ocultar la clave mientras la escribes o la compruebas"))
        self.ver_clave.toggled.connect(lambda on: (self.d_clave.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password), self.ver_clave.setText(_("Ocultar") if on else _("Mostrar"))))
        fila_clave = QWidget(); hc = QHBoxLayout(fila_clave); hc.setContentsMargins(0, 0, 0, 0); hc.addWidget(self.d_clave, 1); hc.addWidget(self.ver_clave); f.addRow(_("Clave"), fila_clave); f.addRow(self.d_recordar); f.addRow(_("Calidad"), self.d_calidad)
        nota = QLabel(_("Se guarda una copia local de lo emitido. La pausa y el zoom no están disponibles en directo. La reducción de ruido del micrófono se aplica en vivo.")); nota.setWordWrap(True); f.addRow(nota); f.addRow(self.b_directo)
        return panel

    def url_plataforma(self): return next((u for i, _n, u in directo.PLATAFORMAS if i == self.d_plat.currentData()), "")

    def transmitir(self):
        """Empieza o termina el directo (el mismo botón). Pide la zona como una grabación y emite al servidor con la clave escrita."""
        if self.grab.corriendo and self.directo_activo: self.parar(); return
        self.ver_clave.setChecked(False)                                     # la clave nunca queda a la vista al empezar (ni si luego alguien comparte la pantalla)
        if self.grab.corriendo: self.estado.setText(_("Ya hay una grabación en curso: deténla antes de transmitir.")); return
        try: url = directo.destino(self.d_url.text(), self.d_clave.text())
        except ValueError as e: self.estado.setText(_(str(e))); return
        _i, _t, alto, kbps = next(c for c in directo.CALIDADES if c[0] == self.d_calidad.currentData())
        self.directo_activo = {"url": url, "clave": self.d_clave.text().strip(), "alto": alto, "kbps": kbps}; self.empezar()

    def opciones_camara(self):
        return burbuja.limpiar({"forma": self.cam["cam_forma"].currentData(), "borde": self.cam["cam_borde"].currentData(), "espejo": self.espejo.isChecked(), "brillo": self.cam["cam_brillo"].value(), "contraste": self.cam["cam_contraste"].value(), "fondo": self.cam["cam_fondo"].currentData()})
    def camara_cambia(self):
        if self.burbuja: self.burbuja.aplicar(self.opciones_camara())

    def cambiar_camara(self, on):
        if on and not self.burbuja:
            ok, motivo = True, ""
            self.burbuja = burbuja.Burbuja(opciones=self.opciones_camara(), alcerrar=lambda: (setattr(self, "burbuja", None), self.camara.setChecked(False))); self.burbuja.show()
        elif not on and self.burbuja: b, self.burbuja = self.burbuja, None; b.alcerrar = None; b.close()

    def presentacion(self):
        """Activa o desactiva el modo presentación (desde la ventana, la bandeja o los controles de la propia capa de dibujo)."""
        if self.dibujo: self.dibujo.close(); return
        self.dibujo = presentacion.Dibujo(alcerrar=self.presentacion_cerrada); self.dibujo.showFullScreen(); self.dibujo.barra.show(); self.refrescar_presentacion()
    def presentacion_cerrada(self): self.dibujo = None; self.refrescar_presentacion()
    def refrescar_presentacion(self):
        texto = _("Desactivar el modo presentación") if self.dibujo else _("Modo presentación"); self.pres.setText(texto); self.acc["presentacion"].setText(texto)

    def alternar(self):
        if self.grab.corriendo: self.parar()
        else: self.directo_activo = None; self.empezar()          # una grabación normal nunca arranca un directo (eso solo lo hace el botón «Transmitir»)

    def empezar(self):
        """Pide la zona (o pantalla completa) sobre el escritorio en vivo y empieza a grabar; el mismo atajo vuelve a llamar a alternar() y detiene."""
        self.guardar(); self.boton.setEnabled(False); self.esconder(lambda: self.con_selector(None, self.empezar_en, self.cfg["formato"] == "vertical"))
    def empezar_en(self, zona):
        self.zona_grabada = zona
        self.estado.setText(_("Eligiendo la pantalla…"))              # la ventana sigue oculta: no debe salir en el vídeo
        self.grab.iniciar(self.cfg["quality"], self.cfg["fps"], self.cfg["audio_system"], self.cfg["audio_mic"], self.al_empezar, self.al_fallar, zona, lambda ruta, err: self.puente.terminado.emit(ruta, err), self.cfg["max_mb"], (self.cfg["zoom"] or 1, self.cfg["halo"]), self.geometria_pantalla(), (self.cfg["vol_sistema"] / 100, self.cfg["vol_mic"] / 100, self.cfg["ruido"]), self.directo_activo)

    def geometria_pantalla(self):
        """(x, y, ancho, alto) lógicos de la pantalla principal: con ella se lleva la posición del cursor al vídeo."""
        g = QApplication.primaryScreen().geometry(); return (g.x(), g.y(), g.width(), g.height())

    def al_empezar(self):
        self.iniciar_entrada()
        if self.zona_grabada: self.marco = marco.Marco(self.zona_grabada); self.marco.movida.connect(lambda r: self.grab.mover_zona(r.x(), r.y())); self.marco.mostrar()          # la línea queda fuera de la zona: no sale en el vídeo
        self.boton.setText(_("Detener")); self.boton.setEnabled(True); self.pausa.setEnabled(not self.directo_activo); self.b_directo.setText(_("Detener la transmisión") if self.directo_activo else self.b_directo.text()); self.b_directo.setEnabled(bool(self.directo_activo)); self.reloj.start(500)
        if self.camara.isChecked(): self.cambiar_camara(True)          # la burbuja vive solo mientras se graba
        self.tic()
    def al_fallar(self, mensaje): self.fin_grabacion(); mensaje = self.sin_clave(mensaje); self.estado.setText(mensaje); self.mostrar()
    def fin_grabacion(self):
        self.parar_entrada(); self.cerrar_marco(); self.reloj.stop(); self.cambiar_camara(False); self.directo_activo = None; self.b_directo.setText(_("Transmitir en directo")); self.b_directo.setEnabled(True); self.boton.setText(_("Grabar")); self.boton.setEnabled(True); self.pausa.setEnabled(False); self.pausa.setText(_("Pausar")); self.refrescar_bandeja()

    def aviso_red(self):
        """En directo, avisa (globo de la bandeja) cuando la conexión se cae y cuando vuelve."""
        e = self.grab.estado_red if self.grab.directo else ""
        if e != getattr(self, "_red_vista", "") and e.startswith(("Sin conexión", "Conectado (reconexiones")): self.avisar("OweeCapture", _(e))
        self._red_vista = e

    def actualizar_ayuda_input(self):
        """La nota del grupo «input» solo se ve si se pide algo que la necesita y falta el permiso."""
        self.ayuda_input.setVisible((self.clics.isChecked() or self.teclas_modo.currentData() != "no") and not entrada.permiso())

    def iniciar_entrada(self):
        """Empieza a mostrar clics y teclas sobre la pantalla (solo si se pidió y hay permiso). Los teclados solo se abren si se quiere mostrar teclas."""
        modo = self.cfg["teclas"]; clics = self.cfg["clics"]
        if not (clics or modo != "no"): return
        if not entrada.permiso(): self.avisar("OweeCapture", _("Clics y teclas: falta el permiso (grupo «input»); mira la pestaña Grabar.")); return
        tec, pun = entrada.dispositivos(); rutas = (pun if clics else []) + (tec if modo != "no" else [])
        self.lector = entrada.Lector(self.puente.entrada.emit, rutas); self.teclas = entrada.Teclas(modo)
        if not self.lector.iniciar(): self.lector = None; return
        self.sup = efectos_pantalla.Superposicion(self.zona_grabada); self.sup.mostrar()
        if clics: self.sigue_para_clics = kwin.seguir_cursor()
    def al_entrada(self, tipo, a, b):
        if self.sup is None: return
        if tipo == "clic":
            pos = kwin.ultima_posicion() if b and self.cfg["clics"] else None
            if pos: self.sup.clic(QPointF(*pos), a)
        elif tipo == "tecla" and self.teclas:
            t = self.teclas.evento(a, b)
            if t: self.sup.tecla(t)
    def parar_entrada(self):
        l, self.lector = self.lector, None; s, self.sup = self.sup, None
        if l: l.detener()
        if s: s.close()
        if getattr(self, "sigue_para_clics", False): self.sigue_para_clics = False; kwin.dejar_cursor()
        self.teclas = None

    def cerrar_marco(self):
        m, self.marco = getattr(self, "marco", None), None
        if m: m.close()

    def tic(self):
        s = self.grab.segundos(); t = f"{s // 60:02d}:{s % 60:02d}"; self.estado.setText((_("En pausa… {0}") if self.grab.pausada else _("EN DIRECTO… {0}") + (" · " + _(self.grab.estado_red) if self.grab.estado_red else "") if self.grab.directo else _("Grabando… {0}")).replace("{0}", t)); self.aviso_red(); self.refrescar_bandeja(t)

    def pausar(self):
        """Pausa o reanuda; el archivo sigue siendo uno solo."""
        if not self.grab.corriendo: return
        (self.grab.reanudar if self.grab.pausada else self.grab.pausar)(); self.pausa.setText(_("Continuar") if self.grab.pausada else _("Pausar")); self.tic()

    def refrescar_bandeja(self, tiempo=""):
        """El icono de la bandeja muestra el estado (rojo grabando, naranja en pausa) y su menú ofrece detener y pausar sin ventana."""
        g, p = self.grab.corriendo, self.grab.pausada
        self.tray.setIcon(icono_estado("pausa" if p else "zoom" if self.grab.zoom_activo() else "grabando") if g else icono()); self.tray.setToolTip(("OweeCapture — " + (_("En pausa") if p else _("Grabando con zoom") if self.grab.zoom_activo() else _("Grabando")) + " " + tiempo) if g else "OweeCapture")
        self.acc["grabar"].setText(_("Detener la grabación") if g else _("Grabar")); self.acc["pausa"].setVisible(g); self.acc["zoom"].setVisible(g and self.cfg["zoom"] > 1); self.acc["clip"].setVisible(g and not p); self.acc["pausa"].setText(_("Continuar") if p else _("Pausar"))

    def parar(self):
        self.reloj.stop(); self.boton.setEnabled(False); self.pausa.setEnabled(False); self.estado.setText(_("Guardando…") + (" " + _("(aplicando zoom y halo: puede tardar)") if self.grab.efectos else "")); self.grab.detener(lambda ruta, err: self.puente.terminado.emit(ruta, err))
        self.cambiar_camara(False); self.refrescar_bandeja()

    def al_terminar(self, ruta, err):
        self.fin_grabacion(); self.mostrar()          # también llega aquí si la captura se cortó desde el indicador del escritorio
        if err: self.estado.setText(self.sin_clave(err)); return
        self.ultimo = ruta; resumen = self.grab.resumen_efectos(); self.estado.setText(_("Guardado: ") + ruta + resumen)
        self.avisar(_("Grabación guardada"), ruta + resumen)

    def hideEvent(self, e): self.ver_clave.setChecked(False); super().hideEvent(e)          # al ocultar la ventana la clave vuelve a taparse
    def closeEvent(self, e): e.ignore(); self.hide()            # cerrar la ventana la oculta; los atajos siguen activos y se sale desde la bandeja
    def salir(self):
        self.guardar()
        if self.grab.corriendo: self.grab.detener(lambda ruta, err: None)
        self.cambiar_camara(False); kwin.descargar_todo(); QApplication.quit()

def burbuja_titulo(): return burbuja.TITULO

def icono():
    """El logo de OweeCapture: el del tema si está instalado; si no, los PNG del repositorio (valen aunque Qt no tenga el complemento de SVG) y, por último, el SVG."""
    i = QIcon.fromTheme("oweecapture")
    if not i.isNull(): return i
    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "icons"); i = QIcon()
    for n in (16, 24, 32, 48, 64, 128, 256, 512):
        f = os.path.join(carpeta, f"oweecapture-{n}.png")
        if os.path.exists(f): i.addFile(f, QSize(n, n))
    return i if not i.isNull() else QIcon(os.path.join(carpeta, "oweecapture.svg"))

def icono_estado(estado):
    """Círculo rojo (grabando) o naranja con barras (en pausa), dibujado a mano para no depender del tema de iconos."""
    pm = QPixmap(64, 64); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
    p.setBrush(QColor("#F4A261" if estado == "pausa" else "#2A7FFF" if estado == "zoom" else "#E63946")); p.drawEllipse(6, 6, 52, 52)
    if estado == "zoom": p.setBrush(Qt.NoBrush); p.setPen(QPen(Qt.white, 6)); p.drawEllipse(18, 16, 22, 22); p.drawLine(36, 36, 47, 47); p.setPen(Qt.NoPen)      # lupa: el zoom está activo
    if estado == "pausa": p.setBrush(Qt.white); p.drawRect(21, 20, 8, 24); p.drawRect(35, 20, 8, 24)
    p.end(); return QIcon(pm)

def bandeja(v):
    """Icono en la bandeja (StatusNotifier en KDE): captura, grabar o detener, pausar, abrir la ventana y salir, sin necesidad de ventana."""
    t = QSystemTrayIcon(icono(), v); m = QMenu(); v.acc = {}
    v.acc["captura"] = m.addAction(_("Captura de pantalla"), v.captura); v.acc["grabar"] = m.addAction(_("Grabar"), v.alternar)
    v.acc["pausa"] = m.addAction(_("Pausar"), v.pausar); v.acc["pausa"].setVisible(False); v.acc["zoom"] = m.addAction(_("Acercar / alejar (zoom)"), v.zoom_tecla); v.acc["zoom"].setVisible(False); v.acc["clip"] = m.addAction(_("Guardar clip de los últimos segundos"), v.clip_tecla); v.acc["clip"].setVisible(False); v.acc["presentacion"] = m.addAction(_("Modo presentación"), v.presentacion)
    m.addAction(_("Herramientas de vídeo…"), v.herramientas); m.addAction(_("Acerca de"), v.acerca_de); m.addAction(_("Abrir ventana"), v.show); m.addSeparator(); m.addAction(_("Salir"), v.salir)
    t.setContextMenu(m); t.setToolTip("OweeCapture"); t.activated.connect(lambda r: (m.popup(QCursor.pos()) if v.grab.corriendo else v.show()) if r == QSystemTrayIcon.Trigger else None); t.show(); return t

def servicio_orden(v, orden): {"Captura": v.captura, "Grabar": v.alternar, "Presentacion": v.presentacion}[orden]()

def main():
    orden = next((servicio.ORDENES[a] for a in sys.argv[1:] if a in servicio.ORDENES), None)
    if servicio.en_marcha():                                                       # ya hay otra instancia: se le pasa la orden (o se le pide que muestre la ventana) y se termina
        servicio.enviar(orden or "Mostrar"); return
    if orden == "Salir": return                                                    # --quit sin instancia: nada que cerrar
    signal.signal(signal.SIGINT, lambda *a: QApplication.quit())                  # Ctrl+C en la terminal cierra la aplicación
    app = QApplication(sys.argv); app.setApplicationName("oweecapture"); app.setDesktopFileName("oweecapture"); app.setQuitOnLastWindowClosed(False); v = Ventana(); oferta = servicio.ofrecer(v)
    pulso = QTimer(); pulso.start(300); pulso.timeout.connect(lambda: None)         # deja que Python atienda las señales mientras Qt espera
    if orden in ("Captura", "Grabar", "Presentacion"): QTimer.singleShot(300, lambda: servicio_orden(v, orden))      # arranque con una orden: se ejecuta y la aplicación queda en la bandeja
    elif "--segundo-plano" not in sys.argv: v.show()          # con --segundo-plano solo atiende a los atajos
    sys.exit(app.exec())

if __name__ == "__main__": main()
