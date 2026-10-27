"""Transmisión en directo por RTMP: una sola codificación H.264 (tasa de datos constante) y AAC que se envía al servidor de la plataforma y, a la vez, se guarda en un MKV local (copia de seguridad; si la conexión se cae, lo emitido no se pierde).
Sin interfaz ni portal: solo construye la tubería de GStreamer y los datos de cada plataforma, así se prueba contra un receptor local. La clave de transmisión es un secreto: `ocultar` la quita de cualquier texto que vaya a mostrarse o guardarse en el registro."""

# (id, nombre, servidor RTMP). TikTok da su servidor y su clave en su página de transmisión (hace falta cumplir sus requisitos); en «otro» se escribe a mano.
PLATAFORMAS = [("youtube", "YouTube", "rtmp://a.rtmp.youtube.com/live2"), ("tiktok", "TikTok", ""), ("twitch", "Twitch", "rtmp://live.twitch.tv/app"), ("otro", "Otro servidor", "")]
# (id, texto, alto del vídeo, kbps). Con 4 núcleos, 720p a 3000 kbps usó ~1,6 núcleos con mucho movimiento; 1080p pide bastante más.
CALIDADES = [("ligera", "480p · 1500 kbps (equipo justo o conexión lenta)", 480, 1500), ("720", "720p · 3000 kbps (recomendada)", 720, 3000), ("1080", "1080p · 5000 kbps (equipo potente)", 1080, 5000)]

def destino(url, clave):
    """URL completa que se entrega a `rtmp2sink`, o ValueError con un mensaje legible si los datos no valen."""
    url = (url or "").strip().rstrip("/"); clave = (clave or "").strip()
    if not url.lower().startswith(("rtmp://", "rtmps://")): raise ValueError("El servidor debe empezar por rtmp:// o rtmps://")
    if not clave: raise ValueError("Falta la clave de transmisión")
    return f"{url}/{clave}"

def ocultar(texto, clave):
    """Quita la clave de un texto (mensajes de error de GStreamer pueden incluir la URL completa)."""
    return texto.replace(clave, "***") if clave else texto

def dimensiones(ancho, alto, altura):
    """(ancho, alto) de salida: el alto pedido (sin ampliar nunca) y el ancho proporcional; ambos pares, porque H.264 lo exige."""
    h = min(altura, alto) & ~1; return (max(2, int(ancho * h / alto / 2 + 0.5) * 2), max(2, h))

def descripcion(origen_video, recorte, fps, kbps, dim, fuentes, mkv, url, aviso_calidad=None):
    """Tubería: vídeo → x264 (CBR, un fotograma clave cada 2 s) → h264parse → tee (MKV local + FLV/RTMP); audio: fuentes con su volumen + silencio (para que el mezclador no se pare) → AAC → tee.
    `fuentes`: [(origen de GStreamer, volumen)]. La rama de red lleva una cola grande: si la red se atasca un rato, el MKV local no se detiene."""
    w, h = dim
    audio = "audiotestsrc is-live=true wave=silence ! audio/x-raw,rate=48000,channels=2 ! mezcla. " + "".join(f"{o} ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! volume volume={v:.3f} ! queue ! mezcla. " for o, v in fuentes)
    return (f"flvmux name=fm streamable=true ! queue max-size-time=10000000000 max-size-buffers=0 max-size-bytes=0 ! rtmp2sink location={url} "
            f"matroskamux name=mux ! filesink location={mkv} "
            f"{origen_video} ! queue ! videoconvert ! {recorte}videorate ! video/x-raw,framerate={fps}/1 ! videoscale ! video/x-raw,width={w},height={h} ! "
            f"x264enc tune=zerolatency speed-preset=veryfast bitrate={kbps} vbv-buf-capacity=2000 option-string=vbv-maxrate={kbps} key-int-max={fps * 2} ! video/x-h264,profile=main ! h264parse ! video/x-h264,stream-format=avc,alignment=au ! tee name=tv "
            f"tv. ! queue ! mux. tv. ! queue max-size-time=10000000000 max-size-buffers=0 max-size-bytes=0 ! fm. "
            f"audiomixer name=mezcla ! audioconvert ! avenc_aac bitrate=128000 ! aacparse ! tee name=ta ta. ! queue ! mux. ta. ! queue max-size-time=10000000000 max-size-buffers=0 max-size-bytes=0 ! fm. {audio}")
