# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(20-oct-2026) Puente de Kodama para Google Antigravity. Etapa 1: el chat aparece en la mascota y el celular
("Antigravity · <carpeta>"), pasa a "trabajando" cuando le escribes y avisa cuando termina.

Antigravity tiene hooks propios (doc: antigravity.google/docs/hooks?tab=ide), DISTINTOS a los de Claude Code:
~/.gemini/config/hooks.json → {"<nombre>": {"<Evento>": [ {type, command, timeout} ]}}; eventos SessionStart,
PreInvocation, PostInvocation, Stop, Pre/PostToolUse; stdin en camelCase (conversationId, workspacePaths,
transcriptPath, terminationReason, fullyIdle…). Ningun evento trae el texto de la respuesta: se busca en
transcriptPath (transcript.jsonl, formato no documentado; si no se puede, aviso generico).

Aprobar permisos desde el celular: todavia NO. Antigravity decide en PreToolUse (allow/ask/deny) pero el hook se
llama en TODAS las herramientas y no sabe cuales pediria permiso; esperar al celular en cada una lo frenaria todo.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

BASE = config.ESTADO
EXTRA = os.path.join(BASE, "sesiones_extra.json")


def anotar(sid, carpeta):
    try:
        x = json.load(open(EXTRA, encoding="utf-8"))
    except (OSError, ValueError):
        x = {}
    if sid in x:
        return
    x[sid] = ["ag" + sid.replace("-", "")[-8:], f"Antigravity · {carpeta or 'chat'}", ""]
    tmp = EXTRA + ".tmp"
    json.dump(x, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, EXTRA)


def ultimo_mensaje(ruta):
    """Ultimo texto del modelo en transcript.jsonl (formato no documentado: se prueban las formas comunes)."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, os.path.getsize(ruta) - 300000))
            lineas = f.read().decode("utf-8", "ignore").splitlines()
    except (OSError, TypeError):
        return None
    for l in reversed(lineas):
        try:
            x = json.loads(l)
        except ValueError:
            continue
        rol = str(x.get("role") or x.get("type") or x.get("source") or "").lower()
        if rol not in ("model", "assistant", "agent", "planner_response", "response"):
            continue
        partes = x.get("parts") or x.get("content") or x.get("text") or x.get("message")
        if isinstance(partes, str) and partes.strip():
            return partes
        if isinstance(partes, list):
            t = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in partes)
            if t.strip():
                return t
    return None


def correr(datos):
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(datos, ensure_ascii=False).encode("utf-8")), encoding="utf-8")
    __import__("companero_hook").main()


def traza(ev, d):
    """(20-oct) Una linea por llamada en estado\\antigravity_hook.log (sin contenido: evento y nombres de campos),
    para saber si Antigravity ejecuta el hook. Se recorta a las ultimas 200 lineas."""
    import datetime
    ruta = os.path.join(BASE, "antigravity_hook.log")
    try:
        lineas = open(ruta, encoding="utf-8").read().splitlines()[-199:] if os.path.exists(ruta) else []
        lineas.append(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {ev or '?'} campos={sorted(d)[:12]}")
        open(ruta, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    except OSError:
        pass


def main():
    ev = sys.argv[1] if len(sys.argv) > 1 else ""   # el evento va como argumento (el JSON no lo trae)
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        traza(ev, {"stdin_invalido": 1})
        return
    traza(ev, d if isinstance(d, dict) else {})
    # (20-oct) las sesiones que lanza un chat de Claude (`agy -p`, p. ej. para ver un video) no van a la mascota.
    # (21-oct) la cadena de padres no siempre llega a claude.exe (salieron 6 "Antigravity · agy" en el celular): toda
    # sesion del CLI agy.exe queda afuera; LShinox usa la APP de Antigravity, el CLI lo usan los chats.
    ps = __import__("companero_codex").padres()
    if ("claude.exe" in ps or "agy.exe" in ps) and os.environ.get("COMPANERO_AG_PRUEBA") != "1":
        return
    sid = str(d.get("conversationId") or "")
    if not sid or ev not in ("SessionStart", "PreInvocation", "Stop"):
        return
    rutas = d.get("workspacePaths") or []
    cwd = rutas[0] if rutas else ""
    anotar(sid, os.path.basename(os.path.normpath(cwd)) if cwd else "")
    base = {"session_id": sid, "cwd": cwd, "agente": "antigravity"}
    if ev == "SessionStart":
        correr(dict(base, hook_event_name="SessionStart"))
    elif ev == "PreInvocation":
        correr(dict(base, hook_event_name="UserPromptSubmit"))   # marca "trabajando" (el texto del pedido no viene)
    elif ev == "Stop" and d.get("fullyIdle", True):
        txt = ultimo_mensaje(d.get("transcriptPath")) or (
            "Antigravity se detuvo con un error." if d.get("error") else "Antigravity terminó su turno.")
        correr(dict(base, hook_event_name="Stop", last_assistant_message=txt))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    print("{}")   # salida JSON vacia: no cambia nada en Antigravity
    sys.exit(0)
