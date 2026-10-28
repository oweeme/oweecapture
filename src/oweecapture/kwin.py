"""Pieza específica de KDE: en Wayland un programa no puede pedir «siempre encima» ni quitar la barra de título de sus ventanas, así que se le pide a KWin con un script mínimo por D-Bus.
En otros escritorios no hace nada (las ventanas quedan como ventanas normales)."""
import json, os, tempfile, zlib
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
    nombre = f"oweecapture-encima-{os.getpid()}-{len(_cargados)}"; ruta = os.path.join(tempfile.gettempdir(), nombre + ".js")
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
    _pendiente[0] = al_listo; _n_lista[0] += 1; nombre = f"oweecapture-ventanas-{os.getpid()}-{_n_lista[0]}"; ruta = os.path.join(tempfile.gettempdir(), nombre + ".js")
    with open(ruta, "w") as f:
        f.write("var l = [];\nworkspace.stackingOrder.forEach(function (w) {\n"
                "  if (!w.normalWindow || w.minimized || w.caption.indexOf(\"OweeCapture\") === 0) return;\n"
                "  if (w.desktops.length > 0 && w.desktops.indexOf(workspace.currentDesktop) < 0) return;\n"
                "  var g = w.frameGeometry; l.push({c: w.caption, x: Math.round(g.x), y: Math.round(g.y), w: Math.round(g.width), h: Math.round(g.height)});\n});\n"
                "callDBus(\"org.oweecapture.App\", \"/org/oweecapture/App\", \"org.oweecapture.App\", \"RecibirVentanas\", JSON.stringify(l));\n")
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

# --- seguimiento del cursor (para el zoom y el halo): en Wayland un programa no puede leer el puntero fuera de sus ventanas, pero KWin sí; un script QML lo lee unas 30 veces por segundo y lo envía por lotes ---
_QML = ("import QtQuick\nimport org.kde.kwin\nItem {\n    property var lote: []\n"
        "    DBusCall { id: envio; service: \"org.oweecapture.App\"; path: \"/org/oweecapture/App\"; dbusInterface: \"org.oweecapture.App\"; method: \"RecibirCursor\" }\n"
        "    Timer { interval: 33; repeat: true; running: true; onTriggered: { var p = Workspace.cursorPos; lote.push([Date.now(), Math.round(p.x), Math.round(p.y)]);\n"
        "        if (lote.length >= 6) { envio.arguments = [JSON.stringify(lote)]; envio.call(); lote = []; } } }\n}\n")
_NOMBRE_CURSOR = "oweecapture-cursor"; muestras = []; _siguiendo = [False]

def seguir_cursor():
    """Empieza a reunir las posiciones del cursor en `muestras` ([hora en ms, x, y]). Devuelve False si no hay KWin (el zoom y el halo no están disponibles en otros escritorios)."""
    if not disponible(): return False
    if _siguiendo[0]: return True
    carpeta = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "oweecapture", "kwin", format(zlib.crc32(_QML.encode()), "08x")); os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "cursor.qml")      # KWin guarda el QML en caché por ruta: una carpeta por versión del texto evita que se use una copia vieja
    if not os.path.exists(ruta): open(ruta, "w").write(_QML)
    muestras.clear(); _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", _NOMBRE_CURSOR)
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadDeclarativeScript", ruta, _NOMBRE_CURSOR); ident = r.arguments()[0] if r.arguments() else -1
    if ident < 0: return False
    _kwin(f"/Scripting/Script{ident}", "org.kde.kwin.Script").call("run"); _siguiendo[0] = True; return True

def dejar_cursor():
    """Deja de seguir el cursor y devuelve lo reunido."""
    if _siguiendo[0]: _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", _NOMBRE_CURSOR); _siguiendo[0] = False
    reunido = list(muestras); muestras.clear(); return reunido

def recibir_cursor(texto):
    if _siguiendo[0]:
        try: muestras.extend(json.loads(texto))
        except ValueError: pass
