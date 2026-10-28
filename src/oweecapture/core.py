"""OweeCapture — núcleo sin interfaz: capturas con grim/slurp y grabación de vídeo con wf-recorder + audio con pw-record (se mezcla con ffmpeg).
Todas las órdenes son procesos externos con tiempo límite; ninguna se espera en el hilo de la interfaz (el llamador usa `run_async`)."""
import datetime, json, os, shutil, signal, subprocess, threading, time
from .i18n import _
HOME = os.path.expanduser("~")
def _dir(kind, fallback):
    """Carpeta estándar del usuario (XDG): Pictures/Videos si no hay otra configurada (no depende del idioma de la interfaz)."""
    from gi.repository import GLib
    return GLib.get_user_special_dir(kind) or os.path.join(HOME, fallback)
def dirs():
    from gi.repository import GLib
    return (os.path.join(_dir(GLib.UserDirectory.DIRECTORY_PICTURES, "Pictures"), "Screenshots"), os.path.join(_dir(GLib.UserDirectory.DIRECTORY_VIDEOS, "Videos"), "Screen Recordings"))
DIR_IMG, DIR_VID = dirs()
CFG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")), "oweecapture", "config.json")

def _migrar_configuracion():
    """Las versiones anteriores se llamaban «screencapture»: la primera vez se COPIA su configuración (ajustes, elección de pantalla del portal) a la carpeta nueva; la vieja no se toca."""
    base = os.path.dirname(os.path.dirname(CFG)); viejo = os.path.join(base, "screencapture"); nuevo = os.path.dirname(CFG)
    try:
        if os.path.isdir(viejo) and not os.path.exists(nuevo): shutil.copytree(viejo, nuevo)
    except OSError: pass
_migrar_configuracion()
DEFAULTS = {"timer": 0, "cursor": False, "clipboard": True, "fps": 24, "audio_system": True, "audio_mic": False, "camera": False, "quality": "whatsapp", "max_mb": 0, "zoom": 0, "halo": False, "vol_sistema": 100, "vol_mic": 100, "ruido": 0,
            "clip_seg": 30, "formato": "libre", "directo_plataforma": "youtube", "directo_url": "", "directo_clave": "", "directo_recordar": False, "directo_calidad": "720",
            "cam_forma": "circulo", "cam_borde": "#2A9D8F", "cam_espejo": False, "cam_brillo": 0, "cam_contraste": 100, "cam_fondo": ""}
LEGACY = {"alta": "maxima", "original": "maxima", "buena": "youtube", "media": "whatsapp", "ligera": "whatsapp"}      # nombres de versiones anteriores

def load_cfg():
    try: d = json.load(open(CFG))
    except (OSError, ValueError): d = {}
    cfg = {**DEFAULTS, **{k: v for k, v in d.items() if k in DEFAULTS}}
    cfg["quality"] = LEGACY.get(cfg["quality"], cfg["quality"])
    if cfg["quality"] not in QUALITY: cfg["quality"] = "whatsapp"
    return cfg

def save_cfg(d):
    os.makedirs(os.path.dirname(CFG), exist_ok=True); tmp = CFG + ".tmp"; open(tmp, "w").write(json.dumps(d, indent=1)); os.chmod(tmp, 0o600); os.replace(tmp, CFG)      # puede guardar la clave de transmisión: solo el usuario la lee

def stamp(): return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
def have(p): return shutil.which(p) is not None

# Temporales de grabación: en el disco (no en /tmp, que es memoria RAM: una grabación larga se comería la memoria del equipo)
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "oweecapture", "rec")
# Perfiles por destino: (preset y crf al grabar, reducción posterior). Al grabar se usa poca CPU y al terminar, en segundo plano y con prioridad baja, se reduce el archivo si el perfil lo pide.
# WhatsApp / Telegram: se graba con calidad alta (crf 20) y se reduce a 720p con crf 23 y escalado lanczos (texto nítido; medido: bajar de crf 27 a 23 sube el SSIM de 0,9927 a 0,9951 por un 36 % más de tamaño).
# YouTube: se graba directo con buena compresión y sin reducir (recomprimir después pesaba más). Máxima: casi sin pérdidas, para editar y aplicar efectos (se recomienda 60 fotogramas).
QUALITY = {"whatsapp": ("ultrafast", 20, {"height": 720, "crf": 23, "fps": 0, "abr": "96k", "preset": "faster"}),
           "youtube": ("veryfast", 18, None),
           "maxima": ("veryfast", 12, None)}
MIN_FREE = 1 << 30      # no se empieza a grabar con menos de 1 GB libre

_SCOPE = None
def scope_prefix():
    """Prefijo `systemd-run --user --scope` con límites de memoria HOLGADOS (alto 45 % y máximo 60 % de la RAM): no estorba a ninguna grabación normal, pero si algo se descontrola
    se frena/cierra la grabación en vez de congelar todo el equipo. Si systemd de usuario no está disponible, se graba sin límite."""
    global _SCOPE
    if _SCOPE is None:
        _SCOPE = []
        if have("systemd-run") and os.environ.get("XDG_RUNTIME_DIR"):
            try:
                kb = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal:")))
                high = max(1 << 30, kb * 1024 * 45 // 100); top = max(3 << 29, kb * 1024 * 60 // 100)
                pre = ["systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryHigh={high}", "-p", f"MemoryMax={top}"]
                if subprocess.run(pre + ["true"], capture_output=True, timeout=5).returncode == 0: _SCOPE = pre
            except Exception: pass
    return list(_SCOPE)

def prune_stale():
    """Borra temporales de grabaciones antiguas que quedaron por un cierre brusco (más de un día y sin su proceso)."""
    try:
        for d in os.listdir(CACHE):
            p = os.path.join(CACHE, d)
            try: pid = int(d.split("-")[1])
            except (IndexError, ValueError): pid = 0
            if time.time() - os.path.getmtime(p) > 86400 and not os.path.exists(f"/proc/{pid}"): shutil.rmtree(p, ignore_errors=True)
    except OSError: pass

def duration(path):
    """Duración en segundos según ffprobe (0 si no se puede saber)."""
    try: return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=20).stdout.strip() or 0)
    except (OSError, ValueError, subprocess.TimeoutExpired): return 0

def reduce_in_background(path, q, max_mb=0):
    """Reduce `path` (MP4) según la calidad elegida, sin bloquear nada: proceso aparte con prioridad baja que sigue aunque se cierre la capturadora.
    Escribe en un archivo temporal y solo reemplaza al original si el resultado es más pequeño; si algo falla, el original queda intacto."""
    r = QUALITY[q][2]
    if not r or not have("ffmpeg"): return False
    tmp = path[:-4] + ".reduciendo.mp4"
    vf = f"scale=-2:'min({r['height']},ih)':flags=lanczos" + (f",fps={r['fps']}" if r["fps"] else "")
    limite = []
    if max_mb and duration(path) > 0:                       # tope de tamaño: crf con velocidad máxima (calidad constante mientras quepa; si no, baja lo justo)
        kbps = max(150, int(max_mb * 8192 * 0.92 / duration(path)) - int(r["abr"].rstrip("k"))); limite = ["-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k"]
    thr = str(max(1, (os.cpu_count() or 2) // 2))
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", vf, "-c:v", "libx264", "-preset", r.get("preset", "veryfast"), "-crf", str(r["crf"])] + limite + ["-pix_fmt", "yuv420p", "-threads", thr,
          "-c:a", "aac", "-b:a", r["abr"], "-movflags", "+faststart", tmp]
    script = ('in=$1; tmp=$2; title=$3; shift 3\n'
              'if command -v ionice >/dev/null 2>&1; then nice -n 15 ionice -c3 "$@" >/dev/null 2>&1; else nice -n 15 "$@" >/dev/null 2>&1; fi || { rm -f "$tmp"; exit 1; }\n'
              'before=$(stat -c %s "$in"); after=$(stat -c %s "$tmp")\n'
              'if [ "$after" -gt 0 ] && [ "$after" -lt "$before" ]; then mv -f "$tmp" "$in"; else rm -f "$tmp"; after=$before; fi\n'
              'notify-send -i oweecapture "$title" "$((before / 1048576)) MB → $((after / 1048576)) MB   $in" >/dev/null 2>&1 || true')
    subprocess.Popen(["sh", "-c", script, "oweecapture-reduce", path, tmp, _("Versión reducida lista")] + ff, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return True

def select_region():
    """Deja elegir una zona con el ratón (slurp). Devuelve 'x,y WxH' o None si se cancela (Esc)."""
    if not have("slurp"): return None
    r = subprocess.run(["slurp", "-d", "-b", "#10201966", "-c", "#2A9D8Fff", "-s", "#2A9D8F33", "-w", "2"], capture_output=True, text=True, timeout=120)
    g = r.stdout.strip()
    return g if r.returncode == 0 and g else None

def shot(geometry=None, cursor=False, path=None):
    """Hace una captura (toda la pantalla o `geometry`). Devuelve la ruta del PNG o lanza RuntimeError con un mensaje legible."""
    if not have("grim"): raise RuntimeError(_("Falta «grim» (captura de pantalla de Wayland)."))
    os.makedirs(DIR_IMG, exist_ok=True); path = path or os.path.join(DIR_IMG, f"captura-{stamp()}.png")
    cmd = ["grim"] + (["-c"] if cursor else []) + (["-g", geometry] if geometry else []) + [path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not os.path.exists(path): raise RuntimeError(_("No se pudo capturar la pantalla: ") + (r.stderr.strip() or _("error desconocido")))
    return path

def copy_image(path):
    if not have("wl-copy"): return False
    with open(path, "rb") as f: subprocess.run(["wl-copy", "--type", "image/png"], stdin=f, timeout=10)
    return True

def audio_sources():
    """(sistema_monitor, micrófono) disponibles según wpctl; None si no hay. Se usan los nombres «@DEFAULT_...@» de PipeWire."""
    if not have("wpctl"): return None, None
    def ok(t):
        try: return subprocess.run(["wpctl", "inspect", t], capture_output=True, timeout=3).returncode == 0
        except Exception: return False
    return ("@DEFAULT_AUDIO_SINK@" if ok("@DEFAULT_AUDIO_SINK@") else None), ("@DEFAULT_AUDIO_SOURCE@" if ok("@DEFAULT_AUDIO_SOURCE@") else None)

def mux(video, wavs, out):
    """Junta el vídeo y el audio (si hay) en `out` (MP4) con ffmpeg sin recodificar el vídeo. Devuelve la ruta final: si algo falla se conserva el vídeo tal cual (MKV), nunca se pierde."""
    if wavs and have("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video] + sum([["-i", w] for w in wavs], [])
        cmd += (["-filter_complex", f"{''.join(f'[{i + 1}:a]' for i in range(len(wavs)))}amix=inputs={len(wavs)}:normalize=0[a]", "-map", "0:v", "-map", "[a]"] if len(wavs) > 1 else ["-map", "0:v", "-map", "1:a"])
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out]
    elif have("ffmpeg"):
        from . import audio; cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c:v", "copy"] + audio.argumentos(video, []) + ["-movflags", "+faststart", out]          # el MKV de portal.py trae el audio en pistas separadas: se mezclan sin ajustes
    else: mkv = out.replace(".mp4", ".mkv"); shutil.copy(video, mkv); return mkv
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not os.path.exists(out): mkv = out.replace(".mp4", ".mkv"); shutil.copy(video, mkv); return mkv      # al menos el vídeo no se pierde
    return out

def orphans():
    """Grabaciones que siguen en marcha sin que la Capturadora las controle (la aplicación se cerró o falló): {carpeta temporal: [pids]}. Se reconocen por su carpeta en la caché."""
    found = {}; me = os.getuid()
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            if os.stat(f"/proc/{d}").st_uid != me: continue
            args = open(f"/proc/{d}/cmdline", "rb").read().decode(errors="replace").split("\0")
        except OSError: continue
        if not args or os.path.basename(args[0]) not in ("wf-recorder", "pw-record"): continue
        t = next((os.path.dirname(a) for a in args if a.startswith(CACHE + os.sep) and "/rec-" in a), None)
        if t: found.setdefault(t, []).append(int(d))
    return found

def leftovers():
    """Carpetas temporales de grabaciones que se cortaron de golpe (la Capturadora y wf-recorder murieron, p. ej. por falta de memoria) pero conservan vídeo: [carpetas]. La Capturadora viva de este
    mismo usuario (el número del nombre es su PID) no cuenta."""
    out = []
    try: names = os.listdir(CACHE)
    except OSError: return out
    live = set(orphans())
    for d in names:
        p = os.path.join(CACHE, d)
        try: pid = int(d.split("-")[1])
        except (IndexError, ValueError): continue
        if d.startswith("rec-") and p not in live and not os.path.exists(f"/proc/{pid}") and os.path.exists(os.path.join(p, "video.mkv")) and os.path.getsize(os.path.join(p, "video.mkv")) > 1000: out.append(p)
    return out

def recover_orphans():
    """Detiene las grabaciones huérfanas (SIGINT: los archivos quedan válidos) y guarda lo grabado hasta ese momento. Devuelve la lista de rutas guardadas. Bloquea: llamar desde un hilo."""
    saved = []
    for tmp, pids in orphans().items():
        for pid in pids:
            try: os.kill(pid, signal.SIGINT)
            except OSError: pass
        for _i in range(150):
            if not any(os.path.exists(f"/proc/{p}") for p in pids): break
            time.sleep(0.4)
        for pid in pids:
            if os.path.exists(f"/proc/{pid}"):
                try: os.kill(pid, signal.SIGKILL)
                except OSError: pass
        video = os.path.join(tmp, "video.mkv")
        if os.path.exists(video) and os.path.getsize(video) > 1000:
            os.makedirs(DIR_VID, exist_ok=True)
            wavs = [f for f in (os.path.join(tmp, "sistema.wav"), os.path.join(tmp, "mic.wav")) if os.path.exists(f) and os.path.getsize(f) > 2000]
            saved.append(mux(video, wavs, os.path.join(DIR_VID, f"grabacion-{stamp()}.mp4")))
        shutil.rmtree(tmp, ignore_errors=True)
    for tmp in leftovers():                                                    # lo que quedó de una grabación que se cortó: se guarda el vídeo (y el audio, si hay)
        os.makedirs(DIR_VID, exist_ok=True)
        wavs = [f for f in (os.path.join(tmp, "sistema.wav"), os.path.join(tmp, "mic.wav")) if os.path.exists(f) and os.path.getsize(f) > 2000]
        try: saved.append(mux(os.path.join(tmp, "video.mkv"), wavs, os.path.join(DIR_VID, f"grabacion-recuperada-{stamp()}.mp4"))); shutil.rmtree(tmp, ignore_errors=True)
        except Exception: pass
    return saved

class Recorder:
    """Grabación de pantalla. start() lanza wf-recorder (vídeo) y, si se pide, pw-record por cada fuente de audio; stop() cierra con SIGINT (así los archivos quedan válidos),
    mezcla el audio con ffmpeg y deja un MP4 en ~/Videos/Screen Recordings. Un fallo en una fuente de audio no estropea el vídeo."""
    def __init__(self): self.procs = []; self.tmp = None; self.out = None; self.t0 = 0; self.running = False; self.quality = "media"

    def start(self, geometry=None, fps=24, system=False, mic=False, quality="media"):
        if not have("wf-recorder"): raise RuntimeError(_("Falta «wf-recorder» (grabación de pantalla)."))
        os.makedirs(DIR_VID, exist_ok=True); os.makedirs(CACHE, exist_ok=True); prune_stale()
        if shutil.disk_usage(CACHE).free < MIN_FREE: raise RuntimeError(_("Queda muy poco espacio en el disco para grabar."))
        self.quality = quality if quality in QUALITY else "media"; preset, crf, _r = QUALITY[self.quality]
        self.out = os.path.join(DIR_VID, f"grabacion-{stamp()}.mp4"); self.tmp = os.path.join(CACHE, f"rec-{os.getpid()}-{stamp()}")
        os.makedirs(self.tmp, exist_ok=True); self.audio = []
        v = scope_prefix() + ["wf-recorder", "-f", os.path.join(self.tmp, "video.mkv"), "-r", str(fps), "-c", "libx264", "-p", f"preset={preset}", "-p", f"crf={crf}", "-p", "pix_fmt=yuv420p"] + (["-g", geometry] if geometry else [])   # el puntero se graba por defecto
        self.procs = [subprocess.Popen(v, stdout=subprocess.DEVNULL, stderr=open(os.path.join(self.tmp, "wf.log"), "w"), start_new_session=True)]
        sys_t, mic_t = audio_sources()
        if system and sys_t:
            self.audio.append(self._pw("sistema", sys_t, True))
        if mic and mic_t:
            self.audio.append(self._pw("mic", mic_t, False))
        self.t0 = time.time(); self.running = True
        time.sleep(0.6)
        if self.procs[0].poll() is not None:
            err = open(os.path.join(self.tmp, "wf.log")).read().strip()[-300:]; self.cleanup(); raise RuntimeError(_("No arrancó la grabación: ") + (err or _("wf-recorder terminó al instante")))

    def _pw(self, name, target, monitor):
        f = os.path.join(self.tmp, name + ".wav")
        cmd = ["pw-record", "--target", target, "--rate", "48000", "--channels", "2"] + (["-P", "{ stream.capture.sink=true }"] if monitor else []) + [f]
        return (name, f, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))

    def elapsed(self): return int(time.time() - self.t0) if self.running else 0

    def stop(self):
        """Termina y devuelve la ruta del MP4 (o lanza RuntimeError). Bloquea unos segundos: llamar desde un hilo."""
        if not self.running: raise RuntimeError(_("No hay una grabación en curso."))
        self.running = False
        for _n, _f, p in self.audio: self._term(p)
        self._term(self.procs[0], 60); video = os.path.join(self.tmp, "video.mkv")
        if not os.path.exists(video) or os.path.getsize(video) < 1000: err = open(os.path.join(self.tmp, "wf.log")).read().strip()[-200:]; self.cleanup(); raise RuntimeError(_("La grabación quedó vacía. ") + err)
        wavs = [f for _n, f, _p in self.audio if os.path.exists(f) and os.path.getsize(f) > 2000]
        self.out = mux(video, wavs, self.out)
        out = self.out; self.cleanup()
        if out.endswith(".mp4"): reduce_in_background(out, self.quality)
        return out

    def _term(self, p, wait=8):
        """Pide cerrar con SIGINT (los archivos quedan válidos) y espera `wait` s; si no, SIGTERM y, como último recurso, SIGKILL. wf-recorder recibe mucho más margen: con la CPU ocupada tarda en vaciar su cola."""
        try:
            os.killpg(p.pid, signal.SIGINT)
            try: p.wait(timeout=wait)
            except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGTERM); p.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass

    def cleanup(self):
        self.running = False
        for _n, _f, p in self.audio:
            if p.poll() is None: self._term(p)
        for p in self.procs:
            if p.poll() is None: self._term(p)
        if self.tmp: shutil.rmtree(self.tmp, ignore_errors=True)

def run_async(fn, done, *a):
    """Ejecuta fn(*a) en un hilo y llama a done(resultado, error) en el hilo de la interfaz (GLib.idle_add)."""
    from gi.repository import GLib
    def work():
        try: r, e = fn(*a), None
        except Exception as ex: r, e = None, str(ex)
        GLib.idle_add(lambda: (done(r, e), False)[1])
    threading.Thread(target=work, daemon=True).start()
