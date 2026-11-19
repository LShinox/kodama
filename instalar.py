# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Instalador de Kodama para Windows y macOS (14-oct-2026, paso 2 hacia el uso masivo; macOS: Mac-F3, 28-oct-2026).

    python instalar.py --prueba     -> muestra TODO lo que haria, sin tocar nada (empezar siempre por aca)
    python instalar.py              -> instala / repara (se puede correr de nuevo sin romper nada)
    python instalar.py --quitar     -> saca hooks, statusLine y tarea programada; tus datos quedan en estado\\
    python instalar.py --quitar --borrar-datos  -> ademas borra estado\\, respaldos\\ y ts\\ (pide confirmacion)

Que hace, en orden:
 1. Revisa Python (3.10+) y la app de Claude (MSIX) y avisa si falta algo.
 2. Crea .venv e instala requirements.txt (pywebpush) — descarga de PyPI, la pregunta antes.
 3. Crea estado\\ con: clave local (local.key), claves VAPID para avisos al celular, config.json si no existe.
 4. Agrega al ~\\.claude\\settings.json (respaldo antes, une sin pisar lo tuyo): los hooks de Kodama
    (SessionStart, UserPromptSubmit, Notification, Stop + puente, SessionEnd, PostToolUse) y la statusLine de uso.
    (28-oct) Si ya tenias una statusLine, se guarda en config.json y Kodama la sigue corriendo: tu barra se ve igual
    y el uso exacto del plan llega a la mascota y al celular. Al desinstalar vuelve la tuya.
 5. Crea la tarea programada "Kodama" (al iniciar sesion y cada 10 min) que corre arrancar.pyw.
 6. (21-oct) La mascota (Tauri) ya viene compilada en el paquete; 7. hooks de Codex y Antigravity si estan instalados.
 Flags (21-oct, para que lo corra el Claude de la persona): --acepto (licencia aceptada en el chat), --si (descargas).
 Lo normal es llegar aca desde instalar.ps1 (la linea de una sola orden del README publico), que baja el paquete,
 comprueba su sha256 y lo deja en estado\\instalacion\\ para que aca se verifique la firma.
macOS (beta): lo normal es llegar desde instalar.sh (la linea `curl ... | bash` del README), que baja kodama-X-macos.zip,
comprueba su sha256, crea el .venv (.venv/bin/python) y corre este archivo. Aca cambian solo: el venv, el "arranque
automatico" (un LaunchAgent, ~/Library/LaunchAgents/app.kodama.plist, en vez de la tarea programada) y que los datos quedan
en ~/Kodama/estado (igual que en Windows). Flag solo para pruebas: --sin-launchctl (escribe/borra el plist pero NO llama a
launchctl ni lanza nada). --quitar en macOS: hooks, statusLine, Codex/Antigravity, launchctl bootout y borra el plist.
Telegram y Tailscale los configuras vos (el instalador te dice como); sin ellos Kodama anda solo en la PC.
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
import kodama_plataforma as plataforma  # noqa: E402

PRUEBA = "--prueba" in sys.argv
QUITAR = "--quitar" in sys.argv
ACEPTO = "--acepto" in sys.argv   # (21-oct) la persona acepto la licencia en el chat con su Claude
SI = "--si" in sys.argv           # (21-oct) responde "sí" a las descargas (sin consola interactiva)
SIN_LAUNCHCTL = "--sin-launchctl" in sys.argv   # (Mac-F3) SOLO pruebas: en macOS no llama a launchctl ni lanza nada
MAC = sys.platform == "darwin"
PYV = plataforma.python_del_venv(AQUI) if sys.platform in ("win32", "darwin") else ""   # Windows: .venv\Scripts\python.exe; macOS: .venv/bin/python
CODEX_HOOKS = os.path.join(config.HOME, ".codex", "hooks.json")
GEMINI_HOOKS = os.path.join(config.HOME, ".gemini", "config", "hooks.json")
OPENCODE_PLUGIN = os.path.join(config.HOME, ".config", "opencode", "plugins", "kodama.js")   # (04-nov) plugin de OpenCode
SETTINGS = os.path.join(config.HOME, ".claude", "settings.json")
CONFIG_JSON = os.path.join(AQUI, "config.json")
PY = sys.executable
PYW = os.path.join(os.path.dirname(PY), "pythonw.exe")
TAREA = "Kodama"
TAREA_VIEJA = "Companero"   # (28-oct) nombre anterior de la tarea: se borra al instalar/quitar para no dejar dos
NUESTROS = ("companero_hook.py", "companero_puente.py", "companero_uso.py", "companero_permiso.py", "companero_hook_pre.py")


def paso(txt):
    if MAC:   # (Mac-F3) los mensajes estan escritos con rutas de Windows (estado\, ~\.claude\...): en macOS, con /
        txt = txt.replace("\\", "/")
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
    """(21-oct) con el Python del .venv de Kodama (no depende de que "python" este en el PATH de la persona)."""
    extra = "".join(" " + a for a in args)
    return f'"{PYV}" "{os.path.join(AQUI, script)}"{extra}'.replace("\\", "/")


def cmd_hook_ligero(script):
    """(04-nov) como cmd_hook, para los hooks livianos: el Python arranca con -I -S (ver companero_hook_pre.py)."""
    return f'"{PYV}" -I -S "{os.path.join(AQUI, script)}"'.replace("\\", "/")


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
        "PreToolUse": [dict(h("companero_permiso.py", timeout=130), matcher="AskUserQuestion"),
                       {"matcher": "Bash|PowerShell|WebFetch|WebSearch|Agent|Task|mcp__.*",
                        "hooks": [{"type": "command", "command": cmd_hook_ligero("companero_hook_pre.py"), "timeout": 10}]}],
        "PostToolUse": [h("companero_hook.py", **{"async": True})],
    }


def es_nuestro(entrada):
    return any(any(n in (x.get("command") or "") for n in NUESTROS) for x in entrada.get("hooks", []))


def guardar_previa(valor):
    """(28-oct) statusLine que la persona ya tenia: se guarda en config.json ("statusline_previa") para que companero_uso.py
    la siga corriendo y para devolverla al desinstalar. valor=None borra la clave. No hace nada en --prueba."""
    if PRUEBA:
        return
    try:
        c = json.load(open(CONFIG_JSON, encoding="utf-8-sig"))
    except FileNotFoundError:
        c = {}
    except ValueError:
        paso("  ojo: config.json no se pudo leer; no guardo tu statusLine anterior (queda en el respaldo de settings.json)")
        return
    if valor is None:
        if "statusline_previa" not in c:
            return
        c.pop("statusline_previa")
    else:
        c["statusline_previa"] = valor
    tmp = CONFIG_JSON + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_JSON)


def previa_guardada():
    try:
        v = json.load(open(CONFIG_JSON, encoding="utf-8-sig")).get("statusline_previa")
        return v if isinstance(v, dict) and v.get("command") else None
    except (OSError, ValueError, AttributeError):
        return None


def tocar_settings(poner, settings=None):
    """Une (o saca) nuestros hooks y la statusLine en settings.json sin tocar nada mas. Respaldo antes.
    (04-nov) `settings` es el settings.json de una carpeta de Claude Code (ver config.dirs_claude); None = el de la por
    defecto, leido AL LLAMAR (no al importar: asi las pruebas que cambian SETTINGS lo ven). La statusLine y su previa
    (config.json) solo se manejan en la carpeta por defecto."""
    if settings is None:
        settings = SETTINGS
    principal = settings == SETTINGS
    if not poner and not os.path.exists(settings):   # (07-nov) quitar sin archivo: no crea el settings.json ni su carpeta
        return
    try:
        d = json.load(open(settings, encoding="utf-8"))
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
        if principal:
            sl = d.get("statusLine")
            mia = {"type": "command", "command": cmd_hook("companero_uso.py")}
            if not sl:
                d["statusLine"] = mia
            elif "companero_uso.py" in json.dumps(sl):   # ya es la nuestra (reinstalar): se deja igual, con lo que traiga de su previa
                previa = previa_guardada()
                d["statusLine"] = dict({k: v for k, v in (previa or {}).items() if k != "command"}, **mia)
            elif isinstance(sl, dict) and sl.get("type") == "command" and isinstance(sl.get("command"), str) and sl["command"].strip():
                # (28-oct) ya tiene la suya: se guarda en config.json y companero_uso.py la corre despues de anotar el uso
                guardar_previa(sl)
                d["statusLine"] = dict({k: v for k, v in sl.items() if k != "command"}, **mia)
                paso("  tu statusLine anterior se conserva: Kodama anota el uso y despues corre tu comando (la barra se ve igual)")
            else:
                paso("  ojo: tu statusLine no es de tipo comando; no la piso (el medidor de uso queda apagado)")
    elif principal and "companero_uso.py" in json.dumps(d.get("statusLine") or {}):
        previa = previa_guardada()
        if previa:   # devuelve la statusLine que tenia la persona antes de Kodama
            d["statusLine"] = previa
            paso("  tu statusLine anterior vuelve a settings.json")
        else:
            d.pop("statusLine")
        guardar_previa(None)
    if not hooks:
        d.pop("hooks", None)
    paso(f"  settings.json: eventos con hooks de Kodama -> {sorted(hooks_nuestros()) if poner else 'ninguno'}")
    if PRUEBA:
        return
    if os.path.exists(settings):
        shutil.copy2(settings, settings + time.strftime(".bak-companero-%Y%m%d-%H%M%S"))
    os.makedirs(os.path.dirname(settings), exist_ok=True)
    tmp = settings + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.load(open(tmp, encoding="utf-8"))          # que quede JSON valido antes de reemplazar
    os.replace(tmp, settings)


def settings_todos():
    """(04-nov) settings.json de cada carpeta de Claude Code de esta PC (la por defecto primero)."""
    return [SETTINGS] + [os.path.join(d, "settings.json") for d in config.dirs_claude()[1:]]   # SETTINGS leido al llamar: las pruebas que lo cambian nunca tocan el real


def agregar_perfil(carpeta):
    """(04-nov) --perfil=<carpeta>: suma esa carpeta de Claude Code a config.json "perfiles_claude" (ruta absoluta, sin
    repetir). Escribe igual que guardar_previa. No hace nada en --prueba."""
    ruta = os.path.abspath(os.path.expanduser(carpeta))
    if PRUEBA:
        paso(f"  perfil de Claude Code: {ruta} (en prueba: no se guarda)")
        return
    try:
        c = json.load(open(CONFIG_JSON, encoding="utf-8-sig"))
    except FileNotFoundError:
        c = {}
    except ValueError:
        raise SystemExit("config.json no se pudo leer; no agrego el perfil. No se tocó nada.")
    perfiles = list(c.get("perfiles_claude") or [])
    if os.path.normcase(ruta) not in [os.path.normcase(os.path.abspath(os.path.expanduser(p))) for p in perfiles]:
        perfiles.append(ruta)
    c["perfiles_claude"] = perfiles
    tmp = CONFIG_JSON + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_JSON)
    paso(f"  perfil de Claude Code agregado: {ruta}")


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
            subprocess.run([PYV, "-c", codigo, priv, pub], check=True)
        hacer("  claves VAPID nuevas para los avisos del celular", gen)
    cfg = os.path.join(AQUI, "config.json")
    if not os.path.exists(cfg):
        hacer("  config.json de ejemplo (sin chats fijos: se eligen desde los grupos de la app de Claude)",
              lambda: json.dump({"url_publica": "", "token_telegram": "", "chats": [], "colores": {}, "escritorio": "tauri"},
                                open(cfg, "w", encoding="utf-8"), indent=2))


def lanzador_mac(poner):
    """(Mac-F3) El equivalente de la tarea programada en macOS: un LaunchAgent (arrancar_mac.py). Con --sin-launchctl solo
    escribe/borra el plist (para las pruebas de CI); sin esa bandera lo carga/descarga con launchctl."""
    import arrancar_mac as am
    if not poner:
        hacer(f'  LaunchAgent "{am.ETIQUETA}" quitado ({am.ruta_plist()})', lambda: am.quitar(descargar=not SIN_LAUNCHCTL))
        return

    def crear():
        r = am.instalar(AQUI, PYV, cargar=not SIN_LAUNCHCTL)
        if not r["ok"]:   # el plist ya esta escrito: se avisa, no se corta (se carga al proximo inicio de sesion)
            paso(f"  ojo: el LaunchAgent quedo escrito pero launchctl no lo cargo ({r['detalle']}). Cierra sesion y vuelve a entrar, "
                 f"o corre: launchctl bootstrap gui/$(id -u) {r['ruta']}")
    hacer(f'  LaunchAgent "{am.ETIQUETA}": al iniciar sesion y cada 10 min -> arrancar.pyw ({am.ruta_plist()})'
          + (" [sin launchctl]" if SIN_LAUNCHCTL else ""), crear)


def tarea(poner):
    if MAC:
        return lanzador_mac(poner)
    if not PRUEBA:
        for t in (TAREA, TAREA_VIEJA):   # (28-oct) borra tambien la tarea "Companero" de versiones anteriores (solo la tarea, ningun proceso)
            subprocess.run(["schtasks", "/Delete", "/TN", t, "/F"], capture_output=True)
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
            for ev, t in (("SessionStart", 10), ("UserPromptSubmit", 10), ("Stop", 1900), ("PermissionRequest", 130)):   # (04-nov) Stop 1900: espera tu respuesta (companero_puente), como con Claude
                hooks.setdefault(ev, []).append({"hooks": [{"type": "command", "command": cmd_hook("companero_codex.py"), "timeout": t}]})
        paso(f"  Codex: hooks de Kodama {'puestos' if poner else 'quitados'} en ~\\.codex\\hooks.json"
             + (" (actívalos una vez dentro de Codex con /hooks)" if poner else ""))
        if not PRUEBA and (poner or os.path.exists(CODEX_HOOKS)):   # (07-nov) quitar sin archivo: no lo crea
            _respaldo(CODEX_HOOKS)
            json.dump(d, open(CODEX_HOOKS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir(os.path.dirname(os.path.dirname(GEMINI_HOOKS))):
        try:
            d = json.load(open(GEMINI_HOOKS, encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d.pop("companero", None)   # (28-oct) clave anterior del hook
        d.pop("kodama", None)
        if poner:
            if " " in AQUI:
                paso("  Antigravity: NO se conecta (su formato de hooks no admite carpetas con espacios en la ruta)")
            else:   # Antigravity corre el comando sin shell: SIN comillas (gotcha del 20-oct)
                c = lambda ev, t: [{"type": "command", "command": cmd_hook("companero_antigravity.py", ev).replace('"', ""), "timeout": t}]
                d["kodama"] = {"SessionStart": c("SessionStart", 10), "PreInvocation": c("PreInvocation", 10), "Stop": c("Stop", 15)}
        paso(f"  Antigravity: hook \"kodama\" {'puesto' if poner and 'kodama' in d else 'quitado'} en ~\\.gemini\\config\\hooks.json")
        if not PRUEBA and (poner or os.path.exists(GEMINI_HOOKS)):   # (07-nov) quitar sin archivo: no lo crea
            _respaldo(GEMINI_HOOKS)
            os.makedirs(os.path.dirname(GEMINI_HOOKS), exist_ok=True)
            json.dump(d, open(GEMINI_HOOKS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    # (04-nov) OpenCode: el plugin va a ~/.config/opencode/plugins/kodama.js, solo si OpenCode esta instalado (existe su carpeta)
    carpeta_opencode = os.path.dirname(os.path.dirname(OPENCODE_PLUGIN))
    if os.path.isdir(carpeta_opencode):
        if poner:
            def barras(x):
                return x.replace("\\", "/")
            with open(os.path.join(AQUI, "opencode_plugin.js"), encoding="utf-8") as f:
                codigo = (f.read().replace("__PY__", barras(PYV))
                          .replace("__SCRIPT__", barras(os.path.join(AQUI, "companero_opencode.py")))
                          .replace("__ESTADO__", barras(config.ESTADO)))
            if not PRUEBA:
                os.makedirs(os.path.dirname(OPENCODE_PLUGIN), exist_ok=True)
                with open(OPENCODE_PLUGIN, "w", encoding="utf-8") as f:
                    f.write(codigo)
            paso("  OpenCode: plugin de Kodama puesto en ~\\.config\\opencode\\plugins\\kodama.js")
        elif os.path.exists(OPENCODE_PLUGIN):
            if not PRUEBA:
                os.remove(OPENCODE_PLUGIN)
            paso("  OpenCode: plugin de Kodama quitado")
    # (04-nov) WSL: Claude Code dentro de cada distro, con su propio ~/.claude/settings.json (se toca por \\wsl.localhost)
    if sys.platform == "win32":
        py_wsl = ruta_wsl(PYV)
        script_wsl = os.path.join(AQUI, "companero_wsl.py").replace("\\", "/")
        for distro in distros_wsl():
            home = home_wsl(distro)
            if not home:
                continue
            carpeta = "\\\\wsl.localhost\\" + distro + home.replace("/", "\\") + "\\.claude"
            if not os.path.isdir(carpeta):
                continue
            ajuste = os.path.join(carpeta, "settings.json")
            if os.path.exists(ajuste):
                try:
                    d = json.load(open(ajuste, encoding="utf-8-sig"))
                except (OSError, ValueError):
                    paso(f"  WSL {distro}: ojo, su settings.json no se pudo leer; no lo toco")
                    continue
            else:
                if not poner:
                    continue
                d = {}
            d = unir_hooks_wsl(d, poner, py_wsl, script_wsl)
            paso(f"  WSL {distro}: hooks de Kodama {'puestos' if poner else 'quitados'} en ~/.claude/settings.json de la distro")
            if not PRUEBA:
                _respaldo(ajuste)
                os.makedirs(carpeta, exist_ok=True)
                json.dump(d, open(ajuste, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def ruta_wsl(ruta):
    """(04-nov) C:\\a\\b.exe -> /mnt/c/a/b.exe: la ruta del Python de Windows vista desde WSL."""
    ruta = ruta.replace("\\", "/")
    if len(ruta) > 1 and ruta[1] == ":":
        return f"/mnt/{ruta[0].lower()}{ruta[2:]}"
    return ruta


def distros_wsl():
    """(04-nov) Nombres de las distros de WSL (wsl.exe -l -q, salida en UTF-16-LE). [] si no hay WSL o falla."""
    try:
        r = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    texto = r.stdout.decode("utf-16-le", errors="ignore").replace("\ufeff", "").replace("\x00", "")
    return [x.strip() for x in texto.splitlines() if x.strip()]


def home_wsl(distro):
    """(04-nov) Carpeta personal dentro de la distro (wsl.exe -d <distro> -- sh -c 'printf %s "$HOME"'). "" si falla."""
    try:
        r = subprocess.run(["wsl.exe", "-d", distro, "--", "sh", "-c", 'printf %s "$HOME"'], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout.decode("utf-8", errors="ignore").strip()


def unir_hooks_wsl(d, poner, py_wsl, script):
    """(04-nov) Une (o saca) los hooks de companero_wsl.py en un settings.json de WSL. Devuelve el diccionario. Nunca borra hooks ajenos."""
    hooks = d.setdefault("hooks", {})
    for ev in list(hooks):
        hooks[ev] = [e for e in hooks[ev] if "companero_wsl.py" not in json.dumps(e)]
        if not hooks[ev]:
            hooks.pop(ev)
    if poner:
        h = lambda modo, t, **kw: {"hooks": [dict({"type": "command", "command": f'"{py_wsl}" "{script}" {modo}', "timeout": t}, **kw)]}
        nuevos = {
            "SessionStart": [h("hook", 10, **{"async": True})],
            "UserPromptSubmit": [h("hook", 10, **{"async": True})],
            "Notification": [h("hook", 10, **{"async": True})],
            "Stop": [h("hook", 10, **{"async": True}), h("puente", 1900)],
            "SessionEnd": [h("hook", 10, **{"async": True})],
            "PostToolUse": [h("hook", 10, **{"async": True})],
            "PermissionRequest": [h("permiso", 130)],
            "PreToolUse": [dict(h("permiso", 130), matcher="AskUserQuestion")],
        }
        for ev, entradas in nuevos.items():
            hooks.setdefault(ev, []).extend(entradas)
    if not hooks:
        d.pop("hooks", None)
    return d


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


def preparar_binario_mac(ruta):
    """(Mac-F3) El zip no guarda permisos de ejecucion de forma fiable: se los pone al binario de la mascota. Una descarga con
    curl no trae el atributo de cuarentena (Gatekeeper no la bloquea); si aun asi lo trae (bajado con un navegador, AirDrop...),
    se quita SOLO de ese binario, jamas de otra cosa."""
    try:
        os.chmod(ruta, 0o755)
    except OSError as e:
        paso(f"  ojo: no pude hacer ejecutable {ruta}: {e}")
    if not os.path.exists("/usr/bin/xattr"):
        return
    r = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", ruta], capture_output=True, text=True)
    if r.returncode == 0:
        subprocess.run(["/usr/bin/xattr", "-d", "com.apple.quarantine", ruta], capture_output=True, text=True)
        paso("  cuarentena de macOS quitada del binario de la mascota")


def instalar():
    ag = config.agentes_presentes()   # (07-nov) que IA de codigo hay en esta PC (solo lee carpetas): Claude, Codex, Antigravity, OpenCode
    print("Kodama — instalación" + (" (PRUEBA: no se toca nada)" if PRUEBA else ""))
    if sys.platform not in ("win32", "darwin"):
        raise SystemExit("Kodama funciona en Windows y macOS (beta).")
    if ACEPTO:
        paso("Licencia aceptada (--acepto)")
    else:
        print("\n" + open(os.path.join(AQUI, "LICENCIA.txt"), encoding="utf-8").read())
        if not PRUEBA and input("¿Aceptas la licencia? escribe ACEPTO: ").strip().upper() != "ACEPTO":
            raise SystemExit("Instalación cancelada: no se tocó nada.")
    if sys.version_info < (3, 10):
        raise SystemExit("Hace falta Python 3.10 o más nuevo.")
    paso(f"1. Python {sys.version.split()[0]} OK · app de Claude: {config.dir_app_claude()}"
         + ("" if os.path.isdir(config.dir_app_claude()) else "  (no está: sin grupos de la app de Claude; no hace falta si usas otra IA)"))
    venv = os.path.join(AQUI, ".venv")
    if not os.path.exists(PYV):
        if preguntar("2. ¿Crear .venv e instalar pywebpush (descarga ~5 MB de PyPI)?"):
            subprocess.run([PY, "-m", "venv", venv], check=True)
            subprocess.run([PYV, "-m", "pip", "install", "-r",
                            os.path.join(AQUI, "requirements.txt")], check=True)
    else:
        paso("2. .venv ya existe")
    if not PRUEBA and not os.path.exists(PYV):
        raise SystemExit("Sin .venv no se puede seguir (los avisos usan ese Python). No se tocó la configuración de Claude.")
    verificar_paquete() if not PRUEBA else paso("  (prueba: no se verifica la firma)")
    paso("3. Claves y configuración")
    if MAC and not PRUEBA:   # (Mac-F3) carpetas de datos: junto al programa, como en Windows (~/Kodama/estado, respaldos, ts)
        for d in (config.ESTADO, config.RESPALDOS, config.TS_DIR, os.path.join(config.ESTADO, "instalacion")):
            os.makedirs(d, exist_ok=True)
    claves()
    if ag["claude"]:   # (07-nov) sin Claude Code no se toca ~\.claude ni se crea
        paso("4. Hooks y medidor de uso en ~\\.claude\\settings.json")
        for st in settings_todos(): tocar_settings(True, settings=st)   # (04-nov) cada carpeta de Claude Code (perfiles)
    else:
        paso("4. Claude Code: no está en esta PC, se salta. Si lo instalas después, vuelve a correr el instalador.")
    paso("5. Arranque automático" + (" (LaunchAgent)" if MAC else ""))
    tarea(True)
    # (21-oct) la mascota ya viene compilada (Tauri) en el paquete: no se descarga nada
    tauri = plataforma.ruta_exe_mascota(AQUI)   # kodama.exe (o el viejo companero.exe) en Windows; el binario `kodama` en macOS
    if MAC and os.path.exists(tauri) and not PRUEBA:
        preparar_binario_mac(tauri)
    paso("6. Mascota de escritorio: " + ("incluida" if os.path.exists(tauri) else "NO viene en esta copia (solo celular/Telegram)"))
    if "--solo-claude" in sys.argv:
        paso("7. Codex y Antigravity: no (--solo-claude)")
    else:
        paso("7. Otras IA: Codex, Antigravity, OpenCode y WSL (si los tienes)")
        otros_agentes(True)
    if not (ag["claude"] or ag["codex"] or ag["antigravity"] or ag["opencode"]):   # (07-nov) ninguna IA de codigo: el instalador sigue igual
        paso("Ojo: no encontré ninguna IA de código en esta PC (Claude Code, Codex, OpenCode o Antigravity). Kodama queda instalado; cuando instales una, vuelve a correr el instalador para conectarla.")
    if MAC:   # el LaunchAgent (RunAtLoad) ya lo lanza al cargarse; con --sin-launchctl no se lanza nada
        paso("8. " + ("Sin lanzar nada (--sin-launchctl)" if SIN_LAUNCHCTL else "La mascota aparece sola (el LaunchAgent la lanza al cargarse)"))
    elif not PRUEBA:
        subprocess.Popen([os.path.join(AQUI, ".venv", "Scripts", "pythonw.exe"), os.path.join(AQUI, "arrancar.pyw")], cwd=AQUI,
                         creationflags=0x00000008, close_fds=True)   # que aparezca ya, sin esperar los 10 min de la tarea
    print("\nListo. Falta (opcional, a mano):\n"
          " - Telegram: crea un bot con @BotFather, guarda el token en un archivo y pone su ruta en config.json\n"
          " - Celular: Tailscale en la PC y en el celular con la misma cuenta; `tailscale serve` del puerto 8787;\n"
          "   pone esa direccion en config.json (url_publica) y abri la app del celular desde ahi\n"
          " - Chats fijos: agregalos en config.json (\"chats\")" + (" o elige un grupo de la app de Claude desde la mascota" if ag["claude"] else "") + "\n"
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


def restaurar_original(settings=None):
    """(22-oct, mejora 5) settings.json exactamente como estaba ANTES de instalar: el respaldo .bak-companero mas viejo.
    Lo de ahora queda en .bak-antes-de-restaurar por si acaso. (04-nov) `settings`: el de cada carpeta de Claude Code."""
    import glob as _g
    if settings is None:
        settings = SETTINGS
    baks = sorted(_g.glob(settings + ".bak-companero-*"))
    if not baks:
        paso("  no hay respaldo de antes de instalar: se quitan solo los hooks de Kodama")
        return False
    paso(f"  settings.json vuelve a {os.path.basename(baks[0])}")
    if not PRUEBA:
        shutil.copy2(settings, settings + time.strftime(".bak-antes-de-restaurar-%Y%m%d-%H%M%S"))
        shutil.copy2(baks[0], settings)
    return True


def quitar():
    print("Kodama — desinstalación" + (" (PRUEBA)" if PRUEBA else ""))
    for st in settings_todos():   # (04-nov) todas las carpetas de Claude Code de esta PC (perfiles)
        if "--restaurar" in sys.argv and restaurar_original(st):
            if st == SETTINGS:
                guardar_previa(None)   # settings.json ya volvio a como estaba: la previa guardada no hace falta
        else:
            tocar_settings(False, settings=st)
    tarea(False)
    otros_agentes(False)
    paso("  la mascota de escritorio y el hub se cierran solos al reiniciar " + ("el Mac" if MAC else "la PC") + " (o cerralos desde la bandeja)")
    if "--borrar-datos" in sys.argv and (PRUEBA or input("¿Borrar estado\\, respaldos\\ y ts\\ (no se puede deshacer)? escribe BORRAR: ") == "BORRAR"):
        for d in (config.ESTADO, config.RESPALDOS, config.TS_DIR):
            hacer(f"  borrar {d}", lambda d=d: shutil.rmtree(d, ignore_errors=True))
    else:
        paso("  tus datos quedan en estado\\ y respaldos\\ (para borrarlos: --quitar --borrar-datos)")


if __name__ == "__main__":
    if "--revisar" in sys.argv:            # (22-oct) Ajustes > Revisar: JSON, sin tocar nada
        print(json.dumps(revisar(), ensure_ascii=False))
    elif "--arreglar-hooks" in sys.argv:   # (22-oct) Ajustes > Arreglar: vuelve a poner SOLO nuestros hooks (con respaldo)
        for st in settings_todos(): tocar_settings(True, settings=st)
        otros_agentes(True)
    elif any(a.startswith("--perfil=") for a in sys.argv):   # (04-nov) una carpeta de Claude Code extra (CLAUDE_CONFIG_DIR de otro perfil)
        agregar_perfil(next(a for a in sys.argv if a.startswith("--perfil="))[len("--perfil="):])
        for st in settings_todos(): tocar_settings(True, settings=st)
    else:
        quitar() if QUITAR else instalar()
