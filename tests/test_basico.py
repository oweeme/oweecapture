"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from screencapture import core, efectos, i18n

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
    def test_camara_no_se_mueve_con_el_cursor_quieto_y_queda_dentro(self):
        p = [(0, 500, 300), (5, 500, 300)]; c = efectos.camara(p, 1000, 600, 2, 30, 5)
        self.assertEqual(len(c), 151); self.assertTrue(all(abs(x - c[0][1]) < 1e-6 and abs(y - c[0][2]) < 1e-6 for _t, x, y, _a, _b in c))
        for _t, x, y, _a, _b in efectos.camara([(0, 0, 0), (2, 1000, 600)], 1000, 600, 2, 30, 2): self.assertTrue(0 <= x <= 500 and 0 <= y <= 300)
    def test_camara_sigue_al_cursor_cuando_sale_de_la_zona_central(self):
        c = efectos.camara([(0, 100, 300), (3, 900, 300)], 1000, 600, 2, 30, 3); self.assertGreater(c[-1][1], c[0][1] + 200)
    def test_filtro_segun_lo_pedido(self):
        self.assertIn("crop@c", efectos.filtro(2, False, 640, 360)[0]); self.assertNotIn("overlay", efectos.filtro(2, False, 640, 360)[0]); self.assertNotIn("crop", efectos.filtro(1, True, 640, 360)[0])
    @unittest.skipUnless(shutil.which("ffmpeg"), "sin ffmpeg")
    def test_aplicar_reescribe_el_video_con_zoom_y_halo(self):
        with tempfile.TemporaryDirectory() as d:
            v = os.path.join(d, "v.mp4"); subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=2", "-pix_fmt", "yuv420p", v], check=True)
            p = [(i / 10, 40 + i * 12, 90) for i in range(21)]
            self.assertTrue(efectos.aplicar(v, p, 2.0, True)); self.assertEqual(efectos.medidas(v)[:2], (320, 180)); self.assertEqual(os.listdir(d), ["v.mp4"])
    def test_sin_pista_o_sin_efectos_no_toca_nada(self): self.assertFalse(efectos.aplicar("/no/existe.mp4", [], 2.0, True)); self.assertFalse(efectos.aplicar("/no/existe.mp4", [(0, 1, 1), (1, 2, 2)], 1, False))

if __name__ == "__main__": unittest.main()
