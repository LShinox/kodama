# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov) Prueba de los perfiles de Claude Code (config.dirs_claude, config.transcript_de y el bucle de tocar_settings
de instalar.py), SIN tocar el ~\\.claude real ni estado\\: todo va a dos carpetas temporales. Lo que escribe corre en un
subproceso con USERPROFILE/HOME apuntando a la primera (si no, el subproceso sale con 9 antes de escribir nada).
Uso: python pruebas/probar_perfiles.py  (sale con 1 si algo falla)"""
import json, os, shutil, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mal = []
oks = []


def ver(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))
    (oks if ok else mal).append(nombre)


# Codigo del subproceso. argv: AQUI, T1 (HOME temporal), T2 (carpeta de CLAUDE_CONFIG_DIR). Imprime una linea JSON al final.
CODIGO = r'''
import json, os, sys
AQUI, T1, T2 = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, AQUI)
import config
norm = lambda p: os.path.normcase(os.path.normpath(p))
if norm(config.HOME) != norm(T1):
    sys.exit(9)   # no es la carpeta temporal: no se escribe nada
import instalar
instalar.CONFIG_JSON = os.path.join(T1, "config-prueba.json")   # nunca el config.json real
R = {}
claude1 = os.path.join(T1, ".claude")
os.makedirs(claude1, exist_ok=True)
AJENO = {"hooks": [{"type": "command", "command": "ajeno.exe --x", "timeout": 5}]}
for carpeta in (claude1, T2):   # hook ajeno previo en las dos carpetas
    with open(os.path.join(carpeta, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"hooks": {"Stop": [AJENO]}}, f)

def comandos(ruta):
    d = json.load(open(ruta, encoding="utf-8"))
    return [h.get("command", "") for ev in (d.get("hooks") or {}).values() for e in ev for h in e.get("hooks", [])]

def nuestros(cmds):
    return [c for c in cmds if any(n in c for n in instalar.NUESTROS)]

# ---- dirs_claude con CLAUDE_CONFIG_DIR = T2
os.environ["CLAUDE_CONFIG_DIR"] = T2
dirs = config.dirs_claude()
R["dirs_primera"] = [norm(dirs[0]), norm(claude1)]
R["dirs_incluye_T2"] = [any(norm(d) == norm(T2) for d in dirs), True]
R["dirs_sin_repetidos"] = [len({norm(d) for d in dirs}) == len(dirs), True]

# ---- repetido y carpeta inexistente
os.environ["CLAUDE_CONFIG_DIR"] = claude1   # igual que la por defecto
R["repetido_cuenta"] = [sum(1 for d in config.dirs_claude() if norm(d) == norm(claude1)), 1]
os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(T1, "no-existe")
R["inexistente_ignorada"] = [any("no-existe" in d for d in config.dirs_claude()), False]
os.environ["CLAUDE_CONFIG_DIR"] = T2

# ---- transcript_de: gana la primera carpeta donde existe; si ninguna, la de la por defecto
def poner(carpeta, cwd):
    p = os.path.join(carpeta, "projects", config.clave_carpeta(cwd), "sesion.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write("x")
    return p
cwd_t2 = os.path.join(T1, "proyecto-uno")
esperado_t2 = poner(T2, cwd_t2)   # primero se crea el archivo, despues se pregunta\nR["tr_solo_en_T2"] = [config.transcript_de(cwd_t2, "sesion"), esperado_t2]
cwd_ninguno = os.path.join(T1, "proyecto-dos")
R["tr_ninguno"] = [config.transcript_de(cwd_ninguno, "sesion"),
                   os.path.join(claude1, "projects", config.clave_carpeta(cwd_ninguno), "sesion.jsonl")]
cwd_ambos = os.path.join(T1, "proyecto-tres")
poner(claude1, cwd_ambos); poner(T2, cwd_ambos)
R["tr_gana_la_primera"] = [config.transcript_de(cwd_ambos, "sesion"),
                           os.path.join(claude1, "projects", config.clave_carpeta(cwd_ambos), "sesion.jsonl")]

# ---- instalar: el bucle de la instalacion sobre todas las carpetas
R["settings_todos"] = [[norm(s) for s in instalar.settings_todos()],
                       [norm(os.path.join(claude1, "settings.json")), norm(os.path.join(T2, "settings.json"))]]
for st in instalar.settings_todos():
    instalar.tocar_settings(True, settings=st)
for nombre, carpeta in (("instalado_T1", claude1), ("instalado_T2", T2)):
    cmds = comandos(os.path.join(carpeta, "settings.json"))
    R[nombre + "_hook"] = [any("companero_hook.py" in c for c in cmds), True]
    R[nombre + "_pre"] = [any("companero_hook_pre.py" in c for c in cmds), True]
    R[nombre + "_ajeno"] = [any("ajeno.exe" in c for c in cmds), True]
pre = json.load(open(os.path.join(claude1, "settings.json"), encoding="utf-8"))["hooks"]["PreToolUse"]
ligero = [e for e in pre if "Bash" in e.get("matcher", "")]
R["pre_ligero"] = [len(ligero) == 1 and ligero[0]["hooks"][0]["command"].count("-I -S") == 1
                   and "companero_hook_pre.py" in ligero[0]["hooks"][0]["command"] and ligero[0]["hooks"][0]["timeout"] == 10, True]

# ---- quitar: sin nuestros, el ajeno sigue
for st in instalar.settings_todos():
    instalar.tocar_settings(False, settings=st)
quedan = nuestros(comandos(os.path.join(claude1, "settings.json"))) + nuestros(comandos(os.path.join(T2, "settings.json")))
R["quitado_sin_nuestros"] = [quedan, []]
R["quitado_ajeno"] = [any("ajeno.exe" in c for c in comandos(os.path.join(T2, "settings.json"))), True]

# ---- --perfil: suma la carpeta una sola vez a config-prueba.json
instalar.agregar_perfil(T2)
instalar.agregar_perfil(T2)
perf = json.load(open(instalar.CONFIG_JSON, encoding="utf-8")).get("perfiles_claude")
R["perfil_una_vez"] = [perf, [os.path.abspath(T2)]]
print(json.dumps(R))
'''


def main():
    tmp1 = tempfile.mkdtemp(prefix="kodama-prueba-perfiles-casa-")
    tmp2 = tempfile.mkdtemp(prefix="kodama-prueba-perfiles-perfil-")
    try:
        env = dict(os.environ, USERPROFILE=tmp1, HOME=tmp1, CLAUDE_CONFIG_DIR=tmp2, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-c", CODIGO, AQUI, tmp1, tmp2], env=env, cwd=tmp1,
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            ver("subproceso termina bien", p.returncode, 0)
            print(p.stderr)
        else:
            R = json.loads(p.stdout.strip().splitlines()[-1])
            for nombre, (obtenido, esperado) in R.items():
                ver(nombre, obtenido, esperado)
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)
    print(f"\n{len(oks)} OK, {len(mal)} MAL")
    if mal:
        print("Fallaron: " + ", ".join(mal))
        sys.exit(1)


if __name__ == "__main__":
    main()
