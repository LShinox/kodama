# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Simula el hook Stop del puente sin tocar ningun chat: sesion de prueba anotada como si fuera al celular,
pregunta al final, y una 'respuesta del celular' escrita a los 4 s. Mide cuanto espera y que devuelve."""
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
finally:
    x = json.load(open(extra, encoding="utf-8")); x.pop(SID, None)
    json.dump(x, open(extra, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("sesion de prueba quitada:", SID not in json.load(open(extra, encoding="utf-8")))
