# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov-2026) Modulos opcionales (kodama_extras): apagados por defecto, se prenden y se apagan, y si falta uno el hub sigue.
Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_extras.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodama_extras as ke  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


TODOS_APAGADOS = {n: False for n in ke.MODULOS}
MIGRAR_REAL = ke._migrar
BASE_REAL = ke.BASE
carpeta = tempfile.mkdtemp(prefix="probar_extras_")
ruta_prueba = os.path.join(carpeta, "extras.json")

# sin log real y con un archivo de prueba: la migracion se prueba aparte, con su propia carpeta
ke.log = lambda *a, **k: None
ke._migrar = lambda: {}
ke.ruta = lambda: ruta_prueba


def limpiar():
    ke._cache["estado"] = None


# 1. archivo faltante: todo apagado y se crea
ver("archivo faltante: los cuatro apagados", ke.cargar_estado() == TODOS_APAGADOS)
ver("archivo faltante: se crea extras.json", os.path.exists(ruta_prueba))

# 2. activo() con todo apagado
limpiar()
ver("activo: los cuatro apagados", all(ke.activo(n) is False for n in ke.MODULOS))

# 3. poner() y activo() tras limpiar cache
ke.poner("correo", True)
limpiar()
ver("poner correo True -> activo True", ke.activo("correo") is True)
ver("poner correo True no toca los otros", ke.activo("pausas") is False and ke.activo("ia") is False)

# 4. nombres desconocidos
ver("nombre desconocido: activo False", ke.activo("nada") is False)
ver("nombre desconocido: modulo None", ke.modulo("nada") is None)
ver("nombre desconocido: disponible False", ke.disponible("nada") is False)

# 5. modulo() apagado = None; encendido = el modulo importado
ke.poner("pausas", False)
limpiar()
ver("modulo pausas apagado: None", ke.modulo("pausas") is None)
ke.poner("correo", True)
limpiar()
ver("modulo correo encendido: se importa", ke.modulo("correo") is not None)
ke.poner("correo", False)
limpiar()

# 6. disponible(): el archivo existe aunque este apagado
ver("disponible pausas: True", ke.disponible("pausas") is True)

# 7. archivo roto: todo apagado, sin excepcion
with open(ruta_prueba, "w", encoding="utf-8") as f:
    f.write("{roto")
limpiar()
try:
    roto_ok = ke.cargar_estado() == TODOS_APAGADOS and all(ke.activo(n) is False for n in ke.MODULOS)
except Exception:
    roto_ok = False
ver("archivo roto: todo apagado sin excepcion", roto_ok)
os.remove(ruta_prueba)

# 8. migracion de una instalacion existente (usa la carpeta de prueba, no la real)
carpeta_mig = os.path.join(carpeta, "mig")
os.makedirs(carpeta_mig)
ke.BASE = carpeta_mig
ver("instalacion nueva (sin archivos): migracion todo False", MIGRAR_REAL() == TODOS_APAGADOS)
with open(os.path.join(carpeta_mig, "correo.json"), "w", encoding="utf-8") as f:
    json.dump({"cuentas": [{"id": "x", "clave": "prueba"}]}, f)
with open(os.path.join(carpeta_mig, "integraciones.json"), "w", encoding="utf-8") as f:
    json.dump({"github": {"activo": True, "token": "prueba"}, "webhook_secreto": "prueba"}, f)
with open(os.path.join(carpeta_mig, "ia.json"), "w", encoding="utf-8") as f:
    json.dump({"elegido": None, "config": {}}, f)
with open(os.path.join(carpeta_mig, "preferencias.json"), "w", encoding="utf-8") as f:
    json.dump({"pausas": {"activo": False}}, f)
mig = MIGRAR_REAL()
ver("migracion: correo con cuenta -> True", mig["correo"] is True)
ver("migracion: integraciones con proveedor -> True", mig["integraciones"] is True)
ver("migracion: ia sin elegido -> False", mig["ia"] is False)
ver("migracion: pausas apagadas en preferencias -> False", mig["pausas"] is False)
ke.BASE = BASE_REAL

# 9. hijo con los modulos opcionales bloqueados: el hub tiene que cargar igual
CHILD = r'''
import os, sys, importlib.abc
RAIZ, RUTA = sys.argv[1], sys.argv[2]
class Bloqueo(importlib.abc.MetaPathFinder):
    NOMBRES = {"kodama_correo", "kodama_integraciones", "kodama_pausas", "kodama_ia"}
    def find_spec(self, name, path, target=None):
        if name in self.NOMBRES:
            raise ImportError("apagado para la prueba: " + name)
        return None
sys.meta_path.insert(0, Bloqueo())
sys.path.insert(0, RAIZ)
import kodama_extras as ke
ke.ruta = lambda: RUTA
ke._migrar = lambda: {}
ke.log = lambda *a, **k: None
for n in ("correo", "integraciones", "pausas", "ia"):
    assert ke.modulo(n) is None, n
import companero_hub, kodama_rutas, kodama_historial, kodama_vigilantes
print("CHILD_OK")
'''
env = dict(os.environ, PYTHONUTF8="1")
try:
    r = subprocess.run([sys.executable, "-c", CHILD, os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        os.path.join(carpeta, "extras_hijo.json")],
                       capture_output=True, text=True, timeout=120, env=env)
    ver("hijo con modulos bloqueados: carga el hub y sale 0", r.returncode == 0 and "CHILD_OK" in r.stdout)
    if r.returncode != 0:
        print(r.stderr[-1500:])
except subprocess.TimeoutExpired:
    ver("hijo con modulos bloqueados: carga el hub y sale 0", False)

shutil.rmtree(carpeta, ignore_errors=True)
print(f"\n{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
