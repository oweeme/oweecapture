"""Pieza específica de KDE: en Wayland un programa no puede pedir «siempre encima» ni quitar la barra de título de sus ventanas, así que se le pide a KWin con un script mínimo por D-Bus.
En otros escritorios no hace nada (las ventanas quedan como ventanas normales)."""
import json, os, tempfile
from PySide6.QtDBus import QDBusConnection, QDBusInterface

_cargados = []

def _kwin(ruta, interfaz):
    return QDBusInterface("org.kde.KWin", ruta, interfaz, QDBusConnection.sessionBus())

def disponible():
    return QDBusConnection.sessionBus().interface().isServiceRegistered("org.kde.KWin")

def mantener_encima(titulos):
    """Deja siempre encima, sin marco y fuera de la barra de tareas las ventanas cuyo título esté en `titulos`. Devuelve True si KWin cargó el script."""
    if not disponible(): return False
    nombre = f"screencapture-encima-{os.getpid()}-{len(_cargados)}"; ruta = os.path.join(tempfile.gettempdir(), nombre + ".js")
    with open(ruta, "w") as f:
        f.write(f"const titulos = {json.dumps(titulos)};\n"
                "function preparar(w) { if (titulos.indexOf(w.caption) < 0) return; w.keepAbove = true; w.skipTaskbar = true; w.skipPager = true; w.skipSwitcher = true; w.noBorder = true; }\n"
                "workspace.windowList().forEach(preparar); workspace.windowAdded.connect(preparar);\n")
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadScript", ruta, nombre); ident = r.arguments()[0] if r.arguments() else -1
    if ident < 0: return False
    _kwin(f"/Scripting/Script{ident}", "org.kde.kwin.Script").call("run"); _cargados.append(nombre); return True

def descargar_todo():
    for nombre in _cargados: _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", nombre)
    _cargados.clear()
