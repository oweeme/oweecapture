"""Grabación de pantalla por el portal ScreenCast + PipeWire + GStreamer (KDE, GNOME y cualquier escritorio con portal). Sin procesos externos para capturar: el vídeo y el audio (sistema y micrófono) se
codifican en un solo canal de GStreamer a un MKV en la caché (si todo se cae, `core.recover_orphans` lo guarda); al parar se pasa a MP4 sin recodificar el vídeo y se reduce en segundo plano según la calidad.
Necesita un bucle de eventos de GLib: Qt en Linux lo usa por defecto, así que dbus-python y GStreamer funcionan dentro de una aplicación Qt."""
import json, os, shutil, subprocess, threading, time
import dbus, dbus.mainloop.glib
import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
from . import core
from .i18n import _

TOKEN = os.path.join(os.path.dirname(core.CFG), "portal.json")          # elección de pantalla recordada (restore token del portal)

def _leer_token():
    try: return json.load(open(TOKEN)).get("restore_token", "")
    except (OSError, ValueError): return ""

def _guardar_token(t):
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True); json.dump({"restore_token": t}, open(TOKEN, "w"))

LOG = os.path.join(os.path.dirname(core.CACHE), "error.log")

def a_mp4(mkv, mp4):
    """MKV → MP4 sin recodificar el vídeo (el audio pasa de Opus a AAC). Si falla, se conserva el MKV: lo grabado nunca se pierde."""
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mkv, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", mp4], capture_output=True, text=True, timeout=600)
    if r.returncode == 0 and os.path.exists(mp4): return mp4
    return shutil.copy(mkv, mp4.replace(".mp4", ".mkv"))

def juntar(segmentos, mp4):
    """Une los trozos de una grabación con pausas en un MP4 (el vídeo sin recodificar; el audio pasa de Opus a AAC). Con un solo trozo es `a_mp4`. Si algo falla, los trozos se conservan como MKV."""
    validos = [x for x in segmentos if os.path.exists(x) and os.path.getsize(x) > 1000]
    if len(validos) <= 1: return a_mp4(validos[0], mp4) if validos else None
    lista = os.path.join(os.path.dirname(validos[0]), "lista.txt"); open(lista, "w").write("".join(f"file '{x}'\n" for x in validos))
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", mp4], capture_output=True, text=True, timeout=900)
    if r.returncode == 0 and os.path.exists(mp4): return mp4
    destino = mp4[:-4]; [shutil.copy(x, f"{destino}-{i + 1}.mkv") for i, x in enumerate(validos)]; return f"{destino}-1.mkv"

class Grabador:
    """iniciar() abre el portal (la primera vez muestra el diálogo de KDE/GNOME), arranca la tubería y llama a `al_empezar()`; detener() cierra con EOS y llama a `al_terminar(ruta, error)` desde un hilo."""
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); Gst.init(None)
        self.pipe = None; self.sesion = None; self.t0 = 0; self.corriendo = False; self.pausada = False; self.t_pausa = 0; self.en_pausa = 0; self.segmentos = []; self.cerrando = False; self.final = False; self.al_terminar = lambda r, e: None; self.n = 0; self.calidad = "whatsapp"; self.tmp = None

    def segundos(self):
        """Tiempo grabado: no cuenta las pausas."""
        if not self.corriendo: return 0
        return int((self.t_pausa if self.pausada else time.time()) - self.t0 - self.en_pausa)

    def pausar(self):
        """Pausa cerrando el trozo actual (EOS): cada trozo es un MKV válido y al continuar se abre otro; al terminar se unen sin recodificar el vídeo."""
        if self.corriendo and not self.pausada: self.pausada = True; self.t_pausa = time.time(); self.pipe.send_event(Gst.Event.new_eos())

    def reanudar(self):
        if not (self.corriendo and self.pausada) or self.pipe is not None: return          # si el trozo anterior aún se está cerrando, se ignora
        self.en_pausa += time.time() - self.t_pausa; self.pausada = False; self._lanzar()

    # --- portal ---
    def _peticion(self, metodo, *args, opciones, siguiente, fallo):
        self.n += 1; token = f"sc{os.getpid()}_{self.n}"; opciones["handle_token"] = token
        ruta = f"/org/freedesktop/portal/desktop/request/{self.bus.get_unique_name()[1:].replace('.', '_')}/{token}"
        def respuesta(codigo, resultados):
            if codigo != 0: fallo(_("Se canceló la elección de pantalla.") if codigo == 1 else _("El portal de pantalla falló.")); return
            siguiente(resultados)
        self.bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
        metodo(*args, opciones)

    def iniciar(self, calidad="media", fps=24, sistema=True, mic=False, al_empezar=None, al_fallar=None, zona=None, al_terminar=None, max_mb=0):
        """`zona`: QRect en píxeles de la pantalla (o None para todo). El portal entrega la pantalla entera y la zona se recorta en la tubería."""
        if self.corriendo or self.sesion: return
        self.calidad = calidad if calidad in core.QUALITY else "whatsapp"; self.fps = fps; self.sistema = sistema; self.mic = mic; self.zona = zona; self.max_mb = max_mb
        self.al_empezar = al_empezar or (lambda: None); self.al_fallar = al_fallar or (lambda m: None); self.al_terminar = al_terminar or self.al_terminar
        os.makedirs(core.CACHE, exist_ok=True); core.prune_stale()
        if shutil.disk_usage(core.CACHE).free < core.MIN_FREE: self.al_fallar(_("Queda muy poco espacio en el disco para grabar.")); return
        self.bus = dbus.SessionBus(); self.sc = dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.ScreenCast")
        f = self._fallo
        self._peticion(self.sc.CreateSession, opciones={"session_handle_token": f"s{os.getpid()}"}, fallo=f, siguiente=self._elegir)

    def _registrar(self, texto):
        """Deja el detalle técnico de un fallo en ~/.cache/screencapture/error.log (el aviso de la ventana es corto)."""
        try:
            os.makedirs(os.path.dirname(LOG), exist_ok=True); open(LOG, "a").write(f"{time.strftime('%F %T')} {texto}\n")
        except OSError: pass

    def _fallo(self, mensaje): self._cerrar_sesion(); self.al_fallar(mensaje)

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
        self.recorte = ""
        if self.zona:
            ancho, alto = (int(x) for x in dict(r["streams"][0][1]).get("size", (0, 0)))
            z = self.zona; x, y = z.x() & ~1, z.y() & ~1; w = min(ancho - x, z.width() + (z.x() - x)) & ~1; h = min(alto - y, z.height() + (z.y() - y)) & ~1      # medidas pares: H.264 las exige
            if ancho and alto and w > 0 and h > 0: self.recorte = f"videocrop left={x} top={y} right={ancho - x - w} bottom={alto - y - h} ! "
        self.segmentos = []; self.pausada = False; self.cerrando = False; self.final = False; self.en_pausa = 0
        if self._lanzar(): self.t0 = time.time(); self.corriendo = True; self.al_empezar()

    def _lanzar(self):
        """Arranca la tubería de un trozo nuevo. El primero se llama video.mkv (nombre que reconoce core.recover_orphans); los siguientes, video-2.mkv…"""
        preset, crf, _red = core.QUALITY[self.calidad]
        self.mkv = os.path.join(self.tmp, "video.mkv" if not self.segmentos else f"video-{len(self.segmentos) + 1}.mkv")
        audio = ""
        caps = "audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! mezcla."
        if self.sistema: audio += f'pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true ! {caps} '
        if self.mic: audio += f"pipewiresrc do-timestamp=true ! {caps} "
        if audio: audio += "audiomixer name=mezcla ! audioconvert ! opusenc bitrate=96000 ! queue ! mux. "
        desc = (f"matroskamux name=mux ! filesink location={self.mkv} "
                f"pipewiresrc fd={os.dup(self.fd)} path={self.nodo} do-timestamp=true keepalive-time=1000 ! queue ! videoconvert ! {self.recorte}videorate ! video/x-raw,framerate={self.fps}/1 ! "
                f"x264enc tune=zerolatency speed-preset={preset} pass=qual quantizer={crf} key-int-max={self.fps * 2} ! video/x-h264,profile=high ! h264parse ! queue ! mux. {audio}")
        try: self.pipe = Gst.parse_launch(desc)
        except GLib.Error as e: self._fallo(str(e)); return False
        bus = self.pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", self._mensaje)
        self.segmentos.append(self.mkv); self.pipe.set_state(Gst.State.PLAYING); return True

    def _mensaje(self, bus, m):
        if self.pipe is None or m.src is None: return           # mensaje de un trozo ya cerrado
        if m.type == Gst.MessageType.ERROR and self.corriendo:
            e, detalle = m.parse_error(); self.corriendo = False; self.pausada = False
            self._registrar(f"{e} | {detalle} | zona={self.zona} | origen={m.src.get_name()}")
            if any(os.path.exists(x) and os.path.getsize(x) > 1000 for x in self.segmentos): self._fin_eos(); return      # lo más probable: se cortó desde el indicador del escritorio («Dejar de compartir»); se guarda lo grabado
            self.pipe.set_state(Gst.State.NULL); self._cerrar_sesion(); self.al_fallar(_("Error al grabar: ") + str(e) + _(" (detalle en ") + LOG + ")")
        elif m.type == Gst.MessageType.EOS and isinstance(m.src, Gst.Pipeline):
            if self.pausada and not self.final: self._cerrar_trozo()          # fin de un trozo por una pausa: la grabación sigue abierta
            else: self._fin_eos()

    def _cerrar_trozo(self):
        self.pipe.get_bus().remove_signal_watch(); self.pipe.set_state(Gst.State.NULL); self.pipe = None

    # --- parada ---
    def detener(self, al_terminar):
        if not self.corriendo: al_terminar(None, _("No hay una grabación en curso.")); return
        self.corriendo = False; self.al_terminar = al_terminar; self.final = True
        if self.pipe is None: self._fin_eos()                                # en pausa y con el trozo ya cerrado
        else:
            if not self.pausada: self.pipe.send_event(Gst.Event.new_eos())  # EOS: el archivo queda cerrado y válido
            GLib.timeout_add_seconds(30, self._fin_eos)                      # por si el EOS no llega (si ya se cerraba por una pausa, su EOS llega solo)

    def _fin_eos(self):
        if self.cerrando: return False
        self.cerrando = True
        if self.pipe is not None: self.pipe.get_bus().remove_signal_watch(); self.pipe.set_state(Gst.State.NULL); self.pipe = None
        self._cerrar_sesion(); segs, calidad, al, tmp, max_mb = list(self.segmentos), self.calidad, self.al_terminar, self.tmp, self.max_mb
        def trabajo():
            try:
                if not any(os.path.exists(x) and os.path.getsize(x) > 1000 for x in segs): al(None, _("La grabación quedó vacía.")); return
                os.makedirs(core.DIR_VID, exist_ok=True); mp4 = juntar(segs, os.path.join(core.DIR_VID, f"grabacion-{core.stamp()}.mp4"))
                shutil.rmtree(tmp, ignore_errors=True)
                if mp4.endswith(".mp4"): core.reduce_in_background(mp4, calidad, max_mb)
                al(mp4, None)
            except Exception as e: al(None, str(e))
        threading.Thread(target=trabajo, daemon=True).start(); return False

    def _cerrar_sesion(self):
        if self.sesion:
            try: dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", self.sesion), "org.freedesktop.portal.Session").Close()
            except Exception: pass
            self.sesion = None
