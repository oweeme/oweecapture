"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("OWEECAPTURE_SIN_ATAJOS", "1")          # crear la ventana en una prueba no debe registrar atajos globales en el KDE del usuario
from oweecapture import audio, clips, core, directo, efectos, entrada, herramientas, i18n, inicio, ruido_vivo, subtitulos

class Calidades(unittest.TestCase):
    def test_perfiles(self): self.assertEqual(set(core.QUALITY), {"whatsapp", "youtube", "maxima"})
    def test_youtube_y_maxima_no_se_recomprimen(self): self.assertIsNone(core.QUALITY["youtube"][2]); self.assertIsNone(core.QUALITY["maxima"][2])
    def test_whatsapp_reduce_a_720p_con_calidad_que_no_pixela(self):
        r = core.QUALITY["whatsapp"][2]; self.assertEqual(r["height"], 720); self.assertLessEqual(r["crf"], 24)      # crf 27 (versión anterior) dejaba el texto borroso
    def test_maxima_es_mas_fiel_que_youtube(self): self.assertLess(core.QUALITY["maxima"][1], core.QUALITY["youtube"][1])
    def test_config_por_defecto_valida(self): self.assertIn(core.load_cfg()["quality"], core.QUALITY)
    def test_nombres_de_versiones_anteriores(self):
        with tempfile.TemporaryDirectory() as d:
            viejo = core.CFG; core.CFG = os.path.join(d, "config.json")
            try:
                for antes, ahora in (("alta", "maxima"), ("original", "maxima"), ("buena", "youtube"), ("media", "whatsapp"), ("ligera", "whatsapp"), ("rara", "whatsapp")):
                    open(core.CFG, "w").write(json.dumps({"quality": antes})); self.assertEqual(core.load_cfg()["quality"], ahora, antes)
            finally: core.CFG = viejo

class Textos(unittest.TestCase):
    def test_marcadores(self): self.assertEqual(i18n._("Monitor {0}", 2), "Monitor 2")
    def test_texto_desconocido_se_devuelve_igual(self): self.assertEqual(i18n._("texto que no existe"), "texto que no existe")
    def test_catalogos_conservan_marcadores(self):
        import json, glob, re
        ph = lambda s: sorted(re.findall(r"\{\d+[^}]*\}|%s", s))
        for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "locales", "[a-z]*.json")):
            if os.path.basename(f).startswith("_"): continue
            for k, v in json.load(open(f, encoding="utf-8")).items(): self.assertEqual(ph(k), ph(v), (f, k))

class Archivos(unittest.TestCase):
    def test_stamp(self): self.assertRegex(core.stamp(), r"^\d{8}-\d{6}$")
    def test_mux_sin_ffmpeg_conserva_el_video(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "video.mkv"); open(v, "wb").write(b"x" * 2000); out = os.path.join(d, "salida.mp4")
            real = shutil.which; core.shutil.which = lambda p: None if p == "ffmpeg" else real(p)
            try: r = core.mux(v, [], out)
            finally: core.shutil.which = real
            self.assertTrue(os.path.exists(r)); self.assertTrue(r.endswith(".mkv"))

class Efectos(unittest.TestCase):
    META = {"t0": 100.0, "pausas": [(102.0, 103.0)], "pantalla": (0, 0, 1000, 500), "flujo": (2000, 1000), "recorte": (200, 100, 800, 600)}
    def test_pista_pasa_a_pixeles_del_video_y_resta_pausas(self):
        m = [[99_000, 500, 250], [101_000, 500, 250], [102_500, 600, 300], [104_000, 700, 350]]       # la 1.ª es anterior al inicio; la 3.ª cae en la pausa
        self.assertEqual(efectos.pista(m, self.META), [(1.0, 800.0, 400.0), (3.0, 1200.0, 600.0)])
    def test_nivel_de_zoom_entra_y_sale_suave(self):
        tr = [(2.0, 5.0)]; self.assertEqual(efectos.nivel(1, tr, 2), 1); self.assertAlmostEqual(efectos.nivel(3, tr, 2), 2); self.assertAlmostEqual(efectos.nivel(2.2, tr, 2), 1.5); self.assertEqual(efectos.nivel(7, tr, 2), 1)
        self.assertAlmostEqual(efectos.nivel(9, [(2.0, None)], 2), 2)           # sin fin: sigue acercado hasta el final
    def test_expresion_de_ffmpeg_coincide_con_nivel(self):
        tr = [(1.0, 3.0), (4.0, None)]
        for t in (0, 1.1, 2, 3.2, 3.9, 4.2, 6):
            v = eval(efectos.expr_zoom(2.5, tr), {"min": min, "max": max, "t": t}); self.assertAlmostEqual(v, efectos.nivel(t, tr, 2.5), places=6)
    def test_camara_queda_dentro_y_empieza_en_el_cursor(self):
        c = efectos.camara([(0, 900, 500), (4, 900, 500)], 1000, 600, 2, 30, 4, [(1.0, None)])
        for _t, z, x, y, _a, _b in c: self.assertTrue(0 <= x <= 1000 * z - 1000 + 1e-6 and 0 <= y <= 600 * z - 600 + 1e-6)
        z, x, y = c[-1][1:4]; self.assertAlmostEqual(z, 2); self.assertGreater(x, 800)            # ventana de 500 px centrada hacia el cursor de la derecha
    def test_camara_sigue_al_cursor_cuando_sale_de_la_zona_central(self):
        c = efectos.camara([(0, 100, 300), (3, 900, 300)], 1000, 600, 2, 30, 3, [(0.0, None)]); self.assertGreater(c[-1][2], c[10][2] + 300)
    def test_filtro_segun_lo_pedido(self):
        solo_zoom = efectos.filtro(2, False, 640, 360, [(1.0, 2.0)])[0]; self.assertIn("crop@c", solo_zoom); self.assertNotIn("overlay", solo_zoom)
        self.assertNotIn("crop", efectos.filtro(2, True, 640, 360, [])[0]); self.assertIn("overlay", efectos.filtro(2, True, 640, 360, [])[0])
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_aplicar_reescribe_el_video_con_zoom_y_halo(self):
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "v.mp4"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=2", "-pix_fmt", "yuv420p", v], check=True)
            p = [(i / 10, 40 + i * 12, 90) for i in range(21)]
            self.assertTrue(efectos.aplicar(v, p, 2.0, True, tramos=[(0.5, 1.5)])); self.assertEqual(efectos.medidas(v)[:2], (320, 180)); self.assertEqual(os.listdir(d), ["v.mp4"])
    def test_sin_pista_o_sin_efectos_no_toca_nada(self): self.assertFalse(efectos.aplicar("/no/existe.mp4", [], 2.0, True)); self.assertFalse(efectos.aplicar("/no/existe.mp4", [(0, 1, 1), (1, 2, 2)], 1, False)); self.assertFalse(efectos.aplicar("/no/existe.mp4", [(0, 1, 1), (1, 2, 2)], 2, False))     # zoom pedido pero sin tramos ni halo

class Audio(unittest.TestCase):
    def test_sin_ajustes_con_un_solo_origen_se_copia(self): self.assertIsNone(audio.filtro(["sistema"], 1)); self.assertIsNone(audio.filtro([], 0))
    def test_filtro_aplica_volumen_y_ruido_solo_al_microfono(self):
        f = audio.filtro(["sistema", "mic"], 2, 0.5, 1.5, 1)
        self.assertIn("[0:a:0]volume=0.500[a0]", f); self.assertIn("[0:a:1]" + audio.RUIDO[1] + ",volume=1.500[a1]", f); self.assertIn("amix=inputs=2:normalize=0", f); self.assertIn("alimiter", f)
    def test_si_las_pistas_no_coinciden_se_mezclan_sin_ajustes(self):
        f = audio.filtro(["sistema", "mic"], 3, 0.5, 2.0, 2); self.assertNotIn("volume", f); self.assertNotIn("afftdn", f); self.assertIn("amix=inputs=3", f)
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_volumen_y_reduccion_de_ruido_medidos(self):
        import re
        from oweecapture import portal
        def medir(f, a, b):
            r = subprocess.run(["ffmpeg", "-i", f, "-af", f"atrim={a}:{b},volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr; return float(re.search(r"mean_volume: (-?[\d.]+)", r).group(1))
        with tempfile.TemporaryDirectory() as d:
            mkv = os.path.join(d, "p.mkv")      # pista 0 = sistema (tono); pista 1 = micrófono: ruido rosa realista (≈ -59 dB) y un tono de «voz» entre los segundos 2 y 4
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=24:d=5", "-f", "lavfi", "-i", "sine=f=440:d=5,volume=0.1", "-f", "lavfi", "-i",
                            "anoisesrc=d=5:c=pink:a=0.006:r=48000[n];sine=f=250:d=5,volume='between(t,2,4)*0.25':eval=frame[t];[n][t]amix=inputs=2:normalize=0", "-map", "0:v", "-map", "1:a", "-map", "2:a",
                            "-c:v", "libx264", "-c:a", "libopus", "-pix_fmt", "yuv420p", mkv], check=True)
            def solo_mic(nombre, vol, ruido): out = os.path.join(d, nombre + ".mp4"); portal.a_mp4(mkv, out, (["sistema", "mic"], 0.0, vol, ruido)); return out
            base = solo_mic("base", 1.0, 0); mitad = solo_mic("mitad", 0.5, 0); suave = solo_mic("suave", 1.0, 1); fuerte = solo_mic("fuerte", 1.0, 2)
            self.assertAlmostEqual(medir(base, 2.3, 3.7) - medir(mitad, 2.3, 3.7), 6.0, delta=0.6)                                     # el 50 % baja 6 dB
            self.assertGreater(medir(base, 0.2, 1.8) - medir(suave, 0.2, 1.8), 4)                                                       # suave: el ruido de fondo baja
            self.assertGreater(medir(base, 0.2, 1.8) - medir(fuerte, 0.2, 1.8), 15)                                                     # fuerte: mucho más
            for f in (suave, fuerte): self.assertLess(abs(medir(base, 2.3, 3.7) - medir(f, 2.3, 3.7)), 1.5)                             # la voz casi no cambia

class Burbuja(unittest.TestCase):
    def test_opciones_invalidas_vuelven_al_valor_por_defecto(self):
        from oweecapture import burbuja
        o = burbuja.limpiar({"forma": "triangulo", "borde": "rosa", "fondo": "rojo", "brillo": 999, "contraste": -3, "espejo": 1, "otra": 1})
        self.assertEqual(o, {"forma": "circulo", "borde": "#2A9D8F", "espejo": True, "brillo": 50, "contraste": 50, "fondo": ""})
    def test_croma_deja_transparente_el_fondo_verde_y_opaco_lo_demas(self):
        import gi; gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        from oweecapture import burbuja
        Gst.init(None)
        def alfa(color):
            p = Gst.parse_launch(burbuja.descripcion(f"videotestsrc num-buffers=3 pattern=solid-color foreground-color={color}", burbuja.limpiar({"fondo": "green"})))
            p.set_state(Gst.State.PLAYING); b = p.get_by_name("sal").emit("pull-sample").get_buffer(); ok, i = b.map(Gst.MapFlags.READ); a = bytes(i.data)[(160 * 320 + 160) * 4 + 3]; b.unmap(i); p.set_state(Gst.State.NULL); return a
        self.assertEqual(alfa(0xff00ff00), 0); self.assertEqual(alfa(0xffff0000), 255)

class Directo(unittest.TestCase):
    def test_destino_valida_servidor_y_clave(self):
        self.assertEqual(directo.destino(" rtmp://a.rtmp.youtube.com/live2/ ", " abc-123 "), "rtmp://a.rtmp.youtube.com/live2/abc-123")
        for url, clave in (("http://x/live", "k"), ("", "k"), ("rtmp://x/live", "  ")): self.assertRaises(ValueError, directo.destino, url, clave)
    def test_la_clave_no_se_filtra_en_los_mensajes(self): self.assertEqual(directo.ocultar("fallo en rtmp://x/live/SECRETA", "SECRETA"), "fallo en rtmp://x/live/***"); self.assertEqual(directo.ocultar("hola", ""), "hola")
    def test_dimensiones_pares_y_sin_ampliar(self):
        self.assertEqual(directo.dimensiones(1366, 768, 720), (1280, 720)); self.assertEqual(directo.dimensiones(1366, 768, 1080), (1366, 768)); self.assertEqual(directo.dimensiones(720, 1280, 720), (406, 720))
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_emite_a_un_receptor_rtmp_y_guarda_copia_local(self):
        import gi, time, threading; gi.require_version("Gst", "1.0")
        from gi.repository import GLib, Gst
        Gst.init(None)
        if not all(Gst.ElementFactory.find(e) for e in ("x264enc", "rtmp2sink", "avenc_aac", "flvmux", "appsink", "appsrc")): self.skipTest("faltan complementos de GStreamer")
        with tempfile.TemporaryDirectory() as d:
            recibido = os.path.join(d, "recibido.flv"); local = os.path.join(d, "local.mkv")
            rx = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-listen", "1", "-f", "flv", "-i", "rtmp://127.0.0.1:19350/live/clave", "-c", "copy", recibido]); time.sleep(1)
            desc = directo.descripcion("videotestsrc is-live=true pattern=ball", "", 30, 1500, (640, 360), [("audiotestsrc is-live=true wave=sine freq=440 volume=0.3", 1.0)], local)
            p = Gst.parse_launch(desc); red = directo.Red(p, directo.destino("rtmp://127.0.0.1:19350/live", "clave")); eos = []
            p.get_bus().add_signal_watch(); p.get_bus().connect("message", lambda b, m: eos.append(1) if m.type == Gst.MessageType.EOS else None)
            p.set_state(Gst.State.PLAYING); red.conectar(); esperar(5); red.cerrar(); p.send_event(Gst.Event.new_eos()); esperar(8, lambda: eos); p.set_state(Gst.State.NULL)
            try: rx.wait(timeout=10)
            except subprocess.TimeoutExpired: rx.kill()
            def pistas(f): return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.split()
            self.assertEqual(sorted(pistas(recibido)), ["aac", "h264"]); self.assertEqual(sorted(pistas(local)), ["aac", "h264"]); self.assertGreater(core.duration(recibido), 2.5)

def esperar(segundos, hasta=None):
    """Espera `segundos` (o hasta que `hasta()` sea verdad) atendiendo los eventos de GLib desde este mismo hilo: no depende de un bucle en otro hilo, que no funciona si Qt (creado por otras pruebas) ya es dueño del contexto por defecto."""
    from gi.repository import GLib
    import time
    fin = time.time() + segundos; ctx = GLib.MainContext.default()
    while time.time() < fin and not (hasta and hasta()):
        while ctx.iteration(False): pass
        time.sleep(0.02)

class Reconexion(unittest.TestCase):
    """La rama de red se cae y se reconecta sin tocar la copia local (tubería real con fuentes de prueba y ffmpeg como receptor RTMP)."""
    def _montar(self, puerto, local, **kw):
        import gi, threading; gi.require_version("Gst", "1.0")
        from gi.repository import GLib, Gst
        Gst.init(None)
        if not all(Gst.ElementFactory.find(e) for e in ("x264enc", "rtmp2sink", "avenc_aac", "flvmux", "appsink", "appsrc")): self.skipTest("faltan complementos de GStreamer")
        url = directo.destino(f"rtmp://127.0.0.1:{puerto}/live", "k"); bucle = None
        p = Gst.parse_launch(directo.descripcion("videotestsrc is-live=true pattern=ball", "", 30, 1500, (320, 180), [("audiotestsrc is-live=true wave=sine volume=0.3", 1.0)], local))
        red = directo.Red(p, url, **kw); red.ESPERAS = [1, 1, 1, 1, 1, 1]; fatales = []; self.eos = threading.Event()
        def msg(bus, m):
            if m.type == Gst.MessageType.ERROR: fatales.append(m.parse_error()[0].message)          # la tubería principal no debe dar NINGÚN error por la red
            elif m.type == Gst.MessageType.EOS: self.eos.set()
        p.get_bus().add_signal_watch(); p.get_bus().connect("message", msg); return Gst, bucle, p, red, url, fatales
    def _parar(self, Gst, p, bucle):
        """EOS (el MKV queda cerrado) y parada; si la parada se atasca, la prueba falla en vez de colgarse."""
        import threading
        p.send_event(Gst.Event.new_eos()); esperar(8, self.eos.is_set); t = threading.Thread(target=p.set_state, args=(Gst.State.NULL,), daemon=True); t.start(); esperar(15, lambda: not t.is_alive())
        self.assertFalse(t.is_alive(), "la tubería no se detuvo")
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_se_reconecta_cuando_vuelve_el_servidor_y_la_copia_local_no_se_corta(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, "local.mkv"); Gst, bucle, p, red, url, fatales = self._montar(19352, local)
            def receptor(n): return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-listen", "1", "-f", "flv", "-i", url, "-c", "copy", os.path.join(d, n)], stderr=subprocess.DEVNULL)
            a = receptor("a.flv"); time.sleep(1); t0 = time.time(); p.set_state(Gst.State.PLAYING); red.conectar(); esperar(15, lambda: red.alguna_vez); self.assertTrue(red.alguna_vez); a.kill(); a.wait(); esperar(2); b = receptor("b.flv")          # primero hay que estar conectado de verdad
            esperar(20, lambda: os.path.exists(os.path.join(d, "b.flv")) and os.path.getsize(os.path.join(d, "b.flv")) > 20000)          # hasta 20 s para que reconecte y llegue algo al segundo receptor
            esperar(1); total = time.time() - t0; red.cerrar(); self._parar(Gst, p, bucle); esperar(1)
            try: b.wait(timeout=8)
            except subprocess.TimeoutExpired: b.kill()
            self.assertEqual(fatales, []); self.assertGreaterEqual(red.caidas, 1); self.assertGreater(os.path.getsize(os.path.join(d, "b.flv")), 20000)
            self.assertGreater(core.duration(local), total - 3, (core.duration(local), total))                          # el MKV local siguió escribiéndose todo el tiempo
    def test_se_rinde_si_nunca_conecta(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            perdidos = []; Gst, bucle, p, red, url, fatales = self._montar(19353, os.path.join(d, "local.mkv"), al_perdido=perdidos.append, max_sin_conectar=2)
            p.set_state(Gst.State.PLAYING); red.conectar(); esperar(20, lambda: perdidos)
            self._parar(Gst, p, bucle); self.assertEqual(len(perdidos), 1); self.assertFalse(red.alguna_vez); self.assertEqual(fatales, [])

class VistaPrevia(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_reproductor_muestra_salta_y_para_donde_se_le_pide(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from oweecapture import reproductor
        app = QApplication.instance() or QApplication([])
        def esperar(seg, hasta=None):
            fin = time.time() + seg
            while time.time() < fin and not (hasta and hasta()): app.processEvents(); time.sleep(0.02)
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "v.mp4"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", v], check=True)
            r = reproductor.Reproductor(silencioso=True); r.resize(400, 260); r.show(); r.cargar(v); esperar(5, lambda: r.imagen is not None and r.dur)
            self.assertIsNotNone(r.imagen); self.assertEqual((r.imagen.width(), r.imagen.height()), (640, 360)); self.assertAlmostEqual(r.dur, 6.0, delta=0.2)          # primer fotograma en pausa y duración
            r.ir_a(4.0); esperar(1); self.assertAlmostEqual(r.segundos(), 4.0, delta=0.1)
            r.ver_tramo(1.0, 2.0); esperar(5, lambda: not r.reproduciendo); self.assertFalse(r.reproduciendo); self.assertAlmostEqual(r.segundos(), 2.0, delta=0.25)          # se para al final del tramo
            r.poner_guia(0.5); esperar(0.3); self.assertEqual(r.guia, 0.5); r.poner_guia(None); self.assertIsNone(r.guia)
            r.cargar(""); self.assertIsNone(r.pipe); self.assertFalse(r.boton.isEnabled()); r.detener()

class RuidoVivo(unittest.TestCase):
    def test_la_configuracion_no_toca_la_ganancia_y_nombra_el_microfono(self):
        c = ruido_vivo.configuracion(); self.assertIn(ruido_vivo.NOMBRE, c); self.assertIn("webrtc.noise_suppression = true", c); self.assertIn("webrtc.gain_control = false", c)          # sin AGC: respeta el volumen elegido
    def test_el_expansor_de_la_opcion_fuerte_es_valido_en_gstreamer(self):
        import gi; gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None); self.assertIsNotNone(Gst.parse_launch("audiotestsrc num-buffers=1 ! audiodynamic mode=expander characteristics=soft-knee threshold=0.02 ratio=3.0 ! fakesink"))
    @unittest.skipUnless(ruido_vivo.disponible(), "sin PipeWire echo-cancel")
    def test_el_microfono_virtual_aparece_al_iniciar_y_desaparece_al_detener(self):
        import time
        l = ruido_vivo.Limpiador(); self.assertTrue(l.iniciar()); self.assertTrue(ruido_vivo._hay_nodo()); conf = l.conf; self.assertTrue(os.path.exists(conf))
        l.detener(); self.assertIsNone(l.proc); self.assertFalse(os.path.exists(conf))
        for _i in range(20):
            if not ruido_vivo._hay_nodo(): break
            time.sleep(0.25)
        self.assertFalse(ruido_vivo._hay_nodo()); l.detener()          # parar dos veces no falla

class Presentacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
    def _ev(self, tipo, p, boton=None):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        tipos = {"p": QEvent.MouseButtonPress, "m": QEvent.MouseMove, "r": QEvent.MouseButtonRelease}; b = boton or Qt.LeftButton; return QMouseEvent(tipos[tipo], QPointF(*p), QPointF(*p), b, b if tipo != "r" else Qt.NoButton, Qt.NoModifier)
    def _trazo(self, d, a, b):
        d.mousePressEvent(self._ev("p", a)); d.mouseMoveEvent(self._ev("m", ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))); d.mouseMoveEvent(self._ev("m", b)); d.mouseReleaseEvent(self._ev("r", b))
    def test_seis_herramientas_deshacer_borrar_y_clic_suelto(self):
        from oweecapture import presentacion as P
        d = P.Dibujo(); d.resize(800, 500); d.show()
        for h, (a, b) in zip(("lapiz", "resaltador", "flecha", "marco", "elipse"), (((10, 10), (200, 60)), ((10, 80), (200, 80)), ((10, 150), (200, 100)), ((300, 10), (500, 120)), ((300, 150), (500, 260)))): d.herramienta_es(h); self._trazo(d, a, b)
        d.herramienta_es("texto"); d.mousePressEvent(self._ev("p", (50, 400))); d.editor.setText("Hola"); d.editor.returnPressed.emit()
        self.assertEqual([e["t"] for e in d.trazos], ["lapiz", "resaltador", "flecha", "marco", "elipse", "texto"]); self.assertEqual(d.trazos[-1]["texto"], "Hola")
        d.herramienta_es("marco"); d.mousePressEvent(self._ev("p", (5, 5))); d.mouseReleaseEvent(self._ev("r", (5, 5))); self.assertEqual(len(d.trazos), 6)          # un clic suelto no deja una figura de tamaño cero
        d.deshacer(); self.assertEqual(len(d.trazos), 5); d.borrar(); self.assertEqual(d.trazos, []); d.close()
    def test_texto_vacio_o_cancelado_no_deja_nada_y_color_y_grosor_se_aplican(self):
        from oweecapture import presentacion as P
        d = P.Dibujo(); d.resize(400, 300); d.show(); d.herramienta_es("texto"); d.mousePressEvent(self._ev("p", (50, 50))); d.editor.setText("   "); d.editor.returnPressed.emit(); self.assertEqual(d.trazos, [])
        d.mousePressEvent(self._ev("p", (50, 50))); d.cerrar_editor(); self.assertIsNone(d.editor); d.herramienta_es("flecha"); d.color_es("#2A7FFF"); d.grosor_es(10); self._trazo(d, (10, 10), (200, 100))
        self.assertEqual((d.trazos[0]["c"], d.trazos[0]["w"]), ("#2A7FFF", 10)); d.close()
    def test_la_punta_de_la_flecha_apunta_al_destino_y_crece_con_el_grosor(self):
        from PySide6.QtCore import QPointF
        from oweecapture import presentacion as P
        a, b = QPointF(0, 0), QPointF(100, 0); c3, c10 = P.cabeza_de_flecha(a, b, 3), P.cabeza_de_flecha(a, b, 10)
        self.assertEqual(c3[0], b); self.assertGreater(abs(c10[1].y()), abs(c3[1].y())); self.assertLess(c3[1].x(), 100)

class VentanaPrincipal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
    def test_pestanas_clave_oculta_y_datos_del_autor(self):
        from PySide6.QtWidgets import QLineEdit
        from oweecapture import autor, kwin, qtapp
        v = qtapp.Ventana(); v.show()
        try:
            self.assertEqual([v.pestanas.tabText(i) for i in range(3)], ["Grabar", "Audio y cámara", "Directo"])
            self.assertEqual(v.d_clave.echoMode(), QLineEdit.Password); v.ver_clave.setChecked(True); self.assertEqual(v.d_clave.echoMode(), QLineEdit.Normal)
            v.hide(); self.assertEqual(v.d_clave.echoMode(), QLineEdit.Password); self.assertFalse(v.ver_clave.isChecked())          # al ocultar la ventana, la clave vuelve a taparse
            self.assertIn("@", autor.EMAIL); self.assertTrue(autor.WEB.startswith("https://")); self.assertTrue(autor.NOMBRE)
        finally: kwin.descargar_todo()

class ClicsYTeclas(unittest.TestCase):
    def test_atajos_y_teclas_especiales_si_el_texto_normal_no(self):
        t = entrada.Teclas("atajos"); fuera = []
        for cod, val in ((30, 1), (30, 0), (57, 1), (14, 1)): fuera.append(t.evento(cod, val))          # a, espacio, retroceso: escribir normal
        self.assertEqual(fuera, [None] * 4)
        t.evento(29, 1); self.assertEqual(t.evento(46, 1), "Ctrl + C"); t.evento(42, 1); self.assertEqual(t.evento(31, 1), "Ctrl + Shift + S"); t.evento(42, 0); t.evento(29, 0)
        self.assertEqual(t.evento(28, 1), "Intro"); self.assertEqual(t.evento(1, 1), "Esc"); self.assertEqual(t.evento(59, 1), "F1"); self.assertEqual(t.evento(105, 1), "←")
        self.assertIsNone(t.evento(46, 1)); self.assertIsNone(t.evento(46, 2))          # soltados los modificadores, la C suelta no se muestra; repetir tampoco
    def test_modos_no_y_todo(self):
        self.assertIsNone(entrada.Teclas("no").evento(30, 1)); self.assertIsNone(entrada.Teclas("no").evento(28, 1))
        t = entrada.Teclas("todo"); self.assertEqual(t.evento(30, 1), "A"); self.assertEqual(t.evento(57, 1), "Espacio"); t.evento(42, 1); self.assertEqual(t.evento(30, 1), "Shift + A")
    def test_dispositivos_clasifica_teclados_y_punteros(self):
        texto = 'N: Name="Power Button"\nH: Handlers=kbd event2 \nB: EV=3\n\nN: Name="AT keyboard"\nH: Handlers=sysrq kbd event3 leds \nB: EV=120013\n\nN: Name="Touchpad"\nH: Handlers=mouse0 event11 \nB: EV=b\n\nN: Name="Mic"\nH: Handlers=event4 \nB: EV=21\n'
        self.assertEqual(entrada.dispositivos(texto), (["/dev/input/event3"], ["/dev/input/event11"]))
    def test_lector_recibe_clics_y_teclas_de_un_dispositivo_falso(self):
        import struct, time
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "event0"); os.mkfifo(ruta); visto = []; l = entrada.Lector(lambda *a: visto.append(a), [ruta]); self.assertTrue(l.iniciar())
            w = os.open(ruta, os.O_WRONLY); ev = lambda tipo, cod, val: struct.pack("llHHi", 0, 0, tipo, cod, val)
            os.write(w, ev(1, 0x110, 1) + ev(0, 0, 0) + ev(1, 0x110, 0) + ev(1, 0x111, 1) + ev(1, 29, 1) + ev(1, 46, 1) + ev(2, 0, 5)); time.sleep(0.8); l.detener(); os.close(w)
            self.assertEqual(visto, [("clic", "izquierdo", True), ("clic", "izquierdo", False), ("clic", "derecho", True), ("tecla", 29, 1), ("tecla", 46, 1)])          # el evento de movimiento (tipo 2) se ignora
        self.assertFalse(entrada.Lector(lambda *a: None, ["/no/existe"]).iniciar())          # sin permiso o sin dispositivos: False
    def test_ondas_y_teclas_nacen_crecen_y_terminan(self):
        from oweecapture import efectos_pantalla as E
        self.assertLess(E.onda(0)[0], E.onda(0.5)[0]); self.assertGreater(E.onda(0)[1], E.onda(0.9)[1]); self.assertIsNone(E.onda(1.0))
        self.assertEqual(E.opacidad_tecla(0.2), 1.0); self.assertLess(E.opacidad_tecla(E.DURACION_TECLA - 0.1), 1.0); self.assertIsNone(E.opacidad_tecla(E.DURACION_TECLA))
    def test_la_superposicion_pinta_una_onda_y_se_apaga_sola(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QPointF
        from PySide6.QtWidgets import QApplication, QWidget
        from oweecapture import efectos_pantalla as E
        QApplication.instance() or QApplication([]); w = E.Superposicion(); w.resize(400, 300); w.show(); w.clic(QPointF(200, 150), "izquierdo"); w.tecla("Ctrl + C"); self.assertTrue(w.reloj.isActive())
        img = QWidget.grab(w).toImage(); self.assertTrue(any(img.pixelColor(x, 150).alpha() > 0 for x in range(180, 260)))          # hay una onda dibujada
        w.ondas = [(p, b, t - 5) for p, b, t in w.ondas]; w.teclas = [(x, t - 5) for x, t in w.teclas]; w.avanzar(); self.assertFalse(w.reloj.isActive()); self.assertEqual((w.ondas, w.teclas), ([], [])); w.close()

class Subtitulos(unittest.TestCase):
    P = lambda self, *x: [{"w": a, "ini": b, "fin": c} for a, b, c in x]
    def test_agrupar_corta_en_pausas_puntos_y_largo(self):
        pal = self.P(("Hola", 0.0, 0.4), ("a", 0.4, 0.5), ("todos.", 0.5, 1.0), ("Hoy", 1.1, 1.4), ("vemos", 1.4, 1.8), ("algo", 1.8, 2.1), ("nuevo", 4.0, 4.5))
        l = subtitulos.agrupar(pal); self.assertEqual([x["texto"] for x in l], ["Hola a todos.", "Hoy vemos algo", "nuevo"]); self.assertEqual((l[0]["ini"], l[0]["fin"]), (0.0, 1.0))
    def test_agrupar_reparte_en_dos_renglones_y_no_pasa_de_la_duracion(self):
        pal = self.P(*[(f"palabra{i}", i * 0.3, i * 0.3 + 0.25) for i in range(12)]); l = subtitulos.agrupar(pal, max_chars=20)
        for x in l: self.assertLessEqual(len(x["texto"].splitlines()), 2); self.assertTrue(all(len(r) <= 20 for r in x["texto"].splitlines())); self.assertLessEqual(x["fin"] - x["ini"], 3.3)
        self.assertEqual(" ".join(x["texto"].replace("\n", " ") for x in l), " ".join(f"palabra{i}" for i in range(12)))          # no se pierde ni se repite ninguna palabra
    def test_srt_con_formato_correcto_sin_solapes(self):
        srt = subtitulos.a_srt([{"ini": 1.0, "fin": 1.2, "texto": "uno"}, {"ini": 1.5, "fin": 3.7, "texto": "dos\ntres"}]); self.assertIn("1\n00:00:01,000 --> 00:00:01,480\nuno\n", srt)          # pide 0,8 s mínimo pero se recorta a 20 ms antes de la siguiente
        self.assertIn("2\n00:00:01,500 --> 00:00:03,700\ndos\ntres", srt)
        l1 = srt.split("\n\n")[0].splitlines()[1].split(" --> ")[1]; self.assertLess(l1, "00:00:01,500")          # la primera termina antes de que empiece la segunda
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_quemar_dibuja_el_texto_abajo(self):
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "v.mp4"); srt = os.path.join(d, "a b:c.srt"); open(srt, "w").write("1\n00:00:00,000 --> 00:00:02,000\nHola mundo\n")          # nombre con espacio y dos puntos: no debe dar problemas
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=24:d=2", "-pix_fmt", "yuv420p", v], check=True)
            r, e = subtitulos.quemar(v, srt, os.path.join(d, "s.mp4")); self.assertIsNone(e, e)
            def brillo(f): return max(subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "1", "-i", f, "-frames:v", "1", "-vf", "crop=640:140:0:220,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout)          # el pixel más claro de la franja de abajo
            self.assertLess(brillo(v), 30); self.assertGreater(brillo(r), 200)          # antes todo negro; después hay texto blanco abajo
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_la_cadena_completa_de_la_ventana_con_un_motor_de_voz_simulado(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from oweecapture import ventana_herramientas as V
        palabras = [{"w": w, "ini": 0.2 + i * 0.35, "fin": 0.5 + i * 0.35} for i, w in enumerate("hola esto es una prueba de subtítulos".split())]; original = subtitulos.transcribir
        subtitulos.transcribir = lambda ruta, idioma="", control=None, al_progreso=None: (al_progreso and al_progreso(0.5), (palabras, "es", None))[1]
        try:
            with tempfile.TemporaryDirectory() as d:
                v = os.path.join(d, "v.mp4"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=4", "-f", "lavfi", "-i", "sine=f=300:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", v], check=True); avisos = []
                o = dict(recorte=False, ini=0, fin=0, exacto=True, vertical=True, modo="desenfoque", pos=0.5, silencios=False, sens="normal", subs=True, idioma="es", quemar=True)
                final, err = V.VentanaHerramientas.trabajo(v, o, herramientas.Control(), avisos.append); self.assertIsNone(err, err)
                self.assertTrue(final.endswith("v-vertical-subtitulado.mp4")); self.assertEqual(herramientas.medidas(final)[:2], (1080, 1920)); srt = os.path.splitext(final)[0] + ".srt"; self.assertTrue(os.path.exists(srt)); self.assertIn("hola esto es una prueba", open(srt, encoding="utf-8").read())
                self.assertEqual(sorted(os.listdir(d)), sorted(["v.mp4", os.path.basename(final), os.path.basename(srt)])); self.assertTrue(any("Transcribiendo" in a for a in avisos))          # sin archivos intermedios
                o2 = {**o, "quemar": False, "vertical": False}; f2, e2 = V.VentanaHerramientas.trabajo(v, o2, herramientas.Control()); self.assertEqual(f2, v); self.assertTrue(os.path.exists(os.path.splitext(v)[0] + ".srt"))          # solo el .srt, el vídeo intacto
                subtitulos.transcribir = lambda *a, **k: ([], "es", None); f3, e3 = V.VentanaHerramientas.trabajo(v, o, herramientas.Control()); self.assertIsNone(f3); self.assertIn("No se encontró voz", e3)
        finally: subtitulos.transcribir = original
    @unittest.skipUnless(subtitulos.preparado(), "motor de voz no instalado")
    def test_el_motor_real_no_inventa_palabras_con_un_tono(self):
        with tempfile.TemporaryDirectory() as d:
            w = os.path.join(d, "t.wav"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=3", w], check=True)
            palabras, _idi, err = subtitulos.transcribir(w, "es"); self.assertIsNone(err); self.assertEqual(palabras, [])

class InicioConElEscritorio(unittest.TestCase):
    def test_activar_y_desactivar_con_una_carpeta_falsa(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(inicio.activado(d)); inicio.activar(d); self.assertTrue(inicio.activado(d)); txt = open(inicio.ruta(d)).read()
            self.assertTrue(txt.startswith("[Desktop Entry]\nType=Application\nName=OweeCapture")); self.assertIn("--segundo-plano", txt); self.assertIn("oweecapture", [l for l in txt.splitlines() if l.startswith("Exec=")][0])
            self.assertEqual(os.listdir(os.path.dirname(inicio.ruta(d))), ["oweecapture.desktop"]); inicio.activar(d)          # activar dos veces no falla ni deja archivos temporales
            inicio.desactivar(d); self.assertFalse(inicio.activado(d)); inicio.desactivar(d)          # quitar dos veces tampoco
    def test_la_orden_arranca_en_segundo_plano_y_apunta_a_este_codigo_si_no_esta_instalado(self):
        real = inicio.shutil.which; inicio.shutil.which = lambda n: None
        try: c = inicio.comando()
        finally: inicio.shutil.which = real
        self.assertIn("PYTHONPATH=", c); self.assertIn("-m oweecapture.qtapp --segundo-plano", c)

class PaqueteDeb(unittest.TestCase):
    @unittest.skipUnless(shutil.which("dpkg-deb"), "sin dpkg-deb")
    def test_el_deb_trae_el_comando_el_lanzador_las_traducciones_y_ninguna_cache(self):
        raiz = os.path.join(os.path.dirname(__file__), ".."); r = subprocess.run([os.path.join(raiz, "packaging", "crear_deb.sh"), "9.8.7"], capture_output=True, text=True, cwd=raiz); self.assertEqual(r.returncode, 0, r.stderr)
        deb = os.path.join(raiz, "dist", "oweecapture_9.8.7_all.deb")
        try:
            ctl = subprocess.run(["dpkg-deb", "-f", deb], capture_output=True, text=True).stdout; self.assertIn("Package: oweecapture", ctl); self.assertIn("Version: 9.8.7", ctl); self.assertIn("python3-pyside6.qtwidgets", ctl); self.assertNotIn("qtdbus", ctl); self.assertTrue(ctl.isascii(), "el control debe ser ASCII: el instalador de Deepin lo muestra roto si no"); self.assertIn("Maintainer: Hector Martinez <hector@oweeme.com>", ctl)
            lista = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True, text=True).stdout; self.assertRegex(lista, r"-rwxr-xr-x root/root .* \./usr/bin/oweecapture"); self.assertIn("./usr/share/applications/oweecapture.desktop", lista)
            self.assertIn("./usr/share/oweecapture/locales/es.json" if os.path.exists(os.path.join(raiz, "locales", "es.json")) else "./usr/share/oweecapture/locales/en.json", lista); self.assertIn("./usr/lib/python3/dist-packages/oweecapture/qtapp.py", lista)
            self.assertNotIn("__pycache__", lista); self.assertNotIn("tests/", lista)
        finally:
            if os.path.exists(deb): os.remove(deb)
        self.assertNotEqual(subprocess.run([os.path.join(raiz, "packaging", "crear_deb.sh"), "no valida!"], capture_output=True, cwd=raiz).returncode, 0)          # una versión inválida se rechaza

class Clips(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_recorta_los_ultimos_segundos_con_su_audio(self):
        with tempfile.TemporaryDirectory() as d:
            mkv = os.path.join(d, "v.mkv")      # 20 s con un fotograma clave cada 2 s y dos pistas de audio (sistema y micrófono), como la grabación del portal
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=20", "-f", "lavfi", "-i", "sine=f=440:d=20", "-f", "lavfi", "-i", "sine=f=880:d=20", "-map", "0:v", "-map", "1:a", "-map", "2:a",
                            "-c:v", "libx264", "-g", "48", "-c:a", "libopus", "-pix_fmt", "yuv420p", mkv], check=True)
            salida = os.path.join(d, "clips", "c.mp4"); r = clips.recortar(mkv, 20, 6, salida, (["sistema", "mic"], 1.0, 1.0, 0))
            self.assertEqual(r, salida); dur = core.duration(salida); self.assertTrue(5.5 <= dur <= 9.5, dur)         # 6 s pedidos + hasta 3 s más por el fotograma clave anterior
            self.assertEqual(sorted(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", salida], capture_output=True, text=True).stdout.split()), ["aac", "h264"])   # audio mezclado en una pista
            self.assertTrue(core.duration(clips.recortar(mkv, 20, 120, os.path.join(d, "todo.mp4"))) >= 19)          # pedir más de lo grabado: sale todo
    def test_sin_archivo_no_hay_clip(self): self.assertIsNone(clips.recortar("/no/existe.mkv", 10, 5, "/tmp/x.mp4"))

class Herramientas(unittest.TestCase):
    def _video(self, d, audio=True):
        """6 s de 1280×720: tono (0–1 s), silencio (1–3,5 s), tono (3,5–6 s)."""
        ruta = os.path.join(d, "v.mp4"); cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=6"]
        if audio: cmd += ["-f", "lavfi", "-i", "sine=f=440:d=6,volume='if(between(t,1,3.5),0,0.5)':eval=frame", "-c:a", "aac"]
        subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", ruta], check=True); return ruta
    def test_tramos_a_conservar_deja_margen_y_descarta_silencios_cortos(self):
        self.assertEqual(herramientas.tramos_a_conservar([(2.0, 5.0)], 9.0), [(0.0, 2.15), (4.85, 9.0)])
        self.assertEqual(herramientas.tramos_a_conservar([(2.0, 2.3)], 9.0), [(0.0, 9.0)])                               # silencio de 0,3 s: no se corta
        self.assertEqual(herramientas.tramos_a_conservar([(0.0, 3.0)], 9.0), [(2.85, 9.0)])                              # silencio al principio
        self.assertEqual(herramientas.tramos_a_conservar([(6.0, float("inf"))], 9.0), [(0.0, 6.15)])                    # silencio abierto hasta el final
    def test_filtro_vertical_de_recorte_cabe_en_el_video(self):
        self.assertIn("crop=404:720:438:0", herramientas.filtro_vertical(1280, 720, "recorte", 0.5)); self.assertIn("crop=404:720:0:0", herramientas.filtro_vertical(1280, 720, "recorte", 0))
        self.assertIn("crop=404:720:876:0", herramientas.filtro_vertical(1280, 720, "recorte", 1)); self.assertIn("crop=720:1280:0:", herramientas.filtro_vertical(720, 1600, "recorte", 0.5))
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_vertical_deja_1080x1920_en_los_dos_modos_y_no_pisa_el_original(self):
        with tempfile.TemporaryDirectory() as d:
            v = self._video(d); antes = os.path.getsize(v)
            for modo in ("desenfoque", "recorte"):
                r, e = herramientas.vertical(v, os.path.join(d, f"{modo}.mp4"), modo, 0.5); self.assertIsNone(e, e); self.assertEqual(herramientas.medidas(r)[:3], (1080, 1920, True))
            r2, _e = herramientas.vertical(v, os.path.join(d, "desenfoque.mp4")); self.assertTrue(r2.endswith("desenfoque-2.mp4")); self.assertEqual(os.path.getsize(v), antes)
            self.assertEqual([f for f in os.listdir(d) if "parcial" in f], [])
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_cortar_silencios_quita_la_pausa(self):
        with tempfile.TemporaryDirectory() as d:
            v = self._video(d); r, e, info = herramientas.cortar_silencios(v, os.path.join(d, "s.mp4"), -35, 0.6); self.assertIsNone(e, e)
            antes, despues, cortes = info; self.assertAlmostEqual(antes, 6, delta=0.3); self.assertTrue(3.5 <= despues <= 4.6, despues); self.assertEqual(cortes, 1)       # 6 s − (2,5 s de silencio − 0,3 s de margen)
            r2, e2, _i = herramientas.cortar_silencios(self._video(d, audio=False), os.path.join(d, "x.mp4")); self.assertIsNone(r2); self.assertIn("no tiene audio", e2)
    def test_tiempos_de_texto_a_segundos_y_viceversa(self):
        for t, v in (("90", 90), ("1:30", 90), ("01:02:03", 3723), ("1:30.5", 90.5), (" 0:07 ", 7), ("1,5", 1.5)): self.assertAlmostEqual(herramientas.a_segundos(t), v)
        for malo in ("", "a", "1::2", "-3", "1:2:3:4", "1:-5"): self.assertRaises(ValueError, herramientas.a_segundos, malo)
        self.assertEqual(herramientas.a_texto(90), "1:30"); self.assertEqual(herramientas.a_texto(3723), "1:02:03"); self.assertEqual(herramientas.a_texto(-4), "0:00")
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_recortar_exacto_y_rapido(self):
        with tempfile.TemporaryDirectory() as d:
            v = self._video(d)           # 6 s
            r, e = herramientas.recortar(v, os.path.join(d, "e.mp4"), 1.0, 4.0, True); self.assertIsNone(e, e); self.assertAlmostEqual(core.duration(r), 3.0, delta=0.25); self.assertTrue(herramientas.medidas(r)[2])
            r2, e2 = herramientas.recortar(v, os.path.join(d, "r.mp4"), 1.0, 4.0, False); self.assertIsNone(e2, e2); self.assertTrue(2.5 <= core.duration(r2) <= 5.2, core.duration(r2))
            self.assertIsNotNone(herramientas.recortar(v, os.path.join(d, "x.mp4"), 3.0, 3.1)[1]); self.assertIsNotNone(herramientas.recortar(v, os.path.join(d, "x.mp4"), 5.0, 2.0)[1])
            self.assertTrue(herramientas.fotograma(v, 2.0, os.path.join(d, "f.png")).endswith("f.png")); self.assertEqual([f for f in os.listdir(d) if "parcial" in f], [])
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_cancelar_detiene_el_proceso_y_no_deja_archivos(self):
        import threading, time
        with tempfile.TemporaryDirectory() as d:
            v = self._video(d); c = herramientas.Control(); salida = os.path.join(d, "c.mp4"); threading.Timer(0.05, c.cancelar).start()
            r, e = herramientas.vertical(v, salida, "desenfoque", 0.5, c)
            if r is None: self.assertEqual(e, "Cancelado."); self.assertEqual(os.listdir(d), ["v.mp4"])

class MarcoVertical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
    def test_marco_vertical_es_9_16_exacto_par_y_cabe_en_la_pantalla(self):
        from PySide6.QtCore import QPoint
        from oweecapture import selector
        s = selector.Selector(None, (), True); s.resize(1366, 768)
        for centro in (QPoint(0, 0), QPoint(683, 384), QPoint(1366, 768)):
            s.centro = centro
            for escala in (0.3, 0.5, 0.92, 1.0):
                s.escala = escala; r = s.marco_vertical()
                self.assertEqual(r.width() * 16, r.height() * 9); self.assertEqual((r.width() % 2, r.height() % 2), (0, 0)); self.assertTrue(0 <= r.left() and r.right() < 1366 and 0 <= r.top() and r.bottom() < 768)
    def test_el_marco_visible_nunca_toca_la_zona_grabada(self):
        from PySide6.QtCore import QRect
        from oweecapture import marco
        for z in (QRect(450, 60, 432, 646), QRect(0, 0, 400, 300), QRect(900, 400, 466, 368)):
            seg = marco.segmentos(z, 1366, 768); self.assertTrue(all(not r.intersects(z) for r in seg)); self.assertTrue(all(r.isEmpty() or QRect(0, 0, 1366, 768).contains(r) for r in seg))          # los que caen fuera de la pantalla (zona pegada al borde) quedan vacíos

class ZonaMovible(unittest.TestCase):
    def test_asa_y_mover_respetan_la_pantalla(self):
        from PySide6.QtCore import QPoint, QRect
        from oweecapture import marco
        z = QRect(450, 90, 396, 560); a = marco.asa(z, 1366, 768); self.assertFalse(a.intersects(z)); self.assertTrue(a.bottom() < z.top())            # el asa va fuera, encima
        self.assertTrue(marco.asa(QRect(450, 4, 396, 700), 1366, 768).top() > 700)                                                                           # sin sitio arriba: abajo
        self.assertIsNone(marco.asa(QRect(0, 0, 400, 768), 1366, 768))                                                                                       # sin sitio en ninguno: sin asa
        self.assertEqual(marco.mover(z, QPoint(5000, -5000), 1366, 768), QRect(1366 - 396, 0, 396, 560)); self.assertEqual(marco.mover(z, QPoint(10, 20), 1366, 768), QRect(460, 110, 396, 560))
    def test_la_mascara_es_solo_de_entrada_y_no_recorta_lo_pintado(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QApplication
        from oweecapture import marco
        QApplication.instance() or QApplication([]); m = marco.Marco(QRect(100, 90, 300, 560)); m.mostrar(); m.zona = QRect(700, 165, 300, 560); m.mascara()
        self.assertTrue(m.mask().isEmpty())          # QWidget.setMask recortaría el pintado y dejaría una estela al arrastrar; la máscara de entrada va en la ventana de plataforma
        m.close()
    def test_mover_zona_cambia_el_recorte_sin_cambiar_el_tamano_y_lo_anota(self):
        from oweecapture import portal
        g = portal.Grabador(); g.corriendo = True; g.t0 = time.time(); g.flujo = (1366, 768); g.rect = (100, 60, 432, 646); g.recorte = g._recorte(); g.movs = [(0.0, 100, 60)]
        self.assertTrue(g.mover_zona(701, 61)); self.assertEqual(g.rect, (700, 60, 432, 646))                  # números pares
        self.assertIn("left=700 top=60 right=234 bottom=62", g.recorte); self.assertEqual(g.movs[-1][1:], (700, 60))
        self.assertFalse(g.mover_zona(700, 60)); g.mover_zona(9999, 9999); self.assertEqual(g.rect, (1366 - 432, 768 - 646, 432, 646)); g.mover_zona(-50, -50); self.assertEqual(g.rect[:2], (0, 0))
        g.corriendo = False; self.assertFalse(g.mover_zona(10, 10))
    def test_pista_sigue_la_esquina_del_recorte_en_cada_momento(self):
        meta = {"t0": 100.0, "pausas": [], "pantalla": (0, 0, 1000, 500), "flujo": (1000, 500), "recorte": (100, 0, 400, 500), "movimientos": [(0.0, 100, 0), (5.0, 300, 0)]}
        m = [[101_000, 400, 250], [106_000, 400, 250]]           # el mismo punto de la pantalla, antes y después de mover la zona
        self.assertEqual(efectos.pista(m, meta), [(1.0, 300.0, 250.0), (6.0, 100.0, 250.0)])

if __name__ == "__main__": unittest.main()
