# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Medidor de uso del plan (14-oct-2026). statusLine global de Claude Code: recibe por stdin el JSON de la sesion,
guarda rate_limits (5 h y semanal: % usado y hora de reinicio) en estado\\uso.json para el Companero y
devuelve una linea corta para la barra de estado. Doc oficial: code.claude.com/docs/en/statusline
("Rate limit usage"; solo planes Pro/Max y despues de la primera respuesta de la sesion).
Sin confirmar si la app de escritorio ejecuta statusLine: si no, este archivo nunca se escribe y no pasa nada."""
import json
import os
import sys
import time

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
USO = os.path.join(config.ESTADO, "uso.json")


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return ""
    rl = d.get("rate_limits") or {}
    if not rl:
        return ""
    out = {"ts": time.time()}
    for clave, nombre in (("five_hour", "5h"), ("seven_day", "semana")):
        v = rl.get(clave) or {}
        if "used_percentage" in v:
            out[nombre] = {"pct": v.get("used_percentage"), "reinicia": v.get("resets_at")}
    try:
        open(USO + ".tmp", "w", encoding="utf-8").write(json.dumps(out)); os.replace(USO + ".tmp", USO)
    except OSError:
        pass
    return " · ".join(f"{k} {round(v['pct'])}%" for k, v in out.items() if isinstance(v, dict) and v.get("pct") is not None)


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(main().encode("utf-8"))   # utf-8: la consola de Windows rompe el "·"
    except Exception:
        pass
