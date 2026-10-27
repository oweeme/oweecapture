"""Prototipo: atajos globales por el portal GlobalShortcuts (KDE 6 y GNOME). Registra Ctrl+Alt+R (grabar) y Ctrl+Alt+S (captura) y escribe cada vez que se pulsan.
Uso: python3 prototipos/atajos_globales.py [segundos]   (por defecto 60). El portal puede mostrar un diálogo para confirmar las teclas la primera vez."""
import sys, time
import dbus, dbus.mainloop.glib
from gi.repository import GLib

SEGUNDOS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus(); loop = GLib.MainLoop()
gs = dbus.Interface(bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.GlobalShortcuts")
yo = bus.get_unique_name()[1:].replace(".", "_"); n = [0]; sesion = [None]

def peticion(metodo, *args, opciones, siguiente):
    n[0] += 1; token = f"gs{n[0]}"; opciones["handle_token"] = token
    ruta = f"/org/freedesktop/portal/desktop/request/{yo}/{token}"
    def respuesta(codigo, resultados):
        print("Portal:", metodo._method_name, "→", int(codigo), "(0 = bien, 1 = cancelado, 2 = error)", flush=True)
        if codigo != 0: loop.quit(); return
        siguiente(resultados)
    bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
    metodo(*args, opciones)

def atajos(r):
    sesion[0] = r["session_handle"]
    lista = dbus.Array([("grabar", {"description": "Grabar la pantalla (empezar / detener)", "preferred_trigger": "CTRL+ALT+r"}),
                        ("captura", {"description": "Hacer una captura de pantalla", "preferred_trigger": "CTRL+ALT+s"})], signature="(sa{sv})")
    peticion(gs.BindShortcuts, sesion[0], lista, "", opciones={}, siguiente=lambda r2: (print("Asignados:", [(str(a), dict(b).get("trigger_description")) for a, b in r2.get("shortcuts", [])], flush=True)))

bus.add_signal_receiver(lambda ses, id_, t, op: print(f"PULSADO: {id_}", flush=True), "Activated", "org.freedesktop.portal.GlobalShortcuts")
peticion(gs.CreateSession, opciones={"session_handle_token": "sc_atajos"}, siguiente=atajos)
GLib.timeout_add_seconds(SEGUNDOS, lambda: (loop.quit(), False)[1]); loop.run()
