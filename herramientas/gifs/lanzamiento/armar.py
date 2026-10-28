# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Arma la carpeta de grabacion: copia escritorio-tauri\\ui\\ (la pagina REAL de la mascota) y escritorio-tauri\\ui\\ + fake-tauri.js.
Uso: python armar.py <carpeta_destino>   (la carpeta se borra y se rehace; nunca toca ui\\ original)"""
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
destino = sys.argv[1]
if os.path.exists(destino):
    shutil.rmtree(destino)
shutil.copytree(os.path.join(APP, "escritorio-tauri", "ui"), destino)
shutil.copy(os.path.join(AQUI, "fake-tauri.js"), os.path.join(destino, "_fake-tauri.js"))
p = os.path.join(destino, "index.html")
t = open(p, encoding="utf-8").read()
marca = '<script src="companero-tauri.js"></script>'
assert marca in t
t = t.replace(marca, '<script src="_fake-tauri.js"></script>\n' + marca, 1)
open(os.path.join(destino, "grabar.html"), "w", encoding="utf-8").write(t)
print("listo:", destino, "->", os.path.join(destino, "grabar.html"))
