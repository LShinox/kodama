"""Cifrado DPAPI de integraciones/correo/ia: ida y vuelta, migracion de texto plano, archivo roto y fuera de Windows.
Todo en una carpeta temporal; no toca el estado real. Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_secreto.py"""
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodama_secreto as ks  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


SECRETO = "TOKEN_SECRETO_123_ñandú"
OBJ = {"github": {"token": SECRETO, "nombre": "Acción ñ"}, "elegido": None}
registros = []
ks.log = registros.append          # sin log real: se revisa lo que se registra
WIN = sys.platform == "win32"

with tempfile.TemporaryDirectory() as td:
    # 1. ida y vuelta con texto no ASCII
    ruta = os.path.join(td, "integraciones.json")
    ks.guardar(ruta, OBJ)
    ver("ida y vuelta devuelve el mismo dict", ks.leer(ruta, None) == OBJ)

    # 2. en disco: cifrado (MARCA) y sin el secreto a la vista
    with open(ruta, "rb") as f:
        crudo = f.read()
    if WIN:
        ver("en disco empieza con MARCA", crudo.startswith(ks.MARCA))
        ver("en disco no aparece el secreto", SECRETO.encode("utf-8") not in crudo and b"github" not in crudo)
    else:
        ver("fuera de Windows: JSON plano legible", crudo.startswith(b"{"))
    ver("no quedan temporales .tmp", not [x for x in os.listdir(td) if x.endswith(".tmp")])

    # 3. archivo viejo en texto plano: se lee bien y (en Windows) queda cifrado
    viejo = os.path.join(td, "correo.json")
    with open(viejo, "w", encoding="utf-8") as f:
        f.write('{"cuentas": [{"id": "x", "clave": "vieja ñ"}]}')
    del registros[:]
    d = ks.leer(viejo, {})
    ver("texto plano viejo: se lee bien", d == {"cuentas": [{"id": "x", "clave": "vieja ñ"}]})
    if WIN:
        with open(viejo, "rb") as f:
            ver("texto plano viejo: se reescribe cifrado", f.read().startswith(ks.MARCA))
        ver("texto plano viejo: se registra una vez", registros == ["secreto: correo.json cifrado"])
        del registros[:]
        ks.leer(viejo, {})
        ver("ya cifrado: no vuelve a registrar", registros == [])
    else:
        with open(viejo, "rb") as f:
            ver("fuera de Windows: no se reescribe", not f.read().startswith(ks.MARCA))

    # 4. archivo cifrado roto: devuelve defecto y NO se modifica (bytes iguales)
    roto = os.path.join(td, "ia.json")
    basura = ks.MARCA + b"esto no es base64 ni DPAPI !!!"
    with open(roto, "wb") as f:
        f.write(basura)
    del registros[:]
    ver("cifrado roto: devuelve defecto", ks.leer(roto, {"x": 1}) == {"x": 1})
    with open(roto, "rb") as f:
        ver("cifrado roto: bytes sin cambios", f.read() == basura)
    ver("cifrado roto: se registra el error", len(registros) == 1 and registros[0].startswith("secreto: no se pudo leer ia.json"))

    # 5. texto plano roto: defecto y sin sobrescribir
    plano_roto = os.path.join(td, "roto_plano.json")
    with open(plano_roto, "wb") as f:
        f.write(b"{roto")
    ver("plano roto: devuelve defecto", ks.leer(plano_roto, []) == [])
    with open(plano_roto, "rb") as f:
        ver("plano roto: bytes sin cambios", f.read() == b"{roto")

    # 6. archivo faltante
    ver("faltante: devuelve defecto", ks.leer(os.path.join(td, "no.json"), {"a": 2}) == {"a": 2})

    # 7. fuera de Windows (plataforma simulada dentro del modulo): guarda JSON plano
    real_sys = ks.sys
    ks.sys = types.SimpleNamespace(platform="darwin")
    try:
        otra = os.path.join(td, "mac.json")
        ks.guardar(otra, OBJ)
        with open(otra, "rb") as f:
            crudo_mac = f.read()
        ver("darwin simulado: guarda JSON plano", crudo_mac.startswith(b"{") and not crudo_mac.startswith(ks.MARCA))
        ver("darwin simulado: lo vuelve a leer", ks.leer(otra, None) == OBJ)
    finally:
        ks.sys = real_sys

print(f"\n{ok} OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
