# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Paso 0 del companero (13-oct-2026): SOLO registra que llega por hooks desde
los 3 chats personales (Juegos, Musica, D&D). No decide nada, no manda nada
afuera. Log: paso0/eventos.jsonl (dentro de la carpeta del programa)

En PermissionRequest espera 10 s antes de salir (sin decidir), para ver si el
dialogo de permiso de la app aparece igual mientras el hook espera.
"""
import json
import os
import sys
import time
from datetime import datetime

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paso0", "eventos.jsonl").replace("\\", "/")
ESPERA_PERMISO = 0  # 13-oct: los 3 chats corren sin permisos (bypass); no hace falta medirlo


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    ev = d.get("hook_event_name", "?")
    reg = {
        "ts": ahora(),
        "evento": ev,
        "session_id": d.get("session_id"),
        "cwd": d.get("cwd"),
        "proyecto": os.path.basename(os.path.dirname(d.get("transcript_path") or "")),
        "claves": sorted(d.keys()),
        "session_title": d.get("session_title"),
        "entrypoint": os.environ.get("CLAUDE_CODE_ENTRYPOINT"),
        "messaging_socket": os.environ.get("CLAUDE_CODE_MESSAGING_SOCKET"),
        "host_session_id": os.environ.get("CLAUDE_CODE_HOST_SESSION_ID"),
        "desktop_version": os.environ.get("CLAUDE_CODE_DESKTOP_APP_VERSION"),
        "env_claude": sorted(k for k in os.environ if k.upper().startswith(("CLAUDE", "ANTHROPIC"))
                             and not any(s in k.upper() for s in ("TOKEN", "KEY", "SECRET"))),
    }
    if ev == "PermissionRequest":
        reg["tool_name"] = d.get("tool_name")
    if ev == "Notification":
        reg["notification_type"] = d.get("notification_type")
        reg["mensaje"] = (d.get("message") or "")[:200]
    if ev == "UserPromptSubmit":
        reg["largo_prompt"] = len(d.get("prompt") or "")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    if ev == "PermissionRequest":
        time.sleep(ESPERA_PERMISO)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ahora(), "evento": "PermissionRequest-fin-espera",
                                "session_id": d.get("session_id")}) + "\n")


if __name__ == "__main__":
    main()
