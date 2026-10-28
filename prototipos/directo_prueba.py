"""Prototipo de directo: captura de pantalla por el portal (como la grabación) → H.264 (x264 o VA-API) + AAC → FLV → RTMP, hacia un receptor local. Mide la CPU del proceso y lo que llegó al receptor.
Uso (con la identidad «oweecapture» para que el portal recuerde la pantalla): systemd-run --user --scope --unit=app-oweecapture-prueba python3 prototipos/directo_prueba.py x264|vaapi SEGUNDOS KBPS"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from gi.repository import GLib
from oweecapture import portal

encoder, segundos, kbps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); URL = "rtmp://127.0.0.1:1935/live/prueba"
CODIF = {"x264": f"x264enc tune=zerolatency speed-preset=veryfast bitrate={kbps} key-int-max=60 ! video/x-raw,format=I420 ! x264enc",
         "vaapi": f"vaapih264enc rate-control=cbr bitrate={kbps} keyframe-period=60"}

class G(portal.Grabador):
    def _lanzar(self):
        enc = f"x264enc tune=zerolatency speed-preset=veryfast bitrate={kbps} key-int-max=60 threads=0" if encoder == "x264" else f"vaapipostproc ! video/x-raw,format=NV12 ! vaapih264enc rate-control=cbr bitrate={kbps} keyframe-period=60"
        desc = (f"flvmux name=fm streamable=true ! rtmp2sink location={URL} "
                f"pipewiresrc fd={os.dup(self.fd)} path={self.nodo} do-timestamp=true keepalive-time=1000 ! queue ! videoconvert ! videorate ! video/x-raw,framerate=30/1 ! {enc} ! video/x-h264,profile=main ! h264parse ! queue ! fm. "
                f'pipewiresrc stream-properties="props,stream.capture.sink=true" do-timestamp=true ! audioconvert ! audioresample ! audio/x-raw,rate=44100,channels=2 ! avenc_aac bitrate=128000 ! aacparse ! queue ! fm.')
        self.pipe = portal.Gst.parse_launch(desc); bus = self.pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", self._msg)
        self.pipe.set_state(portal.Gst.State.PLAYING); return True
    def _msg(self, bus, m):
        if m.type == portal.Gst.MessageType.ERROR: print("ERROR", m.parse_error(), flush=True); bucle.quit()

def cpu(): t = os.times(); return t.user + t.system

def empezado():
    print("emitiendo", encoder, kbps, "kbps", flush=True); c0, w0 = cpu(), time.time()
    def fin():
        print(f"CPU del proceso: {(cpu() - c0) / (time.time() - w0) * 100:.0f} % de un núcleo (4 núcleos = 400 %)  carga del sistema: {os.getloadavg()[0]:.2f}", flush=True)
        g.pipe.set_state(portal.Gst.State.NULL); g._cerrar_sesion(); bucle.quit(); return False
    GLib.timeout_add_seconds(segundos, fin)

bucle = GLib.MainLoop(); g = G(); g.iniciar("whatsapp", 30, False, False, empezado, lambda m: (print("fallo", m), bucle.quit()), None, lambda r, e: None); bucle.run()
