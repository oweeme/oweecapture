"""Ejecuta todas las pruebas y sale con el resultado REAL (0 si pasan todas, 1 si falla alguna) sin pasar por el desmontaje final del intérprete.
Motivo: con el PySide6 de PyPI junto a GStreamer y GLib del sistema (como en la integración continua de Ubuntu), el proceso aborta al cerrarse con «malloc_consolidate(): unaligned fastbin chunk»
DESPUÉS de que las pruebas hayan pasado, y eso volvía roja una ejecución correcta. Uso: python3 tests/ejecutar.py"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
resultado = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.flush(); sys.stderr.flush(); os._exit(0 if resultado.wasSuccessful() else 1)
