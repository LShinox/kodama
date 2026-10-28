# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
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
