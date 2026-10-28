"""Prototipo: grabar la pantalla por el portal ScreenCast + PipeWire + GStreamer (KDE, GNOME y cualquier escritorio con portal), con audio del sistema y micrófono.
Uso: python3 prototipos/portal_grabar.py [segundos] [salida.mp4] [--sin-sistema] [--mic]
La primera vez el portal muestra su diálogo; la elección se recuerda (restore token en ~/.config/oweecapture/portal.json) y las siguientes veces no pregunta."""
import json, os, sys
import dbus, dbus.mainloop.glib
import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SEGUNDOS = int(args[0]) if args else 10
SALIDA = args[1] if len(args) > 1 else "/tmp/portal-prueba.mp4"
SISTEMA = "--sin-sistema" not in sys.argv; MIC = "--mic" in sys.argv
TOKEN = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "oweecapture", "portal.json")
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); Gst.init(None)
bus = dbus.SessionBus(); loop = GLib.MainLoop()
portal = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
sc = dbus.Interface(portal, "org.freedesktop.portal.ScreenCast")
yo = bus.get_unique_name()[1:].replace(".", "_"); n = [0]; estado = {}

def leer_token():
    try: return json.load(open(TOKEN)).get("restore_token", "")
    except (OSError, ValueError): return ""

def guardar_token(t):
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True); json.dump({"restore_token": t}, open(TOKEN, "w"))

def peticion(metodo, *a, opciones, siguiente):
    """Llama a un método del portal y espera su señal Response (el portal responde de forma asíncrona)."""
    n[0] += 1; token = f"sc{os.getpid()}_{n[0]}"; opciones["handle_token"] = token
    ruta = f"/org/freedesktop/portal/desktop/request/{yo}/{token}"
    def respuesta(codigo, resultados):
        print("Portal:", metodo._method_name, "→", int(codigo), "(0 = bien, 1 = cancelado, 2 = error)")
        if codigo != 0: loop.quit(); return
        siguiente(resultados)
    bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
    metodo(*a, opciones)

def crear(): peticion(sc.CreateSession, opciones={"session_handle_token": f"s{os.getpid()}"}, siguiente=elegir)

def elegir(r):
    estado["sesion"] = r["session_handle"]
    op = {"types": dbus.UInt32(1 | 2), "cursor_mode": dbus.UInt32(2), "persist_mode": dbus.UInt32(2)}      # persist_mode 2: recordar hasta que el usuario lo revoque
    if leer_token(): op["restore_token"] = leer_token(); print("Usando la elección recordada")
    peticion(sc.SelectSources, estado["sesion"], opciones=op, siguiente=lambda _r: peticion(sc.Start, estado["sesion"], "", opciones={}, siguiente=grabar))

def grabar(r):
    if r.get("restore_token"): guardar_token(str(r["restore_token"]))
    flujo = r["streams"][0]; nodo = int(flujo[0]); print("Nodo PipeWire:", nodo, tuple(int(x) for x in dict(flujo[1])["size"]))
    fd = sc.OpenPipeWireRemote(estado["sesion"], {}).take()
    audio = ""
    if SISTEMA: audio += 'pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! mezcla. '
    if MIC: audio += "pipewiresrc do-timestamp=true ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! mezcla. "
    if audio: audio += "audiomixer name=mezcla ! audioconvert ! opusenc bitrate=96000 ! queue ! mux. "
    desc = (f"matroskamux name=mux ! filesink location={SALIDA}.mkv "
            f"pipewiresrc fd={fd} path={nodo} do-timestamp=true keepalive-time=1000 ! queue ! videoconvert ! videorate ! video/x-raw,framerate=24/1 ! "
            f"x264enc tune=zerolatency speed-preset=ultrafast bitrate=6000 key-int-max=48 ! h264parse ! queue ! mux. {audio}")
    print(desc); pipe = Gst.parse_launch(desc); estado["pipe"] = pipe
    pipe.set_state(Gst.State.PLAYING)
    def mensajes(b, m):
        if m.type == Gst.MessageType.ERROR: print("ERROR GStreamer:", m.parse_error()); loop.quit()
        elif m.type == Gst.MessageType.EOS: terminar()
    pipe.get_bus().add_signal_watch(); pipe.get_bus().connect("message", mensajes)
    GLib.timeout_add_seconds(SEGUNDOS, lambda: (pipe.send_event(Gst.Event.new_eos()), False)[1])      # EOS: así el archivo queda cerrado y válido

def terminar():
    estado["pipe"].set_state(Gst.State.NULL)
    os.system(f"ffmpeg -y -loglevel error -i '{SALIDA}.mkv' -c:v copy -c:a aac -b:a 128k '{SALIDA}' && ffprobe -v error -show_entries stream=codec_name,width,height,duration -of default=nw=1 '{SALIDA}'; ls -la '{SALIDA}'")
    loop.quit()

crear(); loop.run()
