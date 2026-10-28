"""Grabación de pantalla por el portal ScreenCast + PipeWire + GStreamer (KDE, GNOME y cualquier escritorio con portal). Sin procesos externos para capturar: el vídeo y el audio (sistema y micrófono) se
codifican en un solo canal de GStreamer a un MKV en la caché (si todo se cae, `core.recover_orphans` lo guarda); al parar se pasa a MP4 sin recodificar el vídeo y se reduce en segundo plano según la calidad.
Necesita un bucle de eventos de GLib: Qt en Linux lo usa por defecto, así que dbus-python y GStreamer funcionan dentro de una aplicación Qt."""
import json, os, shutil, subprocess, threading, time
import dbus, dbus.mainloop.glib
import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
from . import audio, clips, core, directo as dir_
from .i18n import _

TOKEN = os.path.join(os.path.dirname(core.CFG), "portal.json")          # elección de pantalla recordada (restore token del portal)

def _leer_token():
    try: return json.load(open(TOKEN)).get("restore_token", "")
    except (OSError, ValueError): return ""

def _guardar_token(t):
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True); json.dump({"restore_token": t}, open(TOKEN, "w"))

LOG = os.path.join(os.path.dirname(core.CACHE), "error.log")

def a_mp4(mkv, mp4, mezcla=None):
    """MKV → MP4 sin recodificar el vídeo; el audio se mezcla en una pista AAC aplicando `mezcla` = (fuentes, volumen del sistema, volumen del micrófono, ruido). Si falla, se conserva el MKV: lo grabado nunca se pierde."""
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mkv, "-c:v", "copy"] + audio.argumentos(mkv, *(mezcla or ([], 1.0, 1.0, 0))) + ["-movflags", "+faststart", mp4], capture_output=True, text=True, timeout=1800)
    if r.returncode == 0 and os.path.exists(mp4): return mp4
    return shutil.copy(mkv, mp4.replace(".mp4", ".mkv"))

def juntar(segmentos, mp4, mezcla=None):
    """Une los trozos de una grabación con pausas en un MP4 (el vídeo sin recodificar; el audio según `mezcla`). Con un solo trozo es `a_mp4`. Si algo falla, los trozos se conservan como MKV."""
    validos = [x for x in segmentos if os.path.exists(x) and os.path.getsize(x) > 1000]
    if len(validos) <= 1: return a_mp4(validos[0], mp4, mezcla) if validos else None
    lista = os.path.join(os.path.dirname(validos[0]), "lista.txt"); open(lista, "w").write("".join(f"file '{x}'\n" for x in validos))
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c:v", "copy"] + audio.argumentos(validos[0], *(mezcla or ([], 1.0, 1.0, 0))) + ["-movflags", "+faststart", mp4], capture_output=True, text=True, timeout=1800)
    if r.returncode == 0 and os.path.exists(mp4): return mp4
    destino = mp4[:-4]; [shutil.copy(x, f"{destino}-{i + 1}.mkv") for i, x in enumerate(validos)]; return f"{destino}-1.mkv"

class Grabador:
    """iniciar() abre el portal (la primera vez muestra el diálogo de KDE/GNOME), arranca la tubería y llama a `al_empezar()`; detener() cierra con EOS y llama a `al_terminar(ruta, error)` desde un hilo."""
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); Gst.init(None)
        self.pipe = None; self.sesion = None; self.t0 = 0; self.corriendo = False; self.pausada = False; self.t_pausa = 0; self.en_pausa = 0; self.segmentos = []; self.cerrando = False; self.final = False; self.al_terminar = lambda r, e: None; self.n = 0; self.calidad = "whatsapp"; self.tmp = None; self.movs = []; self.pausas = []; self.movs = []; self.efectos = None; self.directo = None; self.red = None; self.estado_red = ""; self.mkv = None; self.t_seg = 0; self.nota = ""; self.tramos = []; self.aplicado = ""; self.pantalla = None; self.flujo = (0, 0); self.rect = None

    def segundos(self):
        """Tiempo grabado: no cuenta las pausas."""
        if not self.corriendo: return 0
        return int((self.t_pausa if self.pausada else time.time()) - self.t0 - self.en_pausa)

    def pausar(self):
        """Pausa cerrando el trozo actual (EOS): cada trozo es un MKV válido y al continuar se abre otro; al terminar se unen sin recodificar el vídeo."""
        if self.corriendo and not self.pausada and not self.directo: self.pausada = True; self.t_pausa = time.time(); self.pausas.append([self.t_pausa, float('inf')]); self.pipe.send_event(Gst.Event.new_eos())

    def alternar_zoom(self):
        """Acerca o aleja el zoom en este instante de la grabación (se aplica al terminar). Devuelve True si queda acercado, False si queda alejado y None si no se puede (sin grabar, en pausa o sin zoom configurado)."""
        if not (self.corriendo and not self.pausada and self.efectos and self.efectos[0] > 1): return None
        t = self.segundos()
        if self.tramos and self.tramos[-1][1] is None: self.tramos[-1][1] = t; return False
        self.tramos.append([t, None]); return True

    def clip(self, segundos, al_listo):
        """Guarda en Videos/Screen Recordings/Clips los últimos `segundos` de lo que se lleva grabado (o emitido), sin parar nada. `al_listo(ruta, error)` se llama desde un hilo. Devuelve False si ahora no se puede (sin grabar o en pausa)."""
        if not self.corriendo or self.pausada or not self.mkv or not os.path.exists(self.mkv): return False
        transcurrido, mkv, mezcla = time.time() - self.t_seg, self.mkv, self.mezcla; salida = os.path.join(core.DIR_VID, "Clips", f"clip-{core.stamp()}.mp4")
        def trabajo():
            try: r = clips.recortar(mkv, transcurrido, segundos, salida, mezcla); al_listo(r, None if r else _("No se pudo guardar el clip."))
            except Exception as e: al_listo(None, str(e))
        threading.Thread(target=trabajo, daemon=True).start(); return True

    def _recorte(self):
        """Texto del `videocrop` para la zona actual (el elemento se llama «recorte» para poder moverlo en caliente)."""
        x, y, w, h = self.rect; ancho, alto = self.flujo; return f"videocrop name=recorte left={x} top={y} right={ancho - x - w} bottom={alto - y - h} ! "

    def mover_zona(self, x, y):
        """Mueve la zona grabada sin parar nada (como la burbuja de cámara): el tamaño no cambia, solo qué parte de la pantalla entra. Las posiciones son en píxeles de la pantalla; se ajustan a la pantalla y a números pares. Si hay una pausa, se aplica al continuar."""
        if not (self.corriendo and self.rect and self.flujo[0]): return False
        ancho, alto = self.flujo; _x, _y, w, h = self.rect; nx = max(0, min(ancho - w, int(x))) & ~1; ny = max(0, min(alto - h, int(y))) & ~1
        if (nx, ny) == (_x, _y): return False
        self.rect = (nx, ny, w, h); self.recorte = self._recorte(); self.movs.append((self.segundos(), nx, ny)); el = self.pipe.get_by_name("recorte") if self.pipe is not None else None
        if el is not None:                       # el orden evita que, entre dos cambios, left + right sumen más que el ancho
            for prop, v in (("right", ancho - nx - w), ("left", nx)) if nx >= _x else (("left", nx), ("right", ancho - nx - w)): el.set_property(prop, v)
            for prop, v in (("bottom", alto - ny - h), ("top", ny)) if ny >= _y else (("top", ny), ("bottom", alto - ny - h)): el.set_property(prop, v)
        return True

    def zoom_activo(self):
        return bool(self.corriendo and self.tramos and self.tramos[-1][1] is None)

    def resumen_efectos(self):
        """Texto para el aviso final: qué efectos se aplicaron de verdad (vacío si no se pidió ninguno)."""
        return "".join(f" — {x}" for x in (self.nota, self.aplicado) if x)

    def reanudar(self):
        if not (self.corriendo and self.pausada) or self.pipe is not None: return          # si el trozo anterior aún se está cerrando, se ignora
        self.en_pausa += time.time() - self.t_pausa; self.pausas[-1][1] = time.time(); self.pausada = False; self._lanzar()

    # --- portal ---
    def _peticion(self, metodo, *args, opciones, siguiente, fallo):
        self.n += 1; token = f"sc{os.getpid()}_{self.n}"; opciones["handle_token"] = token
        ruta = f"/org/freedesktop/portal/desktop/request/{self.bus.get_unique_name()[1:].replace('.', '_')}/{token}"
        def respuesta(codigo, resultados):
            if codigo != 0: fallo(_("Se canceló la elección de pantalla.") if codigo == 1 else _("El portal de pantalla falló.")); return
            siguiente(resultados)
        self.bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
        metodo(*args, opciones)

    def iniciar(self, calidad="media", fps=24, sistema=True, mic=False, al_empezar=None, al_fallar=None, zona=None, al_terminar=None, max_mb=0, efectos=None, pantalla=None, mezcla=(1.0, 1.0, 0), directo=None):
        """`zona`: QRect en píxeles de la pantalla (o None para todo). El portal entrega la pantalla entera y la zona se recorta en la tubería.
        `efectos`: (zoom, halo) para aplicar al terminar (con zoom 1 y sin halo, ninguno); `mezcla`: (volumen del sistema, volumen del micrófono, nivel de reducción de ruido 0-2) que se aplica al guardar; `directo`: {"url", "clave", "alto", "kbps"} para transmitir por RTMP mientras se guarda una copia local (sin pausa ni efectos posteriores); `pantalla`: (x, y, ancho, alto) lógicos de la pantalla que se graba, para situar el cursor en el vídeo."""
        if self.corriendo or self.sesion: return
        self.calidad = "youtube" if directo else calidad if calidad in core.QUALITY else "whatsapp"; self.fps = fps; self.sistema = sistema; self.mic = mic; self.zona = zona; self.max_mb = max_mb; self.efectos = efectos if efectos and (efectos[0] > 1 or efectos[1]) and pantalla and not directo else None; self.directo = directo; self.red = None; self.estado_red = ""; self.nota = ""; self.pantalla = pantalla; self.mezcla = ([f for f, on in (('sistema', sistema), ('mic', mic)) if on],) + tuple(mezcla)
        self.al_empezar = al_empezar or (lambda: None); self.al_fallar = al_fallar or (lambda m: None); self.al_terminar = al_terminar or self.al_terminar
        os.makedirs(core.CACHE, exist_ok=True); core.prune_stale()
        if shutil.disk_usage(core.CACHE).free < core.MIN_FREE: self.al_fallar(_("Queda muy poco espacio en el disco para grabar.")); return
        self.bus = dbus.SessionBus(); self.sc = dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.ScreenCast")
        f = self._fallo
        self._peticion(self.sc.CreateSession, opciones={"session_handle_token": f"s{os.getpid()}"}, fallo=f, siguiente=self._elegir)

    def _registrar(self, texto):
        """Deja el detalle técnico de un fallo en ~/.cache/screencapture/error.log (el aviso de la ventana es corto)."""
        try:
            os.makedirs(os.path.dirname(LOG), exist_ok=True); open(LOG, "a").write(f"{time.strftime('%F %T')} {self._ocultar(texto)}\n")
        except OSError: pass

    def _ocultar(self, texto):
        """Los mensajes de error de GStreamer pueden traer la URL con la clave de transmisión: nunca se muestra ni se guarda."""
        return dir_.ocultar(str(texto), self.directo["clave"]) if self.directo else str(texto)

    def _fallo(self, mensaje): self._cursor_grabado(); self._cerrar_sesion(); self.al_fallar(self._ocultar(mensaje))

    def _elegir(self, r):
        self.sesion = r["session_handle"]
        op = {"types": dbus.UInt32(1 | 2), "cursor_mode": dbus.UInt32(2), "persist_mode": dbus.UInt32(2)}            # pantalla o ventana, cursor dentro del vídeo, recordar la elección
        if _leer_token(): op["restore_token"] = _leer_token()
        self._peticion(self.sc.SelectSources, self.sesion, opciones=op, fallo=self._fallo,
                       siguiente=lambda _r: self._peticion(self.sc.Start, self.sesion, "", opciones={}, fallo=self._fallo, siguiente=self._grabar))

    # --- tubería ---
    def _grabar(self, r):
        if r.get("restore_token"): _guardar_token(str(r["restore_token"]))
        self.nodo = int(r["streams"][0][0]); self.fd = self.sc.OpenPipeWireRemote(self.sesion, {}).take()
        self.tmp = os.path.join(core.CACHE, f"rec-{os.getpid()}-{core.stamp()}"); os.makedirs(self.tmp, exist_ok=True)
        self.recorte = ""; self.rect = None; ancho, alto = (int(x) for x in dict(r["streams"][0][1]).get("size", (0, 0))); self.flujo = (ancho, alto)
        if self.zona:
            z = self.zona; x, y = z.x() & ~1, z.y() & ~1; w = min(ancho - x, z.width() + (z.x() - x)) & ~1; h = min(alto - y, z.height() + (z.y() - y)) & ~1      # medidas pares: H.264 las exige
            if ancho and alto and w > 0 and h > 0: self.rect = (x, y, w, h); self.recorte = self._recorte()
        self.segmentos = []; self.pausada = False; self.cerrando = False; self.final = False; self.en_pausa = 0; self.pausas = []; self.tramos = []; self.aplicado = ""; self.movs = [(0.0, self.rect[0], self.rect[1])] if self.rect else []
        if self._lanzar():
            self.t0 = time.time(); self.corriendo = True
            if self.efectos and self.flujo[0]:
                from . import kwin
                if not kwin.seguir_cursor(): self.efectos = None          # sin KWin no hay posición del cursor: se graba sin zoom ni halo
            self.al_empezar()

    def _lanzar_directo(self):
        """Tubería de directo (ver directo.py): una sola codificación para la red y la copia local. La copia queda con el audio ya mezclado en una pista: no hay ajustes posteriores."""
        ancho, alto = (self.rect[2], self.rect[3]) if self.rect else self.flujo
        self.mkv = os.path.join(self.tmp, "video.mkv")
        fuentes = ([('pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true', self.mezcla[1])] if self.sistema else []) + ([("pipewiresrc do-timestamp=true", self.mezcla[2])] if self.mic else [])
        desc = dir_.descripcion(f"pipewiresrc fd={os.dup(self.fd)} path={self.nodo} do-timestamp=true keepalive-time=1000", self.recorte, self.fps, self.directo["kbps"], dir_.dimensiones(ancho, alto, self.directo["alto"]), fuentes, self.mkv)
        try: self.pipe = Gst.parse_launch(desc)
        except GLib.Error as e: self._fallo(str(e)); return False
        self.mezcla = (["sistema"], 1.0, 1.0, 0)
        bus = self.pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", self._mensaje)
        self.segmentos.append(self.mkv); self.pipe.set_state(Gst.State.PLAYING); self.t_seg = time.time()
        self.red = dir_.Red(self.pipe, self.directo["url"], self._estado_red, self._red_perdida); self.red.conectar(); return True

    def _estado_red(self, texto): self.estado_red = texto

    def _red_perdida(self, motivo):
        """La rama de red se rindió (nunca conectó o agotó los reintentos): el directo termina, pero lo grabado en local se guarda."""
        self.nota = (_("sin conexión con el servidor") if self.red and self.red.alguna_vez else _("no se pudo conectar con el servidor: revisa la dirección y la clave")); self._registrar(f"Red perdida: {motivo}")
        if self.corriendo: self.corriendo = False; self._fin_eos() if any(os.path.exists(x) and os.path.getsize(x) > 1000 for x in self.segmentos) else (self.pipe.set_state(Gst.State.NULL), self._cerrar_sesion(), self.al_fallar(self.nota))

    def _lanzar(self):
        """Arranca la tubería de un trozo nuevo. El primero se llama video.mkv (nombre que reconoce core.recover_orphans); los siguientes, video-2.mkv…"""
        if self.directo: return self._lanzar_directo()
        preset, crf, _red = core.QUALITY[self.calidad]
        self.mkv = os.path.join(self.tmp, "video.mkv" if not self.segmentos else f"video-{len(self.segmentos) + 1}.mkv")
        audio = ""
        caps = "audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! opusenc bitrate=128000 ! queue ! mux."          # cada fuente en su propia pista: el volumen y el ruido se ajustan al guardar
        if self.sistema: audio += f'pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true ! {caps} '
        if self.mic: audio += f"pipewiresrc do-timestamp=true ! {caps} "
        desc = (f"matroskamux name=mux ! filesink location={self.mkv} "
                f"pipewiresrc fd={os.dup(self.fd)} path={self.nodo} do-timestamp=true keepalive-time=1000 ! queue ! videoconvert ! {self.recorte}videorate ! video/x-raw,framerate={self.fps}/1 ! "
                f"x264enc tune=zerolatency speed-preset={preset} pass=qual quantizer={crf} key-int-max={self.fps * 2} ! video/x-h264,profile=high ! h264parse ! queue ! mux. {audio}")
        try: self.pipe = Gst.parse_launch(desc)
        except GLib.Error as e: self._fallo(str(e)); return False
        bus = self.pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", self._mensaje)
        self.segmentos.append(self.mkv); self.pipe.set_state(Gst.State.PLAYING); self.t_seg = time.time(); return True

    def _mensaje(self, bus, m):
        if self.pipe is None or m.src is None: return           # mensaje de un trozo ya cerrado
        if m.type == Gst.MessageType.ERROR and self.corriendo:
            e, detalle = m.parse_error(); self.corriendo = False; self.pausada = False
            if self.directo: self.nota = _("la transmisión se cortó: ") + self._ocultar(e.message)
            self._registrar(f"{e} | {detalle} | zona={self.zona} | origen={m.src.get_name()}")
            if any(os.path.exists(x) and os.path.getsize(x) > 1000 for x in self.segmentos): self._fin_eos(); return      # lo más probable: se cortó desde el indicador del escritorio («Dejar de compartir»); se guarda lo grabado
            self.pipe.set_state(Gst.State.NULL); self._cursor_grabado(); self._cerrar_sesion(); self.al_fallar(_("Error al grabar: ") + self._ocultar(e) + _(" (detalle en ") + LOG + ")")
        elif m.type == Gst.MessageType.EOS and isinstance(m.src, Gst.Pipeline):
            if self.pausada and not self.final: self._cerrar_trozo()          # fin de un trozo por una pausa: la grabación sigue abierta
            else: self._fin_eos()

    def _cerrar_trozo(self):
        self.pipe.get_bus().remove_signal_watch(); self.pipe.set_state(Gst.State.NULL); self.pipe = None

    # --- parada ---
    def detener(self, al_terminar):
        if not self.corriendo: al_terminar(None, _("No hay una grabación en curso.")); return
        self.corriendo = False; self.al_terminar = al_terminar; self.final = True
        if self.red: self.red.cerrar()
        if self.pipe is None: self._fin_eos()                                # en pausa y con el trozo ya cerrado
        else:
            if not self.pausada: self.pipe.send_event(Gst.Event.new_eos())  # EOS: el archivo queda cerrado y válido
            GLib.timeout_add_seconds(30, self._fin_eos)                      # por si el EOS no llega (si ya se cerraba por una pausa, su EOS llega solo)

    def _fin_eos(self):
        if self.cerrando: return False
        self.cerrando = True
        if self.pipe is not None: self.pipe.get_bus().remove_signal_watch(); self.pipe.set_state(Gst.State.NULL); self.pipe = None
        self._cerrar_sesion(); segs, calidad, al, tmp, max_mb = list(self.segmentos), self.calidad, self.al_terminar, self.tmp, self.max_mb
        efectos = self._cursor_grabado(); mezcla = self.mezcla
        def trabajo():
            try:
                if not any(os.path.exists(x) and os.path.getsize(x) > 1000 for x in segs): al(None, _("La grabación quedó vacía.")); return
                os.makedirs(core.DIR_VID, exist_ok=True); mp4 = juntar(segs, os.path.join(core.DIR_VID, f"grabacion-{core.stamp()}.mp4"), mezcla)
                shutil.rmtree(tmp, ignore_errors=True)
                if efectos and mp4.endswith(".mp4"):
                    from . import efectos as fx
                    p, (zoom, halo), tramos = fx.pista(efectos[0], efectos[1]), efectos[1]["efectos"], efectos[1]["tramos"]
                    ok = (tramos or halo) and fx.aplicar(mp4, p, zoom, halo, core.QUALITY[calidad][1], tramos=tramos)
                    if ok: self.aplicado = (_("zoom aplicado en {0} tramo(s)").replace("{0}", str(len(tramos))) if tramos else "") + (", " if tramos and halo else "") + (_("halo en el cursor") if halo else "")
                    elif tramos or halo: self.aplicado = _("no se pudieron aplicar los efectos"); self._registrar("No se pudieron aplicar los efectos (zoom/halo); se conserva la grabación sin ellos.")
                    elif zoom > 1: self.aplicado = _("sin zoom: no pulsaste Ctrl+Alt+Z")
                if mp4.endswith(".mp4"): core.reduce_in_background(mp4, calidad, max_mb)
                al(mp4, None)
            except Exception as e: al(None, str(e))
        threading.Thread(target=trabajo, daemon=True).start(); return False

    def _cursor_grabado(self):
        """Cierra el seguimiento del cursor y devuelve (muestras, meta) para los efectos, o None si no se pidieron."""
        if not self.efectos: return None
        from . import kwin
        muestras = kwin.dejar_cursor(); ahora = time.time(); pausas = [(a, min(b, ahora)) for a, b in self.pausas]
        meta = {"t0": self.t0, "pausas": pausas, "pantalla": self.pantalla, "flujo": self.flujo, "recorte": self.rect, "movimientos": list(self.movs), "efectos": self.efectos, "tramos": [tuple(x) for x in self.tramos]}
        return (muestras, meta) if len(muestras) > 10 else None

    def _cerrar_sesion(self):
        if self.sesion:
            try: dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", self.sesion), "org.freedesktop.portal.Session").Close()
            except Exception: pass
            self.sesion = None
