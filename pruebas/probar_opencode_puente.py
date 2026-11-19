# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(16-nov-2026) Prueba de companero_opencode.py sin tocar estado\\: se cambian en memoria `correr` (qué módulo y qué datos recibe)
y `anotar` (no escribe sesiones_extra.json). Uso: python pruebas\\probar_opencode_puente.py  (sale con 1 si algo falla)."""
import importlib.util
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
spec = importlib.util.spec_from_file_location("companero_opencode", os.path.join(AQUI, "companero_opencode.py"))
puente = importlib.util.module_from_spec(spec)
spec.loader.exec_module(puente)

llamadas = []
puente.correr = lambda modulo, datos: llamadas.append((modulo, datos))
puente.anotar = lambda *a, **k: None

ok, mal = 0, []


def ver(nombre, obtenido, esperado):
    global ok
    if obtenido == esperado:
        ok += 1
        print("OK  " + nombre)
    else:
        mal.append(nombre)
        print("MAL " + nombre + f" -> {obtenido!r} (esperado {esperado!r})")


def enviar(d):
    """Pasa un evento por main() como lo hace el plugin (JSON por stdin)."""
    del llamadas[:]
    viejo = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(d, ensure_ascii=False).encode("utf-8")), encoding="utf-8")
    try:
        puente.main()
    finally:
        sys.stdin = viejo
    return list(llamadas)


SID = "ses_abc123"
BASE = {"session_id": SID, "cwd": "C:/x", "titulo": "t"}

r = enviar(dict(BASE, evento="PreToolUse", tool_name="Bash", tool_input={"command": "ls"}))
ver("PreToolUse -> companero_hook_pre", [m for m, _ in r], ["companero_hook_pre"])
ver("PreToolUse: session_id primero, tool_name despues", list(r[0][1])[:2] if r else None, ["session_id", "tool_name"])
ver("PreToolUse: datos", r[0][1].get("tool_name") if r else None, "Bash")
ver("PreToolUse: agente opencode", r[0][1].get("agente") if r else None, "opencode")

# el hook ligero debe leer session_id y tool_name del JSON tal como lo serializa el puente
import companero_hook_pre as pre  # noqa: E402
s = json.dumps(r[0][1], ensure_ascii=False) if r else ""
ver("companero_hook_pre lee session_id del JSON del puente", pre.valor(s, "session_id"), SID)
ver("companero_hook_pre lee tool_name del JSON del puente", pre.valor(s, "tool_name"), "Bash")

r = enviar(dict(BASE, evento="PostToolUse", tool_name="TodoWrite", tool_input={"todos": [{"content": "a", "status": "completed"}]}))
ver("PostToolUse -> companero_hook", [m for m, _ in r], ["companero_hook"])
ver("PostToolUse: hook_event_name", r[0][1]["hook_event_name"] if r else None, "PostToolUse")
ver("PostToolUse: tool_name e input", (r[0][1]["tool_name"], r[0][1]["tool_input"]) if r else None,
    ("TodoWrite", {"todos": [{"content": "a", "status": "completed"}]}))

r = enviar(dict(BASE, evento="Notification", message="OpenCode: error — x"))
ver("Notification -> companero_hook con message", [(m, d["hook_event_name"], d["message"]) for m, d in r],
    [("companero_hook", "Notification", "OpenCode: error — x")])

r = enviar(dict(BASE, evento="Stop", texto="hola"))
ver("Stop sigue igual", [(m, d["hook_event_name"], d["last_assistant_message"]) for m, d in r], [("companero_hook", "Stop", "hola")])

r = enviar(dict(BASE, evento="PermissionRequest", tool_name="bash", tool_input={"command": "echo"}))
ver("PermissionRequest normal -> companero_permiso como PermissionRequest",
    [(m, d["hook_event_name"]) for m, d in r], [("companero_permiso", "PermissionRequest")])

pregunta = {"questions": [{"question": "¿Cuál?", "header": "Elige", "options": [{"label": "Uno", "description": ""}], "multiSelect": False}]}
r = enviar(dict(BASE, evento="PermissionRequest", tool_name="AskUserQuestion", tool_input=pregunta))
ver("AskUserQuestion -> companero_permiso como PreToolUse",
    [(m, d["hook_event_name"], d["tool_name"], d["tool_input"]) for m, d in r],
    [("companero_permiso", "PreToolUse", "AskUserQuestion", pregunta)])

r = enviar(dict(BASE, evento="UserPromptSubmit", texto="hola"))
ver("UserPromptSubmit sigue igual", [(m, d["prompt"]) for m, d in r], [("companero_hook", "hola")])

r = enviar({"session_id": "", "evento": "Stop", "texto": "x"})
ver("sin session_id: no se llama a nada", r, [])

print(f"\nprobar_opencode_puente: {ok} OK, {len(mal)} MAL")
sys.exit(1 if mal else 0)
