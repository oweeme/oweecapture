"""Clips de los últimos segundos de una grabación o un directo en curso: se corta del MKV que ya se está escribiendo (sin recodificar el vídeo y sin parar nada), así que no añade CPU ni una segunda captura.
Sin interfaz: recibe el archivo y cuánto lleva grabado; el corte empieza en el fotograma clave anterior (hay uno cada 2 s), por eso se retrocede un segundo de más."""
import os, subprocess
from . import audio

OPCIONES = [15, 30, 60, 120]          # segundos hacia atrás que se pueden elegir

def recortar(mkv, transcurrido, segundos, salida, mezcla=None):
    """Guarda en `salida` (MP4) los últimos `segundos` de `mkv`, que lleva `transcurrido` s escritos. `mezcla`: (fuentes, volumen del sistema, del micrófono, ruido) como en portal.a_mp4. Devuelve la ruta o None si no se pudo."""
    if not os.path.exists(mkv) or os.path.getsize(mkv) < 1000: return None
    ini = max(0.0, transcurrido - segundos - 1); os.makedirs(os.path.dirname(salida), exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ini:.2f}", "-i", mkv, "-c:v", "copy"] + audio.argumentos(mkv, *(mezcla or ([], 1.0, 1.0, 0))) + ["-movflags", "+faststart", salida], capture_output=True, text=True, timeout=300)
    return salida if r.returncode == 0 and os.path.exists(salida) and os.path.getsize(salida) > 1000 else None
