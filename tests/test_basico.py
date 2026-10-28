"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from screencapture import audio, clips, core, directo, efectos, herramientas, i18n

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
        from screencapture import portal
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
        from screencapture import burbuja
        o = burbuja.limpiar({"forma": "triangulo", "borde": "rosa", "fondo": "rojo", "brillo": 999, "contraste": -3, "espejo": 1, "otra": 1})
        self.assertEqual(o, {"forma": "circulo", "borde": "#2A9D8F", "espejo": True, "brillo": 50, "contraste": 50, "fondo": ""})
    def test_croma_deja_transparente_el_fondo_verde_y_opaco_lo_demas(self):
        import gi; gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        from screencapture import burbuja
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
        from gi.repository import Gst
        Gst.init(None)
        if not all(Gst.ElementFactory.find(e) for e in ("x264enc", "rtmp2sink", "avenc_aac", "flvmux")): self.skipTest("faltan complementos de GStreamer")
        with tempfile.TemporaryDirectory() as d:
            recibido = os.path.join(d, "recibido.flv"); local = os.path.join(d, "local.mkv")
            rx = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-listen", "1", "-f", "flv", "-i", "rtmp://127.0.0.1:19350/live/clave", "-c", "copy", recibido]); time.sleep(1)
            desc = directo.descripcion("videotestsrc is-live=true pattern=ball", "", 30, 1500, (640, 360), [("audiotestsrc is-live=true wave=sine freq=440 volume=0.3", 1.0)], local, directo.destino("rtmp://127.0.0.1:19350/live", "clave"))
            p = Gst.parse_launch(desc); p.set_state(Gst.State.PLAYING); time.sleep(4); p.send_event(Gst.Event.new_eos()); p.get_bus().timed_pop_filtered(8 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR); p.set_state(Gst.State.NULL)
            try: rx.wait(timeout=10)
            except subprocess.TimeoutExpired: rx.kill()
            def pistas(f): return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.split()
            self.assertEqual(sorted(pistas(recibido)), ["aac", "h264"]); self.assertEqual(sorted(pistas(local)), ["aac", "h264"]); self.assertGreater(core.duration(recibido), 2.5)

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
        from screencapture import selector
        s = selector.Selector(None, (), True); s.resize(1366, 768)
        for centro in (QPoint(0, 0), QPoint(683, 384), QPoint(1366, 768)):
            s.centro = centro
            for escala in (0.3, 0.5, 0.92, 1.0):
                s.escala = escala; r = s.marco_vertical()
                self.assertEqual(r.width() * 16, r.height() * 9); self.assertEqual((r.width() % 2, r.height() % 2), (0, 0)); self.assertTrue(0 <= r.left() and r.right() < 1366 and 0 <= r.top() and r.bottom() < 768)
    def test_el_marco_visible_nunca_toca_la_zona_grabada(self):
        from PySide6.QtCore import QRect
        from screencapture import marco
        for z in (QRect(450, 60, 432, 646), QRect(0, 0, 400, 300), QRect(900, 400, 466, 368)):
            seg = marco.segmentos(z, 1366, 768); self.assertTrue(all(not r.intersects(z) for r in seg)); self.assertTrue(all(r.isEmpty() or QRect(0, 0, 1366, 768).contains(r) for r in seg))          # los que caen fuera de la pantalla (zona pegada al borde) quedan vacíos

class ZonaMovible(unittest.TestCase):
    def test_asa_y_mover_respetan_la_pantalla(self):
        from PySide6.QtCore import QPoint, QRect
        from screencapture import marco
        z = QRect(450, 90, 396, 560); a = marco.asa(z, 1366, 768); self.assertFalse(a.intersects(z)); self.assertTrue(a.bottom() < z.top())            # el asa va fuera, encima
        self.assertTrue(marco.asa(QRect(450, 4, 396, 700), 1366, 768).top() > 700)                                                                           # sin sitio arriba: abajo
        self.assertIsNone(marco.asa(QRect(0, 0, 400, 768), 1366, 768))                                                                                       # sin sitio en ninguno: sin asa
        self.assertEqual(marco.mover(z, QPoint(5000, -5000), 1366, 768), QRect(1366 - 396, 0, 396, 560)); self.assertEqual(marco.mover(z, QPoint(10, 20), 1366, 768), QRect(460, 110, 396, 560))
    def test_mover_zona_cambia_el_recorte_sin_cambiar_el_tamano_y_lo_anota(self):
        from screencapture import portal
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
