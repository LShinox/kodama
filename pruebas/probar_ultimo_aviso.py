# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Poda de ultimo_aviso (hub.json). Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_ultimo_aviso.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kodama_notificaciones import podar_ultimo_aviso  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


AHORA = 100000.0

ult = {f"chat{i}|termino": AHORA - 3600 for i in range(5000)}
ult.update({"nuevo|permiso": AHORA - 60, "nuevo|pregunta|x": AHORA - 60, "nuevo|error": AHORA - 60})
ult["texto|raro"] = "no es numero"
podar_ultimo_aviso(ult, AHORA)
ver("5000 viejas + 1 texto: quedan exactamente 3", len(ult) == 3)
ver("quedan las 3 recientes", set(ult) == {"nuevo|permiso", "nuevo|pregunta|x", "nuevo|error"})

ult = {"justo|termino": AHORA - 600, "pasado|termino": AHORA - 601}
podar_ultimo_aviso(ult, AHORA)
ver("clave de exactamente 600 s se queda", "justo|termino" in ult)
ver("clave de 601 s se borra", "pasado|termino" not in ult)

vacio = {}
podar_ultimo_aviso(vacio, AHORA)
ver("dict vacio queda vacio", vacio == {})

print(f"\n{ok} OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
