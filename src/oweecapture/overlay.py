"""Modo presentación de OweeLinux: una capa transparente a pantalla completa para DIBUJAR sobre lo que se ve (lápiz, resaltador, flecha, rectángulo), con un halo que sigue al puntero y
ondas al hacer clic. Pensado para clases, demostraciones y grabaciones. Atajos: Esc o clic derecho larga → salir, Supr/Retroceso → borrar todo, 1-6 → color, F → alternar halo.
Mientras está activo, la capa recibe el ratón (los clics NO llegan a las apps de debajo); al salir, todo vuelve a la normalidad."""
import math, time
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LS
import cairo
from .i18n import _

COLORS = [("#F06548", "1"), ("#F2C94C", "2"), ("#2A9D8F", "3"), ("#3B82C4", "4"), ("#FFFFFF", "5"), ("#8B6FD6", "6")]

class Overlay(Gtk.Window):
    def __init__(self, app, on_close=None):
        super().__init__(application=app, decorated=False); self.on_close = on_close; self.add_css_class("oweecapture-presentation")
        LS.init_for_window(self); LS.set_layer(self, LS.Layer.OVERLAY); LS.set_namespace(self, "oweecapture-presentation"); LS.set_keyboard_mode(self, LS.KeyboardMode.EXCLUSIVE); LS.set_exclusive_zone(self, -1)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(self, e, True)
        self.strokes = []; self.cur = None; self.color = COLORS[0][0]; self.tool = "pen"; self.halo = True; self.px = self.py = None; self.ripples = []
        prov = Gtk.CssProvider(); prov.load_from_string("window.oweecapture-presentation, window.oweecapture-presentation > * { background: rgba(0,0,0,0.002); } .opbar { background: rgba(16,32,25,0.92); border-radius: 14px; padding: 6px; color: #EFF0F1; } .opbar button { background: #1b3128; color: #EFF0F1; border: none; background-image: none; box-shadow: none; border-radius: 10px; min-width: 0; padding: 4px 10px; } .opbar button.on { background: #2A9D8F; color: #102019; } .opbar button.sw { min-width: 22px; min-height: 22px; padding: 0; border-radius: 999px; border: 2px solid transparent; } .opbar button.sw.on { border-color: #EFF0F1; }")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        ov = Gtk.Overlay(); self.set_child(ov); self.area = Gtk.DrawingArea(hexpand=True, vexpand=True); self.area.set_draw_func(self.draw); ov.set_child(self.area)
        bar = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=22); bar.add_css_class("opbar"); ov.add_overlay(bar); self.btns = {}
        for k, label, tip in (("pen", _("✎ Lápiz"), _("Dibujar libremente")), ("marker", _("▬ Resaltador"), _("Resaltar texto")), ("arrow", _("➚ Flecha"), _("Señalar con una flecha")), ("rect", _("▭ Rectángulo"), _("Encuadrar una zona"))):
            b = Gtk.Button(label=label, tooltip_text=tip); b.connect("clicked", lambda _b, k=k: self.set_tool(k)); bar.append(b); self.btns[k] = b
        self.sw = {}
        for c, key in COLORS:
            b = Gtk.Button(css_classes=["sw"], tooltip_text=_('Color ({0})', key)); p = Gtk.CssProvider(); p.load_from_string(f"button {{ background: {c}; background-image: none; }}"); b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            b.connect("clicked", lambda _b, c=c: self.set_color(c)); bar.append(b); self.sw[c] = b
        hb = Gtk.Button(label=_("◉ Halo"), tooltip_text=_("Resaltar el puntero (F)")); hb.connect("clicked", lambda b: self.toggle_halo()); bar.append(hb); self.halo_btn = hb
        cl = Gtk.Button(label=_("⌫ Borrar"), tooltip_text=_("Borrar todo (Supr)")); cl.connect("clicked", lambda b: self.clear()); bar.append(cl)
        ex = Gtk.Button(label=_("✕ Salir"), tooltip_text=_("Salir del modo presentación (Esc)")); ex.connect("clicked", lambda b: self.finish()); bar.append(ex)
        drag = Gtk.GestureDrag(); drag.connect("drag-begin", self.begin); drag.connect("drag-update", self.update); drag.connect("drag-end", self.end); self.area.add_controller(drag)
        mc = Gtk.EventControllerMotion(); mc.connect("motion", self.motion); self.area.add_controller(mc)
        k = Gtk.EventControllerKey(); k.connect("key-pressed", self.on_key); self.add_controller(k)
        self.set_tool("pen"); self.set_color(COLORS[0][0]); self.refresh_halo()

    def set_tool(self, t):
        self.tool = t
        for k, b in self.btns.items(): (b.add_css_class if k == t else b.remove_css_class)("on")
    def set_color(self, c):
        self.color = c
        for cc, b in self.sw.items(): (b.add_css_class if cc == c else b.remove_css_class)("on")
    def toggle_halo(self): self.halo = not self.halo; self.refresh_halo(); self.area.queue_draw()
    def refresh_halo(self): (self.halo_btn.add_css_class if self.halo else self.halo_btn.remove_css_class)("on")
    def clear(self): self.strokes.clear(); self.area.queue_draw()
    def finish(self):
        self.close()
        if self.on_close: self.on_close()

    def on_key(self, c, kv, code, st):
        n = Gdk.keyval_name(kv)
        if n == "Escape": self.finish(); return True
        if n in ("Delete", "BackSpace"): self.clear(); return True
        if n in ("f", "F"): self.toggle_halo(); return True
        if n in ("r", "R"): self.set_tool("rect"); return True
        if n in ("1", "2", "3", "4", "5", "6"): self.set_color(COLORS[int(n) - 1][0]); return True
        if (st & Gdk.ModifierType.CONTROL_MASK) and n in ("z", "Z") and self.strokes: self.strokes.pop(); self.area.queue_draw(); return True
        return False

    def motion(self, c, x, y): self.px, self.py = x, y; self.area.queue_draw()
    def begin(self, g, x, y): self.x0, self.y0 = x, y; self.px, self.py = x, y; self.cur = {"t": self.tool, "pts": [(x, y)], "c": self.color}; self.ripples.append((x, y, time.time())); GLib.timeout_add(30, self.anim)
    def update(self, g, dx, dy):
        if not self.cur: return
        p = (self.x0 + dx, self.y0 + dy); self.px, self.py = p
        if self.cur["t"] in ("pen", "marker"): self.cur["pts"].append(p)
        else: self.cur["pts"] = [self.cur["pts"][0], p]
        self.area.queue_draw()
    def end(self, g, dx, dy):
        if self.cur and (abs(dx) + abs(dy) > 2 or self.cur["t"] in ("pen", "marker")): self.update(g, dx, dy); self.strokes.append(self.cur)
        self.cur = None; self.area.queue_draw()
    def anim(self):
        now = time.time(); self.ripples = [r for r in self.ripples if now - r[2] < 0.6]; self.area.queue_draw(); return bool(self.ripples)

    def rgb(self, c): c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    def draw(self, area, cr, w, h):
        cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for s in self.strokes + ([self.cur] if self.cur else []):
            r, g, b = self.rgb(s["c"]); pts = s["pts"]
            if s["t"] == "rect":
                if len(pts) > 1:
                    (x1, y1), (x2, y2) = pts[0], pts[-1]; cr.set_source_rgb(r, g, b); cr.set_line_width(4); cr.set_line_join(cairo.LINE_JOIN_ROUND); cr.rectangle(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)); cr.stroke()
                continue
            if s["t"] == "marker": cr.set_source_rgba(r, g, b, 0.4); cr.set_line_width(22); cr.set_line_cap(cairo.LINE_CAP_BUTT)
            else: cr.set_source_rgb(r, g, b); cr.set_line_width(4); cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(*pts[0]); [cr.line_to(*p) for p in pts[1:]]; cr.stroke()
            if s["t"] == "arrow" and len(pts) > 1:
                (x1, y1), (x2, y2) = pts[0], pts[-1]; a = math.atan2(y2 - y1, x2 - x1); cr.set_source_rgb(r, g, b); cr.set_line_width(4)
                for da in (math.pi * 0.85, -math.pi * 0.85): cr.move_to(x2, y2); cr.line_to(x2 + 20 * math.cos(a + da), y2 + 20 * math.sin(a + da)); cr.stroke()
        if self.halo and self.px is not None:
            r, g, b = self.rgb(self.color); cr.set_source_rgba(1, 0.9, 0.2, 0.28); cr.arc(self.px, self.py, 26, 0, 2 * math.pi); cr.fill()
            cr.set_source_rgba(1, 0.9, 0.2, 0.8); cr.set_line_width(2); cr.arc(self.px, self.py, 26, 0, 2 * math.pi); cr.stroke()
        now = time.time()
        for x, y, t in self.ripples:
            k = (now - t) / 0.6; cr.set_source_rgba(0.16, 0.62, 0.56, 1 - k); cr.set_line_width(3); cr.arc(x, y, 12 + 40 * k, 0, 2 * math.pi); cr.stroke()
