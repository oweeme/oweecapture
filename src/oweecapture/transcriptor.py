"""Motor de voz: se ejecuta con el Python del ENTORNO PROPIO donde está faster-whisper (no con el de la aplicación) y escribe una línea JSON por evento en la salida estándar:
  {"idioma": "es", "duracion": 63.2}  ·  {"p": 0.42}  ·  {"w": "hola", "ini": 1.2, "fin": 1.5}  ·  {"fin": true}
Uso: python transcriptor.py transcribir RUTA IDIOMA MODELO CARPETA_MODELOS   |   python transcriptor.py descargar MODELO CARPETA_MODELOS"""
import json, sys

def decir(**kw): print(json.dumps(kw, ensure_ascii=False), flush=True)

def modelo(nombre, carpeta):
    from faster_whisper import WhisperModel
    return WhisperModel(nombre, device="cpu", compute_type="int8", cpu_threads=3, download_root=carpeta)          # int8 y 3 hilos: rápido en CPU y deja un núcleo libre

def main(argv):
    if argv[0] == "descargar": modelo(argv[1], argv[2]); decir(listo=True); return 0
    ruta, idioma, nombre, carpeta = argv[1:5]; m = modelo(nombre, carpeta)
    segmentos, info = m.transcribe(ruta, language=idioma or None, word_timestamps=True, vad_filter=True, beam_size=1); decir(idioma=info.language, duracion=info.duration)          # vad_filter: ignora los silencios (menos «alucinaciones»)
    for s in segmentos:
        for p in (s.words or []): decir(w=p.word.strip(), ini=round(p.start, 3), fin=round(p.end, 3))
        decir(p=round(min(1.0, s.end / info.duration), 3) if info.duration else 0)
    decir(fin=True); return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
