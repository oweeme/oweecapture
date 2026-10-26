"""Traducciones de Screencapture: `_("texto en español")` devuelve el texto en el idioma del sistema (LANGUAGE / LC_ALL / LANG). El español del código es el original; cada idioma tiene
un catálogo `locales/<código>.json` {"español": "traducción"}. Si falta un texto o un idioma se muestra el español (nunca falla). Los marcadores {0}, {1}… se rellenan con los argumentos extra."""
import json, os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
for _alt in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "locales"), "/usr/share/screencapture/locales"):
    if not os.path.isdir(_DIR) and os.path.isdir(_alt): _DIR = _alt

def _lang():
    for v in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        x = os.environ.get(v, "")
        if x and x != "C": return x.split(":")[0].split(".")[0].replace("_", "-").split("-")[0].lower()
    return "es"

LANG = _lang(); _CAT = {}
try: _CAT = json.load(open(os.path.join(_DIR, LANG + ".json"), encoding="utf-8"))
except (OSError, ValueError): pass

def _(msg, *args):
    t = _CAT.get(msg, msg)
    for i, a in enumerate(args): t = t.replace("{%d}" % i, str(a))
    return t

def N_(msg): return msg
def apply_direction():
    """Idiomas de derecha a izquierda (árabe, persa, urdu): la interfaz se espeja."""
    if LANG in ("ar", "fa", "ur"):
        import gi; gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk; Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
