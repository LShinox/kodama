# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Pone el hook del companero en settings.local.json de las 3 carpetas personales y
saca el del paso 0. Con --quitar saca los dos. Respaldo .bak-companero antes de tocar."""
import json
import os
import shutil
import sys

_CASA = os.path.expanduser("~").replace("\\", "/")
CARPETAS = [_CASA + "/Videos/Ingenieria-inversa",
            _CASA + "/Videos/Musica",
            _CASA + "/Videos/Rol",
            _CASA + "/Videos/Claude"]   # Instalaciones: el hook filtra por sesiones_extra.json (los chats de empresa salen sin escribir)
VIEJO = 'python "' + _CASA + '/Apps/companero/paso0_registrar.py"'
NUEVO = 'python "' + _CASA + '/Apps/companero/companero_hook.py"'
EVENTOS = ["SessionStart", "UserPromptSubmit", "Notification", "Stop", "SessionEnd"]
TODOS = EVENTOS + ["PermissionRequest", "SubagentStop"]
# 14-oct: el hook paso a ~\.claude\settings.json (global). Este script ahora se usa con --quitar para sacarlo
# de las carpetas (si no, en esas 4 carpetas corria dos veces).

# (27-oct, idea de clawd #1018) "pensando" vs "ejecutando": registra el hook en PreToolUse de la configuracion GLOBAL, SOLO para las
# herramientas largas (comando, web, subagente, conectores), para no sumar un proceso a cada lectura o edicion. Respalda
# settings.json (junto al archivo y en respaldos\) y es idempotente. Con --quitar-pretool lo saca. Uso: python instalar_hooks.py --pretool
GLOBAL = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
MATCHER_PRETOOL = "Bash|PowerShell|WebFetch|WebSearch|Agent|Task|mcp__.*"
# hook ligero aparte (sin json ni config, `-I -S`): arrancar python ya cuesta ~60 ms aqui y companero_hook.py pasa de 150 ms
NUEVO_PRE = 'python -I -S "' + _CASA + '/Apps/companero/companero_hook_pre.py"'
RESPALDOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "respaldos")


def pretool(quitar_pre=False):
    raw = open(GLOBAL, encoding="utf-8").read()
    d = json.loads(raw)
    hooks = d.setdefault("hooks", {})
    lista = hooks.get("PreToolUse", [])
    ya = [e for e in lista if any(h.get("command") == NUEVO_PRE for h in e.get("hooks", []))]
    if quitar_pre:
        if not ya:
            print("PreToolUse: no estaba; nada que hacer"); return
        nueva = [e for e in lista if e not in ya]
    elif ya and all(e.get("matcher") == MATCHER_PRETOOL for e in ya) and len(ya) == 1:
        print("PreToolUse: ya registrado; nada que hacer"); return
    else:
        nueva = [e for e in lista if e not in ya] + [{"matcher": MATCHER_PRETOOL, "hooks": [{"type": "command", "command": NUEVO_PRE, "timeout": 10}]}]
    os.makedirs(RESPALDOS_DIR, exist_ok=True)
    shutil.copy2(GLOBAL, GLOBAL + ".bak-companero")
    shutil.copy2(GLOBAL, os.path.join(RESPALDOS_DIR, "settings.json.bak-ultimos-20261027"))
    if nueva:
        hooks["PreToolUse"] = nueva
    else:
        hooks.pop("PreToolUse", None)
    tmp = GLOBAL + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.loads(open(tmp, encoding="utf-8").read())   # que quede JSON valido antes de reemplazar
    os.replace(tmp, GLOBAL)
    print("PreToolUse:", "quitado" if quitar_pre else f"registrado ({MATCHER_PRETOOL})")


if "--pretool" in sys.argv or "--quitar-pretool" in sys.argv:
    pretool(quitar_pre="--quitar-pretool" in sys.argv)
    sys.exit(0)

quitar = "--quitar" in sys.argv
for c in CARPETAS:
    p = os.path.join(c, ".claude", "settings.local.json")
    shutil.copy2(p, p + ".bak-companero")
    d = json.load(open(p, encoding="utf-8"))
    hooks = d.setdefault("hooks", {})
    for ev in TODOS:
        lista = [e for e in hooks.get(ev, [])
                 if not any(h.get("command") in (VIEJO, NUEVO) for h in e.get("hooks", []))]
        if not quitar and ev in EVENTOS:
            lista.append({"hooks": [{"type": "command", "command": NUEVO, "timeout": 10}]})
        if lista:
            hooks[ev] = lista
        else:
            hooks.pop(ev, None)
    if not hooks:
        d.pop("hooks")
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("ok", p, sorted(d.get("hooks", {})))
