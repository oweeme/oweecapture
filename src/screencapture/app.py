#!/usr/bin/env python3
"""Screencapture: capturas de pantalla (con editor de anotaciones), grabación de vídeo (con audio del sistema y micrófono, y burbuja de cámara web) y modo
presentación para dibujar sobre la pantalla. Reemplaza a Spectacle. Python + GTK4; las herramientas de fondo son grim, slurp, wf-recorder, pw-record y ffmpeg.
Uso:  screencapture                      ventana principal
      screencapture --shot [full|region] captura inmediata y abre el editor        --record [full|region]   empieza a grabar (de nuevo = parar)
      screencapture --present            modo presentación                            --camera                 burbuja de cámara"""
import os, sys, time, subprocess
_LS = "/usr/lib/x86_64-linux-gnu/libgtk4-layer-shell.so.0"                                      # layer-shell antes que libwayland (necesario con Python)
if "libgtk4-layer-shell" not in os.environ.get("LD_PRELOAD", "") and os.path.exists(_LS):
    os.environ["LD_PRELOAD"] = (_LS + " " + os.environ.get("LD_PRELOAD", "")).strip(); os.execv(sys.executable, [sys.executable] + sys.argv)
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gdk, Gio, GLib, Gtk4LayerShell as LS
os.environ.pop("LD_PRELOAD", None)          # la capa de paneles ya está cargada en ESTE proceso; los programas que lance (terminales, cajas de desarrollo…) no deben heredarla: en otros entornos no existe y escribía un error en cada comando
from . import core
owee_config = None                                                       # integración opcional con una paleta de escritorio (en OweeLinux la daba owee_config); aquí, colores propios
from . import editor as ed
from . import overlay as ov
from .i18n import _
from . import i18n as _i18n; _i18n.apply_direction()

CSS = """
window.cap { background: @bg@; color: @fg@; }
.cap .title { font-weight: bold; font-size: 15pt; } .cap .big { font-size: 12pt; padding: 14px 10px; border-radius: 12px; background-image: none; border: none; box-shadow: none; background: @key@; color: @fg@; } .cap .big:hover { background: @keyh@; }
.cap .go { background: @accent@; color: @on@; font-weight: bold; } .cap .rec { background: #F06548; color: #fff; font-weight: bold; }
.cap .seg button { background: @key@; color: @fg@; border: none; box-shadow: none; background-image: none; border-radius: 8px; padding: 6px 18px; } .cap .seg button.on { background: @accent@; color: @on@; }
.cap switch:checked { background: @accent@; } .cap switch:checked slider { background: @on@; }
.cap .setrow { padding: 6px 0; border-bottom: 1px solid alpha(@fg@, 0.1); }
window.pill, window.pill > * { background: transparent; } .pillbox { background: rgba(16,32,25,0.94); border: 1px solid #F06548; border-radius: 999px; padding: 4px 10px; color: #EFF0F1; }
.pillbox button { background: #F06548; color: #fff; border: none; border-radius: 999px; background-image: none; box-shadow: none; font-weight: bold; padding: 2px 12px; min-height: 0; } .pillbox button.alt { background: #2b4a3d; }
.count { font-size: 80pt; font-weight: bold; color: #fff; text-shadow: 0 0 20px #000; }
"""

def colors():
    if owee_config:
        pal = owee_config.palette(owee_config.load())
        return dict(bg=pal["win"], fg=pal["fg"], key=pal["key"], keyh=pal["keyh"], accent=pal["accent"], on=pal["on"]), pal["icons"]
    return dict(bg="#102019", fg="#EFF0F1", key="#1b3128", keyh="#264438", accent="#2A9D8F", on="#102019"), "Owee"

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.screencapture.App", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.cfg = core.load_cfg(); self.rec = core.Recorder(); self.win = None; self.pill = None; self.cam = None; self.pres = None; self.tick_id = 0
        for name, fn in (("stop", lambda *a: self.stop_recording()), ("present", lambda *a: self.present_mode()), ("camera", lambda *a: self.toggle_camera())):
            act = Gio.SimpleAction.new(name, None); act.connect("activate", fn); self.add_action(act)     # el panel controla la grabación con `gapplication action org.screencapture.App stop|present|camera`

    STATE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "screencapture-recording")
    @staticmethod
    def panel_present():
        """¿Hay un panel de OweeLinux que pueda mostrar los controles de grabación? (dueño del nombre org.oweelinux.PanelPrototype en el bus de sesión)"""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            r = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner", GLib.Variant("(s)", ("org.oweelinux.PanelPrototype",)), GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 800, None)
            return bool(r.unpack()[0])
        except GLib.Error: return False

    def restyle(self):
        col, icons = colors(); css = CSS
        for k, v in col.items(): css = css.replace("@%s@" % k, v)
        css = css.replace("alpha(@fg@, 0.1)", "rgba(128,128,128,0.2)")
        if not hasattr(self, "prov"):
            self.prov = Gtk.CssProvider(); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.prov.load_from_string(css); Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)

    def do_command_line(self, cl):
        args = cl.get_arguments()[1:]; self.restyle(); self.hold_once()
        def opt(name, default=None):
            if name in args:
                i = args.index(name); return args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else default
            return None
        if "--shot" in args: self.do_shot(opt("--shot", "full") or "full")
        elif "--record" in args:
            if self.rec.running: self.stop_recording()
            else: self.start_recording(opt("--record", "full") or "full")
        elif "--present" in args: self.present_mode()
        elif "--camera" in args: self.toggle_camera()
        else: self.show_main()
        return 0

    def hold_once(self):
        if not getattr(self, "_held", False): self._held = True; self.hold()

    def quit_if_idle(self):
        if getattr(self, "pending_main", False): return
        if not self.rec.running and not self.pres and not self.cam and not self.win and not [w for w in self.get_windows() if isinstance(w, ed.Editor)]:
            self.release(); self._held = False

    # --- ventana principal
    def hide_main(self):
        """Quita la ventana principal mientras se captura o graba. Se DESTRUYE y se vuelve a crear después: una ventana minimizada o escondida que reaparece pierde en labwc
        su barra de título; una ventana nueva, no."""
        if self.win: w, self.win = self.win, None; self.reopen = True; w.destroy()
    def restore_main(self):
        if getattr(self, "reopen", False): self.reopen = False; self.pending_main = True; GLib.timeout_add(300, lambda: (setattr(self, "pending_main", False), self.show_main(), False)[2])
    def show_main(self):
        if self.win: self.win.present(); return
        if not self.rec.running and core.leftovers(): self.recover_orphans()      # una grabación anterior se cortó de golpe: se guarda lo que quedó
        w = self.win = Gtk.ApplicationWindow(application=self, title=_("Capturadora"), icon_name="screencapture", default_width=480, default_height=560); w.add_css_class("cap")
        w.connect("close-request", lambda x: (setattr(self, "win", None), GLib.idle_add(self.quit_if_idle), False)[2])
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=16, margin_bottom=16, margin_start=18, margin_end=18); w.set_child(root)
        root.append(Gtk.Label(label=_("Capturadora"), xalign=0, css_classes=["title"]))
        seg = Gtk.Box(spacing=6, css_classes=["seg"]); self.b_img = Gtk.Button(label=_("Imagen")); self.b_vid = Gtk.Button(label=_("Vídeo")); seg.append(self.b_img); seg.append(self.b_vid); root.append(seg)
        self.stack = Gtk.Stack(); root.append(self.stack); self.b_img.connect("clicked", lambda b: self.page("img")); self.b_vid.connect("clicked", lambda b: self.page("vid"))
        self.stack.add_named(self.page_img(), "img"); self.stack.add_named(self.page_vid(), "vid")
        root.append(Gtk.Box(vexpand=True)); foot = Gtk.Box(spacing=8); root.append(foot)
        for label, fn in ((_("Abrir carpeta de capturas"), lambda b: self.open_dir(core.DIR_IMG)), (_("Abrir carpeta de grabaciones"), lambda b: self.open_dir(core.DIR_VID))):
            b = Gtk.Button(label=label, css_classes=["flat"]); b.connect("clicked", fn); foot.append(b)
        self.msg = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label"]); root.append(self.msg)
        self.page("img"); w.present()
        if getattr(self, "last_msg", ""): self.msg.set_text(self.last_msg)

    def page(self, k):
        self.stack.set_visible_child_name(k)
        for b, kk in ((self.b_img, "img"), (self.b_vid, "vid")): (b.add_css_class if kk == k else b.remove_css_class)("on")

    def row(self, label, widget, hint=""):
        r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["setrow"]); h = Gtk.Box(spacing=10); h.append(Gtk.Label(label=label, xalign=0, hexpand=True)); widget.set_valign(Gtk.Align.CENTER); h.append(widget); r.append(h)
        if hint: r.append(Gtk.Label(label=hint, xalign=0, wrap=True, css_classes=["dim-label"]))
        return r
    def set(self, **kw): self.cfg.update(kw); core.save_cfg(self.cfg)
    def sw(self, key, **kw):
        s = Gtk.Switch(active=bool(self.cfg[key]), **kw); s.connect("notify::active", lambda w, _p: self.set(**{key: w.get_active()})); return s
    def drop(self, key, opts):
        dd = Gtk.DropDown.new_from_strings([t for _k, t in opts]); keys = [k for k, _t in opts]; cur = self.cfg[key]; dd.set_selected(keys.index(cur) if cur in keys else 0)
        dd.connect("notify::selected", lambda w, _p: self.set(**{key: keys[w.get_selected()]})); return dd

    def page_img(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for label, mode, cls in ((_("🖵  Pantalla completa"), "full", "go"), (_("⬚  Seleccionar una zona"), "region", "big")):
            btn = Gtk.Button(label=label, css_classes=["big"] + (["go"] if cls == "go" else [])); btn.connect("clicked", lambda _b, m=mode: self.do_shot(m)); b.append(btn)
        b.append(self.row(_("Temporizador"), self.drop("timer", [(0, _("Sin temporizador")), (3, _("3 segundos")), (5, _("5 segundos")), (10, _("10 segundos"))])))
        b.append(self.row(_("Incluir el puntero del ratón"), self.sw("cursor"))); b.append(self.row(_("Copiar al portapapeles"), self.sw("clipboard")))
        return b

    def page_vid(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for label, mode, cls in ((_("●  Grabar pantalla completa"), "full", "rec"), (_("⬚  Grabar una zona"), "region", "big")):
            btn = Gtk.Button(label=label, css_classes=["big"] + (["rec"] if cls == "rec" else [])); btn.connect("clicked", lambda _b, m=mode: self.start_recording(m)); b.append(btn)
        sys_t, mic_t = core.audio_sources()
        b.append(self.row(_("Fotogramas por segundo"), self.drop("fps", [(15, "15"), (24, "24"), (30, "30"), (60, "60")])))
        b.append(self.row(_("Calidad del vídeo"), self.drop("quality", [("original", _("Original (máxima calidad, pesa más)")), ("buena", _("Buena (nítida, más ligera que la original)")), ("media", _("Intermedia (720p, recomendada)")), ("ligera", _("Básica (la más pequeña, ideal para WhatsApp y Telegram)"))]),
                          _("Original y Buena se guardan tal cual al grabar; Intermedia y Básica reducen el vídeo al terminar, en segundo plano, y si algo falla se conserva el original")))
        sw = self.sw("audio_system"); sw.set_sensitive(bool(sys_t)); b.append(self.row(_("Audio del sistema"), sw, "" if sys_t else _("No se detectó una salida de audio")))
        sm = self.sw("audio_mic"); sm.set_sensitive(bool(mic_t)); b.append(self.row(_("Micrófono"), sm, "" if mic_t else _("No se detectó un micrófono")))
        cs = self.sw("camera"); b.append(self.row(_("Mostrar mi cámara en la grabación"), cs, _("Una burbuja redonda que puedes arrastrar; la rueda cambia su tamaño")))
        pb = Gtk.Button(label=_("✎  Modo presentación (dibujar en pantalla)"), css_classes=["big"]); pb.connect("clicked", lambda _b: self.present_mode()); b.append(pb)
        return b

    def say(self, t):
        self.last_msg = t
        if self.win and hasattr(self, "msg"): self.msg.set_text(t)
        else: print("[capturadora]", t, flush=True)

    def open_dir(self, d):
        os.makedirs(d, exist_ok=True); Gio.AppInfo.launch_default_for_uri("file://" + d, None)

    # --- capturas
    def do_shot(self, mode):
        geometry = None
        self.hide_main()
        delay = 400                                                                     # tiempo para que la ventana desaparezca del todo
        def go():
            nonlocal geometry
            if mode == "region":
                geometry = core.select_region()
                if not geometry: self.after_cancel(); return False
            t = int(self.cfg["timer"])
            if t: self.countdown(t, lambda: self.take(geometry))
            else: GLib.timeout_add(150, lambda: (self.take(geometry), False)[1])
            return False
        GLib.timeout_add(delay, go)

    def after_cancel(self):
        self.restore_main(); self.quit_if_idle()

    def take(self, geometry):
        def work(): return core.shot(geometry, cursor=bool(self.cfg["cursor"]))
        def done(path, err):
            if err: self.say(err); self.after_cancel(); return
            if self.cfg["clipboard"]: core.copy_image(path)
            self.reopen = False                                                          # el editor es ahora el foco; la Capturadora se reabre desde el lanzador
            ed.open_editor(self, path)
            self.say(_("Guardada en ") + path + (_(" y copiada al portapapeles") if self.cfg["clipboard"] else ""))
        core.run_async(work, done)

    def countdown(self, n, cb):
        w = Gtk.Window(application=self, decorated=False); w.add_css_class("pill"); LS.init_for_window(w); LS.set_layer(w, LS.Layer.OVERLAY); LS.set_namespace(w, "owee-countdown"); LS.set_keyboard_mode(w, LS.KeyboardMode.NONE); LS.set_exclusive_zone(w, -1)
        lab = Gtk.Label(label=str(n), css_classes=["count"]); w.set_child(lab); w.present(); left = [n]
        def tick():
            left[0] -= 1
            if left[0] <= 0: w.close(); GLib.timeout_add(250, lambda: (cb(), False)[1]); return False
            lab.set_text(str(left[0])); return True
        GLib.timeout_add_seconds(1, tick)

    # --- vídeo
    def start_recording(self, mode):
        if self.rec.running: return
        self.hide_main()
        def go():
            geometry = None
            if mode == "region":
                geometry = core.select_region()
                if not geometry: self.after_cancel(); return False
            def begin():
                if self.cfg["camera"]: self.toggle_camera(force=True)
                def work(): self.rec.start(geometry, int(self.cfg["fps"]), bool(self.cfg["audio_system"]), bool(self.cfg["audio_mic"]), str(self.cfg["quality"])); return True
                def done(_r, err):
                    if err: self.say(err); self.close_cam(); self.after_cancel(); return
                    self.show_pill()
                core.run_async(work, done)
            self.countdown(3, begin); return False
        GLib.timeout_add(400, go)

    def show_pill(self):
        if self.panel_present():              # controles dentro del panel (arriba), no flotando sobre la pantalla: así no salen en el vídeo
            try: open(self.STATE, "w").write(str(int(time.time()) - self.rec.elapsed()))
            except OSError: pass
            return
        w = self.pill = Gtk.Window(application=self, decorated=False); w.add_css_class("pill"); LS.init_for_window(w); LS.set_layer(w, LS.Layer.OVERLAY); LS.set_namespace(w, "owee-rec"); LS.set_keyboard_mode(w, LS.KeyboardMode.NONE)
        LS.set_anchor(w, LS.Edge.TOP, True); LS.set_anchor(w, LS.Edge.RIGHT, True); LS.set_margin(w, LS.Edge.TOP, 52); LS.set_margin(w, LS.Edge.RIGHT, 12)
        box = Gtk.Box(spacing=8, css_classes=["pillbox"]); self.timer_l = Gtk.Label(label="●  00:00"); box.append(self.timer_l)
        pen = Gtk.Button(label="✎", css_classes=["alt"], tooltip_text=_("Modo presentación (dibujar)")); pen.connect("clicked", lambda b: self.present_mode()); box.append(pen)
        cam = Gtk.Button(label="📷", css_classes=["alt"], tooltip_text=_("Mostrar u ocultar la cámara")); cam.connect("clicked", lambda b: self.toggle_camera()); box.append(cam)
        st = Gtk.Button(label=_("■ Detener")); st.connect("clicked", lambda b: self.stop_recording()); box.append(st); w.set_child(box); w.present()
        self.tick_id = GLib.timeout_add_seconds(1, self.tick_pill)

    def tick_pill(self):
        if not self.rec.running: return False
        s = self.rec.elapsed(); self.timer_l.set_text(f"●  {s // 60:02d}:{s % 60:02d}"); return True

    def recover_orphans(self):
        """«Detener» sin grabación propia: puede que una grabación quedara en marcha sin su Capturadora (la aplicación se cerró o falló). Se detiene y se guarda lo grabado, y se quita el aviso del panel."""
        try: os.remove(self.STATE)
        except OSError: pass
        def done(paths, err):
            if err: self.say(err); return
            if paths: self.notify(_("Grabación guardada"), "\n".join(paths)); self.say(_("Grabación guardada: ") + paths[0])
            GLib.idle_add(self.quit_if_idle)
        core.run_async(core.recover_orphans, done)

    def stop_recording(self):
        if not self.rec.running:
            if not getattr(self, "saving", False): self.recover_orphans()
            return
        self.saving = True
        if self.pill: self.timer_l.set_text(_("Guardando…"))
        self.close_cam()                  # la cámara se apaga al instante; guardar puede tardar unos segundos
        try: os.remove(self.STATE)
        except OSError: pass
        def done(path, err):
            self.saving = False
            if self.pill: self.pill.close(); self.pill = None
            self.close_cam()
            if self.pres: self.pres.finish()
            if err: self.say(err)
            else:
                lite = core.QUALITY.get(self.rec.quality, (0, 0, None))[2] is not None and path.endswith(".mp4")
                self.say(_("Grabación guardada: ") + path + (_(" · la versión reducida se prepara en segundo plano y reemplazará a este archivo") if lite else ""))
                self.notify(_("Grabación guardada"), path + (("\n" + _("Reduciendo el tamaño en segundo plano…")) if lite else ""))
                self.restore_main()
            GLib.idle_add(self.quit_if_idle)
        core.run_async(self.rec.stop, done)

    def notify(self, title, body):
        try: subprocess.Popen(["notify-send", "-i", "screencapture", title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: pass

    # --- extras
    def toggle_camera(self, force=False):
        if self.cam: 
            if not force: self.close_cam()
            return
        from . import camera
        ok, why = camera.available()
        if not ok: self.say(_("Cámara: ") + why); self.notify(_("Cámara no disponible"), why); return
        self.cam = camera.Bubble(self); self.cam.start()
    def close_cam(self):
        if self.cam: self.cam.stop(); self.cam = None

    def present_mode(self):
        if self.pres: self.pres.finish(); return
        self.hide_main()
        self.pres = ov.Overlay(self, on_close=lambda: (setattr(self, "pres", None), self.after_cancel() if not self.rec.running else None)); self.pres.present()

if __name__ == "__main__": sys.exit(App().run(sys.argv))

def main():
    return App().run(sys.argv)

if __name__ == "__main__": sys.exit(main())
