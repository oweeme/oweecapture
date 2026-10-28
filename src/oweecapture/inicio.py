"""Iniciar OweeCapture con el escritorio: un archivo en ~/.config/autostart (estándar freedesktop: lo respetan KDE, GNOME, Deepin y compañía) que arranca la aplicación en segundo plano (`--segundo-plano`: solo el icono de la bandeja y los atajos).
Así los atajos (Ctrl+Alt+R grabar, Ctrl+Alt+S captura…) responden desde que se inicia la sesión, sin abrir la ventana. Con la aplicación ya abierta, una segunda instancia solo le pasa la orden (ver servicio.py), así que no hay duplicados.
Sin interfaz: se prueba con una carpeta de configuración falsa."""
import os, shlex, shutil, sys

NOMBRE = "oweecapture.desktop"

def carpeta(base=None):
    return os.path.join(base or os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"), "autostart")

def ruta(base=None): return os.path.join(carpeta(base), NOMBRE)

def comando():
    """La orden de arranque: el programa instalado (`oweecapture`) si está en el PATH; si no (una copia del código), el mismo Python con PYTHONPATH apuntando a este código."""
    ejecutable = shutil.which("oweecapture")
    if ejecutable: return f"{shlex.quote(ejecutable)} --segundo-plano"
    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"env PYTHONPATH={shlex.quote(src)} {shlex.quote(sys.executable)} -m oweecapture.qtapp --segundo-plano"

def contenido():
    return ("[Desktop Entry]\nType=Application\nName=OweeCapture\nComment=Atajos de captura y grabación siempre activos\n"
            f"Exec={comando()}\nIcon=oweecapture\nTerminal=false\nStartupNotify=false\nX-GNOME-Autostart-enabled=true\nX-KDE-autostart-after=panel\n")

def activado(base=None): return os.path.exists(ruta(base))

def activar(base=None):
    """Crea el archivo de autoarranque (de forma atómica: nunca queda a medias)."""
    os.makedirs(carpeta(base), exist_ok=True); destino = ruta(base); tmp = destino + ".tmp"
    with open(tmp, "w") as f: f.write(contenido())
    os.replace(tmp, destino)

def desactivar(base=None):
    """Quita el archivo de autoarranque (solo el de OweeCapture)."""
    try: os.remove(ruta(base))
    except FileNotFoundError: pass
