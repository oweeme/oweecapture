"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from screencapture import audio, core, efectos, i18n

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

if __name__ == "__main__": unittest.main()
