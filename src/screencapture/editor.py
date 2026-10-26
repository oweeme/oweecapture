"""Editor de capturas de OweeLinux: dibuja sobre la imagen (lápiz, resaltador, flecha, rectángulo, elipse, texto, números de pasos, pixelar), deshacer/rehacer,
copiar, guardar y «guardar como». Python + GTK4 + cairo; no modifica el archivo original hasta que se pulsa Guardar."""
import math, os, subprocess, sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
import cairo
from . import core
from .i18n import _

TOOLS = [("pen", _("Lápiz"), "✎"), ("marker", _("Resaltador"), "▬"), ("arrow", _("Flecha"), "➚"), ("rect", _("Rectángulo"), "▭"), ("ellipse", _("Elipse"), "◯"), ("text", _("Texto"), "T"), ("step", _("Número"), "①"), ("blur", _("Pixelar"), "▦")]
COLORS = ["#F06548", "#2A9D8F", "#F2C94C", "#3B82C4", "#FFFFFF", "#111111"]
CSS = b"""
window.editor { background: #102019; color: #EFF0F1; }
.tb button { background: #1b3128; color: #EFF0F1; border: none; box-shadow: none; background-image: none; border-radius: 8px; padding: 4px 10px; min-width: 0; }
.tb button:hover { background: #264438; } .tb button.on { background: #2A9D8F; color: #102019; }
.tb button.swatch { min-width: 22px; min-height: 22px; padding: 0; border-radius: 999px; border: 2px solid transparent; } .tb button.swatch.on { border-color: #EFF0F1; }
.tb label { padding: 0 6px; }
"""

class Editor(Gtk.ApplicationWindow):
    def __init__(self, app, path):
        super().__init__(application=app, title=_("Editar captura — ") + os.path.basename(path)); self.add_css_class("editor"); self.path = path
        prov = Gtk.CssProvider(); prov.load_from_data(CSS); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.base = cairo.ImageSurface.create_from_png(path); self.w, self.h = self.base.get_width(), self.base.get_height()
        self.items = []; self.redo = []; self.cur = None; self.tool = "pen"; self.color = COLORS[0]; self.width = 4; self.step_n = 1; self.zoom = 1.0
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.set_child(root)
        tb = Gtk.Box(spacing=4, margin_top=6, margin_bottom=6, margin_start=8, margin_end=8); tb.add_css_class("tb"); root.append(tb); self.tool_btns = {}
        for k, name, ic in TOOLS:
            b = Gtk.Button(label=ic, tooltip_text=name); b.connect("clicked", lambda _b, k=k: self.set_tool(k)); tb.append(b); self.tool_btns[k] = b
        tb.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)); self.sw = {}
        for c in COLORS:
            b = Gtk.Button(css_classes=["swatch"], tooltip_text=c); p = Gtk.CssProvider(); p.load_from_string(f"button {{ background: {c}; background-image: none; }}"); b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            b.connect("clicked", lambda _b, c=c: self.set_color(c)); tb.append(b); self.sw[c] = b
        tb.append(Gtk.Label(label=_("Grosor"))); sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 24, 1); sc.set_value(4); sc.set_size_request(110, -1); sc.connect("value-changed", lambda s: setattr(self, "width", s.get_value())); tb.append(sc)
        tb.append(Gtk.Box(hexpand=True))
        for label, fn in (("↶", self.undo), ("↷", self.do_redo), (_("Copiar"), self.copy), (_("Guardar"), self.save), (_("Guardar como…"), self.save_as)):
            b = Gtk.Button(label=label, tooltip_text={"↶": _("Deshacer (Ctrl+Z)"), "↷": _("Rehacer (Ctrl+Mayús+Z)")}.get(label)); b.connect("clicked", lambda _b, fn=fn: fn()); tb.append(b)
        self.area = Gtk.DrawingArea(); self.area.set_draw_func(self.draw); self.area.set_content_width(min(self.w, 1100)); self.area.set_content_height(min(self.h, 700))
        drag = Gtk.GestureDrag(); drag.connect("drag-begin", self.begin); drag.connect("drag-update", self.update); drag.connect("drag-end", self.end); self.area.add_controller(drag)
        sw = Gtk.ScrolledWindow(child=self.area, hexpand=True, vexpand=True); root.append(sw)
        self.status = Gtk.Label(xalign=0, margin_start=10, margin_bottom=4, css_classes=["dim-label"]); root.append(self.status)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.on_key); self.add_controller(k)
        self.set_tool("pen"); self.set_color(COLORS[0]); self.set_default_size(min(self.w + 40, 1180), min(self.h + 120, 820)); self.msg(f"{self.w}×{self.h}")

    def msg(self, t): self.status.set_text(t)
    def toast(self, title, body, icon="screencapture"):
        """Aviso en pantalla (mako): así se sabe al instante que la captura se guardó o se copió, sin mirar la barra de abajo ni la carpeta."""
        try: subprocess.Popen(["notify-send", "-i", icon, title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: pass
    def set_tool(self, k):
        self.tool = k
        for kk, b in self.tool_btns.items(): (b.add_css_class if kk == k else b.remove_css_class)("on")
    def set_color(self, c):
        self.color = c
        for cc, b in self.sw.items(): (b.add_css_class if cc == c else b.remove_css_class)("on")
    def rgb(self, c): c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))

    # --- dibujo
    def scale_factor(self):
        aw, ah = self.area.get_width(), self.area.get_height(); return min(aw / self.w, ah / self.h, 1.0) if aw and ah else 1.0
    def to_img(self, x, y): s = self.scale_factor(); return x / s, y / s

    def draw(self, area, cr, w, h):
        s = self.scale_factor(); cr.scale(s, s); cr.set_source_surface(self.base, 0, 0); cr.paint()
        for it in self.items + ([self.cur] if self.cur else []): self.draw_item(cr, it)

    def draw_item(self, cr, it):
        t, pts, col, wd = it["t"], it["pts"], it["c"], it["w"]; r, g, b = self.rgb(col)
        cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
        if t in ("pen", "marker"):
            cr.set_source_rgba(r, g, b, 0.38 if t == "marker" else 1); cr.set_line_width(wd * (4 if t == "marker" else 1))
            if t == "marker": cr.set_line_cap(cairo.LINE_CAP_BUTT)
            cr.move_to(*pts[0]); [cr.line_to(*p) for p in pts[1:]]; cr.stroke()
        elif t == "arrow":
            (x1, y1), (x2, y2) = pts[0], pts[-1]; cr.set_source_rgb(r, g, b); cr.set_line_width(wd); cr.move_to(x1, y1); cr.line_to(x2, y2); cr.stroke()
            a = math.atan2(y2 - y1, x2 - x1); L = 10 + wd * 3
            for da in (math.pi * 0.85, -math.pi * 0.85): cr.move_to(x2, y2); cr.line_to(x2 + L * math.cos(a + da), y2 + L * math.sin(a + da)); cr.stroke()
        elif t in ("rect", "ellipse", "blur"):
            (x1, y1), (x2, y2) = pts[0], pts[-1]; x, y, w, h = min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)
            if t == "blur":
                self.pixelate(cr, x, y, w, h); return
            cr.set_source_rgb(r, g, b); cr.set_line_width(wd)
            if t == "rect": cr.rectangle(x, y, w, h)
            else: cr.save(); cr.translate(x + w / 2, y + h / 2); cr.scale(max(w / 2, 1), max(h / 2, 1)); cr.arc(0, 0, 1, 0, 2 * math.pi); cr.restore()
            cr.stroke()
        elif t == "text":
            cr.set_source_rgb(r, g, b); cr.select_font_face("Noto Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); cr.set_font_size(12 + wd * 3); cr.move_to(*pts[0]); cr.show_text(it.get("text", ""))
        elif t == "step":
            x, y = pts[0]; R = 10 + wd * 2; cr.set_source_rgb(r, g, b); cr.arc(x, y, R, 0, 2 * math.pi); cr.fill()
            cr.set_source_rgb(*( (0, 0, 0) if sum(self.rgb(col)) > 1.8 else (1, 1, 1))); cr.select_font_face("Noto Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); cr.set_font_size(R * 1.1)
            tx = cr.text_extents(str(it["n"])); cr.move_to(x - tx.width / 2 - tx.x_bearing, y + tx.height / 2); cr.show_text(str(it["n"]))

    def pixelate(self, cr, x, y, w, h, block=12):
        x0, y0 = max(0, int(x)), max(0, int(y)); x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x1 - x0 < 2 or y1 - y0 < 2: return
        sub = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0); c2 = cairo.Context(sub); c2.set_source_surface(self.base, -x0, -y0); c2.paint()
        small = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)); c3 = cairo.Context(small); c3.scale(small.get_width() / sub.get_width(), small.get_height() / sub.get_height()); c3.set_source_surface(sub, 0, 0); c3.get_source().set_filter(cairo.FILTER_BILINEAR); c3.paint()
        cr.save(); cr.rectangle(x0, y0, x1 - x0, y1 - y0); cr.clip(); cr.translate(x0, y0); cr.scale((x1 - x0) / small.get_width(), (y1 - y0) / small.get_height()); cr.set_source_surface(small, 0, 0); cr.get_source().set_filter(cairo.FILTER_NEAREST); cr.paint(); cr.restore()

    # --- ratón
    def begin(self, g, x, y):
        self.x0, self.y0 = self.to_img(x, y)
        if self.tool == "text": self.ask_text(self.x0, self.y0); return
        if self.tool == "step": self.push({"t": "step", "pts": [(self.x0, self.y0)], "c": self.color, "w": self.width, "n": self.step_n}); self.step_n += 1; return
        self.cur = {"t": self.tool, "pts": [(self.x0, self.y0)], "c": self.color, "w": self.width}
    def update(self, g, dx, dy):
        if not self.cur: return
        s = self.scale_factor(); p = (self.x0 + dx / s, self.y0 + dy / s)
        if self.tool in ("pen", "marker"): self.cur["pts"].append(p)
        else: self.cur["pts"] = [self.cur["pts"][0], p]
        self.area.queue_draw()
    def end(self, g, dx, dy):
        if not self.cur: return
        self.update(g, dx, dy)
        if len(self.cur["pts"]) > 1 or self.cur["t"] in ("pen", "marker"):
            if abs(dx) + abs(dy) > 2: self.push(self.cur)
        self.cur = None; self.area.queue_draw()
    def push(self, it): self.items.append(it); self.redo.clear(); self.area.queue_draw()

    def ask_text(self, x, y):
        dlg = Gtk.Window(title=_("Texto"), transient_for=self, modal=True, default_width=320); box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        e = Gtk.Entry(placeholder_text=_("Escribe y pulsa Intro")); box.append(e); dlg.set_child(box)
        def ok(_e):
            if e.get_text(): self.push({"t": "text", "pts": [(x, y)], "c": self.color, "w": self.width, "text": e.get_text()})
            dlg.close()
        e.connect("activate", ok); dlg.present(); e.grab_focus()

    def undo(self):
        if self.items: self.redo.append(self.items.pop()); self.area.queue_draw()
    def do_redo(self):
        if self.redo: self.items.append(self.redo.pop()); self.area.queue_draw()
    def on_key(self, c, kv, code, st):
        ctrl = st & Gdk.ModifierType.CONTROL_MASK; name = Gdk.keyval_name(kv)
        if ctrl and name in ("z", "Z"): (self.do_redo if st & Gdk.ModifierType.SHIFT_MASK else self.undo)(); return True
        if ctrl and name in ("s", "S"): self.save(); return True
        if ctrl and name in ("c", "C"): self.copy(); return True
        if name == "Escape": self.close(); return True
        return False

    # --- salida
    def render(self, path):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h); cr = cairo.Context(surf); cr.set_source_surface(self.base, 0, 0); cr.paint()
        for it in self.items: self.draw_item(cr, it)
        surf.write_to_png(path)
    def save(self):
        if self.items: self.render(self.path)
        self.msg("✓ " + _("Guardado: ") + self.path); self.toast(_("Captura guardada"), self.path, self.path); return self.path
    def save_as(self):
        dlg = Gtk.FileDialog(title=_("Guardar como"), initial_name=os.path.basename(self.path))
        def done(d, res):
            try: f = d.save_finish(res).get_path()
            except GLib.Error: return
            self.render(f); self.path = f; self.msg("✓ " + _("Guardado: ") + f); self.toast(_("Captura guardada"), f, f)
        dlg.save(self, None, done)
    def copy(self):
        tmp = os.path.join("/tmp", f"screencapture-copy-{os.getpid()}.png"); self.render(tmp); ok = core.copy_image(tmp); os.remove(tmp); self.msg(_("Copiada al portapapeles") if ok else _("Falta wl-copy")); self.toast(_("Copiada al portapapeles"), "", "edit-copy") if ok else None

def open_editor(app, path): w = Editor(app, path); w.present(); return w
