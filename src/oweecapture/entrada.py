"""Clics del ratón y teclas pulsadas, para resaltarlos mientras se graba o se transmite. Wayland no deja que un programa vea el ratón ni el teclado fuera de sus ventanas: la única vía es leer los dispositivos /dev/input/event*, y eso exige que el usuario
esté en el grupo «input» (`sudo usermod -aG input $USER` y volver a iniciar sesión). Sin ese permiso no se lee nada y se avisa.
PRIVACIDAD: solo se lee mientras dura la grabación o el directo, nada se guarda ni se escribe en ningún registro y por defecto solo se muestran atajos y teclas especiales (Ctrl+C, Intro, Esc…), no lo que se escribe (podrían ser contraseñas).
Sin interfaz: `Teclas` convierte códigos en texto y `Lector` lee los dispositivos en un hilo; ambos se prueban con eventos simulados."""
import os, select, struct, threading

EVENTO = struct.Struct("llHHi")              # struct input_event en Linux de 64 bits: hora (2 × long), tipo, código, valor (24 bytes)
EV_KEY = 1
BOTONES = {0x110: "izquierdo", 0x111: "derecho", 0x112: "central"}
MODIFICADORES = {29: "Ctrl", 97: "Ctrl", 56: "Alt", 100: "AltGr", 42: "Shift", 54: "Shift", 125: "Meta", 126: "Meta"}
ORDEN = ("Ctrl", "Alt", "AltGr", "Meta", "Shift")
ESPECIALES = {"Intro", "Esc", "Tab", "Supr", "Insertar", "Inicio", "Fin", "Re Pág", "Av Pág", "↑", "↓", "←", "→", "Impr Pant", "Mayús Bloq"} | {f"F{i}" for i in range(1, 13)}

def _tabla():
    t = {1: "Esc", 14: "Retroceso", 15: "Tab", 28: "Intro", 57: "Espacio", 58: "Mayús Bloq", 96: "Intro", 99: "Impr Pant", 102: "Inicio", 103: "↑", 104: "Re Pág", 105: "←", 106: "→", 107: "Fin", 108: "↓", 109: "Av Pág", 110: "Insertar", 111: "Supr",
         12: "-", 13: "=", 26: "[", 27: "]", 39: ";", 40: "'", 41: "`", 43: "\\", 51: ",", 52: ".", 53: "/", 87: "F11", 88: "F12"}
    for i, c in enumerate("1234567890"): t[2 + i] = c
    for i, c in enumerate("QWERTYUIOP"): t[16 + i] = c
    for i, c in enumerate("ASDFGHJKL"): t[30 + i] = c
    for i, c in enumerate("ZXCVBNM"): t[44 + i] = c
    for i in range(10): t[59 + i] = f"F{i + 1}"
    return t
TECLAS = _tabla()                                  # nombres por POSICIÓN física (QWERTY): los atajos como Ctrl+C salen bien aunque el teclado esté en otro idioma

class Teclas:
    """Convierte (código, valor) en el texto a mostrar. `modo`: «no» (nada), «atajos» (combinaciones con Ctrl/Alt/Meta y teclas especiales) o «todo» (también lo que se escribe)."""
    def __init__(self, modo="atajos"): self.modo = modo; self.mod = set()

    def evento(self, codigo, valor):
        """Texto de la tecla recién pulsada (p. ej. «Ctrl + Shift + S»), o None si no hay nada que mostrar. valor: 1 pulsar, 0 soltar, 2 repetir."""
        if self.modo == "no": return None
        m = MODIFICADORES.get(codigo)
        if m:
            if valor: self.mod.add((codigo, m))
            else: self.mod.discard((codigo, m))
            return None
        if valor != 1 or codigo not in TECLAS: return None
        mods = [x for x in ORDEN if any(n == x for _c, n in self.mod)]; tecla = TECLAS[codigo]
        if self.modo == "atajos" and not (set(mods) & {"Ctrl", "Alt", "AltGr", "Meta"}) and tecla not in ESPECIALES: return None          # escribir normal no se muestra
        return " + ".join(mods + [tecla])

def dispositivos(texto=None):
    """([teclados], [punteros]) como rutas /dev/input/eventN, según /proc/bus/input/devices. Teclado: el que tiene repetición de teclas (no los botones de encendido); puntero: el que tiene un manejador «mouse» (ratón, touchpad, trackpoint)."""
    if texto is None:
        try: texto = open("/proc/bus/input/devices").read()
        except OSError: return [], []
    tec, pun = [], []
    for bloque in texto.strip().split("\n\n"):
        h = next((l for l in bloque.splitlines() if l.startswith("H:")), ""); ev = next((l for l in bloque.splitlines() if l.startswith("B: EV=")), ""); n = next((w for w in h.split() if w.startswith("event")), None)
        if not n: continue
        ruta = "/dev/input/" + n
        try: bits = int(ev.split("=")[1], 16)
        except (IndexError, ValueError): bits = 0
        if "mouse" in h: pun.append(ruta)
        elif bits & 0x100000 and "kbd" in h: tec.append(ruta)
    return tec, pun

def permiso():
    """True si se puede leer al menos un teclado o un puntero (el usuario está en el grupo «input»)."""
    return any(os.access(r, os.R_OK) for r in sum(dispositivos(), []))

class Lector:
    """Lee los dispositivos en un hilo y llama a `al_evento(tipo, a, b)`: («clic», botón, apretado) o («tecla», código, valor). Se detiene con `detener()`. `rutas` permite probarlo con archivos o tuberías falsas."""
    def __init__(self, al_evento, rutas=None): self.al_evento = al_evento; self.rutas = rutas; self.fds = []; self.hilo = None; self.parar = False

    def iniciar(self):
        """Abre los dispositivos. Devuelve True si hay alguno que leer; False si no (sin permiso o sin dispositivos)."""
        for r in (self.rutas if self.rutas is not None else sum(dispositivos(), [])):
            try: self.fds.append(os.open(r, os.O_RDONLY | os.O_NONBLOCK))
            except OSError: continue
        if not self.fds: return False
        self.parar = False; self.hilo = threading.Thread(target=self._leer, daemon=True); self.hilo.start(); return True

    def _leer(self):
        resto = {fd: b"" for fd in self.fds}
        while not self.parar and self.fds:
            try: listos, _w, _x = select.select(self.fds, [], [], 0.3)
            except (OSError, ValueError): break
            for fd in listos:
                try: datos = os.read(fd, EVENTO.size * 64)
                except BlockingIOError: continue
                except OSError: continue
                if not datos: continue
                datos = resto[fd] + datos; n = len(datos) // EVENTO.size * EVENTO.size; resto[fd] = datos[n:]
                for i in range(0, n, EVENTO.size):
                    _s, _u, tipo, codigo, valor = EVENTO.unpack_from(datos, i)
                    if tipo != EV_KEY: continue
                    if codigo in BOTONES:
                        if valor in (0, 1): self.al_evento("clic", BOTONES[codigo], valor == 1)
                    else: self.al_evento("tecla", codigo, valor)

    def detener(self):
        self.parar = True
        if self.hilo: self.hilo.join(timeout=2); self.hilo = None
        for fd in self.fds:
            try: os.close(fd)
            except OSError: pass
        self.fds = []
