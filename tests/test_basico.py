"""Pruebas sin interfaz ni compositor: traducciones, tabla de calidades, nombres de archivo y mezcla de audio y vídeo."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from screencapture import core, i18n

class Calidades(unittest.TestCase):
    def test_niveles(self): self.assertEqual(set(core.QUALITY), {"original", "buena", "media", "ligera"})
    def test_original_y_buena_no_se_recomprimen(self): self.assertIsNone(core.QUALITY["original"][2]); self.assertIsNone(core.QUALITY["buena"][2])
    def test_media_y_ligera_reducen_a_720p(self): self.assertEqual(core.QUALITY["media"][2]["height"], 720); self.assertLess(core.QUALITY["ligera"][2]["crf"] - core.QUALITY["media"][2]["crf"], 9)
    def test_config_por_defecto_valida(self): self.assertIn(core.load_cfg()["quality"], core.QUALITY)

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
