# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Lo que comparten los hooks de Claude Code (companero_permiso, companero_puente, companero_codex y
companero_antigravity). Claude Code los corre como scripts sueltos, asi que este modulo vive junto a ellos (sin paquetes)
y va en el zip. Solo usa config y la biblioteca estandar."""
import json
import os
import time

import config

BASE = config.ESTADO


def celular_abierto():
    """La app del celular esta abierta ahora (el hub toca estado/celular_activo mientras la usas)."""
    try:
        return time.time() - os.path.getmtime(os.path.join(BASE, "celular_activo")) < 30
    except OSError:
        return False


def va_al_celular(sid, proy):
    """True si el chat `sid` (de la carpeta `proy`) va al celular: es personal, esta fijo, o lo elegiste en la app."""
    if sid not in config.OCULTAR and (config.es_personal(proy) or sid in config.FIJAS):
        return True
    for f, campo in (("sesiones_extra.json", None), ("elegidos.json", "sesiones")):
        try:
            x = json.load(open(os.path.join(BASE, f), encoding="utf-8"))
            if sid in (x.get(campo) if campo else x):
                return True
        except Exception:
            pass
    return False


def lineas_finales(ruta, tope=300000):
    """Las lineas del final de un archivo (los ultimos `tope` bytes), para leer el ultimo mensaje de un transcript JSONL
    sin cargarlo entero. None si no se puede leer."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, os.path.getsize(ruta) - tope))
            return f.read().decode("utf-8", "ignore").splitlines()
    except (OSError, TypeError):
        return None
