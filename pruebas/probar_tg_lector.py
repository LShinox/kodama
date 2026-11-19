# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov) Prueba del lector de Telegram (kodama_tg_lector) y del silencio de getUpdates en kodama_nucleo.api.
Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_tg_lector.py"""
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodama_nucleo  # noqa: E402
import kodama_tg_lector  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


# a. Telegram cuelga: el bucle de avisos sigue entregando cada ~1,5 s
def api_colgada(metodo, _silencio=False, **params):
    time.sleep(20)
    return {"ok": False}


lec = kodama_tg_lector.Lector(api_colgada, 0, lambda m: None)
lec.iniciar()
t0 = time.time()
vueltas, maximo = 0, 0.0
while time.time() - t0 < 10:
    a = time.time()
    lec.tomar(1.5)
    maximo = max(maximo, time.time() - a)
    vueltas += 1
ver("con Telegram colgado, el bucle da 5 o mas vueltas en 10 s", vueltas >= 5)
ver("ninguna vuelta tarda mas de 2 s", maximo <= 2.0)

# b. Espera creciente al fallar
def api_falla(metodo, _silencio=False, **params):
    return {"ok": False}


lec = kodama_tg_lector.Lector(api_falla, 0, lambda m: None)
esperas = [lec.una_vuelta() for _ in range(8)]
ver("espera creciente hasta 5 min", esperas == [5, 10, 20, 40, 80, 160, 300, 300])

# c. Un aviso por caida y uno al volver
logs = []
estado = {"n": 0}


def api_8_fallos(metodo, _silencio=False, **params):
    estado["n"] += 1
    if estado["n"] <= 8:
        return {"ok": False}
    return {"ok": True, "result": []}


lec = kodama_tg_lector.Lector(api_8_fallos, 0, logs.append)
for _ in range(8):
    lec.una_vuelta()
lec.una_vuelta()
ver("8 fallos y una vuelta buena: 2 avisos", len(logs) == 2)
ver("el segundo aviso dice 8", len(logs) == 2 and "8" in logs[1])

# d. Orden y offset
llamadas = []
respuestas = [{"ok": True, "result": [{"update_id": 10}, {"update_id": 11}, {"update_id": 12}]},
              {"ok": True, "result": []}]


def api_lote(metodo, _silencio=False, **params):
    llamadas.append(params)
    return respuestas.pop(0) if respuestas else {"ok": True, "result": []}


lec = kodama_tg_lector.Lector(api_lote, 0, lambda m: None)
lec.una_vuelta()
nuevos = lec.tomar(0.5)
ver("tomar devuelve los 3 en orden", [u["update_id"] for u in nuevos] == [10, 11, 12])
ver("offset queda en 13", lec.offset == 13)
lec.una_vuelta()
ver("la siguiente consulta pide offset=13", llamadas[1].get("offset") == 13)

# e. kodama_nucleo.api: _silencio no llega a Telegram y no loguea; sin el, loguea una vez
token_orig = kodama_nucleo.TOKEN
log_orig = kodama_nucleo.log
req_orig = urllib.request.Request
url_orig = urllib.request.urlopen
cuerpos, registro = [], []


def req_espia(url, data=None, **kw):
    cuerpos.append(data)
    return req_orig(url, data=data, **kw)


def urlopen_roto(req, timeout=None):
    raise urllib.error.URLError("x")


try:
    kodama_nucleo.TOKEN = "123456:TOKEN-DE-PRUEBA"
    kodama_nucleo.log = registro.append
    urllib.request.Request = req_espia
    urllib.request.urlopen = urlopen_roto
    r1 = kodama_nucleo.api("getUpdates", _silencio=True, offset=1)
    ver("api con _silencio devuelve ok False", r1 == {"ok": False})
    ver("api con _silencio no loguea", registro == [])
    ver("_silencio no viaja a Telegram", b"_silencio" not in cuerpos[0] and b"offset=1" in cuerpos[0])
    kodama_nucleo.api("getUpdates", offset=1)
    ver("api sin _silencio loguea una vez", len(registro) == 1)
finally:
    kodama_nucleo.TOKEN = token_orig
    kodama_nucleo.log = log_orig
    urllib.request.Request = req_orig
    urllib.request.urlopen = url_orig

print(f"\n{ok} OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
