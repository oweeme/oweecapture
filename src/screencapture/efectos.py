"""Efectos sobre la grabación ya terminada: zoom a demanda (se acerca y se aleja con una tecla durante la grabación y sigue al cursor mientras está cerca) y halo en el puntero. Sin interfaz ni Qt: recibe la pista del cursor (muestras con su hora) y reescribe el MP4 con ffmpeg.
Las posiciones del cursor se guardan durante la grabación en coordenadas de la pantalla y aquí se pasan a píxeles del vídeo (escala del flujo del portal y recorte de la zona elegida)."""
import bisect, math, os, shutil, struct, subprocess, tempfile, zlib
from . import core

HALO = 48                  # lado del halo en píxeles del vídeo
TRANSICION = 0.4         # segundos que tarda el zoom en entrar y en salir
ZONA_MUERTA = 0.3          # la ventana ampliada no se mueve mientras el cursor esté en su 60 % central
SUAVIZADO = 0.12           # fracción del camino que recorre la cámara en cada fotograma (más bajo = más suave)

def pista(muestras, meta):
    """[[ms, x, y], …] de la pantalla → [(segundos de vídeo, x, y)] en píxeles del vídeo. Se descartan las muestras anteriores al inicio o tomadas en pausa y se restan las pausas
    (el vídeo no las contiene). `meta`: t0, pausas [(inicio, fin)] en hora de reloj, pantalla (x, y, ancho, alto lógicos), flujo (ancho, alto del portal) y recorte (x, y, ancho, alto) o None."""
    px, py, pw, ph = meta["pantalla"]; fx = meta["flujo"][0] / pw; fy = meta["flujo"][1] / ph; rx, ry = meta["recorte"][:2] if meta.get("recorte") else (0, 0)
    fin = []
    for ms, x, y in sorted(muestras):
        w = ms / 1000
        if w < meta["t0"] or any(a <= w < b for a, b in meta["pausas"]): continue
        fin.append((w - meta["t0"] - sum(b - a for a, b in meta["pausas"] if b <= w), (x - px) * fx - rx, (y - py) * fy - ry))
    return fin

def _suave(x): x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

def nivel(t, tramos, zoom):
    """Zoom en el segundo `t`: 1 sin zoom y `zoom` dentro de un tramo, con entrada y salida suaves. `tramos`: [(inicio, fin o None si sigue hasta el final)] sin solaparse."""
    return 1 + (zoom - 1) * sum(_suave((t - a) / TRANSICION) - (_suave((t - b) / TRANSICION) if b is not None else 0) for a, b in tramos)

def expr_zoom(zoom, tramos):
    """La misma función que `nivel`, escrita como expresión de ffmpeg en `t` (el filtro `scale` la evalúa en cada fotograma)."""
    def s(x): c = f"min(max({x},0),1)"; return f"({c}*{c}*(3-2*{c}))"
    return f"(1+{zoom - 1:g}*(" + "+".join(s(f"(t-{a:.3f})/{TRANSICION}") + (f"-{s(f'(t-{b:.3f})/{TRANSICION}')}" if b is not None else "") for a, b in tramos) + "))"

def camara(p, ancho, alto, zoom, fps, duracion, tramos):
    """Un cuadro por fotograma: (t, nivel de zoom, esquina x e y del recorte sobre el vídeo ya ampliado, cursor x, cursor y). Al acercar, la ventana nace centrada en el cursor y solo se mueve cuando el cursor sale de su zona central, con suavizado."""
    ts = [m[0] for m in p]; out = []
    def cursor(t):
        i = bisect.bisect_right(ts, t)
        if i == 0: return p[0][1], p[0][2]
        if i == len(p): return p[-1][1], p[-1][2]
        (t0, x0, y0), (t1, x1, y1) = p[i - 1], p[i]; f = (t - t0) / (t1 - t0) if t1 > t0 else 0
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    cx, cy = cursor(0)
    for n in range(int(duracion * fps) + 1):
        t = n / fps; x, y = cursor(t); z = nivel(t, tramos, zoom); cw, ch = ancho / z, alto / z
        if z < 1.01: cx, cy = x, y
        else:
            mx, my = cw * ZONA_MUERTA, ch * ZONA_MUERTA
            tx = x - mx if x > cx + mx else x + mx if x < cx - mx else cx; ty = y - my if y > cy + my else y + my if y < cy - my else cy
            cx += (tx - cx) * SUAVIZADO; cy += (ty - cy) * SUAVIZADO
        out.append((t, z, min(max((cx - cw / 2) * z, 0), ancho * z - ancho), min(max((cy - ch / 2) * z, 0), alto * z - alto), x, y))
    return out

def png_halo(ruta, lado=HALO):
    """Anillo amarillo con relleno suave y transparencia, escrito a mano (PNG RGBA) para no depender de ninguna biblioteca de imágenes."""
    filas = []
    for y in range(lado):
        f = b"\0"
        for x in range(lado):
            d = math.hypot(x - lado / 2 + .5, y - lado / 2 + .5); a = 0
            if d < lado / 2: a = int(66 * (1 - d / (lado / 2)) + (90 if d > lado / 2 - 5 else 0))
            f += bytes([255, 214, 10, min(255, a)])
        filas.append(f)
    def trozo(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    with open(ruta, "wb") as f: f.write(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0)) + trozo(b"IDAT", zlib.compress(b"".join(filas))) + trozo(b"IEND", b""))

def medidas(ruta):
    """(ancho, alto, fotogramas por segundo, duración) del primer vídeo del archivo, o None si ffprobe no puede leerlo."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", ruta], capture_output=True, text=True, timeout=20).stdout.strip().split(",")
        n, d = r[2].split("/"); return int(r[0]), int(r[1]), float(n) / float(d or 1), core.duration(ruta)
    except (OSError, ValueError, IndexError, ZeroDivisionError, subprocess.TimeoutExpired): return None

def filtro(zoom, halo, ancho, alto, tramos):
    """Cadena de filtros de ffmpeg: `sendcmd` mueve el halo y el recorte fotograma a fotograma; `scale` amplía según `expr_zoom` y `crop` toma la ventana del tamaño original."""
    f = "[0:v]sendcmd=f=ordenes.txt[a]"; ultimo = "a"
    if halo: f += ";[a][1:v]overlay@h=x=0:y=0:shortest=1:format=auto[b]"; ultimo = "b"
    if tramos: f += f";[{ultimo}]scale=w='trunc(iw*{expr_zoom(zoom, tramos)}/2)*2':h='trunc(ih*{expr_zoom(zoom, tramos)}/2)*2':eval=frame:flags=bilinear,crop@c=w={ancho}:h={alto}:x=0:y=0,format=yuv420p[s]"
    else: f += f";[{ultimo}]format=yuv420p[s]"
    return f, "s"

def aplicar(entrada, p, zoom=2.0, halo=True, crf=18, preset="veryfast", tramos=()):
    """Reescribe `entrada` (MP4) con el zoom de los `tramos` (segundos de vídeo) y/o el halo, siguiendo la pista `p`. Escribe en un archivo temporal y solo reemplaza al original si todo salió bien; devuelve True si se aplicó."""
    tramos = [(a, b) for a, b in tramos] if zoom > 1 else []
    if len(p) < 2 or not (tramos or halo) or not core.have("ffmpeg"): return False
    m = medidas(entrada)
    if not m or m[3] <= 0: return False
    ancho, alto, fps, dur = m; fps = min(max(fps, 1), 60); cam = camara(p, ancho, alto, zoom, fps, dur, tramos)
    tmp = tempfile.mkdtemp(prefix="efectos-", dir=os.path.dirname(entrada)); salida = os.path.join(tmp, "salida.mp4")
    try:
        lineas = []
        for t, _z, x, y, cx, cy in cam:
            o = []
            if halo: o += [f"overlay@h x {cx - HALO / 2:.1f}", f"overlay@h y {cy - HALO / 2:.1f}"]
            if tramos: o += [f"crop@c x {x:.1f}", f"crop@c y {y:.1f}"]
            lineas.append(f"{t:.3f} " + ", ".join(o) + ";")
        open(os.path.join(tmp, "ordenes.txt"), "w").write("\n".join(lineas))
        ff = ["ffmpeg", "-y", "-loglevel", "error", "-i", entrada] + (["-loop", "1", "-i", os.path.join(tmp, "halo.png")] if halo else [])
        if halo: png_halo(os.path.join(tmp, "halo.png"))
        graf, etiqueta = filtro(zoom, halo, ancho, alto, tramos)
        ff += ["-filter_complex", graf, "-map", f"[{etiqueta}]", "-map", "0:a?", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "copy", "-movflags", "+faststart", "-shortest", salida]
        r = subprocess.run(ff, capture_output=True, text=True, timeout=int(max(600, dur * 6)), cwd=tmp)
        if r.returncode != 0 or not os.path.exists(salida) or os.path.getsize(salida) < 1000: return False
        os.replace(salida, entrada); return True
    except (OSError, subprocess.TimeoutExpired): return False
    finally: shutil.rmtree(tmp, ignore_errors=True)
