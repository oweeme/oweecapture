"""Pieza específica de KDE: en Wayland un programa no puede pedir «siempre encima» ni quitar la barra de título de sus ventanas, así que se le pide a KWin con un script mínimo por D-Bus.
En otros escritorios no hace nada (las ventanas quedan como ventanas normales)."""
import json, os, tempfile, zlib
import dbus, dbus.mainloop.glib
from PySide6.QtCore import QTimer

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)          # D-Bus con dbus-python (que la aplicación ya necesita para el portal y los atajos): así no hace falta el módulo QtDBus de PySide6, que algunas distribuciones (Deepin) no empaquetan
_cargados = []; _TIEMPO = 5          # segundos máximos que se espera a KWin en cada llamada

class _Respuesta:
    """La respuesta de una llamada a KWin: `arguments()` es la lista de valores devueltos, o un único texto de error si la llamada falló."""
    def __init__(self, valores): self.valores = valores
    def arguments(self): return self.valores

class _Interfaz:
    """Una interfaz de KWin; `call(método, argumentos…)` no lanza excepciones: si KWin no está o falla, devuelve una respuesta con el texto del error."""
    def __init__(self, ruta, interfaz): self.ruta = ruta; self.interfaz = interfaz
    def call(self, metodo, *args):
        try:
            extra = {"signature": "s" * len(args)} if args and all(isinstance(x, str) for x in args) else {}          # KWin ofrece loadScript(ruta) y loadScript(ruta, nombre): sin firma explícita dbus-python elige la primera y falla
            r = getattr(dbus.Interface(dbus.SessionBus().get_object("org.kde.KWin", self.ruta), self.interfaz), metodo)(*args, timeout=_TIEMPO, **extra)
            return _Respuesta([] if r is None else [r])
        except dbus.DBusException as e: return _Respuesta([str(e)])

def _kwin(ruta, interfaz): return _Interfaz(ruta, interfaz)

def _entero(respuesta):
    """El identificador de script que devuelve KWin, o -1 si la llamada falló (entonces el primer argumento es un texto de error)."""
    a = respuesta.arguments()
    return int(a[0]) if a and isinstance(a[0], int) and not isinstance(a[0], bool) else -1

def disponible():
    """True solo si hay un KWin en la sesión (KDE Plasma). En GNOME, Deepin sin KWin o una sesión sin bus, False."""
    try: return bool(dbus.SessionBus().name_has_owner("org.kde.KWin"))
    except dbus.DBusException: return False

def mantener_encima(titulos):
    """Deja siempre encima, sin marco y fuera de la barra de tareas las ventanas cuyo título esté en `titulos`. Devuelve True si KWin cargó el script."""
    if not disponible(): return False
    nombre = f"oweecapture-encima-{os.getpid()}-{len(_cargados)}"; ruta = os.path.join(tempfile.gettempdir(), nombre + ".js")
    with open(ruta, "w") as f:
        f.write(f"const titulos = {json.dumps(titulos)};\n"
                "function preparar(w) { if (titulos.indexOf(w.caption) < 0) return; w.keepAbove = true; w.skipTaskbar = true; w.skipPager = true; w.skipSwitcher = true; w.noBorder = true; }\n"
                "workspace.windowList().forEach(preparar); workspace.windowAdded.connect(preparar);\n")
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadScript", ruta, nombre); ident = _entero(r)
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
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadScript", ruta, nombre); ident = _entero(r)
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
_NOMBRE_CURSOR = "oweecapture-cursor"; muestras = []; _siguiendo = [False]; _usos = [0]; ultima = [None]          # _usos: cuántos lo están usando a la vez (zoom/halo al grabar y ondas de clic); el script de KWin se descarga cuando el último termina

def seguir_cursor():
    """Empieza a reunir las posiciones del cursor en `muestras` ([hora en ms, x, y]). Devuelve False si no hay KWin (el zoom y el halo no están disponibles en otros escritorios)."""
    if not disponible(): return False
    _usos[0] += 1
    if _siguiendo[0]: return True
    carpeta = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "oweecapture", "kwin", format(zlib.crc32(_QML.encode()), "08x")); os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "cursor.qml")      # KWin guarda el QML en caché por ruta: una carpeta por versión del texto evita que se use una copia vieja
    if not os.path.exists(ruta): open(ruta, "w").write(_QML)
    muestras.clear(); _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", _NOMBRE_CURSOR)
    r = _kwin("/Scripting", "org.kde.kwin.Scripting").call("loadDeclarativeScript", ruta, _NOMBRE_CURSOR); ident = _entero(r)
    if ident < 0: _usos[0] -= 1; return False
    _kwin(f"/Scripting/Script{ident}", "org.kde.kwin.Script").call("run"); _siguiendo[0] = True; return True

def dejar_cursor():
    """Un uso menos del seguimiento. Si era el último, lo para y devuelve lo reunido (vaciándolo); si aún lo usa otro, devuelve una copia y lo deja en marcha."""
    if _usos[0] > 0: _usos[0] -= 1
    if _usos[0] > 0: return list(muestras)
    if _siguiendo[0]: _kwin("/Scripting", "org.kde.kwin.Scripting").call("unloadScript", _NOMBRE_CURSOR); _siguiendo[0] = False
    reunido = list(muestras); muestras.clear(); return reunido

def recibir_cursor(texto):
    if _siguiendo[0]:
        try: muestras.extend(json.loads(texto))
        except ValueError: return
        if muestras: ultima[0] = muestras[-1]
        if len(muestras) > 400_000: del muestras[:200_000]          # tope (≈ 3 h a 30 muestras por segundo)

def ultima_posicion():
    """(x, y) de la última posición conocida del cursor (hace menos de ~35 ms mientras se sigue) o None."""
    return (ultima[0][1], ultima[0][2]) if ultima[0] else None
