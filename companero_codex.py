# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(20-oct-2026) Puente de Kodama para Codex CLI (OpenAI). Etapa 1: avisos (terminó / pregunta) y aprobar o
denegar permisos desde el celular, reusando los mismos scripts que con Claude Code.

Codex tiene hooks casi iguales a los de Claude Code (~/.codex/hooks.json: SessionStart, UserPromptSubmit,
PermissionRequest… mismo JSON por stdin, misma salida `hookSpecificOutput.decision`) y ademas `notify` en
~/.codex/config.toml, que al terminar cada turno llama a un programa con un JSON como ULTIMO ARGUMENTO
({"type": "agent-turn-complete", "thread-id", "turn-id", "cwd", "input-messages", "last-assistant-message"}).
Doc: developers.openai.com/codex/hooks y /codex/config-advanced (lo confirmo el propio Codex 0.153, 20-oct).

- Cada sesion de Codex se anota UNA vez en estado\\sesiones_extra.json como chat "Codex · <carpeta>" (asi va a la
  app y a la mascota). Las sesiones que lanza un chat de Claude (p. ej. `codex exec` para imagenes) NO se anotan: se
  reconoce porque el transcript dice originator "codex_exec" (21-oct) o porque claude.exe esta entre los procesos padre.
- "terminó" sale de `notify` (trae el ultimo mensaje); los permisos van por el hook PermissionRequest.
- Responder un mensaje a una sesion de Codex abierta: todavia NO (no hay forma confirmada de escribirle a la TUI).
"""
import ctypes
import ctypes.wintypes as w
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

BASE = config.ESTADO
EXTRA = os.path.join(BASE, "sesiones_extra.json")


def padres():
    """Nombres de los procesos padre (hasta 8 niveles), con la API de Windows (sin PowerShell: el hook debe ser rapido)."""
    class PE(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    tabla, e = {}, PE()
    e.dwSize = ctypes.sizeof(PE)
    ok = k.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        tabla[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile.lower())
        ok = k.Process32NextW(snap, ctypes.byref(e))
    k.CloseHandle(snap)
    out, pid = [], os.getpid()
    for _ in range(8):
        if pid not in tabla:
            break
        pid, _n = tabla[pid]
        if pid in tabla:
            out.append(tabla[pid][1])
    return out


def titulo_hilo(sid):
    """Titulo que Codex le pone al hilo (~/.codex/session_index.jsonl); None si todavia no lo escribio."""
    try:
        with open(os.path.join(os.path.expanduser("~"), ".codex", "session_index.jsonl"), encoding="utf-8") as f:
            for l in reversed(f.readlines()[-500:]):
                if sid in l:
                    return (json.loads(l).get("thread_name") or "").strip() or None
    except (OSError, ValueError):
        pass
    return None


def es_exec(sid, ruta=None):
    """(21-oct) True si la sesion es un `codex exec` (sin ventana: la lanza un programa, p. ej. un chat de Claude que
    genera una imagen). Lo dice la 1.a linea del transcript: originator "codex_exec" / source "exec" (la app de Codex
    escribe "Codex Desktop"). Hace falta porque la cadena de procesos padre no siempre llega a claude.exe."""
    try:
        if not ruta:
            raiz = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
            for dias in (0, 1):   # sessions\AAAA\MM\DD\rollout-...-<sid>.jsonl: hoy y ayer alcanzan
                carpeta = os.path.join(raiz, time.strftime("%Y\\%m\\%d", time.localtime(time.time() - dias * 86400)))
                hallado = [f for f in (os.listdir(carpeta) if os.path.isdir(carpeta) else []) if sid in f]
                if hallado:
                    ruta = os.path.join(carpeta, hallado[0])
                    break
        if not ruta:
            return False
        with open(ruta, encoding="utf-8") as f:
            p = (json.loads(f.readline()) or {}).get("payload") or {}
        return p.get("originator") == "codex_exec" or p.get("source") == "exec"
    except (OSError, ValueError, AttributeError):
        return False


def anotar(sid, cwd, ruta=None):
    """Anota la sesion en sesiones_extra.json si no estaba. False si es una sesion lanzada por un chat de Claude.
    (20-oct) El nombre es el titulo del hilo en Codex; la carpeta solo si todavia no hay titulo (la app de Codex
    reusa carpetas con nombres de otro pedido). Si el titulo aparece despues, se corrige el nombre."""
    try:
        x = json.load(open(EXTRA, encoding="utf-8"))
    except (OSError, ValueError):
        x = {}
    titulo = titulo_hilo(sid)
    if sid in x:
        if not titulo or x[sid][1] == f"Codex · {titulo}":
            return True
        x[sid][1] = f"Codex · {titulo}"
    elif (es_exec(sid, ruta) or "claude.exe" in padres()) and os.environ.get("COMPANERO_CODEX_PRUEBA") != "1":
        return False
    else:
        carpeta = os.path.basename(os.path.normpath(cwd or "")) or "Codex"
        # ids UUIDv7: los primeros 8 hex son la hora (hilos del mismo minuto chocan); el final es aleatorio
        x[sid] = ["cx" + sid.replace("-", "")[-8:], f"Codex · {titulo or carpeta}", ""]
    tmp = EXTRA + ".tmp"
    json.dump(x, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, EXTRA)
    return True


def correr(modulo, datos):
    """Ejecuta main() del script de Kodama con `datos` como stdin (mismo formato que Claude Code)."""
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(datos, ensure_ascii=False).encode("utf-8")), encoding="utf-8")
    __import__(modulo).main()


def main():
    # notify: el JSON llega como ultimo argumento
    if len(sys.argv) > 1 and sys.argv[-1].lstrip().startswith("{"):
        try:
            n = json.loads(sys.argv[-1])
        except ValueError:
            return
        if n.get("type") != "agent-turn-complete":
            return
        sid, cwd = str(n.get("thread-id") or ""), n.get("cwd") or ""
        if not sid or not anotar(sid, cwd):
            return
        correr("companero_hook", {"hook_event_name": "Stop", "session_id": sid, "cwd": cwd, "agente": "codex",
                                  "last_assistant_message": n.get("last-assistant-message") or ""})
        return
    # hooks (stdin)
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    sid, ev = str(d.get("session_id") or ""), d.get("hook_event_name") or ""
    if not sid or not anotar(sid, d.get("cwd"), d.get("transcript_path")):
        return
    d["agente"] = "codex"
    if ev == "PermissionRequest":
        correr("companero_permiso", d)
    elif ev == "Stop":
        # (20-oct) `notify` de config.toml ya lo usa el plugin de computer-use de Codex: no se toca y el "terminó" sale
        # del hook Stop. Si no trae el ultimo mensaje, se busca en el transcript (formato no estable: si falla, generico)
        if not d.get("last_assistant_message"):
            d["last_assistant_message"] = ultimo_mensaje(d.get("transcript_path")) or "Codex terminó su turno."
        correr("companero_hook", d)
    elif ev in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
        correr("companero_hook", d)


def ultimo_mensaje(ruta):
    """Ultimo mensaje del asistente en el transcript de Codex (JSONL). None si no se puede leer."""
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
        p = x.get("payload") or x
        if p.get("type") == "agent_message" and p.get("message"):
            return str(p["message"])
        if p.get("type") == "message" and p.get("role") == "assistant":
            t = "".join(c.get("text", "") for c in (p.get("content") or []) if isinstance(c, dict))
            if t:
                return t
    return None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
