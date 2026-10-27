"""Pieza específica de KDE: en Wayland un programa no puede pedir «siempre encima» ni quitar la barra de título de sus ventanas, así que se le pide a KWin con un script mínimo por D-Bus.
En otros escritorios no hace nada (las ventanas quedan como ventanas normales)."""
import json, os, tempfile
from PySide6.QtCore import QTimer
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

_pendiente = [None]; _n_lista = [0]

def listar_ventanas(al_listo):
    """Pide a KWin las ventanas normales visibles (de abajo arriba): `al_listo([{"c": título, "x", "y", "w", "h"}, …])`. KWin responde llamando a `RecibirVentanas` del servicio D-Bus de la aplicación.
    Sin KWin (o si no responde en 1 s) la lista llega vacía y el selector solo ofrece zona o pantalla completa."""
    if not disponible(): al_listo([]); return
    _pendiente[0] = al_listo; _n_lista[0] += 1; nombre = f"screencapture-ventanas-{os.getpid()}-{_n_lista[0]}"; ruta = os.path.join(tempfile.gettempdir(), nombre + ".js")
    with open(ruta, "w") as f:
        f.write("var l = [];\nworkspace.stackingOrder.forEach(function (w) {\n"
                "  if (!w.normalWindow || w.minimized || w.caption.indexOf(\"Screencapture\") === 0) return;\n"
                "  if (w.desktops.length > 0 && w.desktops.indexOf(workspace.currentDesktop) < 0) return;\n"
                "  var g = w.frameGeometry; l.push({c: w.caption, x: Math.round(g.x), y: Math.round(g.y), w: Math.round(g.width), h: Math.round(g.height)});\n});\n"
                "callDBus(\"org.screencapture.App\", \"/org/screencapture/App\", \"org.screencapture.App\", \"RecibirVentanas\", JSON.stringify(l));\n")
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadScript", ruta, nombre); ident = r.arguments()[0] if r.arguments() else -1
    if ident < 0: recibir_ventanas("[]"); return
    _kwin(f"/Scripting/Script{ident}", "org.kde.kwin.Script").call("run")
    QTimer.singleShot(1000, lambda: (recibir_ventanas("[]"), _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", nombre)))

def recibir_ventanas(texto):
    """Entrega la lista que envió el script de KWin (JSON) a quien la pidió; una respuesta tardía o repetida se ignora."""
    al_listo, _pendiente[0] = _pendiente[0], None
    if al_listo:
        try: al_listo(json.loads(texto))
        except ValueError: al_listo([])
