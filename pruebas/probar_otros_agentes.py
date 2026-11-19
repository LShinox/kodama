# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov) Prueba de OpenCode y WSL: instalar.py (otros_agentes, unir_hooks_wsl, ruta_wsl), companero_wsl.py,
companero_opencode.py y kodama_comun.opencode_encolar. Todo va a carpetas temporales: ni ~\\.claude, ni ~\\.config,
ni estado\\ reales. Uso: python pruebas/probar_otros_agentes.py  (sale con 1 si algo falla)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import instalar as ins  # noqa: E402
import companero_wsl as cw  # noqa: E402
import companero_opencode as co  # noqa: E402
import kodama_comun as kc  # noqa: E402
import companero_codex as cc  # noqa: E402

mal = []
ok_n = 0


def ver(nombre, obtenido, esperado):
    global ok_n
    ok = obtenido == esperado
    if ok:
        ok_n += 1
    else:
        mal.append(nombre)
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# proceso hijo: instala y quita OpenCode con HOME temporal; los resultados salen en una linea RESULTADO
HIJO = r'''
import json, os, sys
AQUI, CASA = sys.argv[1], sys.argv[2]
sys.path.insert(0, AQUI)
import config
if os.path.normcase(os.path.normpath(config.HOME)) != os.path.normcase(os.path.normpath(CASA)):
    sys.exit(9)
import instalar
instalar.distros_wsl = lambda: []
if not (instalar.OPENCODE_PLUGIN.startswith(CASA) and instalar.CODEX_HOOKS.startswith(CASA) and instalar.GEMINI_HOOKS.startswith(CASA)):
    sys.exit(8)
res = {}
plugin = instalar.OPENCODE_PLUGIN
instalar.otros_agentes(True)
res["existe"] = os.path.exists(plugin)
txt = open(plugin, encoding="utf-8").read() if res["existe"] else ""
res["sin_placeholders"] = bool(txt) and not any(t in txt for t in ("__PY__", "__SCRIPT__", "__ESTADO__"))
res["rutas"] = instalar.PYV.replace("\\", "/") in txt and "companero_opencode.py" in txt
instalar.otros_agentes(False)
res["quitado"] = not os.path.exists(plugin)
print("RESULTADO " + json.dumps(res))
'''

tmp = tempfile.mkdtemp(prefix="kodama-prueba-otros-")
try:
    # ---- 1. funciones puras de WSL (instalar.py)
    ver("ruta_wsl C:\\a\\b.exe", ins.ruta_wsl("C:\\a\\b.exe"), "/mnt/c/a/b.exe")
    py_w, scr = "/mnt/c/k/.venv/Scripts/python.exe", "C:/k/companero_wsl.py"
    ajeno = {"type": "command", "command": "/usr/bin/ajeno.sh"}
    d0 = {"permisos": {"x": 1}, "hooks": {"Stop": [{"hooks": [ajeno]}]}}
    d1 = ins.unir_hooks_wsl(json.loads(json.dumps(d0)), True, py_w, scr)
    d2 = ins.unir_hooks_wsl(json.loads(json.dumps(d1)), True, py_w, scr)
    ver("poner dos veces no duplica", d2, d1)
    stop = d1["hooks"]["Stop"]
    cmds = [x["command"] for e in stop for x in e["hooks"]]
    ver("Stop: hook ajeno + modo hook + modo puente", len(stop), 3)
    ver("Stop tiene los dos modos", (any(c.endswith(" hook") for c in cmds), any(c.endswith(" puente") for c in cmds)), (True, True))
    ver("comando WSL completo", cmds[1], f'"{py_w}" "{scr}" hook')
    ver("timeout del puente 1900", [x["timeout"] for e in stop for x in e["hooks"] if x["command"].endswith(" puente")], [1900])
    ver("SessionStart async", d1["hooks"]["SessionStart"][0]["hooks"][0].get("async"), True)
    ver("PermissionRequest timeout 130", d1["hooks"]["PermissionRequest"][0]["hooks"][0]["timeout"], 130)
    ver("PreToolUse con matcher AskUserQuestion", d1["hooks"]["PreToolUse"][0].get("matcher"), "AskUserQuestion")
    d3 = ins.unir_hooks_wsl(json.loads(json.dumps(d1)), False, py_w, scr)
    ver("quitar deja el hook ajeno y borra eventos vacios", d3["hooks"], {"Stop": [{"hooks": [ajeno]}]})
    ver("quitar conserva claves ajenas", d3.get("permisos"), {"x": 1})
    solo = ins.unir_hooks_wsl({}, True, py_w, scr)
    ver("quitar sin nada ajeno borra la clave hooks", "hooks" in ins.unir_hooks_wsl(solo, False, py_w, scr), False)

    # ---- 2. companero_wsl.py y companero_opencode.py: nombres de la sesion
    cw.EXTRA = os.path.join(tmp, "wsl_extra.json")
    sid_w = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    cw.anotar(sid_w, "/home/yo/proyectos/app")
    ver("WSL: nombre con carpeta de ruta Linux", leer_json(cw.EXTRA)[sid_w][1], "WSL · app")

    co.EXTRA = os.path.join(tmp, "oc_extra.json")
    sid_o = "ses_abc123XYZ"
    carpeta_win = "D:\\Proyectos\\mi-proyecto"
    co.anotar(sid_o, carpeta_win, "New session - 2026-11-04T10:00")
    ver("OpenCode: titulo automatico usa la carpeta", leer_json(co.EXTRA)[sid_o][1], "OpenCode · mi-proyecto")
    co.anotar(sid_o, carpeta_win, "Refactor login")
    ver("OpenCode: titulo real corrige el nombre", leer_json(co.EXTRA)[sid_o][1], "OpenCode · Refactor login")
    co.anotar(sid_o, carpeta_win, "New session - 2026-11-05")
    ver("OpenCode: New session no pisa el nombre", leer_json(co.EXTRA)[sid_o][1], "OpenCode · Refactor login")

    # ---- 3. kodama_comun.opencode_encolar
    kc.BASE = os.path.join(tmp, "estado")
    carpeta_oc = os.path.join(kc.BASE, "opencode")
    os.makedirs(carpeta_oc, exist_ok=True)
    exe_real, popen_real = kc.opencode_exe, kc.subprocess.Popen
    kc.opencode_exe = lambda: None   # sin ejecutable de OpenCode
    ver("encolar sin OpenCode abierta ni ejecutable: 'en_cola'", kc.opencode_encolar("ses1", "hola celu"), "en_cola")
    encolados = [f for f in os.listdir(carpeta_oc) if f.endswith(".respuesta")]
    ver("encolar deja un .respuesta", len(encolados), 1)
    with open(os.path.join(carpeta_oc, encolados[0]), encoding="utf-8") as f:
        ver("encolar guarda el texto", f.read(), "hola celu")
    with open(os.path.join(carpeta_oc, "vivo-4242.json"), "w", encoding="utf-8") as f:
        json.dump(["ses1"], f)
    ver("OpenCode abierta con la sesion: 'entregado'", kc.opencode_encolar("ses1", "otra"), "entregado")
    ver("sesion no listada, sin ejecutable: 'en_cola'", kc.opencode_encolar("ses2", "x", cwd=tmp), "en_cola")
    try:
        kc.opencode_encolar("../x", "y")
        ver("id con .. lanza ValueError", "no lanzo", "ValueError")
    except ValueError:
        ver("id con .. lanza ValueError", "ValueError", "ValueError")

    # despertar: OpenCode cerrada y con ejecutable -> Popen falso, sin ventana y con KODAMA_DESPERTAR=1
    llamadas_popen = []

    class FalsoProc:
        def __init__(self):
            self.pid = 999
            self.fin = threading.Event()

        def poll(self):
            return 0 if self.fin.is_set() else None

        def wait(self, timeout=None):
            self.fin.wait(timeout)
            return 0

    def popen_falso(args, **kw):
        llamadas_popen.append((args, kw))
        return FalsoProc()

    kc.subprocess.Popen = popen_falso
    kc.opencode_exe = lambda: "C:/fake/opencode.exe"
    try:
        cwd_t = os.path.join(tmp, "proy")
        os.makedirs(cwd_t, exist_ok=True)
        ver("despertar: devuelve 'despertando'", kc.opencode_encolar("ses3", "Responde solo: dos", cwd=cwd_t), "despertando")
        ver("despertar: args exactos", llamadas_popen[0][0] if llamadas_popen else None,
            ["C:/fake/opencode.exe", "run", "-s", "ses3", "--dir", cwd_t, "--", "Responde solo: dos"])
        ver("despertar: env KODAMA_DESPERTAR=1", llamadas_popen[0][1]["env"].get("KODAMA_DESPERTAR") if llamadas_popen else None, "1")
        ver("despertar: no deja .respuesta", len([f for f in os.listdir(carpeta_oc) if "ses3" in f]), 0)
        ver("segunda llamada mientras corre: no lanza otro enseguida", kc.opencode_encolar("ses3", "segundo", cwd=cwd_t), "despertando")
        ver("segunda llamada: Popen aun 1 vez", len(llamadas_popen), 1)
        kc._DESPERTANDO["ses3"].fin.set()   # termina el primero: el hilo lanza el segundo
        t0 = time.time()
        while len(llamadas_popen) < 2 and time.time() - t0 < 5:
            time.sleep(0.05)
        ver("tras terminar el primero: se lanza el segundo", [a[0][-1] for a in llamadas_popen], ["Responde solo: dos", "segundo"])
    finally:
        kc.subprocess.Popen = popen_real
        kc.opencode_exe = exe_real
        for p in kc._DESPERTANDO.values():
            p.fin.set()

    # es_exec de companero_codex: transcript de la 1.a linea
    def rollout(nombre, payload):
        ruta = os.path.join(tmp, f"rollout-{nombre}.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(json.dumps({"payload": payload}) + "\n")
        return ruta
    ver("es_exec: originator 'Claude Code' -> True", cc.es_exec("x", rollout("a", {"originator": "Claude Code"})), True)
    ver("es_exec: source con 'subagent' -> True", cc.es_exec("x", rollout("b", {"source": {"subagent": {}}})), True)
    ver("es_exec: 'Codex Desktop' -> False", cc.es_exec("x", rollout("c", {"originator": "Codex Desktop", "source": "vscode"})), False)

    # ---- 4. instalar.otros_agentes con HOME temporal, en un proceso aparte
    casa = os.path.join(tmp, "casa")
    os.makedirs(os.path.join(casa, ".config", "opencode"))
    env = dict(os.environ, USERPROFILE=casa, HOME=casa, PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-c", HIJO, AQUI, casa], env=env, capture_output=True, text=True, timeout=180)
    ver("proceso hijo sale con 0", r.returncode, 0)
    lineas = [x for x in r.stdout.splitlines() if x.startswith("RESULTADO ")]
    res = json.loads(lineas[-1][len("RESULTADO "):]) if lineas else {}
    ver("kodama.js existe tras poner", res.get("existe"), True)
    ver("kodama.js sin __PY__/__SCRIPT__/__ESTADO__", res.get("sin_placeholders"), True)
    ver("kodama.js con la ruta del Python y del script", res.get("rutas"), True)
    ver("kodama.js ya no existe tras quitar", res.get("quitado"), True)
    if r.returncode != 0:
        print(r.stderr[-800:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\nprobar_otros_agentes: {ok_n} OK, {len(mal)} MAL")
sys.exit(1 if mal else 0)
