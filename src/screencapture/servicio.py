"""Una sola instancia: la primera que arranca ofrece el servicio D-Bus `org.screencapture.App`; las siguientes (o una orden como `screencapture --shot`) le envían la orden y terminan.
Sirve también para asignar atajos a mano en cualquier escritorio: `screencapture --shot`, `--record`, `--present`, `--quit`."""
import dbus, dbus.mainloop.glib, dbus.service
from . import kwin

NOMBRE = "org.screencapture.App"; RUTA = "/org/screencapture/App"
ORDENES = {"--shot": "Captura", "--record": "Grabar", "--present": "Presentacion", "--quit": "Salir"}       # opción de la línea de órdenes → método

class Servicio(dbus.service.Object):
    def __init__(self, ventana, nombre):
        super().__init__(nombre, RUTA); self.v = ventana
    @dbus.service.method(NOMBRE)
    def Captura(self): self.v.captura()
    @dbus.service.method(NOMBRE)
    def Grabar(self): self.v.alternar()
    @dbus.service.method(NOMBRE)
    def Presentacion(self): self.v.presentacion()
    @dbus.service.method(NOMBRE)
    def Mostrar(self): self.v.show(); self.v.raise_(); self.v.activateWindow()
    @dbus.service.method(NOMBRE)
    def Salir(self): self.v.salir()
    @dbus.service.method(NOMBRE, in_signature="s")
    def RecibirVentanas(self, texto): kwin.recibir_ventanas(str(texto))      # lo llama el script que se carga en KWin (kwin.listar_ventanas)

def en_marcha():
    """True si ya hay otra instancia ofreciendo el servicio."""
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    return dbus.SessionBus().name_has_owner(NOMBRE)

def enviar(metodo):
    getattr(dbus.Interface(dbus.SessionBus().get_object(NOMBRE, RUTA), NOMBRE), metodo)()

def ofrecer(ventana):
    """Registra el servicio; devuelve el objeto (hay que conservarlo mientras viva la aplicación)."""
    return Servicio(ventana, dbus.service.BusName(NOMBRE, dbus.SessionBus(), do_not_queue=True))
