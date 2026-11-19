# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov) Prueba de la carga de la PC (kodama_plataforma.estado_maquina / procesos_top) para que el gato reaccione.
No toca estado\\: solo lee. Uso: python pruebas/probar_maquina.py  (sale con 1 si algo falla)"""
import os, sys, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import kodama_plataforma as pl  # noqa: E402

mal = []


def ver(nombre, ok, detalle=""):
    print(("OK  " if ok else "MAL ") + nombre + (f" -> {detalle}" if detalle else ""))
    if not ok:
        mal.append(nombre)


def es_entero(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


# ---- estado_maquina: 4 claves, nunca lanza
try:
    m1 = pl.estado_maquina()
    ver("estado_maquina no lanza", True)
except Exception as e:  # noqa: BLE001
    m1 = None
    ver("estado_maquina no lanza", False, repr(e))
if m1 is not None:
    ver("estado_maquina tiene las 4 claves", set(m1.keys()) == {"cpu", "mem", "bateria", "enchufado"}, repr(sorted(m1.keys())))

time.sleep(0.3)
t0 = time.perf_counter()
m2 = pl.estado_maquina()
dur = (time.perf_counter() - t0) * 1000
print(f"     estado_maquina tardo {dur:.1f} ms")
ver("estado_maquina < 50 ms", dur < 50, f"{dur:.1f} ms")

if sys.platform == "win32":
    ver("cpu es entero 0..100 (segunda lectura)", es_entero(m2["cpu"], 0, 100), repr(m2["cpu"]))
    ver("mem es entero 1..100", es_entero(m2["mem"], 1, 100), repr(m2["mem"]))
else:
    ver("fuera de Windows todo es None", all(v is None for v in m2.values()), repr(m2))

ver("bateria None o 0..100", m2["bateria"] is None or es_entero(m2["bateria"], 0, 100), repr(m2["bateria"]))
ver("enchufado None o bool", m2["enchufado"] is None or isinstance(m2["enchufado"], bool), repr(m2["enchufado"]))
if m2["bateria"] is None:
    ver("sin bateria: enchufado es None", m2["enchufado"] is None, repr(m2["enchufado"]))

# ---- procesos_top: lista de hasta 2 nombres sin .exe, en menos de 3 s
t0 = time.perf_counter()
try:
    top = pl.procesos_top()
    ok_lista = isinstance(top, list)
except Exception as e:  # noqa: BLE001
    top, ok_lista = [], False
    print(f"     procesos_top lanzo: {e!r}")
dur_top = time.perf_counter() - t0
ver("procesos_top es lista", ok_lista, repr(top))
ver("procesos_top tiene como mucho 2 nombres", len(top) <= 2, repr(top))
ver("procesos_top son str sin .exe", all(isinstance(x, str) and not x.lower().endswith(".exe") and x for x in top), repr(top))
ver("procesos_top tarda menos de 3 s", dur_top < 3, f"{dur_top:.2f} s")
if sys.platform != "win32":
    ver("fuera de Windows procesos_top es []", top == [], repr(top))

print("\nRESULTADO: " + ("TODO OK" if not mal else "FALLARON: " + ", ".join(mal)))
sys.exit(1 if mal else 0)
