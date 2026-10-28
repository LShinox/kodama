# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Agrega (o quita con --quitar) los hooks del paso 0 en settings.local.json de
las 3 carpetas personales. Respaldo .bak-paso0 antes de tocar."""
import json
import os
import shutil
import sys

_CASA = os.path.expanduser("~").replace("\\", "/")
CARPETAS = [_CASA + "/Videos/Ingenieria-inversa",
            _CASA + "/Videos/Musica",
            _CASA + "/Videos/Rol"]
CMD = 'python "' + _CASA + '/Apps/companero/paso0_registrar.py"'
EVENTOS = ["SessionStart", "UserPromptSubmit", "PermissionRequest", "Notification", "Stop", "SubagentStop"]

quitar = "--quitar" in sys.argv
for c in CARPETAS:
    p = os.path.join(c, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    d = {}
    if os.path.exists(p):
        shutil.copy2(p, p + ".bak-paso0")
        d = json.load(open(p, encoding="utf-8"))
    hooks = d.setdefault("hooks", {})
    for ev in EVENTOS:
        lista = [e for e in hooks.get(ev, []) if not any(h.get("command") == CMD for h in e.get("hooks", []))]
        if not quitar:
            ent = {"hooks": [{"type": "command", "command": CMD,
                              "timeout": 30 if ev == "PermissionRequest" else 10}]}
            if ev == "PermissionRequest":
                ent["matcher"] = "*"
            lista.append(ent)
        if lista:
            hooks[ev] = lista
        else:
            hooks.pop(ev, None)
    if not hooks:
        d.pop("hooks")
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("ok", p)
