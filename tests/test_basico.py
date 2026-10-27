"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from screencapture import core, i18n

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

if __name__ == "__main__": unittest.main()
