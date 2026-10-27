"""Atajos globales (Ctrl+Alt+R grabar o detener, Ctrl+Alt+S captura, Ctrl+Alt+P pausar o continuar, Ctrl+Alt+D modo presentación, Ctrl+Alt+Z zoom, Ctrl+Alt+G clip de los últimos segundos) por el portal GlobalShortcuts: KDE 6 y GNOME con el mismo código. Se emite `activado("grabar" | "captura")`.
Dos cosas que se descubrieron en KDE neon (Plasma 6.8): el portal solo atiende a una aplicación con identificador propio y un `.desktop` instalado (screencapture.desktop), y KDE deja la tecla preferida como
«ninguna»; hay que asignarla con `kglobalaccel` (pieza específica de KDE, solo si el atajo aún no tiene tecla: no se pisa lo que el usuario cambie en Ajustes)."""
import os
import dbus, dbus.mainloop.glib
from PySide6.QtCore import QObject, Signal

ATAJOS = [("grabar", "Grabar la pantalla (empezar / detener)", "CTRL+ALT+r", 0x04000000 | 0x08000000 | ord("R")),
          ("captura", "Hacer una captura de pantalla", "CTRL+ALT+s", 0x04000000 | 0x08000000 | ord("S")),
          ("pausar", "Pausar o continuar la grabación", "CTRL+ALT+p", 0x04000000 | 0x08000000 | ord("P")),
          ("clip", "Guardar un clip de los últimos segundos", "CTRL+ALT+g", 0x04000000 | 0x08000000 | ord("G")),
          ("zoom", "Acercar o alejar (zoom) mientras se graba", "CTRL+ALT+z", 0x04000000 | 0x08000000 | ord("Z")),
          ("presentacion", "Activar o desactivar el modo presentación", "CTRL+ALT+d", 0x04000000 | 0x08000000 | ord("D"))]

class Atajos(QObject):
    activado = Signal(str); fallo = Signal(str)

    def __init__(self):
        super().__init__(); dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); self.n = 0

    def iniciar(self):
        self.bus = dbus.SessionBus()
        try: self.gs = dbus.Interface(self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.GlobalShortcuts")
        except dbus.DBusException as e: self.fallo.emit(str(e)); return
        self.bus.add_signal_receiver(lambda ses, id_, t, op: self.activado.emit(str(id_)), "Activated", "org.freedesktop.portal.GlobalShortcuts")
        self._peticion(self.gs.CreateSession, opciones={"session_handle_token": f"sc{os.getpid()}"}, siguiente=self._asignar)

    def _peticion(self, metodo, *args, opciones, siguiente):
        self.n += 1; token = f"at{os.getpid()}_{self.n}"; opciones["handle_token"] = token
        ruta = f"/org/freedesktop/portal/desktop/request/{self.bus.get_unique_name()[1:].replace('.', '_')}/{token}"
        def respuesta(codigo, resultados):
            if codigo != 0: self.fallo.emit("portal GlobalShortcuts: " + str(int(codigo))); return
            siguiente(resultados)
        self.bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta); metodo(*args, opciones)

    def _asignar(self, r):
        self.sesion = r["session_handle"]
        lista = dbus.Array([(i, {"description": d, "preferred_trigger": t}) for i, d, t, _k in ATAJOS], signature="(sa{sv})")
        self._peticion(self.gs.BindShortcuts, self.sesion, lista, "", opciones={}, siguiente=lambda _r: self._kde())

    def _kde(self):
        """KDE: si el atajo no tiene tecla (la preferida queda solo como predeterminada), se le pone la de la lista."""
        try:
            ga = dbus.Interface(self.bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"), "org.kde.KGlobalAccel")
            for ident, desc, _t, tecla in ATAJOS:
                aid = dbus.Array(["screencapture", ident, "Screencapture", desc], signature="s")
                if not [k for k in ga.shortcut(aid) if int(k)]: ga.setForeignShortcut(aid, dbus.Array([tecla], signature="i"))
        except dbus.DBusException: pass                                  # no es KDE: el escritorio muestra su propio diálogo de atajos
