# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
# (28-oct) macOS/Linux: esta prueba solo corre en Windows.
import sys as _sys_plat
if _sys_plat.platform != "win32":
    print("SALTADA: necesita dist/companero-0.9.0.* (paquete de Windows ya publicado), que no esta en el repo")
    raise SystemExit(0)
import json, os, sys, shutil, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import companero_actualizar as ca, companero_reporte as cr
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist")
man = json.load(open(os.path.join(D, "companero-0.9.0.json"), encoding="utf-8"))
z = os.path.join(D, "companero-0.9.0.zip")
print("verifica bien:", ca.verificar(z, man))
t = z + ".alterado.zip"; shutil.copy(z, t)
with zipfile.ZipFile(t, "a") as zz:
    zz.writestr("malo.py", "print('x')")
print("zip alterado rechazado:", not ca.verificar(t, man))
os.remove(t)
m2 = dict(man); m2["sha256"] = __import__("hashlib").sha256(open(z, "rb").read()).hexdigest(); m2["firma"] = man["firma"][:-8] + "AAAAAAA="
print("firma falsa rechazada:", not ca.verificar(z, m2))
with zipfile.ZipFile(z) as zz:
    falso = zipfile.ZipInfo("estado/local.key")
    print("protegidos fuera:", all(not n.startswith(ca.PROTEGIDO) for n in ca._miembros_tamizados(zz)))
print("buscar (sin repo/release todavia):", ca.buscar())
ruta, r = cr.armar([("x", "prueba")], lambda s: s.replace(os.path.basename(os.path.expanduser("~")), "~"))
with zipfile.ZipFile(ruta) as zz:
    print("reporte:", os.path.basename(ruta), zz.namelist())
    print("  hub.log sin el nombre de usuario:", os.path.basename(os.path.expanduser("~")) not in zz.read("hub.log").decode("utf-8", "ignore") if "hub.log" in zz.namelist() else "sin log")
print(json.dumps(r, ensure_ascii=False)[:500])
print(cr.url_issue(r, ruta)[:160])
os.remove(ruta)
