# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(19-nov) Claude quito la ventana de 5 h: solo queda la semanal. Prueba que Kodama no la muestra ni la estima
(kodama_medidor.VENTANA_5H = False) y que el aviso de salud se guarda en salud_avisos.json (sobrevive a reinicios).
Todo en carpetas temporales: NO toca estado\\ real. Uso: python probar_sin_5h.py"""
import json, os, shutil, sys, tempfile, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import kodama_medidor as km  # noqa: E402
import kodama_vigilantes as kv  # noqa: E402

fallos = []


def ok(nombre, cond, extra=""):
    print(("OK   " if cond else "FALLA"), nombre, ("" if cond else extra))
    if not cond:
        fallos.append(nombre)


ahora = time.time()
rei5, rei7 = int(ahora + 3 * 3600), int(ahora + 4 * 86400)

# ---------- 1) _sin_5h ----------
r = km._sin_5h({"5h": {"pct": 50}, "semana": {"pct": 30}, "ts": 1})
ok("_sin_5h: quita 5h y conserva semana y ts", bool(r) and "5h" not in r and r.get("semana") == {"pct": 30} and r.get("ts") == 1, str(r))
ok("_sin_5h: sin semana -> None", km._sin_5h({"5h": {"pct": 50}, "ts": 1}) is None)
ok("_sin_5h: None -> None", km._sin_5h(None) is None)

VENTANA_ORIG = km.VENTANA_5H
try:
    km.VENTANA_5H = True
    d = {"5h": {"pct": 50}, "ts": 1}
    ok("VENTANA_5H=True: devuelve el dato sin cambios", km._sin_5h(d) is d)
finally:
    km.VENTANA_5H = VENTANA_ORIG

# ---------- 2) combinar con exacto y estimado ----------
exacto = {"5h": {"pct": 50, "reinicia": rei5}, "semana": {"pct": 30, "reinicia": rei7}, "ts": ahora, "fuente": "statusline"}
estimado = {"5h": {"pct": 40, "estimado": True}, "semana": {"pct": 35, "estimado": True}, "ts": ahora, "exacto": False, "fuente": "estimado"}
c = km.combinar_uso(km._sin_5h(exacto), km._sin_5h(estimado))
ok("combinar exacto+estimado: sin 5h", bool(c) and "5h" not in c, str(c))
ok("combinar exacto+estimado: semana = la exacta", bool(c) and c.get("semana") == exacto["semana"], str(c))
ok("combinar exacto+estimado: exacto True", bool(c) and c.get("exacto") is True, str(c))

c = km.combinar_uso(None, km._sin_5h({"5h": {"pct": 10, "estimado": True}, "semana": {"pct": 40, "estimado": True}, "ts": 5}))
ok("solo estimado: sin 5h", bool(c) and "5h" not in c, str(c))
ok("solo estimado: exacto False y fuente estimado", bool(c) and c.get("exacto") is False and c.get("fuente") == "estimado", str(c))

# ---------- 3) salud persistente (carpeta temporal) ----------
TMP = tempfile.mkdtemp(prefix="kodama-sin5h-")
BASE_ORIG = kv.BASE
try:
    kv.BASE = TMP
    ruta = os.path.join(TMP, "salud_avisos.json")

    kv._SALUD.clear()
    kv._SALUD.update({"uso": 1700000000.5, "ids": 1700000100.25})
    kv._salud_guardar()
    ok("salud: se guarda el archivo", os.path.isfile(ruta))
    ok("salud: al cargar devuelve lo mismo", kv._salud_cargar() == {"uso": 1700000000.5, "ids": 1700000100.25}, str(kv._salud_cargar()))

    open(ruta, "w", encoding="utf-8").write("{no es json")
    ok("salud: archivo roto -> {}", kv._salud_cargar() == {})
    os.remove(ruta)
    ok("salud: archivo ausente -> {}", kv._salud_cargar() == {})
    open(ruta, "w", encoding="utf-8").write("[1, 2]")
    ok("salud: no es un dict -> {}", kv._salud_cargar() == {})
finally:
    kv.BASE = BASE_ORIG
    kv._SALUD.clear()
    shutil.rmtree(TMP, ignore_errors=True)

print("TODO BIEN" if not fallos else "FALLARON: " + ", ".join(fallos))
sys.exit(1 if fallos else 0)
