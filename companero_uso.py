# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Medidor de uso del plan (14-oct-2026). statusLine global de Claude Code: recibe por stdin el JSON de la sesion,
guarda rate_limits (5 h y semanal: % usado y hora de reinicio) en estado\\uso.json para el Companero y
devuelve una linea corta para la barra de estado. Doc oficial: code.claude.com/docs/en/statusline
("Rate limit usage"; solo planes Pro/Max y despues de la primera respuesta de la sesion).
El hub lee ese archivo (kodama_medidor.uso_statusline) y, si esta fresco, muestra el dato EXACTO en la mascota y el celular.

(28-oct) Encadenado: si la persona ya tenia una statusLine propia, el instalador la guarda en config.json
("statusline_previa": {"type": "command", "command": ...}) y pone esta. Entonces este archivo anota el uso y despues
corre ese comando con el MISMO stdin e imprime SU salida tal cual: la barra de estado queda igual que antes.
Sin comando previo imprime la linea corta de siempre ("5h NN% · semana NN%")."""
import json
import os
import subprocess
import sys
import time

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
USO = os.path.join(config.ESTADO, "uso.json")
PLAZO_PREVIA_S = 5      # tope para el comando previo (la barra de estado no puede quedar colgada)


def anotar(raw, uso=None):
    """Lee el JSON de la sesion (bytes), guarda rate_limits en uso.json y devuelve la linea corta ("" si no hay datos)."""
    uso = uso or USO
    try:
        d = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return ""
    rl = (d.get("rate_limits") if isinstance(d, dict) else None) or {}
    if not rl:
        return ""
    out = {"ts": time.time()}
    for clave, nombre in (("five_hour", "5h"), ("seven_day", "semana")):
        v = rl.get(clave) or {}
        if "used_percentage" in v:
            out[nombre] = {"pct": v.get("used_percentage"), "reinicia": v.get("resets_at")}
    try:
        open(uso + ".tmp", "w", encoding="utf-8").write(json.dumps(out)); os.replace(uso + ".tmp", uso)
    except OSError:
        pass
    return " · ".join(f"{k} {round(v['pct'])}%" for k, v in out.items() if isinstance(v, dict) and v.get("pct") is not None)


def _bash_de_git():
    """En Windows Claude Code corre estos comandos con Git Bash: se busca ese (no el bash.exe de WSL, que esta en System32)."""
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for sub in (("Git", "bin", "bash.exe"), ("Programs", "Git", "bin", "bash.exe")):
            ruta = os.path.join(base, *sub) if base else ""
            if ruta and os.path.isfile(ruta):
                return ruta
    return None


def correr_previa(previa, raw):
    """Corre el comando de la statusLine anterior con el mismo stdin y devuelve su salida (bytes). b"" si falla."""
    cmd = previa.get("command") if isinstance(previa, dict) else None
    if not cmd or not isinstance(cmd, str) or "companero_uso.py" in cmd:   # sin comando, o seria llamarse a si misma
        return b""
    kw = {"input": raw, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL, "timeout": PLAZO_PREVIA_S}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000   # CREATE_NO_WINDOW
        bash = _bash_de_git()
        args = [bash, "-c", cmd] if bash else cmd
    else:
        args = cmd
    try:
        return subprocess.run(args, shell=not isinstance(args, list), **kw).stdout or b""
    except Exception:
        return b""


def main(raw=None, previa=None, uso=None):
    """Devuelve los bytes que van a la barra de estado."""
    if raw is None:
        raw = sys.stdin.buffer.read()
    try:
        linea = anotar(raw, uso)
    except Exception:
        linea = ""
    if previa is None:
        previa = getattr(config, "STATUSLINE_PREVIA", None)
    if previa:
        return correr_previa(previa, raw)
    return linea.encode("utf-8")   # utf-8: la consola de Windows rompe el "·"


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(main())
        sys.stdout.buffer.flush()
    except Exception:
        pass
