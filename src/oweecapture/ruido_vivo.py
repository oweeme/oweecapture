"""Reducción de ruido del micrófono EN DIRECTO (en la grabación se hace al guardar, ver audio.py): un micrófono virtual «OweeCapture: micrófono sin ruido» creado con el módulo echo-cancel de PipeWire (biblioteca WebRTC de Google), que la aplicación
arranca al empezar el directo y cierra al terminar. Vive en un proceso `pipewire -c` propio (hijo de la aplicación: muere con ella) y no toca la configuración de audio del usuario. Medido con ruido rosa: de -43,5 a -62,4 dB (≈19 dB menos).
Sin interfaz ni GStreamer: solo escribe la configuración y gestiona el proceso."""
import ctypes, json, os, shutil, signal, subprocess, tempfile, time

NOMBRE = "oweecapture_mic_limpio"
MODULO = "/usr/lib/x86_64-linux-gnu/pipewire-0.3/libpipewire-module-echo-cancel.so"

def disponible():
    """True si hay `pipewire` y el módulo echo-cancel (con la biblioteca WebRTC) en este equipo."""
    return shutil.which("pipewire") is not None and shutil.which("pw-dump") is not None and (os.path.exists(MODULO) or bool(_buscar_modulo()))

def _buscar_modulo():
    for d in ("/usr/lib64/pipewire-0.3", "/usr/lib/pipewire-0.3", "/usr/lib/aarch64-linux-gnu/pipewire-0.3"):
        if os.path.exists(os.path.join(d, "libpipewire-module-echo-cancel.so")): return d
    return None

def configuracion():
    """Texto de la configuración de `pipewire -c`: solo supresión de ruido y filtro de graves (sin control automático de ganancia, que cambiaría el volumen elegido)."""
    return f"""context.properties = {{ log.level = 1 }}
context.spa-libs = {{ audio.convert.* = audioconvert/libspa-audioconvert  support.* = support/libspa-support }}
context.modules = [
  {{ name = libpipewire-module-rt args = {{ nice.level = -11 }} flags = [ ifexists nofail ] }}
  {{ name = libpipewire-module-protocol-native }}
  {{ name = libpipewire-module-client-node }}
  {{ name = libpipewire-module-adapter }}
  {{ name = libpipewire-module-echo-cancel
    args = {{
      library.name = aec/libspa-aec-webrtc
      monitor.mode = false
      aec.args = {{ webrtc.gain_control = false webrtc.noise_suppression = true webrtc.high_pass_filter = true webrtc.voice_detection = false webrtc.extended_filter = false }}
      capture.props = {{ node.name = "oweecapture.aec.capture" node.passive = true }}
      source.props = {{ node.name = "{NOMBRE}" node.description = "OweeCapture: micrófono sin ruido" }}
      sink.props = {{ node.name = "oweecapture.aec.sink" node.description = "OweeCapture: referencia de eco" }}
      playback.props = {{ node.name = "oweecapture.aec.playback" node.passive = true }}
    }}
  }}
]
"""

def _hay_nodo():
    try: datos = json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5).stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired): return False
    return any(o.get("info", {}).get("props", {}).get("node.name") == NOMBRE for o in datos if isinstance(o, dict))

def _morir_con_el_padre():
    """En el hijo: pide a Linux que lo termine si la aplicación muere (así el micrófono virtual no se queda huérfano)."""
    try: ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)          # PR_SET_PDEATHSIG
    except Exception: pass

class Limpiador:
    def __init__(self): self.proc = None; self.conf = None

    def iniciar(self, espera=5.0):
        """Arranca el micrófono virtual y espera a que aparezca. True si está listo; si no, no queda nada en marcha."""
        if self.proc or not disponible(): return False
        fd, self.conf = tempfile.mkstemp(prefix="oweecapture-aec-", suffix=".conf", dir=os.environ.get("XDG_RUNTIME_DIR") or None); os.write(fd, configuracion().encode()); os.close(fd)
        self.proc = subprocess.Popen(["pipewire", "-c", self.conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=_morir_con_el_padre)
        fin = time.time() + espera
        while time.time() < fin:
            if self.proc.poll() is not None: break
            if _hay_nodo(): return True
            time.sleep(0.25)
        self.detener(); return False

    def detener(self):
        """Cierra SOLO el proceso que arrancó esta instancia y borra su configuración."""
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            p.terminate()
            try: p.wait(timeout=3)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        if self.conf:
            try: os.remove(self.conf)
            except OSError: pass
            self.conf = None
