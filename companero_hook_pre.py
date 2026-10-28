# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Hook LIGERO de PreToolUse (27-oct-2026, idea de clawd #1018: "pensando" vs "ejecutando").

Se registra con `python -I -S` y SIN importar json ni config: arrancar el interprete ya cuesta ~60 ms en esta PC y cada import suma
(json ~30 ms), y este hook corre antes de cada herramienta larga. Solo marca "ejecutando" + la categoria de la herramienta
(comando / web / subagente / herramienta) en estado\\fase\\<sesion>.txt ("fase|categoria|ts"); companero_hook.py lo vuelve a "pensando"
en PostToolUse y lo borra en Stop. Nunca escribe nada a la salida ni toma decisiones: siempre termina con codigo 0.
El hub solo lo lee de los chats que muestra (los demas quedan en un archivito sin contenido que el mantenimiento borra al dia).
"""
import os
import sys
import time

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado", "fase")


def valor(s, clave):
    """Primer "clave": "valor" del JSON (el hook de Claude Code trae session_id y tool_name antes de tool_input). Sin json."""
    i = s.find('"' + clave + '"')
    if i < 0:
        return ""
    i = s.find(":", i + len(clave) + 2)
    if i < 0:
        return ""
    i += 1
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    if i >= len(s) or s[i] != '"':
        return ""
    j = s.find('"', i + 1)
    return s[i + 1:j] if j > i else ""


def categoria(tool):
    if tool in ("Bash", "PowerShell"):
        return "comando"
    if tool in ("WebFetch", "WebSearch"):
        return "web"
    if tool in ("Agent", "Task"):
        return "subagente"
    if tool.startswith("mcp__"):
        srv = tool.split("__")[1].lower() if tool.count("__") >= 2 else ""
        return "web" if any(x in srv for x in ("browser", "chrome", "playwright", "puppeteer")) else "herramienta"
    return ""


def main():
    try:
        s = sys.stdin.buffer.read(65536).decode("utf-8", "replace")   # los dos campos vienen al principio
        sid, tool = valor(s, "session_id"), valor(s, "tool_name")
        cat = categoria(tool)
        if not cat or not sid or len(sid) > 80 or not sid.replace("-", "").replace("_", "").isalnum():
            return
        os.makedirs(BASE, exist_ok=True)
        with open(os.path.join(BASE, sid + ".txt"), "w", encoding="utf-8") as f:
            f.write("ejecutando|%s|%.2f" % (cat, time.time()))
    except Exception:
        pass


if __name__ == "__main__":
    main()
