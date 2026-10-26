"""Burbuja de cámara web para grabaciones: una ventana redonda y flotante con la imagen de la cámara (GStreamer + gtk4paintablesink), que se puede arrastrar y cambiar de tamaño
con la rueda. Al estar sobre la pantalla, queda dentro de la grabación. Si no hay cámara o falta el complemento, avisa y no hace nada. OWEE_CAM_TEST=1 usa una imagen de prueba."""
import json, os
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LS
from .i18n import _
try:
    gi.require_version("Gst", "1.0"); from gi.repository import Gst; Gst.init(None); HAVE_GST = True
except Exception: HAVE_GST = False

SIZES = [120, 180, 240, 320]
STATE = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "screencapture", "camera.json")      # posición y tamaño que se recuerdan entre usos

def load_state():
    try:
        d = json.load(open(STATE)); return max(0, int(d["x"])), max(0, int(d["y"])), int(d["size"]) if int(d["size"]) in SIZES else SIZES[1]
    except Exception: return 24, 24, SIZES[1]

def available():
    """(ok, motivo) — comprueba el complemento y que haya una cámara (o el modo de prueba)."""
    if not HAVE_GST: return False, _("Falta GStreamer para Python (gir1.2-gst).")
    if not Gst.ElementFactory.find("gtk4paintablesink"): return False, _("Falta el complemento gstreamer1.0-gtk4.")
    if os.environ.get("OWEE_CAM_TEST"): return True, ""
    if not any(n.startswith("video") for n in os.listdir("/dev")): return False, _("No se encontró ninguna cámara.")
    return True, ""

class Bubble(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, decorated=False); self.add_css_class("sc-cam"); self.mx, self.my, self.size = load_state()
        LS.init_for_window(self); LS.set_layer(self, LS.Layer.OVERLAY); LS.set_namespace(self, "screencapture-camera"); LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)
        LS.set_anchor(self, LS.Edge.BOTTOM, True); LS.set_anchor(self, LS.Edge.LEFT, True); self.apply_margins()
        prov = Gtk.CssProvider(); prov.load_from_string("window.sc-cam { background: transparent; } .camwrap { border-radius: 999px; border: 3px solid #2A9D8F; background: #102019; }"); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        src = "videotestsrc is-live=true pattern=ball" if os.environ.get("OWEE_CAM_TEST") else "v4l2src"
        self.pipe = Gst.parse_launch(f"{src} ! videoconvert ! videocrop name=crop ! videoscale ! gtk4paintablesink name=sink"); sink = self.pipe.get_by_name("sink")
        pic = Gtk.Picture(paintable=sink.props.paintable, content_fit=Gtk.ContentFit.COVER); self.wrap = Gtk.Box(); self.wrap.add_css_class("camwrap"); self.wrap.set_overflow(Gtk.Overflow.HIDDEN); self.wrap.append(pic); self.set_child(self.wrap); self.resize_to()
        d = Gtk.GestureDrag(); d.connect("drag-begin", lambda g, x, y: setattr(self, "m0", (self.mx, self.my))); d.connect("drag-update", self.drag); d.connect("drag-end", lambda g, dx, dy: self.save()); self.wrap.add_controller(d)
        sc = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL); sc.connect("scroll", self.scroll); self.wrap.add_controller(sc)

    def apply_margins(self): LS.set_margin(self, LS.Edge.LEFT, int(self.mx)); LS.set_margin(self, LS.Edge.BOTTOM, int(self.my))
    def drag(self, g, dx, dy):
        # La ventana se mueve con el puntero, así que (dx, dy) es solo lo que aún no ha seguido: se corrige un 60 % cada vez (con el 100 % la burbuja oscila y «cuesta arrastrar»)
        self.move(self.mx + dx * 0.6, self.my - dy * 0.6)
    def save(self):
        try: os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump({"x": int(self.mx), "y": int(self.my), "size": self.size}, open(STATE, "w"))
        except OSError: pass
    def move(self, x, y): self.mx, self.my = max(0, x), max(0, y); self.apply_margins()
    def resize_to(self): self.wrap.set_size_request(self.size, self.size); self.set_default_size(self.size, self.size)
    def scroll(self, c, dx, dy):
        i = SIZES.index(min(SIZES, key=lambda s: abs(s - self.size))); i = max(0, min(len(SIZES) - 1, i + (1 if dy < 0 else -1))); self.size = SIZES[i]; self.resize_to(); self.save(); return True
    def start(self): self.present(); self.pipe.set_state(Gst.State.PLAYING)
    def stop(self): self.pipe.set_state(Gst.State.NULL); self.close()
