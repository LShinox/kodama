# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
# (28-oct) macOS/Linux: esta prueba solo corre en Windows.
import sys as _sys_plat
if _sys_plat.platform != "win32":
    print("SALTADA: lee las sesiones de la app de Claude y abre un buzon \\\\.\\pipe\\ (tuberia de Windows)")
    raise SystemExit(0)
import json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import companero_hub as h
regs = h.regs_medidor()
r = max(regs, key=lambda x: x.get("visto", 0))
s = r.get("socket") or ""
print("elegido:", r.get("session_id"), "| pipe:", s.lower().startswith("\\\\.\\pipe\\"), "| existe:", os.path.exists(s))
try:
    p = open(s, "r+b", buffering=0); print("abre: si"); p.close()
except Exception as e:
    print("abre: no", type(e).__name__, e.args[:2])
