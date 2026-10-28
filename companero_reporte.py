# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(21-oct-2026) "Reportar un problema": arma un .zip con lo que hace falta para diagnosticar (versiones, salud,
procesos, que hooks hay instalados y el final de los registros, con claves y rutas personales tapadas) y abre el
formulario de "issue" del repo de GitHub con el resumen ya escrito. El .zip queda en el Escritorio para que la
persona lo REVISE y lo arrastre al issue (GitHub no deja adjuntar por enlace).

No manda nada solo: todo sale de la PC cuando la persona publica el issue.
No incluye: clave local, tokens, suscripciones del celular, mensajes de los chats, fotos, estado de Tailscale.
"""
import json
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

BASE = config.ESTADO
LOGS = [("hub.log", 400), ("arrancar.log", 120), ("antigravity_hook.log", 60), ("actualizar.log", 120)]
# config.json: se quitan los campos que pueden llevar datos personales o secretos
CONF_FUERA = ("token_telegram", "nombres", "url_publica", "chats", "raices_personales", "excluir_carpetas")


def _vivo(pidfile, texto):
    try:
        pid = int(open(os.path.join(BASE, pidfile)).read().strip())
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                             capture_output=True, text=True, timeout=20, creationflags=0x08000000).stdout
        return "si" if texto in out else "no"
    except Exception:
        return "?"


def _hooks():
    """Que eventos tienen el hook del Companero en ~/.claude/settings.json, y si hay hooks de Codex y Antigravity."""
    r = {}
    try:
        s = json.load(open(os.path.join(config.HOME, ".claude", "settings.json"), encoding="utf-8"))
        for ev, grupos in (s.get("hooks") or {}).items():
            if any("companero" in (h.get("command") or "") for g in grupos for h in g.get("hooks") or []):
                r[ev] = "si"
    except (OSError, ValueError, AttributeError):
        r["error"] = "no pude leer settings.json"
    r["codex"] = "si" if os.path.exists(os.path.join(config.HOME, ".codex", "hooks.json")) else "no"
    r["antigravity"] = "si" if os.path.exists(os.path.join(config.HOME, ".gemini", "config", "hooks.json")) else "no"
    return r


def _app_claude():
    try:   # WindowsApps no se puede listar sin permisos de administrador: se pregunta a Windows por el paquete
        return subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-AppxPackage -Name Claude).Version"],
                              capture_output=True, text=True, timeout=20, creationflags=0x08000000).stdout.strip() or "?"
    except Exception:
        return "?"


def resumen(salud):
    return {
        "companero": config.VERSION,
        "windows": platform.platform(),
        "python": platform.python_version(),
        "app_claude": _app_claude(),
        "hub_vivo": _vivo("hub.pid", "companero_hub.py"),
        "mascota_viva": _vivo("escritorio.pid", "companero"),
        "salud": [t for _, t in salud] or ["sin problemas detectados"],
        "hooks": _hooks(),
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }


def armar(salud, redactar):
    """Crea el .zip en el Escritorio. Devuelve (ruta, resumen)."""
    r = resumen(salud)
    escritorio = os.path.join(config.HOME, "Desktop")
    if not os.path.isdir(escritorio):
        escritorio = config.HOME
    ruta = os.path.join(escritorio, f"Companero-reporte-{time.strftime('%Y%m%d-%H%M')}.zip")
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("resumen.json", json.dumps(r, ensure_ascii=False, indent=1))
        for nombre, n in LOGS:
            p = os.path.join(BASE, nombre)
            if os.path.exists(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    z.writestr(nombre, redactar("".join(f.readlines()[-n:])))
        try:
            c = json.load(open(os.path.join(config.APP_DIR, "config.json"), encoding="utf-8-sig"))
            z.writestr("config.json", json.dumps({k: v for k, v in c.items() if k not in CONF_FUERA}, ensure_ascii=False, indent=1))
        except (OSError, ValueError):
            pass
        z.writestr("LEEME.txt", "Revisa este archivo antes de subirlo: lleva el final de los registros del Companero con "
                                "claves y rutas tapadas. No lleva tus mensajes ni tus claves.\n")
    return ruta, r


def url_issue(r, archivo):
    cuerpo = (
        "**Qué pasó** (cuéntalo con tus palabras):\n\n\n"
        "**Qué esperabas que pasara:**\n\n\n"
        f"**Adjunta el archivo** `{os.path.basename(archivo)}` que quedó en tu Escritorio (arrástralo aquí).\n\n"
        "---\n"
        f"- Kodama {r['companero']} · app de Claude {r['app_claude']} · {r['windows']} · Python {r['python']}\n"
        f"- Hub vivo: {r['hub_vivo']} · mascota viva: {r['mascota_viva']}\n"
        f"- Salud: {'; '.join(r['salud'])[:600]}\n"
    )
    q = urllib.parse.urlencode({"title": f"[{r['companero']}] ", "body": cuerpo})
    return f"https://github.com/{config.REPO}/issues/new?{q}"


def reportar(salud, redactar):
    """Arma el .zip, lo muestra en el Explorador y abre el formulario del issue. Devuelve la ruta del .zip."""
    ruta, r = armar(salud, redactar)
    subprocess.Popen(["explorer", "/select,", ruta])
    os.startfile(url_issue(r, ruta))
    return ruta
