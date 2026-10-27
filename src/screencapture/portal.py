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

def a_mp4(mkv, mp4):
    """MKV → MP4 sin recodificar el vídeo (el audio pasa de Opus a AAC). Si falla, se conserva el MKV: lo grabado nunca se pierde."""
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mkv, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", mp4], capture_output=True, text=True, timeout=600)
    if r.returncode == 0 and os.path.exists(mp4): return mp4
    return shutil.copy(mkv, mp4.replace(".mp4", ".mkv"))

class Grabador:
    """iniciar() abre el portal (la primera vez muestra el diálogo de KDE/GNOME), arranca la tubería y llama a `al_empezar()`; detener() cierra con EOS y llama a `al_terminar(ruta, error)` desde un hilo."""
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); Gst.init(None)
        self.pipe = None; self.sesion = None; self.t0 = 0; self.corriendo = False; self.n = 0; self.calidad = "media"; self.tmp = None

    def segundos(self): return int(time.time() - self.t0) if self.corriendo else 0

    # --- portal ---
    def _peticion(self, metodo, *args, opciones, siguiente, fallo):
        self.n += 1; token = f"sc{os.getpid()}_{self.n}"; opciones["handle_token"] = token
        ruta = f"/org/freedesktop/portal/desktop/request/{self.bus.get_unique_name()[1:].replace('.', '_')}/{token}"
        def respuesta(codigo, resultados):
            if codigo != 0: fallo(_("Se canceló la elección de pantalla.") if codigo == 1 else _("El portal de pantalla falló.")); return
            siguiente(resultados)
        self.bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
        metodo(*args, opciones)

    def iniciar(self, calidad="media", fps=24, sistema=True, mic=False, al_empezar=None, al_fallar=None):
        if self.corriendo or self.sesion: return
        self.calidad = calidad if calidad in core.QUALITY else "media"; self.fps = fps; self.sistema = sistema; self.mic = mic
        self.al_empezar = al_empezar or (lambda: None); self.al_fallar = al_fallar or (lambda m: None)
        os.makedirs(core.CACHE, exist_ok=True); core.prune_stale()
        if shutil.disk_usage(core.CACHE).free < core.MIN_FREE: self.al_fallar(_("Queda muy poco espacio en el disco para grabar.")); return
        self.bus = dbus.SessionBus(); self.sc = dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.ScreenCast")
        f = self._fallo
        self._peticion(self.sc.CreateSession, opciones={"session_handle_token": f"s{os.getpid()}"}, fallo=f, siguiente=self._elegir)

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
        nodo = int(r["streams"][0][0]); fd = self.sc.OpenPipeWireRemote(self.sesion, {}).take()
        preset, crf, _red = core.QUALITY[self.calidad]
        self.tmp = os.path.join(core.CACHE, f"rec-{os.getpid()}-{core.stamp()}"); os.makedirs(self.tmp, exist_ok=True); self.mkv = os.path.join(self.tmp, "video.mkv")     # nombre que reconoce core.recover_orphans
        audio = ""
        caps = "audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! mezcla."
        if self.sistema: audio += f'pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true ! {caps} '
        if self.mic: audio += f"pipewiresrc do-timestamp=true ! {caps} "
        if audio: audio += "audiomixer name=mezcla ! audioconvert ! opusenc bitrate=96000 ! queue ! mux. "
        desc = (f"matroskamux name=mux ! filesink location={self.mkv} "
                f"pipewiresrc fd={fd} path={nodo} do-timestamp=true keepalive-time=1000 ! queue ! videoconvert ! videorate ! video/x-raw,framerate={self.fps}/1 ! "
                f"x264enc tune=zerolatency speed-preset={preset} pass=qual quantizer={crf} key-int-max={self.fps * 2} ! video/x-h264,profile=high ! h264parse ! queue ! mux. {audio}")
        try: self.pipe = Gst.parse_launch(desc)
        except GLib.Error as e: self._fallo(str(e)); return
        bus = self.pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", self._mensaje)
        self.pipe.set_state(Gst.State.PLAYING); self.t0 = time.time(); self.corriendo = True; self.al_empezar()

    def _mensaje(self, _b, m):
        if m.type == Gst.MessageType.ERROR and self.corriendo:
            err = str(m.parse_error()[0]); self.corriendo = False; self.pipe.set_state(Gst.State.NULL); self._cerrar_sesion(); self.al_fallar(_("Error al grabar: ") + err)
        elif m.type == Gst.MessageType.EOS: self._fin_eos()

    # --- parada ---
    def detener(self, al_terminar):
        if not self.corriendo: al_terminar(None, _("No hay una grabación en curso.")); return
        self.corriendo = False; self.al_terminar = al_terminar; self.pipe.send_event(Gst.Event.new_eos())          # EOS: el archivo queda cerrado y válido
        GLib.timeout_add_seconds(30, self._fin_eos)                                                                  # por si el EOS no llega

    def _fin_eos(self):
        if self.pipe is None: return False
        self.pipe.set_state(Gst.State.NULL); self.pipe = None; self._cerrar_sesion(); mkv, calidad, al = self.mkv, self.calidad, self.al_terminar
        def trabajo():
            try:
                if not os.path.exists(mkv) or os.path.getsize(mkv) < 1000: al(None, _("La grabación quedó vacía.")); return
                os.makedirs(core.DIR_VID, exist_ok=True); mp4 = a_mp4(mkv, os.path.join(core.DIR_VID, f"grabacion-{core.stamp()}.mp4"))
                shutil.rmtree(os.path.dirname(mkv), ignore_errors=True)
                if mp4.endswith(".mp4"): core.reduce_in_background(mp4, calidad)
                al(mp4, None)
            except Exception as e: al(None, str(e))
        threading.Thread(target=trabajo, daemon=True).start(); return False

    def _cerrar_sesion(self):
        if self.sesion:
            try: dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", self.sesion), "org.freedesktop.portal.Session").Close()
            except Exception: pass
            self.sesion = None
