"""Subtítulos automáticos y locales: el audio no sale del equipo. El motor es faster-whisper (modelo «base») instalado en un ENTORNO PROPIO en ~/.local/share/oweecapture/voz, que se descarga solo si el usuario lo acepta.
Aquí solo hay lógica sin interfaz: lanzar el motor, agrupar las palabras en líneas legibles, escribir el SRT y quemarlo en el vídeo con ffmpeg (libass). `agrupar` y `a_srt` no dependen de nada instalado."""
import json, os, re, shutil, subprocess, tempfile
from . import herramientas

BASE = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "oweecapture")
VENV = os.path.join(BASE, "voz"); MODELOS = os.path.join(BASE, "modelos"); MODELO = "base"; MARCA = os.path.join(MODELOS, f"{MODELO}.listo")
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcriptor.py")
DESCARGA_MB = 620          # tamaño real en disco de lo que se descarga: librerías de PyPI (~470 MB: faster-whisper, ctranslate2, onnxruntime, numpy, av) + modelo «base» de Hugging Face (~145 MB)
IDIOMAS = [("", "Detectar solo"), ("es", "Español"), ("en", "Inglés"), ("pt", "Portugués"), ("fr", "Francés"), ("it", "Italiano"), ("de", "Alemán")]

def python_voz(): return os.path.join(VENV, "bin", "python")
def preparado(): return os.path.exists(python_voz()) and os.path.exists(MARCA)

def agrupar(palabras, max_chars=32, max_seg=3.2, pausa=0.7):
    """[{"w", "ini", "fin"}] → [{"ini", "fin", "texto"}]: líneas de a lo sumo `max_chars` letras por renglón (dos renglones como máximo), de `max_seg` segundos como mucho y que cortan en pausas mayores de `pausa` s o tras un punto. Pensado para leerse de un vistazo, también en vertical."""
    lineas, actual = [], []
    def cerrar():
        if not actual: return
        txt = " ".join(p["w"] for p in actual); renglones = [""]
        for pal in txt.split():                                                                          # reparte en renglones de hasta max_chars
            if renglones[-1] and len(renglones[-1]) + 1 + len(pal) > max_chars: renglones.append(pal)
            else: renglones[-1] = (renglones[-1] + " " + pal).strip()
        lineas.append({"ini": actual[0]["ini"], "fin": actual[-1]["fin"], "texto": "\n".join(renglones)})
    for p in palabras:
        if not p["w"]: continue
        if actual:
            largo = len(" ".join(x["w"] for x in actual)) + 1 + len(p["w"])
            if p["ini"] - actual[-1]["fin"] > pausa or p["fin"] - actual[0]["ini"] > max_seg or largo > 2 * max_chars or re.search(r"[.!?…]$", actual[-1]["w"]): cerrar(); actual.clear()
        actual.append(p)
    cerrar(); return lineas

def _t(seg): ms = int(round(seg * 1000)); h, r = divmod(ms, 3_600_000); m, r = divmod(r, 60_000); s, ms = divmod(r, 1000); return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def a_srt(lineas):
    """Texto del archivo .srt. Cada línea dura al menos 0,8 s y nunca se solapa con la siguiente."""
    out = []
    for i, l in enumerate(lineas):
        fin = max(l["fin"], l["ini"] + 0.8)
        if i + 1 < len(lineas): fin = min(fin, lineas[i + 1]["ini"] - 0.02) if lineas[i + 1]["ini"] - 0.02 > l["ini"] else l["fin"]
        out.append(f"{i + 1}\n{_t(l['ini'])} --> {_t(fin)}\n{l['texto']}\n")
    return "\n".join(out)

def instalar(al_mensaje, control=None):
    """Crea el entorno propio, instala faster-whisper y descarga el modelo. Devuelve None si salió bien o un mensaje de error. Bloquea (minutos): llamar desde un hilo."""
    control = control or herramientas.Control()
    try:
        os.makedirs(MODELOS, exist_ok=True); shutil.rmtree(VENV, ignore_errors=True); al_mensaje("Creando el entorno…")
        r = subprocess.run(["python3", "-m", "venv", "--without-pip", VENV], capture_output=True, text=True)
        if r.returncode != 0: return "No se pudo crear el entorno: " + r.stderr.strip()[-200:]
        import json as _j, urllib.request
        datos = _j.load(urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=30)); url = next(u["url"] for u in datos["urls"] if u["filename"].endswith(".whl"))
        with tempfile.TemporaryDirectory() as d:
            whl = os.path.join(d, "pip.whl"); urllib.request.urlretrieve(url, whl); al_mensaje("Instalando pip…")
            # av<17: las versiones nuevas de PyAV ya no aceptan un argumento que usa faster-whisper 1.2
            for cmd, msg in (([python_voz(), whl + "/pip", "install", "--quiet", "--ignore-installed", "pip"], None), ([os.path.join(VENV, "bin", "pip"), "install", "--quiet", "faster-whisper", "av<17"], "Descargando e instalando faster-whisper (unos 470 MB)…")):
                if msg: al_mensaje(msg)
                rc, err = herramientas._correr(cmd, control, 1800)
                if control.cancelado: return "Cancelado."
                if rc != 0: return "Falló la instalación: " + (err.strip().splitlines() or ["?"])[-1]
        al_mensaje("Descargando el modelo de voz «base» (unos 145 MB)…"); rc, err = herramientas._correr([python_voz(), SCRIPT, "descargar", MODELO, MODELOS], control, 1800)
        if control.cancelado: return "Cancelado."
        if rc != 0: return "No se pudo descargar el modelo: " + (err.strip().splitlines() or ["?"])[-1]
        open(MARCA, "w").write("ok"); return None
    except Exception as e: return f"No se pudo instalar: {e}"

def transcribir(ruta, idioma="", control=None, al_progreso=None):
    """Transcribe el audio de `ruta` con el motor local. Devuelve (palabras, idioma detectado, error). Con prioridad baja para no frenar el resto del equipo."""
    if not preparado(): return [], "", "El motor de voz no está instalado."
    control = control or herramientas.Control(); palabras, idi = [], idioma
    cmd = ["nice", "-n", "10", python_voz(), SCRIPT, "transcribir", ruta, idioma, MODELO, MODELOS]
    control.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for linea in control.proc.stdout:
        try: e = json.loads(linea)
        except ValueError: continue
        if "w" in e: palabras.append({"w": e["w"], "ini": e["ini"], "fin": e["fin"]})
        elif "idioma" in e: idi = e["idioma"]
        elif "p" in e and al_progreso: al_progreso(e["p"])
    err = control.proc.stderr.read(); control.proc.wait()
    if control.cancelado: return [], idi, "Cancelado."
    if control.proc.returncode != 0: return [], idi, (err.strip().splitlines() or ["El motor de voz falló."])[-1]
    return palabras, idi, None

def quemar(entrada, srt, salida, control=None, crf=20):
    """Escribe en `salida` el vídeo con los subtítulos del `srt` dibujados encima (blancos con contorno negro, abajo y centrados; el tamaño sigue al del vídeo, también en vertical). Devuelve (ruta, error)."""
    m = herramientas.medidas(entrada)
    if not m: return None, "No se pudo leer el vídeo."
    ancho, alto = m[0], m[1]; px = 0.065 * min(ancho, alto); tam = round(px * 288 / alto, 1); margen = round((0.2 if alto > ancho else 0.09) * 288)          # el SRT se dibuja en una cuadrícula de 288 de alto
    estilo = f"FontName=DejaVu Sans,FontSize={tam},Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV={margen}"
    salida = herramientas.libre(salida); tmp = salida + ".parcial.mp4"
    with tempfile.TemporaryDirectory() as d:                       # el filtro se ejecuta en una carpeta con el SRT con nombre simple: así no hay que escapar rutas con espacios, comillas o «:»
        shutil.copy(srt, os.path.join(d, "s.srt"))
        rc, err = herramientas._correr(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.abspath(entrada), "-vf", f"subtitles=s.srt:force_style='{estilo}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-c:a", "copy", "-movflags", "+faststart", os.path.abspath(tmp)], control, 7200, cwd=d)
    return herramientas._cerrar(rc, err, tmp, salida, control)

def desinstalar():
    """Borra el motor de voz y el modelo (la carpeta propia de OweeCapture en ~/.local/share/oweecapture/voz y /modelos): libera unos 600 MB. Nada más se toca."""
    for d in (VENV, MODELOS): shutil.rmtree(d, ignore_errors=True)
