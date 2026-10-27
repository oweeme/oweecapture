"""Efectos sobre la grabación ya terminada: zoom que sigue al cursor y halo en el puntero. Sin interfaz ni Qt: recibe la pista del cursor (muestras con su hora) y reescribe el MP4 con ffmpeg.
Las posiciones del cursor se guardan durante la grabación en coordenadas de la pantalla y aquí se pasan a píxeles del vídeo (escala del flujo del portal y recorte de la zona elegida)."""
import bisect, math, os, shutil, struct, subprocess, tempfile, zlib
from . import core

HALO = 48                  # lado del halo en píxeles del vídeo
ZONA_MUERTA = 0.3          # el zoom no se mueve mientras el cursor esté en el 60 % central de la ventana ampliada
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

def camara(p, ancho, alto, zoom, fps, duracion):
    """Un cuadro por fotograma: (t, esquina x, esquina y de la ventana ampliada, cursor x, cursor y). La ventana solo se mueve cuando el cursor sale de su zona central y lo hace con suavizado."""
    ts = [m[0] for m in p]; cw, ch = ancho / zoom, alto / zoom; cx, cy = ancho / 2, alto / 2; out = []
    def cursor(t):
        i = bisect.bisect_right(ts, t)
        if i == 0: return p[0][1], p[0][2]
        if i == len(p): return p[-1][1], p[-1][2]
        (t0, x0, y0), (t1, x1, y1) = p[i - 1], p[i]; f = (t - t0) / (t1 - t0) if t1 > t0 else 0
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    cx, cy = cursor(0)
    for n in range(int(duracion * fps) + 1):
        t = n / fps; x, y = cursor(t); mx, my = cw * ZONA_MUERTA, ch * ZONA_MUERTA
        tx = x - mx if x > cx + mx else x + mx if x < cx - mx else cx; ty = y - my if y > cy + my else y + my if y < cy - my else cy
        cx += (tx - cx) * SUAVIZADO; cy += (ty - cy) * SUAVIZADO
        out.append((t, min(max(cx - cw / 2, 0), ancho - cw), min(max(cy - ch / 2, 0), alto - ch), x, y))
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

def filtro(zoom, halo, ancho, alto):
    """Cadena de filtros de ffmpeg: las órdenes de `sendcmd` mueven el halo y la ventana ampliada fotograma a fotograma."""
    f = "[0:v]sendcmd=f=ordenes.txt[a]"; ultimo = "a"
    if halo: f += ";[a][1:v]overlay@h=x=0:y=0:shortest=1:format=auto[b]"; ultimo = "b"
    if zoom > 1: f += f";[{ultimo}]crop@c=w={int(ancho / zoom) & ~1}:h={int(alto / zoom) & ~1}:x=0:y=0,scale={ancho}:{alto}:flags=lanczos,format=yuv420p[s]"; ultimo = "s"
    else: f += f";[{ultimo}]format=yuv420p[s]"; ultimo = "s"
    return f, ultimo

def aplicar(entrada, p, zoom=2.0, halo=True, crf=18, preset="veryfast"):
    """Reescribe `entrada` (MP4) con zoom y/o halo siguiendo la pista `p`. Escribe en un archivo temporal y solo reemplaza al original si todo salió bien; devuelve True si se aplicó."""
    if len(p) < 2 or not (zoom > 1 or halo) or not core.have("ffmpeg"): return False
    m = medidas(entrada)
    if not m or m[3] <= 0: return False
    ancho, alto, fps, dur = m; fps = min(max(fps, 1), 60); cam = camara(p, ancho, alto, zoom, fps, dur)
    tmp = tempfile.mkdtemp(prefix="efectos-", dir=os.path.dirname(entrada)); salida = os.path.join(tmp, "salida.mp4")
    try:
        lineas = []
        for t, x, y, cx, cy in cam:
            o = []
            if zoom > 1: o += [f"crop@c x {x:.1f}", f"crop@c y {y:.1f}"]
            if halo: o += [f"overlay@h x {cx - HALO / 2:.1f}", f"overlay@h y {cy - HALO / 2:.1f}"]
            lineas.append(f"{t:.3f} " + ", ".join(o) + ";")
        open(os.path.join(tmp, "ordenes.txt"), "w").write("\n".join(lineas))
        ff = ["ffmpeg", "-y", "-loglevel", "error", "-i", entrada] + (["-loop", "1", "-i", os.path.join(tmp, "halo.png")] if halo else [])
        if halo: png_halo(os.path.join(tmp, "halo.png"))
        graf, etiqueta = filtro(zoom, halo, ancho, alto)
        ff += ["-filter_complex", graf, "-map", f"[{etiqueta}]", "-map", "0:a?", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "copy", "-movflags", "+faststart", "-shortest", salida]
        r = subprocess.run(ff, capture_output=True, text=True, timeout=int(max(600, dur * 4)), cwd=tmp)
        if r.returncode != 0 or not os.path.exists(salida) or os.path.getsize(salida) < 1000: return False
        os.replace(salida, entrada); return True
    except (OSError, subprocess.TimeoutExpired): return False
    finally: shutil.rmtree(tmp, ignore_errors=True)
