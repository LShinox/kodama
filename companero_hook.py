# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Hook del companero (etapa 1, 13-oct-2026). Desde el 14-oct se registra en la configuracion GLOBAL
(~\\.claude\\settings.json) y corre en todos los chats; ver el filtro de abajo.

- Cada evento: actualiza el registro de la sesion (buzon + titulo + estado).
- Stop / Notification: deja el mensaje en la cola para que el hub lo mande a Telegram.
No manda nada por red: eso lo hace companero_hub.py.
"""
import json
import os
import re
import sys
import time

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
BASE = config.ESTADO
SES = os.path.join(BASE, "sesiones")
COLA = os.path.join(BASE, "cola.jsonl")
PERSONALES = config.PERSONALES


FASE_DIR = os.path.join(BASE, "fase")


def fase_escribir(ev, sid):
    """(27-oct, idea de clawd #1018) "pensando" vs "ejecutando". Un archivo chico por sesion, estado\\fase\\<id>.txt: "fase|categoria|ts".
    PreToolUse (companero_hook_pre.py, ligero: solo herramientas largas) escribe "ejecutando"; aqui, PostToolUse (cualquier herramienta) y
    UserPromptSubmit lo vuelven a "pensando"; Stop / SessionStart / SessionEnd lo borran. Sin contenido: solo la categoria."""
    if not sid.replace("-", "").replace("_", "").isalnum() or len(sid) > 80:
        return
    p = os.path.join(FASE_DIR, sid + ".txt")
    try:
        if ev in ("PostToolUse", "UserPromptSubmit"):
            os.makedirs(FASE_DIR, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write("pensando||%.2f" % time.time())
        elif ev in ("Stop", "SessionStart", "SessionEnd"):
            os.remove(p)
    except OSError:
        pass


def que_hace(tool, inp):
    arch = os.path.basename(str(inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or ""))
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return f"editando {arch}" if arch else "editando un archivo"
    if tool == "Read":
        return f"leyendo {arch}" if arch else "leyendo"
    if tool in ("Bash", "PowerShell"):
        return "corriendo un comando"
    if tool in ("Grep", "Glob"):
        return "buscando en archivos"
    if tool in ("WebFetch", "WebSearch"):
        return "buscando en la web"
    if tool in ("Agent", "Task"):
        return "con un subagente"
    if tool.startswith("mcp__"):
        srv = tool.split("__")[1]
        return "usando un conector" if all(c in "0123456789abcdef-" for c in srv) else "usando " + srv[:24]
    if tool in HERR_TAREAS:
        return "actualizando sus tareas"
    return tool[:30] or "trabajando"


# (26-oct) progreso de tareas "3 de 7". Claude Code en esta PC usa TaskCreate / TaskUpdate (verificado contando nombres de
# herramienta en los .jsonl de los ultimos 7 dias; TodoWrite no aparece, se acepta por si una version vieja lo usa).
# Este mismo hook ya escucha PostToolUse sin matcher: no hace falta registrar nada nuevo en settings.json.
# Se guarda en el registro de la sesion SOLO conteos y el asunto (<= 80 caracteres) de la tarea en curso.
# (26-oct, prueba real) la app de escritorio le da al chat su propia lista: mcp__ccd_turn__update_plan, que manda la
# lista ENTERA cada vez ({"items": [{"content", "status"}]}), igual que TodoWrite.
HERR_TAREAS = ("TaskCreate", "TaskUpdate", "TodoWrite", "mcp__ccd_turn__update_plan")
_ESTADOS_TAREA = {"pending": "p", "in_progress": "c", "completed": "h"}   # pendiente / en curso / hecha


def _id_creada(resp, items):
    """Id que le dio Claude Code a la tarea nueva (viene en la respuesta); si no se puede leer, el siguiente numero."""
    try:
        if isinstance(resp, dict):
            t = resp.get("task") if isinstance(resp.get("task"), dict) else resp
            if t.get("id") is not None:
                return str(t["id"])
        m = re.search(r"Task #(\d+)", resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False))
        if m:
            return m.group(1)
    except Exception:
        pass
    nums = [int(k) for k in items if str(k).isdigit()]
    return str((max(nums) if nums else 0) + 1)


def tareas_actualizar(reg, d):
    tool, inp, resp = d.get("tool_name"), d.get("tool_input") or {}, d.get("tool_response")
    prev = reg.get("tareas") if isinstance(reg.get("tareas"), dict) else {}
    items = prev.get("items") if isinstance(prev.get("items"), dict) else {}   # id -> [p|c|h, asunto]
    if tool in ("TodoWrite", "mcp__ccd_turn__update_plan"):   # mandan la lista entera cada vez
        items = {str(i + 1): [_ESTADOS_TAREA.get(x.get("status"), "p"), str(x.get("content") or "")[:80]]
                 for i, x in enumerate(inp.get("todos") or inp.get("items") or []) if isinstance(x, dict)}
    elif tool == "TaskCreate":
        items[_id_creada(resp, items)] = ["p", str(inp.get("subject") or "")[:80]]
    elif tool == "TaskUpdate":
        tid, st = str(inp.get("taskId")), inp.get("status")
        if st == "deleted":
            items.pop(tid, None)
        elif st in _ESTADOS_TAREA:
            items[tid] = [_ESTADOS_TAREA[st], (items.get(tid) or ["", ""])[1]]
        if inp.get("subject") and tid in items:
            items[tid][1] = str(inp["subject"])[:80]
    if len(items) > 80:   # tope: nunca crece sin limite
        items = dict(list(items.items())[-80:])
    hechas = sum(1 for v in items.values() if v[0] == "h")
    actual = next((v[1] for v in items.values() if v[0] == "c"), "")
    reg["tareas"] = {"h": hechas, "t": len(items), "a": actual[:80], "ts": time.time(), "items": items}


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    ev = d.get("hook_event_name", "")
    sid = d.get("session_id")
    if not sid or ev == "SubagentStop":
        return
    fase_escribir(ev, sid)   # (27-oct) "pensando": aqui; "ejecutando": companero_hook_pre.py (PreToolUse)
    # 14-oct: el hook corre en TODOS los chats (config global) para poder llevar al celular un grupo de la
    # app de Claude. De cualquier chat se guarda solo el registro (buzon, titulo, estado: sin contenido), asi
    # se le puede responder si mas tarde lo elegis. El TEXTO de sus mensajes se guarda SOLO si es de las 3
    # carpetas personales, de sesiones_extra.json (Instalaciones) o del grupo elegido (elegidos.json, lo
    # escribe el hub). Si falla algo, sale sin escribir.
    proy = os.path.basename(os.path.dirname(d.get("transcript_path") or ""))
    guardar_texto = sid not in config.OCULTAR and (config.es_personal(proy) or sid in config.FIJAS)   # (14-oct) regla de carpeta
    if not guardar_texto:
        for f, campo in (("sesiones_extra.json", None), ("elegidos.json", "sesiones")):
            try:
                x = json.load(open(os.path.join(BASE, f), encoding="utf-8"))
                if sid in (x.get(campo) if campo else x):
                    guardar_texto = True
            except Exception:
                pass
    if ev == "PostToolUse" and not guardar_texto:   # "que esta haciendo": solo de los chats que van al celular
        return
    os.makedirs(SES, exist_ok=True)
    p = os.path.join(SES, f"{sid}.json")
    try:
        reg = json.load(open(p, encoding="utf-8"))
    except Exception:
        reg = {}
    if ev == "PostToolUse":   # (14-oct) una linea corta: verbo + nombre de archivo, nunca el contenido
        reg["haciendo"], reg["haciendo_ts"] = que_hace(d.get("tool_name") or "", d.get("tool_input") or {}), time.time()
    if ev == "PostToolUse" and d.get("tool_name") in HERR_TAREAS:   # (26-oct) "3 de 7"
        try:
            tareas_actualizar(reg, d)
        except Exception:
            pass
    elif ev == "SessionEnd" or (ev == "SessionStart" and d.get("source") in ("startup", "clear")):
        reg.pop("tareas", None)   # chat nuevo, limpiado o cerrado: la lista de antes ya no vale (en resume/compact se conserva)
    reg.update({
        "session_id": sid,
        "cwd": d.get("cwd") or reg.get("cwd"),
        "proyecto": os.path.basename(os.path.dirname(d.get("transcript_path") or "")) or reg.get("proyecto"),
        "socket": os.environ.get("CLAUDE_CODE_MESSAGING_SOCKET") or reg.get("socket"),
        "token": os.environ.get("CLAUDE_CODE_MESSAGING_TOKEN") or reg.get("token"),
        "visto": time.time(),
    })
    if d.get("session_title"):
        reg["titulo"] = d["session_title"]
    if d.get("agente"):   # (20-oct) "codex": viene de companero_codex.py (Codex CLI); sin buzon para responderle
        reg["agente"] = d["agente"]
    if ev == "UserPromptSubmit":
        reg["estado"] = "trabajando"
    elif ev == "Stop":
        reg["estado"] = "termino"
    elif ev in ("SessionStart", "SessionEnd"):   # SessionEnd (14-oct): al cerrar el chat no queda "trabajando"
        reg["estado"] = "reposo"
    tmp = p + ".tmp"
    json.dump(reg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, p)

    # (15-oct) el chat "Medidor" (carpeta medidor\) responde el uso EXACTO del plan en una linea JSON: se anota para el
    # estimador del Companero (estado\uso_exacto.jsonl). No va a la app ni avisa.
    try:
        sid_medidor = json.load(open(os.path.join(BASE, "medidor.json"), encoding="utf-8")).get("sid")
    except Exception:
        sid_medidor = None
    if ev == "Stop" and (sid == sid_medidor or os.path.normcase(os.path.normpath(d.get("cwd") or "")) == os.path.normcase(config.CHAT_DIR)):
        try:
            import re as _r, datetime as _dt
            m = _r.search(r'\{[^{}]*"medidor"[^{}]*\}', d.get("last_assistant_message") or "")
            x = json.loads(m.group(0)) if m else {}
            if x.get("5h") is not None:
                rein = x.get("reinicia5h")
                rein = _dt.datetime.fromisoformat(str(rein).replace("Z", "+00:00")).timestamp() if rein else None
                with open(os.path.join(BASE, "uso_exacto.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.time(), "5h": float(x["5h"]), "semana": float(x.get("semana") or 0),
                                        "reinicia5h": rein, "fuente": "medidor"}) + "\n")
        except Exception:
            pass
        return

    texto, extra = None, {}
    if not guardar_texto:
        return
    if ev == "Stop":
        texto = d.get("last_assistant_message") or ""
    elif ev == "Notification":
        texto = d.get("message") or ""
    elif ev == "UserPromptSubmit":   # (15-oct) lo que escribes en la PC: para verlo tambien en el celular
        texto = (d.get("prompt") or "").strip()
        # (16-oct) avisos que inyecta el sistema como si fueran del usuario (fin de un subagente, mensajes de otro chat,
        # comandos): no los escribiste vos, no van al celular como tuyos
        if re.match(r"\s*(<(task-notification|system-reminder|cross-session-message|local-command|command-name|command-message)\b"
                    r"|\[SYSTEM NOTIFICATION|Another Claude session sent a message)", texto):
            texto = ""
    elif ev == "PostToolUse" and d.get("tool_name") == "SendUserFile":   # (15-oct) archivos que el chat te manda: al celular
        fs = (d.get("tool_input") or {}).get("files") or []
        base = d.get("cwd") or ""
        rutas = [f if os.path.isabs(f) else os.path.join(base, f) for f in fs if isinstance(f, str)]
        if rutas:
            ev = "Archivo"
            cap = ((d.get("tool_input") or {}).get("caption") or "").strip()
            texto = ((cap + "\n\n") if cap else "") + "\n".join("`" + r + "`" for r in rutas)
            # (27-oct) ademas del texto (compatible con lo de antes), las rutas y el caption sueltos: el hub los entrega a la
            # app del celular, que muestra miniatura (imagen) o enlace. No se copia ningun archivo.
            extra = {"archivos": rutas[:12], "caption": cap[:2000]}
    if texto:
        with open(COLA, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "evento": ev, "session_id": sid, "texto": texto, **extra},
                               ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
