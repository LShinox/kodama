# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov-2026, idea de happy #265) Puente de Kodama para OpenCode. El plugin (opencode_plugin.js, copiado por instalar.py a ~/.config/opencode/plugins/kodama.js)
llama a este script por cada evento, con un JSON por stdin: {"evento", "session_id", "cwd", "titulo", "texto", "tool_name", "tool_input"}.
evento = SessionStart | UserPromptSubmit | Stop | SessionEnd | PermissionRequest | PreToolUse | PostToolUse | Notification. Reusa los mismos scripts que con Claude Code.
(16-nov) PreToolUse -> companero_hook_pre; PostToolUse -> companero_hook (tool_name ya en nombres de Claude); Notification -> companero_hook (message).
- Cada sesion se anota como chat "OpenCode · <titulo o carpeta>".
- PermissionRequest: imprime la decision de companero_permiso; el plugin la convierte en la respuesta de OpenCode. Sin salida: decide la PC.
- Responderle: el hub deja la respuesta en estado\\opencode\\ (kodama_comun.opencode_encolar) y el plugin se la manda a la sesion.
Si algo falla, sale con 0 sin imprimir nada.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

EXTRA = os.path.join(config.ESTADO, "sesiones_extra.json")
TITULO_DEFECTO = ("new session", "child session")


def anotar(sid, cwd, titulo):
    """Anota la sesion en sesiones_extra.json. Los titulos automaticos de OpenCode ("New session - fecha") no cuentan; si despues llega uno real, se corrige el nombre."""
    if (titulo or "").strip().lower().startswith(TITULO_DEFECTO):
        titulo = ""
    try:
        x = json.load(open(EXTRA, encoding="utf-8"))
    except (OSError, ValueError):
        x = {}
    if sid in x and (not titulo or x[sid][1] == f"OpenCode · {titulo}"):
        return
    carpeta = os.path.basename(os.path.normpath(cwd or "")) or "OpenCode"
    if sid in x:
        x[sid][1] = f"OpenCode · {titulo}"
    else:
        x[sid] = ["oc" + "".join(c for c in sid if c.isalnum())[-8:], f"OpenCode · {titulo or carpeta}", ""]
    tmp = EXTRA + ".tmp"
    json.dump(x, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, EXTRA)


def correr(modulo, datos):
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(datos, ensure_ascii=False).encode("utf-8")), encoding="utf-8")
    __import__(modulo).main()


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    sid, ev, cwd = str(d.get("session_id") or ""), d.get("evento") or "", d.get("cwd") or ""
    if not sid or not sid.replace("-", "").replace("_", "").isalnum() or len(sid) > 80:
        return
    anotar(sid, cwd, d.get("titulo") or "")
    base = {"hook_event_name": ev, "session_id": sid, "cwd": cwd, "agente": "opencode"}
    tool = str(d.get("tool_name") or "OpenCode")
    if ev == "PermissionRequest":
        # AskUserQuestion: companero_permiso solo la atiende como PreToolUse (pregunta() devuelve answers)
        ev_perm = "PreToolUse" if tool == "AskUserQuestion" else ev
        correr("companero_permiso", dict(base, hook_event_name=ev_perm, tool_name=tool, tool_input=d.get("tool_input") or {}))
    elif ev == "PreToolUse":
        # companero_hook_pre lee session_id y tool_name al principio del JSON (sin json)
        correr("companero_hook_pre", {"session_id": sid, "tool_name": tool, "hook_event_name": ev, "cwd": cwd, "agente": "opencode", "tool_input": d.get("tool_input") or {}})
    elif ev == "PostToolUse":
        correr("companero_hook", dict(base, tool_name=tool, tool_input=d.get("tool_input") or {}))
    elif ev == "Notification":
        correr("companero_hook", dict(base, message=str(d.get("message") or "")[:200]))
    elif ev == "Stop":
        correr("companero_hook", dict(base, last_assistant_message=d.get("texto") or "OpenCode terminó su turno."))
    elif ev == "UserPromptSubmit":
        correr("companero_hook", dict(base, prompt=d.get("texto") or ""))
    elif ev in ("SessionStart", "SessionEnd"):
        correr("companero_hook", base)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
