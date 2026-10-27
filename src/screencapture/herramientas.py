"""Herramientas para publicar un vídeo ya grabado, sin interfaz: exportar en vertical 9:16 (YouTube Shorts, TikTok, Reels) y cortar los silencios (tutoriales). Nunca tocan el original: escriben un archivo nuevo al lado.
Cada función recibe un `Control` para poder cancelar desde la interfaz sin esperar a que ffmpeg termine."""
import os, re, subprocess
from . import core

ANCHO, ALTO = 1080, 1920                # tamaño de salida vertical (el que piden Shorts y TikTok)
MODOS = [("desenfoque", "Vídeo entero sobre un fondo desenfocado"), ("recorte", "Recortar a vertical (eliges qué parte queda)")]
SILENCIOS = [("suave", "Suave (solo pausas largas)", -40, 1.0), ("normal", "Normal", -35, 0.6), ("fuerte", "Fuerte (corta también pausas cortas)", -30, 0.35)]       # (id, texto, umbral dB, silencio mínimo en s)

class Control:
    """Permite cancelar la tarea en curso desde otro hilo."""
    def __init__(self): self.proc = None; self.cancelado = False
    def cancelar(self):
        self.cancelado = True
        if self.proc and self.proc.poll() is None: self.proc.terminate()

def _correr(cmd, control, timeout=7200):
    """Ejecuta ffmpeg guardando el proceso en `control`; devuelve (código, texto de error)."""
    control = control or Control(); control.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try: _o, err = control.proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired: control.proc.kill(); _o, err = control.proc.communicate()
    return control.proc.returncode, err

def libre(ruta):
    """Si `ruta` existe añade -2, -3… antes de la extensión: nunca se pisa nada."""
    base, ext = os.path.splitext(ruta); n = 1
    while os.path.exists(ruta): n += 1; ruta = f"{base}-{n}{ext}"
    return ruta

def medidas(ruta):
    """(ancho, alto, tiene_audio, duración) o None si no se puede leer."""
    try:
        v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", ruta], capture_output=True, text=True, timeout=30).stdout.strip().split(",")
        a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", ruta], capture_output=True, text=True, timeout=30).stdout.split()
        return int(v[0]), int(v[1]), bool(a), core.duration(ruta)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired): return None

def filtro_vertical(ancho, alto, modo="desenfoque", posicion=0.5):
    """Filtro de ffmpeg que deja el vídeo en 1080×1920. `desenfoque`: el vídeo entero centrado sobre una copia ampliada y desenfocada de sí mismo (el desenfoque se hace a 1/5 de tamaño y se amplía: se ve igual y cuesta una fracción de CPU). `recorte`: una ventana vertical del vídeo cuyo centro horizontal está en `posicion` (0 = izquierda, 1 = derecha)."""
    if modo == "recorte":
        if ancho * 16 >= alto * 9: w, h = int(alto * 9 / 16) & ~1, alto & ~1; x, y = int(max(0.0, min(1.0, posicion)) * (ancho - w)) & ~1, 0      # más ancho que 9:16: una ventana vertical a la altura completa
        else: w, h = ancho & ~1, int(ancho * 16 / 9) & ~1; x, y = 0, ((alto - h) // 2) & ~1                                                            # ya es más alto que 9:16: se recorta por arriba y abajo
        return f"crop={w}:{h}:{x}:{y},scale={ANCHO}:{ALTO}:flags=lanczos,setsar=1,format=yuv420p"
    return (f"split[a][b];[a]scale={ANCHO // 5}:{ALTO // 5}:force_original_aspect_ratio=increase,crop={ANCHO // 5}:{ALTO // 5},boxblur=5:3,scale={ANCHO}:{ALTO}:flags=bilinear,eq=brightness=-0.08[fondo];"
            f"[b]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=decrease:flags=lanczos[frente];[fondo][frente]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p")

def vertical(entrada, salida, modo="desenfoque", posicion=0.5, control=None, crf=20):
    """Exporta `entrada` en vertical 9:16. Devuelve (ruta, error): error es None si salió bien."""
    m = medidas(entrada)
    if not m: return None, "No se pudo leer el vídeo."
    ancho, alto, _a, _d = m; salida = libre(salida); tmp = salida + ".parcial.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", entrada, "-vf" if modo == "recorte" else "-filter_complex", filtro_vertical(ancho, alto, modo, posicion), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp]
    rc, err = _correr(cmd, control)
    return _cerrar(rc, err, tmp, salida, control)

def _cerrar(rc, err, tmp, salida, control):
    if control and control.cancelado: _borrar(tmp); return None, "Cancelado."
    if rc != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1000: _borrar(tmp); return None, (err.strip().splitlines() or ["ffmpeg falló."])[-1]
    os.replace(tmp, salida); return salida, None

def _borrar(ruta):
    try: os.remove(ruta)
    except OSError: pass

def silencios(entrada, umbral=-35, minimo=0.6, control=None):
    """[(inicio, fin)] de los silencios del audio (silencedetect de ffmpeg); el último puede quedar abierto hasta el final del vídeo."""
    rc, err = _correr(["ffmpeg", "-hide_banner", "-nostats", "-i", entrada, "-vn", "-af", f"silencedetect=noise={umbral}dB:d={minimo}", "-f", "null", "-"], control, 3600)
    ini, out = None, []
    for linea in err.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", linea)
        if m: ini = max(0.0, float(m.group(1))); continue
        m = re.search(r"silence_end: ([\d.]+)", linea)
        if m and ini is not None: out.append((ini, float(m.group(1)))); ini = None
    if ini is not None: out.append((ini, float("inf")))
    return out

def tramos_a_conservar(sil, duracion, margen=0.15, minimo_tramo=0.25):
    """Complemento de los silencios: los tramos del vídeo que se quedan. Cada silencio se recorta `margen` s por cada lado (así no se come el principio ni el final de las palabras) y los tramos muy cortos se descartan."""
    out, pos = [], 0.0
    for s, e in sorted(sil):
        e = min(e, duracion); a, b = s + margen, e - margen
        if b - a < 0.2: continue                                                      # silencio demasiado corto para cortarlo
        if a - pos >= minimo_tramo: out.append((pos, a))
        pos = b
    if duracion - pos >= minimo_tramo: out.append((pos, duracion))
    return out

def cortar_silencios(entrada, salida, umbral=-35, minimo=0.6, control=None, crf=20):
    """Quita los silencios del vídeo (se recodifica, un solo paso). Devuelve (ruta, error, info) con info = (duración antes, después, cortes)."""
    m = medidas(entrada)
    if not m: return None, "No se pudo leer el vídeo.", None
    _w, _h, audio, dur = m
    if not audio: return None, "El vídeo no tiene audio: no hay silencios que cortar.", None
    sil = silencios(entrada, umbral, minimo, control)
    if control and control.cancelado: return None, "Cancelado.", None
    quedan = tramos_a_conservar(sil, dur)
    if not sil or len(quedan) == 0: return None, "No se encontraron silencios que cortar con esa sensibilidad.", None
    if len(quedan) > 400: return None, "Hay demasiados cortes: prueba con una sensibilidad más suave.", None
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in quedan); salida = libre(salida); tmp = salida + ".parcial.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", entrada, "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{expr}',asetpts=N/SR/TB", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp]
    rc, err = _correr(cmd, control)
    ruta, e = _cerrar(rc, err, tmp, salida, control)
    return ruta, e, ((dur, core.duration(ruta), len(quedan) - 1) if ruta else None)
