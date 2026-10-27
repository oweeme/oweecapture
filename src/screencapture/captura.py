"""Captura de pantalla por el portal Screenshot (KDE, GNOME y cualquier escritorio con portal): sin `grim`. La primera vez el escritorio pide permiso y luego lo recuerda.
Con el selector de zona la imagen se toma ANTES de mostrar el selector (queda congelada debajo) y después se recorta."""
import os
from urllib.parse import unquote, urlparse
import dbus, dbus.mainloop.glib
from PySide6.QtGui import QGuiApplication, QImage
from . import core
from .i18n import _

_n = [0]

def tomar(al_listo, al_fallar):
    """Pide al portal una captura de toda la pantalla. `al_listo(QImage)` o `al_fallar(mensaje)`, en el hilo de la interfaz."""
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True); bus = dbus.SessionBus()
    portal = dbus.Interface(bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"), "org.freedesktop.portal.Screenshot")
    _n[0] += 1; token = f"shot{os.getpid()}_{_n[0]}"; ruta = f"/org/freedesktop/portal/desktop/request/{bus.get_unique_name()[1:].replace('.', '_')}/{token}"
    def respuesta(codigo, resultados):
        if codigo != 0: al_fallar(_("Se canceló la captura.") if codigo == 1 else _("El portal no pudo capturar la pantalla.")); return
        archivo = unquote(urlparse(str(resultados["uri"])).path); img = QImage(archivo)
        try: os.remove(archivo)                                                    # el portal deja el PNG en una carpeta temporal; no se conserva
        except OSError: pass
        if img.isNull(): al_fallar(_("No se pudo leer la captura.")); return
        al_listo(img)
    bus.add_signal_receiver(respuesta, "Response", "org.freedesktop.portal.Request", path=ruta)
    portal.Screenshot("", {"handle_token": token, "interactive": False, "modal": False})

def guardar(img, copiar=True):
    """Guarda `img` como PNG en la carpeta de capturas y, si se pide, la copia al portapapeles. Devuelve la ruta."""
    os.makedirs(core.DIR_IMG, exist_ok=True); ruta = os.path.join(core.DIR_IMG, f"captura-{core.stamp()}.png")
    if not img.save(ruta): raise RuntimeError(_("No se pudo guardar la captura."))
    if copiar: QGuiApplication.clipboard().setImage(img)
    return ruta
