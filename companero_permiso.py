# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Aprobar o denegar permisos desde el celular (14-oct-2026; para quien NO usa bypass — el pedido nº 1 de los
issues de la competencia). Hook PermissionRequest (config global, NO async, timeout 130 s).

- Siempre anota el pedido en estado\\permisos.jsonl (herramienta, carpeta, modo; sin el contenido): sirve para
  saber si la app de escritorio dispara este evento (la doc no lo garantiza).
- Si el chat va al celular y estas LEJOS (PC sin uso >= 2 min, o la app del celular abierta ahora mismo): avisa
  (Telegram con Permitir/Denegar, push, app) y espera hasta 110 s. Si respondes, devuelve la decision.
- Si no respondes o estas en la PC: sale sin decidir y aparece el dialogo normal de Claude Code.
Doc: code.claude.com/docs/en/hooks ("PermissionRequest decision control").
"""
import ctypes
import json
import os
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
from kodama_comun import celular_abierto, va_al_celular  # noqa: E402,F401

BASE = config.ESTADO
DIR = os.path.join(BASE, "permisos")
ESPERA = 110


def sin_uso():
    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    lii = LII(); lii.cbSize = ctypes.sizeof(LII)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0


def _responder(dec):
    """(28-oct) Escribe la decision del hook PermissionRequest: es lo unico que Claude Code lee de la salida."""
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": dec}}, ensure_ascii=False))
    sys.stdout.flush()


def _quitar(ruta):
    try:
        os.remove(ruta)
    except OSError:
        pass


def resumen(tool, inp, tope=1500):
    """Lo que se ve para decidir: QUE herramienta y TODO lo que va a hacer. (14-oct, auditoria) antes se cortaba a
    160 caracteres sin avisar y las herramientas MCP / Write salian sin argumentos: se podia aprobar algo que no se veia."""
    if tool in ("Bash", "PowerShell"):
        txt = f"{tool}: {inp.get('command', '')}"
    else:
        arch = inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or inp.get("url") or ""
        resto = {k: v for k, v in inp.items() if k not in ("file_path", "notebook_path", "path", "url")}
        try:
            args = json.dumps(resto, ensure_ascii=False)
        except (TypeError, ValueError):
            args = str(resto)
        txt = f"{tool}: {arch}".rstrip(": ") + ("\n" + args if resto else "")
    return txt if len(txt) <= tope else txt[:tope] + f"\n… [cortado: {len(txt) - tope} caracteres más; revísalo en la PC]"


REGLAS = os.path.join(BASE, "reglas_permiso.json")


def clave_regla(tool, inp):
    """(22-oct, mejora 2, idea de Nudge/Happy) a que se aplica una regla: el comando exacto (Bash/PowerShell) o la
    herramienta + archivo/URL. Exacto a proposito: "npm test" no aprueba "npm test && rm -rf ."."""
    if tool in ("Bash", "PowerShell"):
        return f"{tool}: {inp.get('command', '')}"
    arch = inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or inp.get("url") or ""
    return f"{tool}: {arch}" if arch else tool


def por_regla(sid, clave):
    """'siempre' / 'tarea' si una regla tuya ya aprueba esto (no te pregunta), o None."""
    try:
        r = json.load(open(REGLAS, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if clave in (r.get("siempre") or []):
        return "siempre"
    if clave in ((r.get("tarea") or {}).get(sid) or []):
        return "tarea"
    return None


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    sid, tool, inp = d.get("session_id") or "", d.get("tool_name") or "", d.get("tool_input") or {}
    proy = os.path.basename(os.path.dirname(d.get("transcript_path") or ""))
    evento = d.get("hook_event_name") or "PermissionRequest"
    if tool == "AskUserQuestion":
        # (19-oct, idea de Coucou PR #712) las preguntas con opciones se responden desde el celular TOCANDO una opcion
        # (no "Permitir/Denegar"). Va por PreToolUse, el camino documentado: allow + updatedInput {questions, answers}.
        if evento == "PreToolUse":
            return pregunta(d, sid, proy, inp)
        return   # PermissionRequest de la misma pregunta: ya la manejo PreToolUse (no preguntar dos veces)
    if evento != "PermissionRequest":
        return
    if tool == "ExitPlanMode":   # (20-oct) aprobar el PLAN desde el celular (idea de Coucou 0.5.2)
        return plan(d, sid, proy, inp)
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(BASE, "permisos.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "sesion": sid[:8], "proyecto": proy, "herramienta": tool,
                            "modo": d.get("permission_mode")}) + "\n")
    clave = clave_regla(tool, inp)
    regla = por_regla(sid, clave)
    if regla:   # (22-oct, mejora 2) ya lo aprobaste con una regla: no se pregunta ni en la PC ni en el celular
        with open(os.path.join(BASE, "permisos.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "sesion": sid[:8], "por_regla": regla, "herramienta": tool}) + "\n")
        _responder({"behavior": "allow"})
        return
    lejos = sin_uso() >= 120 or celular_abierto() or os.environ.get("COMPANERO_PERMISO_PRUEBA") == "1"
    if not sid or not lejos or not va_al_celular(sid, proy):
        return
    pid = secrets.token_hex(4)
    ped, resp = os.path.join(DIR, pid + ".pedido"), os.path.join(DIR, pid + ".respuesta")
    texto = resumen(tool, inp)
    json.dump({"id": pid, "sesion": sid, "texto": texto, "ts": time.time(), "regla": clave}, open(ped, "w", encoding="utf-8"))
    with open(os.path.join(BASE, "cola.jsonl"), "a", encoding="utf-8") as f:   # el hub lo avisa
        f.write(json.dumps({"ts": time.time(), "evento": "PermissionRequest", "session_id": sid,
                            "texto": texto, "permiso_id": pid}, ensure_ascii=False) + "\n")
    inicio = time.time()
    try:
        while time.time() - inicio < ESPERA:
            if os.path.exists(resp):
                r = json.load(open(resp, encoding="utf-8"))
                os.remove(resp)
                if r.get("decision") == "pc":   # (22-oct, mejora 2) "que lo decida la PC": sale sin decidir -> dialogo normal
                    return
                if r.get("decision") == "allow":
                    dec = {"behavior": "allow"}
                else:
                    # (22-oct, mejora 6) con motivo, Claude sabe por que y busca otra forma en vez de insistir
                    mot = (r.get("motivo") or "").strip()
                    dec = {"behavior": "deny", "message": f"{config.NOMBRE} lo denegó desde el celular." + (f" Motivo: {mot}" if mot else "")}
                _responder(dec)
                return
            time.sleep(1)
    finally:
        _quitar(ped)


PLAN_Q = "¿Apruebo el plan?"
PLAN_OPS = {"Sí, y acepta los cambios": "acceptEdits", "Sí, revisando cada cambio": "default", "No, sigue planeando": None}


def plan(d, sid, proy, inp):
    """(20-oct) ExitPlanMode: el plan llega al celular con 3 opciones (como el dialogo de Claude Code). Doc hooks:
    PermissionRequest allow + updatedPermissions setMode (acceptEdits/default); "seguir planeando" = deny con mensaje
    (que mantenga el modo plan esta SIN CONFIRMAR en la doc). Sin respuesta en 110 s: dialogo normal en la PC."""
    with open(os.path.join(BASE, "permisos.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "sesion": sid[:8], "proyecto": proy, "herramienta": "ExitPlanMode"}) + "\n")
    lejos = sin_uso() >= 120 or celular_abierto() or os.environ.get("COMPANERO_PERMISO_PRUEBA") == "1"
    if not sid or not lejos or not va_al_celular(sid, proy):
        return
    texto_plan = str(inp.get("plan") or "")
    if not texto_plan and inp.get("planFilePath"):
        try:
            texto_plan = open(inp["planFilePath"], encoding="utf-8").read()
        except OSError:
            pass
    os.makedirs(DIR, exist_ok=True)
    pid = secrets.token_hex(4)
    ped, resp = os.path.join(DIR, pid + ".pedido"), os.path.join(DIR, pid + ".respuesta")
    texto = "Plan listo para aprobar:\n" + texto_plan[:3000]
    preguntas = [{"q": PLAN_Q, "header": "Plan", "opciones": list(PLAN_OPS), "multi": False}]
    json.dump({"id": pid, "sesion": sid, "texto": texto, "ts": time.time(), "preguntas": preguntas, "plan": True},
              open(ped, "w", encoding="utf-8"))
    with open(os.path.join(BASE, "cola.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "evento": "PermissionRequest", "session_id": sid, "texto": "¿Apruebo el plan? " + texto_plan[:300],
                            "permiso_id": pid, "pregunta": True}, ensure_ascii=False) + "\n")
    inicio = time.time()
    try:
        while time.time() - inicio < ESPERA:
            if os.path.exists(resp):
                r = json.load(open(resp, encoding="utf-8"))
                os.remove(resp)
                eleccion = (r.get("respuestas") or {}).get(PLAN_Q)
                if eleccion not in PLAN_OPS:
                    return
                modo = PLAN_OPS[eleccion]
                if modo:
                    dec = {"behavior": "allow", "updatedPermissions": [{"type": "setMode", "mode": modo, "destination": "session"}]}
                else:
                    dec = {"behavior": "deny", "message": f"{config.NOMBRE} pidió desde el celular seguir planeando: todavía no ejecutes el plan; espera sus cambios."}
                _responder(dec)
                return
            time.sleep(1)
    finally:
        _quitar(ped)


def pregunta(d, sid, proy, inp):
    """AskUserQuestion: si estas lejos y el chat va al celular, manda la pregunta con sus opciones y espera hasta 110 s.
    Respondida: PreToolUse allow + updatedInput {questions (las mismas), answers {pregunta: etiqueta}}. Si no: nada
    (la app de Claude la muestra como siempre)."""
    qs = inp.get("questions") or []
    if not isinstance(qs, list) or not qs:
        return
    with open(os.path.join(BASE, "permisos.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "sesion": sid[:8], "proyecto": proy, "herramienta": "AskUserQuestion",
                            "evento": "PreToolUse"}) + "\n")
    lejos = sin_uso() >= 120 or celular_abierto() or os.environ.get("COMPANERO_PERMISO_PRUEBA") == "1"
    if not sid or not lejos or not va_al_celular(sid, proy):
        return
    preguntas = [{"q": str(q.get("question") or "")[:500], "header": str(q.get("header") or "")[:40],
                  "opciones": [str(o.get("label") or "")[:120] for o in (q.get("options") or []) if isinstance(o, dict)][:8],
                  "multi": bool(q.get("multiSelect"))} for q in qs[:4] if isinstance(q, dict)]
    os.makedirs(DIR, exist_ok=True)
    pid = secrets.token_hex(4)
    ped, resp = os.path.join(DIR, pid + ".pedido"), os.path.join(DIR, pid + ".respuesta")
    texto = "\n\n".join(p["q"] + "\n" + "\n".join("• " + o for o in p["opciones"]) for p in preguntas)
    json.dump({"id": pid, "sesion": sid, "texto": texto, "ts": time.time(), "preguntas": preguntas}, open(ped, "w", encoding="utf-8"))
    with open(os.path.join(BASE, "cola.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "evento": "PermissionRequest", "session_id": sid, "texto": texto,
                            "permiso_id": pid, "pregunta": True}, ensure_ascii=False) + "\n")
    inicio = time.time()
    try:
        while time.time() - inicio < ESPERA:
            if os.path.exists(resp):
                r = json.load(open(resp, encoding="utf-8"))
                os.remove(resp)
                validas = {p["q"]: set(p["opciones"]) for p in preguntas}
                ans = {}
                for q, v in (r.get("respuestas") or {}).items():
                    elegidas = [x for x in str(v).split(", ") if x in validas.get(q, ())]
                    if elegidas:
                        ans[q] = ", ".join(elegidas)
                if not ans:
                    return
                sys.stdout.write(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "allow",
                    "updatedInput": {"questions": qs, "answers": ans}}}, ensure_ascii=False))
                sys.stdout.flush()
                return
            time.sleep(1)
    finally:
        _quitar(ped)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
