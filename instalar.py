# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Instalador del Companero para Windows (14-oct-2026, paso 2 hacia el uso masivo).

    python instalar.py --prueba     -> muestra TODO lo que haria, sin tocar nada (empezar siempre por aca)
    python instalar.py              -> instala / repara (se puede correr de nuevo sin romper nada)
    python instalar.py --quitar     -> saca hooks, statusLine y tarea programada; tus datos quedan en estado\\
    python instalar.py --quitar --borrar-datos  -> ademas borra estado\\, respaldos\\ y ts\\ (pide confirmacion)

Que hace, en orden:
 1. Revisa Python (3.10+) y la app de Claude (MSIX) y avisa si falta algo.
 2. Crea .venv e instala requirements.txt (pywebpush) — descarga de PyPI, la pregunta antes.
 3. Crea estado\\ con: clave local (local.key), claves VAPID para avisos al celular, config.json si no existe.
 4. Agrega al ~\\.claude\\settings.json (respaldo antes, une sin pisar lo tuyo): los hooks del Companero
    (SessionStart, UserPromptSubmit, Notification, Stop + puente, SessionEnd, PostToolUse) y la statusLine de uso.
 5. Crea la tarea programada "Companero" (al iniciar sesion y cada 10 min) que corre arrancar.pyw.
 6. (21-oct) La mascota (Tauri) ya viene compilada en el paquete; 7. hooks de Codex y Antigravity si estan instalados.
 Flags (21-oct, para que lo corra el Claude de la persona): --acepto (licencia aceptada en el chat), --si (descargas).
 Lo normal es llegar aca desde instalar.ps1 (la linea de una sola orden del README publico), que baja el paquete,
 comprueba su sha256 y lo deja en estado\\instalacion\\ para que aca se verifique la firma.
Telegram y Tailscale los configuras vos (el instalador te dice como); sin ellos el Companero anda solo en la PC.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import config  # noqa: E402

PRUEBA = "--prueba" in sys.argv
QUITAR = "--quitar" in sys.argv
ACEPTO = "--acepto" in sys.argv   # (21-oct) la persona acepto la licencia en el chat con su Claude
SI = "--si" in sys.argv           # (21-oct) responde "sí" a las descargas (sin consola interactiva)
PYV = os.path.join(AQUI, ".venv", "Scripts", "python.exe")
CODEX_HOOKS = os.path.join(config.HOME, ".codex", "hooks.json")
GEMINI_HOOKS = os.path.join(config.HOME, ".gemini", "config", "hooks.json")
SETTINGS = os.path.join(config.HOME, ".claude", "settings.json")
PY = sys.executable
PYW = os.path.join(os.path.dirname(PY), "pythonw.exe")
TAREA = "Companero"
NUESTROS = ("companero_hook.py", "companero_puente.py", "companero_uso.py", "companero_permiso.py")


def paso(txt):
    print(("[PRUEBA] " if PRUEBA else "") + txt)


def hacer(desc, fn):
    paso(desc)
    if not PRUEBA:
        fn()


def preguntar(txt):
    if PRUEBA:
        paso(txt + " -> (en prueba: no)")
        return False
    if SI:   # (21-oct) lo corre el Claude de la persona, que ya le pregunto en el chat
        paso(txt + " -> sí (--si)")
        return True
    return input(txt + " [s/N] ").strip().lower() in ("s", "si", "sí", "y")


def cmd_hook(script, *args):
    """(21-oct) con el Python del .venv del Companero (no depende de que "python" este en el PATH de la persona)."""
    extra = "".join(" " + a for a in args)
    return f'"{PYV}" "{os.path.join(AQUI, script)}"{extra}'.replace("\\", "/")


def hooks_nuestros():
    h = lambda s, **kw: {"hooks": [dict({"type": "command", "command": cmd_hook(s), "timeout": 10}, **kw)]}
    return {
        "SessionStart": [h("companero_hook.py", **{"async": True})],
        "UserPromptSubmit": [h("companero_hook.py", **{"async": True})],
        "Notification": [h("companero_hook.py", **{"async": True})],
        "Stop": [h("companero_hook.py", **{"async": True}), h("companero_puente.py", timeout=1900)],   # (21-oct) espera adaptable del puente: hasta 30 min
        "SessionEnd": [h("companero_hook.py", **{"async": True})],
        "PermissionRequest": [h("companero_permiso.py", timeout=130)],
        # (21-oct) preguntas con opciones respondidas desde el celular (como en la PC de LShinox)
        "PreToolUse": [dict(h("companero_permiso.py", timeout=130), matcher="AskUserQuestion")],
        "PostToolUse": [h("companero_hook.py", **{"async": True})],
    }


def es_nuestro(entrada):
    return any(any(n in (x.get("command") or "") for n in NUESTROS) for x in entrada.get("hooks", []))


def tocar_settings(poner):
    """Une (o saca) nuestros hooks y la statusLine en settings.json sin tocar nada mas. Respaldo antes."""
    try:
        d = json.load(open(SETTINGS, encoding="utf-8"))
    except FileNotFoundError:
        d = {}
    hooks = d.setdefault("hooks", {})
    for ev in list(hooks):
        hooks[ev] = [e for e in hooks[ev] if not es_nuestro(e)]   # primero sacar lo nuestro (idempotente)
        if not hooks[ev]:
            hooks.pop(ev)
    if poner:
        for ev, entradas in hooks_nuestros().items():
            hooks.setdefault(ev, []).extend(entradas)
        sl = d.get("statusLine")
        if sl and "companero_uso.py" not in json.dumps(sl):
            paso("  ojo: ya tenes una statusLine propia; no la piso (el medidor de uso queda apagado)")
        else:
            d["statusLine"] = {"type": "command", "command": cmd_hook("companero_uso.py")}
    elif "companero_uso.py" in json.dumps(d.get("statusLine") or {}):
        d.pop("statusLine")
    if not hooks:
        d.pop("hooks", None)
    paso(f"  settings.json: eventos con hooks del Companero -> {sorted(hooks_nuestros()) if poner else 'ninguno'}")
    if PRUEBA:
        return
    if os.path.exists(SETTINGS):
        shutil.copy2(SETTINGS, SETTINGS + time.strftime(".bak-companero-%Y%m%d-%H%M%S"))
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    tmp = SETTINGS + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.load(open(tmp, encoding="utf-8"))          # que quede JSON valido antes de reemplazar
    os.replace(tmp, SETTINGS)


def claves():
    os.makedirs(config.ESTADO, exist_ok=True)
    k = os.path.join(config.ESTADO, "local.key")
    if not os.path.exists(k):
        hacer("  clave local nueva (estado\\local.key)", lambda: open(k, "w").write(secrets.token_urlsafe(32)))
    priv, pub = os.path.join(config.ESTADO, "vapid_private.pem"), os.path.join(config.ESTADO, "vapid_public.txt")
    if not os.path.exists(priv):
        def gen():   # con el Python de .venv (ahi esta py_vapid, que viene con pywebpush)
            codigo = ("import sys\nfrom py_vapid import Vapid01, b64urlencode\n"
                      "from cryptography.hazmat.primitives import serialization as s\n"
                      "v = Vapid01(); v.generate_keys(); v.save_key(sys.argv[1])\n"
                      "open(sys.argv[2], 'w').write(b64urlencode(v.public_key.public_bytes(s.Encoding.X962, s.PublicFormat.UncompressedPoint)))\n")
            subprocess.run([os.path.join(AQUI, ".venv", "Scripts", "python.exe"), "-c", codigo, priv, pub], check=True)
        hacer("  claves VAPID nuevas para los avisos del celular", gen)
    cfg = os.path.join(AQUI, "config.json")
    if not os.path.exists(cfg):
        hacer("  config.json de ejemplo (sin chats fijos: se eligen desde los grupos de la app de Claude)",
              lambda: json.dump({"url_publica": "", "token_telegram": "", "chats": [], "colores": {}, "escritorio": "tauri"},
                                open(cfg, "w", encoding="utf-8"), indent=2))


def tarea(poner):
    subprocess.run(["schtasks", "/Delete", "/TN", TAREA, "/F"], capture_output=True) if not PRUEBA else None
    if not poner:
        paso(f'  tarea programada "{TAREA}" quitada')
        return
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled><Repetition><Interval>PT10M</Interval></Repetition></LogonTrigger></Triggers>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT5M</ExecutionTimeLimit><Enabled>true</Enabled></Settings>
  <Actions><Exec><Command>{PYW}</Command><Arguments>"{os.path.join(AQUI, 'arrancar.pyw')}"</Arguments><WorkingDirectory>{AQUI}</WorkingDirectory></Exec></Actions>
</Task>"""
    def crear():
        x = os.path.join(config.ESTADO, "tarea.xml")
        open(x, "w", encoding="utf-16").write(xml)
        r = subprocess.run(["schtasks", "/Create", "/TN", TAREA, "/XML", x, "/F"], capture_output=True, text=True)
        os.remove(x)
        if r.returncode:
            raise SystemExit("No pude crear la tarea programada: " + (r.stderr or r.stdout).strip())
    hacer(f'  tarea programada "{TAREA}": al iniciar sesion y cada 10 min -> arrancar.pyw', crear)


def _respaldo(ruta):
    if os.path.exists(ruta) and not PRUEBA:
        shutil.copy2(ruta, ruta + time.strftime(".bak-companero-%Y%m%d-%H%M%S"))


def otros_agentes(poner):
    """(21-oct) Codex y Antigravity, solo si estan instalados (existe su carpeta). Respaldo antes; solo lo nuestro."""
    if os.path.isdir(os.path.dirname(CODEX_HOOKS)):
        try:
            d = json.load(open(CODEX_HOOKS, encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        hooks = d.setdefault("hooks", {})
        for ev in list(hooks):
            hooks[ev] = [e for e in hooks[ev] if "companero_codex.py" not in json.dumps(e)]
            if not hooks[ev]:
                hooks.pop(ev)
        if poner:
            for ev, t in (("SessionStart", 10), ("UserPromptSubmit", 10), ("Stop", 15), ("PermissionRequest", 130)):
                hooks.setdefault(ev, []).append({"hooks": [{"type": "command", "command": cmd_hook("companero_codex.py"), "timeout": t}]})
        paso(f"  Codex: hooks de Kodama {'puestos' if poner else 'quitados'} en ~\\.codex\\hooks.json"
             + (" (actívalos una vez dentro de Codex con /hooks)" if poner else ""))
        if not PRUEBA:
            _respaldo(CODEX_HOOKS)
            json.dump(d, open(CODEX_HOOKS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir(os.path.dirname(os.path.dirname(GEMINI_HOOKS))):
        try:
            d = json.load(open(GEMINI_HOOKS, encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d.pop("companero", None)
        if poner:
            if " " in AQUI:
                paso("  Antigravity: NO se conecta (su formato de hooks no admite carpetas con espacios en la ruta)")
            else:   # Antigravity corre el comando sin shell: SIN comillas (gotcha del 20-oct)
                c = lambda ev, t: [{"type": "command", "command": cmd_hook("companero_antigravity.py", ev).replace('"', ""), "timeout": t}]
                d["companero"] = {"SessionStart": c("SessionStart", 10), "PreInvocation": c("PreInvocation", 10), "Stop": c("Stop", 15)}
        paso(f"  Antigravity: hook \"companero\" {'puesto' if poner and 'companero' in d else 'quitado'} en ~\\.gemini\\config\\hooks.json")
        if not PRUEBA:
            _respaldo(GEMINI_HOOKS)
            os.makedirs(os.path.dirname(GEMINI_HOOKS), exist_ok=True)
            json.dump(d, open(GEMINI_HOOKS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def verificar_paquete():
    """(21-oct) Si el instalador de una linea dejo el zip y su .json en estado\\instalacion\\, se comprueba la firma
    con el Python del .venv (ahi esta cryptography). Si no pasa, se corta ANTES de tocar la configuracion de Claude."""
    carpeta = os.path.join(config.ESTADO, "instalacion")
    zips = [f for f in os.listdir(carpeta) if f.endswith(".zip")] if os.path.isdir(carpeta) else []
    if not zips:
        paso("  (sin paquete descargado que verificar: instalación desde una carpeta copiada a mano)")
        return
    z = os.path.join(carpeta, sorted(zips)[-1])
    codigo = ("import json,sys\nsys.path.insert(0, sys.argv[1])\nimport companero_actualizar as ca\n"
              "print('OK' if ca.verificar(sys.argv[2], json.load(open(sys.argv[3], encoding='utf-8'))) else 'MAL')")
    r = subprocess.run([PYV, "-c", codigo, AQUI, z, z[:-4] + ".json"], capture_output=True, text=True)
    if "OK" not in r.stdout:
        raise SystemExit("La firma del paquete NO es válida: no se instala nada. Bájalo de nuevo desde el repo oficial.")
    paso("  firma del paquete verificada")


def instalar():
    print("Kodama — instalación" + (" (PRUEBA: no se toca nada)" if PRUEBA else ""))
    if ACEPTO:
        paso("Licencia aceptada (--acepto)")
    else:
        print("\n" + open(os.path.join(AQUI, "LICENCIA.txt"), encoding="utf-8").read())
        if not PRUEBA and input("¿Aceptas la licencia? escribe ACEPTO: ").strip().upper() != "ACEPTO":
            raise SystemExit("Instalación cancelada: no se tocó nada.")
    if sys.version_info < (3, 10):
        raise SystemExit("Hace falta Python 3.10 o más nuevo.")
    paso(f"1. Python {sys.version.split()[0]} OK · app de Claude: {config.dir_app_claude()}"
         + ("" if os.path.isdir(config.dir_app_claude()) else "  (NO ENCONTRADA: los grupos de la app no van a andar)"))
    venv = os.path.join(AQUI, ".venv")
    if not os.path.exists(os.path.join(venv, "Scripts", "python.exe")):
        if preguntar("2. ¿Crear .venv e instalar pywebpush (descarga ~5 MB de PyPI)?"):
            subprocess.run([PY, "-m", "venv", venv], check=True)
            subprocess.run([os.path.join(venv, "Scripts", "python.exe"), "-m", "pip", "install", "-r",
                            os.path.join(AQUI, "requirements.txt")], check=True)
    else:
        paso("2. .venv ya existe")
    if not PRUEBA and not os.path.exists(PYV):
        raise SystemExit("Sin .venv no se puede seguir (los avisos usan ese Python). No se tocó la configuración de Claude.")
    verificar_paquete() if not PRUEBA else paso("  (prueba: no se verifica la firma)")
    paso("3. Claves y configuración")
    claves()
    paso("4. Hooks y medidor de uso en ~\\.claude\\settings.json")
    tocar_settings(True)
    paso("5. Arranque automático")
    tarea(True)
    # (21-oct) la mascota ya viene compilada (Tauri) en el paquete: no se descarga nada
    tauri = os.path.join(AQUI, "escritorio-tauri", "src-tauri", "target", "release", "companero.exe")
    paso("6. Mascota de escritorio: " + ("incluida" if os.path.exists(tauri) else "NO viene en esta copia (solo celular/Telegram)"))
    if "--solo-claude" in sys.argv:
        paso("7. Codex y Antigravity: no (--solo-claude)")
    else:
        paso("7. Codex y Antigravity (si los tienes)")
        otros_agentes(True)
    if not PRUEBA:
        subprocess.Popen([os.path.join(AQUI, ".venv", "Scripts", "pythonw.exe"), os.path.join(AQUI, "arrancar.pyw")], cwd=AQUI,
                         creationflags=0x00000008, close_fds=True)   # que aparezca ya, sin esperar los 10 min de la tarea
    print("\nListo. Falta (opcional, a mano):\n"
          " - Telegram: crea un bot con @BotFather, guarda el token en un archivo y pone su ruta en config.json\n"
          " - Celular: Tailscale en la PC y en el celular con la misma cuenta; `tailscale serve` del puerto 8787;\n"
          "   pone esa direccion en config.json (url_publica) y abri la app del celular desde ahi\n"
          " - Chats fijos: agregalos en config.json (\"chats\") o elegí un grupo de la app de Claude desde la mascota\n"
          "Los hooks rigen en los chats que abras desde ahora.")


def revisar():
    """(22-oct, mejora 5, idea de Perch/Nudge) ¿siguen puestos nuestros hooks? Solo lee. Para Ajustes > Revisar."""
    try:
        d = json.load(open(SETTINGS, encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    hooks, out = d.get("hooks") or {}, []
    for ev in hooks_nuestros():
        out.append({"que": ev, "ok": any(es_nuestro(e) for e in hooks.get(ev, []))})
    ajenos = sum(1 for ev in hooks.values() for e in ev if not es_nuestro(e))
    if os.path.exists(CODEX_HOOKS):
        try:
            cx = json.dumps(json.load(open(CODEX_HOOKS, encoding="utf-8")))
        except (OSError, ValueError):
            cx = ""
        out.append({"que": "Codex", "ok": "companero_codex.py" in cx})
    return {"ok": all(x["ok"] for x in out), "items": out, "ajenos": ajenos}


def restaurar_original():
    """(22-oct, mejora 5) settings.json exactamente como estaba ANTES de instalar: el respaldo .bak-companero mas viejo.
    Lo de ahora queda en .bak-antes-de-restaurar por si acaso."""
    import glob as _g
    baks = sorted(_g.glob(SETTINGS + ".bak-companero-*"))
    if not baks:
        paso("  no hay respaldo de antes de instalar: se quitan solo los hooks de Kodama")
        return False
    paso(f"  settings.json vuelve a {os.path.basename(baks[0])}")
    if not PRUEBA:
        shutil.copy2(SETTINGS, SETTINGS + time.strftime(".bak-antes-de-restaurar-%Y%m%d-%H%M%S"))
        shutil.copy2(baks[0], SETTINGS)
    return True


def quitar():
    print("Kodama — desinstalación" + (" (PRUEBA)" if PRUEBA else ""))
    if not ("--restaurar" in sys.argv and restaurar_original()):
        tocar_settings(False)
    tarea(False)
    otros_agentes(False)
    paso("  la mascota de escritorio y el hub se cierran solos al reiniciar la PC (o cerralos desde la bandeja)")
    if "--borrar-datos" in sys.argv and (PRUEBA or input("¿Borrar estado\\, respaldos\\ y ts\\ (no se puede deshacer)? escribe BORRAR: ") == "BORRAR"):
        for d in (config.ESTADO, config.RESPALDOS, config.TS_DIR):
            hacer(f"  borrar {d}", lambda d=d: shutil.rmtree(d, ignore_errors=True))
    else:
        paso("  tus datos quedan en estado\\ y respaldos\\ (para borrarlos: --quitar --borrar-datos)")


if __name__ == "__main__":
    if "--revisar" in sys.argv:            # (22-oct) Ajustes > Revisar: JSON, sin tocar nada
        print(json.dumps(revisar(), ensure_ascii=False))
    elif "--arreglar-hooks" in sys.argv:   # (22-oct) Ajustes > Arreglar: vuelve a poner SOLO nuestros hooks (con respaldo)
        tocar_settings(True); otros_agentes(True)
    else:
        quitar() if QUITAR else instalar()
