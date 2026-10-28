# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Copia web\\ (la app del celular) a una carpeta de grabacion y le agrega herramientas\\gifs\\mock_celular.js (chats FICTICIOS).
Uso: python armar_celular.py <carpeta_destino>   (se borra y se rehace; web\\ original no se toca; sin respaldos .bak ni muestras)"""
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
destino = sys.argv[1]
if os.path.exists(destino):
    shutil.rmtree(destino)
shutil.copytree(os.path.join(APP, "web"), destino, ignore=shutil.ignore_patterns("*.bak*", "muestras", "maquetas*", "bench.html", "GSDevTools*", "ajustes.json"))
shutil.copy(os.path.join(APP, "herramientas", "gifs", "mock_celular.js"), os.path.join(destino, "mock_celular.js"))
p = os.path.join(destino, "app.html")
t = open(p, encoding="utf-8").read()
assert "<head>" in t
t = t.replace("<head>", '<head>\n<script src="mock_celular.js"></script>', 1)
open(p, "w", encoding="utf-8").write(t)
print("listo:", destino)
