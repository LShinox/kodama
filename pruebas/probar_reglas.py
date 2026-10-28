# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Prueba mejora 2 sin chats reales: aprobar con 'siempre' guarda la regla y el hook la aplica solo. Deja todo como estaba."""
# (28-oct) macOS/Linux: esta prueba solo corre en Windows.
import sys as _sys_plat
if _sys_plat.platform != "win32":
    print("SALTADA: usa el hub vivo y el python del venv de Windows (.venv\\Scripts\\python.exe)")
    raise SystemExit(0)
import json, os, subprocess, sys, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import companero_hub as h
import companero_permiso as cp
antes = open(h.REGLAS_PERMISO, encoding="utf-8").read() if os.path.exists(h.REGLAS_PERMISO) else None
pid = "bbbb0001"
ped = os.path.join(h.PERMISOS, pid + ".pedido")
try:
    clave = cp.clave_regla("Bash", {"command": "npm test"})
    json.dump({"id": pid, "sesion": "prueba-reglas", "texto": "Bash: npm test", "ts": time.time(), "regla": clave}, open(ped, "w", encoding="utf-8"))
    print("responder siempre:", h.responder_permiso(pid, "allow", "", "siempre"))
    print("regla guardada:", clave in h.leer_reglas()["siempre"])
    print("por_regla mismo comando:", cp.por_regla("x", clave), "| otro comando:", cp.por_regla("x", cp.clave_regla("Bash", {"command": "npm test && rm -rf ."})))
    entrada = json.dumps({"session_id": "prueba-reglas", "tool_name": "Bash", "tool_input": {"command": "npm test"},
                          "hook_event_name": "PermissionRequest", "transcript_path": ""})
    r = subprocess.run([os.path.join(APP, ".venv", "Scripts", "python.exe"), os.path.join(APP, "companero_permiso.py")],
                       input=entrada.encode(), capture_output=True, timeout=20)
    print("hook devuelve:", r.stdout.decode()[:200])
    print("responder 'pc':", h.responder_permiso(pid, "pc"), "->", open(os.path.join(h.PERMISOS, pid + ".respuesta")).read())
finally:
    for f in (ped, os.path.join(h.PERMISOS, pid + ".respuesta")):
        try:
            os.remove(f)
        except OSError:
            pass
    if antes is None:
        try:
            os.remove(h.REGLAS_PERMISO)
        except OSError:
            pass
    else:
        open(h.REGLAS_PERMISO, "w", encoding="utf-8").write(antes)
    print("reglas restauradas:", (open(h.REGLAS_PERMISO, encoding="utf-8").read() if os.path.exists(h.REGLAS_PERMISO) else None) == antes)
