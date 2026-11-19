# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov-2026, idea de coucou #52) Claude Code dentro de WSL. Sus hooks viven en el ~/.claude/settings.json de la distro y llaman a este script
con el Python de Windows (/mnt/c/.../python.exe, interoperabilidad de WSL): el JSON llega igual por stdin y el resultado sale igual por stdout.

Uso: companero_wsl.py hook | puente | permiso  (el modulo de Kodama que corresponde a ese hook).
- Cada sesion se anota como chat "WSL · <carpeta>", y por eso va a la mascota y al celular.
- Avisos y permisos: iguales que en Windows. Responderle: solo mientras espera en el hook Stop (companero_puente), porque el buzon de esa sesion
  es un socket de Linux que Windows no puede abrir.
Si algo falla, sale con 0 sin imprimir nada: nunca deja un chat trabado.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

EXTRA = os.path.join(config.ESTADO, "sesiones_extra.json")
MODULOS = {"hook": "companero_hook", "puente": "companero_puente", "permiso": "companero_permiso"}


def carpeta_de(cwd):
    return (cwd or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or "WSL"


def anotar(sid, cwd):
    """Anota la sesion en sesiones_extra.json si no estaba."""
    try:
        x = json.load(open(EXTRA, encoding="utf-8"))
    except (OSError, ValueError):
        x = {}
    if sid in x:
        return
    x[sid] = ["ws" + sid.replace("-", "")[-8:], f"WSL · {carpeta_de(cwd)}", ""]
    tmp = EXTRA + ".tmp"
    json.dump(x, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, EXTRA)


def main():
    modulo = MODULOS.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not modulo:
        return
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    sid = str(d.get("session_id") or "")
    if not sid:
        return
    anotar(sid, d.get("cwd"))
    d["agente"] = "wsl"
    # el buzon de Linux no se puede abrir desde Windows: que el registro de la sesion no lo guarde
    os.environ.pop("CLAUDE_CODE_MESSAGING_SOCKET", None)
    os.environ.pop("CLAUDE_CODE_MESSAGING_TOKEN", None)
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(d, ensure_ascii=False).encode("utf-8")), encoding="utf-8")
    __import__(modulo).main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
