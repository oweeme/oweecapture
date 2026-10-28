"""Transmisión en directo por RTMP (con reconexión automática): una sola codificación H.264 (tasa de datos constante) y AAC que se envía al servidor de la plataforma y, a la vez, se guarda en un MKV local (copia de seguridad; si la conexión se cae, lo emitido no se pierde).
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

def descripcion(origen_video, recorte, fps, kbps, dim, fuentes, mkv):
    """Tubería principal: vídeo → x264 (CBR, un fotograma clave cada 2 s) → h264parse → tee; audio: fuentes con su volumen + silencio (para que el mezclador no se pare) → AAC → tee. Cada `tee` alimenta el MKV local y un `appsink` («net_v», «net_a»)
    del que `Red` toma los datos para enviarlos por RTMP en OTRA tubería: así un fallo de la red nunca llega a esta (un error de la rama de red viaja por el `tee` hasta las fuentes y las para).
    `fuentes`: [(origen de GStreamer, volumen)]."""
    w, h = dim; cola_red = "queue leaky=downstream max-size-time=10000000000 max-size-buffers=0 max-size-bytes=0"
    audio = "audiotestsrc is-live=true wave=silence ! audio/x-raw,rate=48000,channels=2 ! mezcla. " + "".join(f"{o} ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! volume volume={v:.3f} ! queue ! mezcla. " for o, v in fuentes)
    return (f"matroskamux name=mux ! filesink location={mkv} "
            f"{origen_video} ! queue ! videoconvert ! {recorte}videorate ! video/x-raw,framerate={fps}/1 ! videoscale ! video/x-raw,width={w},height={h} ! "
            f"x264enc tune=zerolatency speed-preset=veryfast bitrate={kbps} vbv-buf-capacity=2000 option-string=vbv-maxrate={kbps} key-int-max={fps * 2} ! video/x-h264,profile=main ! h264parse ! video/x-h264,stream-format=avc,alignment=au ! tee name=tv "
            f"tv. ! queue ! mux. tv. ! {cola_red} ! appsink name=net_v emit-signals=true drop=true max-buffers=300 sync=false "
            f"audiomixer name=mezcla ! audioconvert ! avenc_aac bitrate=128000 ! aacparse ! tee name=ta ta. ! queue ! mux. ta. ! {cola_red} ! appsink name=net_a emit-signals=true drop=true max-buffers=300 sync=false {audio}")

import threading

class Red:
    """El envío por RTMP, en una tubería propia (appsrc → flvmux → rtmp2sink) alimentada con lo que sale de los `appsink` de la tubería principal. Si la conexión falla, esa tubería se tira y se crea otra tras una espera creciente (1, 2, 4, 8, 15 y 30 s) sin tocar la
    principal (el MKV local sigue escribiéndose). Cada conexión empieza en un fotograma clave y con las marcas de tiempo a cero, como un directo nuevo.
    Si nunca llegó a conectar (clave o servidor mal puestos) se rinde pronto y avisa; si ya había conectado, sigue intentándolo hasta `max_intentos` seguidos. `al_estado(texto)` cuenta qué pasa; `al_perdido(texto)` se llama si se rinde."""
    ESPERAS = [1, 2, 4, 8, 15, 30]
    FIRME = 3              # segundos sin error para dar la conexión por buena (un servidor que rechaza la clave o la dirección lo hace en milisegundos o en 1–2 s)

    def __init__(self, pipe, url, al_estado=None, al_perdido=None, max_sin_conectar=3, max_intentos=40):
        import gi; gi.require_version("Gst", "1.0")
        from gi.repository import GLib, Gst
        self.Gst, self.GLib = Gst, GLib; self.url = url; self.al_estado = al_estado or (lambda t: None); self.al_perdido = al_perdido or (lambda t: None); self.max_sin_conectar = max_sin_conectar; self.max_intentos = max_intentos
        self.red = None; self.av = self.aa = None; self.caps = {"v": None, "a": None}; self.listo = False; self.base = None; self.lock = threading.Lock()
        self.intento = 0; self.reconexiones = 0; self.caidas = 0; self.alguna_vez = False; self.cerrada = False; self.gen = 0; self.temporizador = None; self.estado = ""; self.enviados = 0
        for nombre, tipo in (("net_v", "v"), ("net_a", "a")): pipe.get_by_name(nombre).connect("new-sample", self._muestra, tipo)

    def _decir(self, texto): self.estado = texto; self.al_estado(texto)

    def _muestra(self, sink, tipo):
        """Corre en el hilo de la tubería principal: copia cada buffer a la tubería de red (si hay una conectada), con la hora puesta a cero en el primer fotograma clave. Nunca falla ni bloquea."""
        Gst = self.Gst; sample = sink.emit("pull-sample")
        if sample is None: return Gst.FlowReturn.OK
        self.caps[tipo] = sample.get_caps(); buf = sample.get_buffer()
        with self.lock:
            src = self.av if tipo == "v" else self.aa
            if not self.listo or src is None or buf.pts == Gst.CLOCK_TIME_NONE: return Gst.FlowReturn.OK
            if self.base is None:
                if tipo != "v" or buf.has_flags(Gst.BufferFlags.DELTA_UNIT): return Gst.FlowReturn.OK          # se empieza en un fotograma clave de vídeo
                self.base = buf.pts
            if buf.pts < self.base: return Gst.FlowReturn.OK
            nb = buf.copy(); nb.pts = buf.pts - self.base; nb.dts = max(0, buf.dts - self.base) if buf.dts != Gst.CLOCK_TIME_NONE and buf.dts >= self.base else Gst.CLOCK_TIME_NONE
            src.emit("push-buffer", nb); self.enviados += 1
        return Gst.FlowReturn.OK

    def conectar(self):
        """Monta la tubería de red. Devuelve False (para que GLib no repita el temporizador)."""
        Gst = self.Gst; self.temporizador = None
        if self.cerrada: return False
        if not (self.caps["v"] and self.caps["a"]): self.temporizador = self.GLib.timeout_add(500, self.conectar); return False             # aún no ha salido ni un buffer de cada tipo
        pipe = Gst.Pipeline.new(None)
        def appsrc(nombre, caps):
            a = Gst.ElementFactory.make("appsrc", nombre); a.set_property("caps", caps); a.set_property("is-live", True); a.set_property("format", Gst.Format.TIME); a.set_property("max-time", 10_000_000_000); a.set_property("max-bytes", 0); a.set_property("leaky-type", 2); return a
        av, aa = appsrc("av", self.caps["v"]), appsrc("aa", self.caps["a"]); fm = Gst.ElementFactory.make("flvmux", None); fm.set_property("streamable", True)
        qo = Gst.ElementFactory.make("queue", None); [qo.set_property(k, v) for k, v in (("max-size-time", 10_000_000_000), ("max-size-buffers", 0), ("max-size-bytes", 0))]
        sink = Gst.ElementFactory.make("rtmp2sink", None); sink.set_property("location", self.url)
        for e in (av, aa, fm, qo, sink): pipe.add(e)
        av.link_pads("src", fm, "video"); aa.link_pads("src", fm, "audio"); fm.link(qo); qo.link(sink)
        self.gen += 1; g = self.gen; bus = pipe.get_bus(); bus.add_signal_watch(); bus.connect("message", lambda b, m: self._mensaje(g, m))
        with self.lock: self.red, self.av, self.aa, self.base, self.listo = pipe, av, aa, None, True
        pipe.set_state(Gst.State.PLAYING); self._decir("Conectando…" if not self.alguna_vez else "Reconectando…"); self.GLib.timeout_add_seconds(self.FIRME, lambda: self._firme(g)); return False

    def _mensaje(self, gen, m):
        if gen == self.gen and m.type == self.Gst.MessageType.ERROR: self.fallo(m.parse_error()[0].message)

    def _firme(self, gen):
        """`FIRME` segundos sin error: se da por conectado."""
        if gen == self.gen and not self.cerrada and self.red is not None and self.estado.startswith(("Conectando", "Reconectando")):
            self.alguna_vez = True; self.intento = 0; self._decir("Conectado" if not self.reconexiones else f"Conectado (reconexiones: {self.reconexiones})")
        return False

    def _tirar(self):
        """Descarta la tubería de red (la principal no se toca)."""
        with self.lock: red, self.red, self.av, self.aa, self.listo = self.red, None, None, None, False
        if red is not None: red.get_bus().remove_signal_watch(); red.set_state(self.Gst.State.NULL)

    def fallo(self, motivo):
        """La conexión falló: se tira la tubería de red y se programa otro intento (o se rinde)."""
        if self.cerrada or self.red is None: return
        self._tirar(); self.intento += 1; self.caidas += 1
        if (not self.alguna_vez and self.intento >= self.max_sin_conectar) or self.intento > self.max_intentos:
            self.cerrada = True; self._decir("Sin conexión"); self.al_perdido(motivo); return
        espera = self.ESPERAS[min(self.intento - 1, len(self.ESPERAS) - 1)]; self.reconexiones += 1 if self.alguna_vez else 0
        self._decir(f"Sin conexión: reintento en {espera} s (intento {self.intento})"); self.temporizador = self.GLib.timeout_add_seconds(espera, self.conectar)

    def cerrar(self):
        """El directo terminó: ya no se reintenta y se corta la conexión."""
        self.cerrada = True
        if self.temporizador: self.GLib.source_remove(self.temporizador); self.temporizador = None
        self._tirar()
