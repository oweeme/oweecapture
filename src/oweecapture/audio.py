"""Mezcla de audio al guardar: el sistema y el micrófono se graban como pistas separadas y aquí se les aplica el volumen de cada una y, al micrófono, la reducción de ruido, antes de juntarlas en una sola pista AAC.
Sin interfaz ni GStreamer: solo construye los argumentos de ffmpeg, así se puede probar con medidas (volumedetect) sin grabar nada."""
import subprocess

# Reducción de ruido del micrófono: filtro de paso alto (quita el retumbo y el golpeteo de la mesa) + `afftdn` (resta el ruido de fondo, que sigue aprendiendo con `tn=1`).
# 1 = suave (ventilador, zumbido leve): baja el ruido de fondo unos 7 dB; 2 = fuerte: además una puerta de ruido que cierra el micrófono entre frases (medido: de -59 a -90 dB con ruido rosa realista) a costa de poder cortar finales de palabra muy bajos.
RUIDO = {1: "highpass=f=80,afftdn=nr=12:nf=-45:tn=1", 2: "highpass=f=100,afftdn=nr=24:nf=-40:tn=1,agate=threshold=0.01:ratio=3:attack=10:release=250"}

def pistas(ruta):
    """Número de pistas de audio del archivo (0 si no hay o ffprobe falla)."""
    try: return len(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", ruta], capture_output=True, text=True, timeout=20).stdout.split())
    except (OSError, subprocess.TimeoutExpired): return 0

def filtro(fuentes, n, vol_sistema=1.0, vol_mic=1.0, ruido=0):
    """`fuentes`: qué es cada pista del archivo en orden (p. ej. ["sistema", "mic"]); `n`: cuántas pistas tiene de verdad (si no coincide se ignora el orden y se mezclan todas sin ajustes).
    Devuelve el `-filter_complex` que deja una sola pista en `[aout]`, o None si basta con copiarla tal cual (un solo origen, volumen normal y sin reducción de ruido)."""
    if n <= 0: return None
    if len(fuentes) != n: fuentes = ["sistema"] * n; vol_sistema = 1.0; ruido = 0
    ajustes = []
    for i, f in enumerate(fuentes):
        v = vol_mic if f == "mic" else vol_sistema; fx = []
        if f == "mic" and ruido in RUIDO: fx.append(RUIDO[ruido])
        if abs(v - 1) > 0.01: fx.append(f"volume={v:.3f}")
        ajustes.append(",".join(fx))
    if n == 1 and not ajustes[0]: return None
    cad = [f"[0:a:{i}]" + (a or "anull") + f"[a{i}]" for i, a in enumerate(ajustes)]
    if n == 1: cad.append("[a0]alimiter=limit=0.95[aout]")
    else: cad.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,alimiter=limit=0.95[aout]")      # el limitador evita que la suma de las dos pistas sature
    return ";".join(cad)

def argumentos(ruta, fuentes, vol_sistema=1.0, vol_mic=1.0, ruido=0):
    """Argumentos de ffmpeg para el audio de salida: el vídeo ya está en `-c:v copy` fuera de aquí. Sin ajustes, las pistas pasan a AAC tal cual (si hay varias se mezclan igualmente en una)."""
    n = pistas(ruta)
    if n == 0: return ["-an"]
    f = filtro(fuentes, n, vol_sistema, vol_mic, ruido) if n > 1 or vol_sistema != 1 or vol_mic != 1 or ruido else None
    if n > 1 and f is None: f = filtro(fuentes, n)                       # sin ajustes pero con varias pistas: se mezclan
    if f is None: return ["-map", "0:v", "-map", "0:a:0", "-c:a", "aac", "-b:a", "160k"]
    return ["-filter_complex", f, "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
