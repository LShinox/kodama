# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Simula el hook Stop del puente sin tocar ningun chat: sesion de prueba anotada como si fuera al celular,
pregunta al final, y una 'respuesta del celular' escrita a los 4 s. Mide cuanto espera y que devuelve."""
# (28-oct) macOS/Linux: esta prueba solo corre en Windows.
import sys as _sys_plat
if _sys_plat.platform != "win32":
    print("SALTADA: usa el hub vivo y el python del venv de Windows (.venv\\Scripts\\python.exe)")
    raise SystemExit(0)
import json, os, subprocess, sys, threading, time
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = APP + r"\.venv\Scripts\python.exe"
EST = APP + r"\estado"
SID = "prueba-puente-0000-0000-000000000000"
extra = os.path.join(EST, "sesiones_extra.json")
x = json.load(open(extra, encoding="utf-8"))
x[SID] = ["zz", "Prueba puente", ""]
json.dump(x, open(extra, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
try:
    entrada = json.dumps({"session_id": SID, "transcript_path": "", "last_assistant_message": "Necesito de ti: ¿lo lanzo? Respóndeme sí o no."})
    def responder():
        time.sleep(4)
        open(os.path.join(EST, "puente", SID + ".respuesta"), "w", encoding="utf-8").write("sí, lánzalo")
    threading.Thread(target=responder).start()
    t0 = time.time()
    env = dict(os.environ, COMPANERO_PUENTE_PRUEBA="1")
    r = subprocess.run([PY, APP + r"\companero_puente.py"], input=entrada.encode(), capture_output=True, env=env, timeout=60)
    print(f"espero {time.time() - t0:.1f} s | salida: {r.stdout.decode('utf-8', 'replace')[:300]}")
    ver_espera = 3.5 < time.time() - t0 < 15 and "additionalContext" in r.stdout.decode("utf-8", "replace")
    print("OK  " if ver_espera else "FALLA", "turno normal: espera y entrega por el hook")

    # (06-nov) turno cerrado con el cuadro con pregunta: no espera, para que el hub use el buzon
    cuadro = os.path.join(EST, "wrapup", SID + ".json")
    os.makedirs(os.path.dirname(cuadro), exist_ok=True)
    json.dump({"ts": time.time(), "recap": "r", "ask": "¿Sigo?", "acciones": []}, open(cuadro, "w", encoding="utf-8"))
    try:
        t0 = time.time()
        r = subprocess.run([PY, APP + r"\companero_puente.py"], input=entrada.encode(), capture_output=True, env=env, timeout=60)
        ok = time.time() - t0 < 3 and not r.stdout and not os.path.exists(os.path.join(EST, "puente", SID + ".esperando"))
        print("OK  " if ok else "FALLA", f"cuadro con pregunta: sale sin esperar ({time.time() - t0:.1f} s), sin salida y sin .esperando")
    finally:
        os.remove(cuadro)

    # cuadro viejo (mas de 2 min): vuelve el comportamiento normal
    json.dump({"ts": time.time() - 300, "recap": "r", "ask": "¿Sigo?", "acciones": []}, open(cuadro, "w", encoding="utf-8"))
    try:
        threading.Thread(target=responder).start()
        t0 = time.time()
        r = subprocess.run([PY, APP + r"\companero_puente.py"], input=entrada.encode(), capture_output=True, env=env, timeout=60)
        print("OK  " if b"additionalContext" in r.stdout else "FALLA", "cuadro viejo: espera normal")
    finally:
        if os.path.exists(cuadro):   # el hook lo borra al entregar
            os.remove(cuadro)
finally:
    x = json.load(open(extra, encoding="utf-8")); x.pop(SID, None)
    json.dump(x, open(extra, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("sesion de prueba quitada:", SID not in json.load(open(extra, encoding="utf-8")))
