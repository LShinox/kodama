# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(Mac-F3, 28-oct) Prueba de punta a punta del instalador de macOS (instalar.sh + instalar.py rama darwin) con un HOME FALSO.

SOLO en macOS (en otro sistema dice "SALTADA"). La corre CI (macos-latest). No toca el HOME real, no carga nada en launchd
(usa --sin-launchctl), no usa la clave de firma real: arma un paquete de prueba con una clave desechable
(pruebas/armar_paquete_prueba.py) y se lo da a instalar.sh con KODAMA_ORIGEN_PRUEBA (variable SOLO de pruebas).

Comprueba:
  1. Un zip alterado se rechaza por el sha256 y no se crea nada.
  2. Un paquete con la firma mala se rechaza ANTES de tocar settings.json.
  3. La instalacion buena: ~/Kodama, .venv, claves, el venv importa los modulos del hub, hooks + statusLine (encadenada con la
     que ya habia) en settings.json con respaldo, hooks de Codex y Antigravity, el plist del LaunchAgent (sin cargarlo).
  4. Reinstalar no duplica nada y --revisar dice que esta todo.
  5. instalar.py --quitar devuelve settings.json, Codex y Antigravity a como estaban y borra el plist."""
import base64
import glob
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.platform != "darwin":
    print("SALTADA: probar_instalador_mac.py solo corre en macOS (CI macos-latest).")
    sys.exit(0)

fallos = []


def ok(nombre, cond, detalle=""):
    print(("OK    " if cond else "FALLA ") + nombre + (f" -> {detalle}" if (detalle and not cond) else ""))
    if not cond:
        fallos.append(nombre)


def correr(cmd, home, extra_env=None, cwd=None, timeout=900):
    env = dict(os.environ, HOME=home, PYTHONUTF8="1", KODAMA_IDIOMA="en")
    env.pop("KODAMA_ORIGEN_PRUEBA", None)
    env.update(extra_env or {})
    r = subprocess.run(cmd, env=env, cwd=cwd or home, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def cola(txt, n=1500):
    return txt[-n:]


trabajo = os.path.realpath(tempfile.mkdtemp(prefix="kodama-e2e-"))
try:
    origen = os.path.join(trabajo, "origen")
    rc, out = correr([sys.executable, os.path.join(AQUI, "pruebas", "armar_paquete_prueba.py"), origen, "0.0.1"], trabajo,
                     {"CI": "true"}, cwd=AQUI)
    ok("paquete de prueba armado", rc == 0 and os.path.exists(os.path.join(origen, "kodama-0.0.1-macos.zip")), cola(out))
    if rc != 0:
        raise SystemExit(1)
    sh = os.path.join(AQUI, "instalar.sh")
    env_origen = lambda d: {"KODAMA_ORIGEN_PRUEBA": d}

    # ------------------------------------------------------------ 1. zip alterado: rechazado por el sha256
    malo = os.path.join(trabajo, "malo")
    shutil.copytree(origen, malo)
    zp = os.path.join(malo, "kodama-0.0.1-macos.zip")
    b = bytearray(open(zp, "rb").read())
    b[200] ^= 0x01
    open(zp, "wb").write(bytes(b))
    h1 = os.path.join(trabajo, "home-sha")
    os.makedirs(h1)
    rc, out = correr(["bash", sh, "-Acepto", "-Si", "--sin-launchctl"], h1, env_origen(malo))
    ok("zip alterado: instalar.sh se niega", rc != 0 and "checksum" in out, cola(out))
    ok("zip alterado: no se crea ~/Kodama", not os.path.exists(os.path.join(h1, "Kodama")))

    # ------------------------------------------------------------ 2. firma mala (sha256 bien): se corta antes de tocar settings.json
    firma_mala = os.path.join(trabajo, "firma-mala")
    shutil.copytree(origen, firma_mala)
    jp = os.path.join(firma_mala, "kodama-0.0.1-macos.json")
    man = json.load(open(jp, encoding="utf-8"))
    man["firma"] = base64.b64encode(os.urandom(64)).decode()
    json.dump(man, open(jp, "w", encoding="utf-8"))
    h2 = os.path.join(trabajo, "home-firma")
    os.makedirs(os.path.join(h2, ".claude"))
    st2 = os.path.join(h2, ".claude", "settings.json")
    open(st2, "w", encoding="utf-8").write('{"model": "x"}')
    rc, out = correr(["bash", sh, "-Acepto", "-Si", "--sin-launchctl"], h2, env_origen(firma_mala))
    ok("firma mala: instalar se niega", rc != 0 and "firma" in out.lower(), cola(out))
    ok("firma mala: settings.json intacto", open(st2, encoding="utf-8").read() == '{"model": "x"}')
    ok("firma mala: sin respaldos ni plist", not glob.glob(st2 + ".bak*")
       and not os.path.exists(os.path.join(h2, "Library", "LaunchAgents", "app.kodama.plist")))

    # ------------------------------------------------------------ 3. instalacion buena en un HOME falso con cosas que ya tenia
    home = os.path.join(trabajo, "home")
    os.makedirs(os.path.join(home, ".claude"))
    os.makedirs(os.path.join(home, ".codex"))
    os.makedirs(os.path.join(home, ".gemini", "config"))
    original = {"model": "opus", "statusLine": {"type": "command", "command": "echo mi-barra", "padding": 2},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hook-ajeno"}]}]}}
    settings = os.path.join(home, ".claude", "settings.json")
    json.dump(original, open(settings, "w", encoding="utf-8"))
    codex = os.path.join(home, ".codex", "hooks.json")
    gemini = os.path.join(home, ".gemini", "config", "hooks.json")
    codex_orig = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo cx-ajeno"}]}]}}
    json.dump(codex_orig, open(codex, "w", encoding="utf-8"))

    rc, out = correr(["bash", sh, "-Acepto", "-Si", "--sin-launchctl"], home, env_origen(origen))
    print(cola(out, 2500))
    ok("instalar.sh termina bien", rc == 0, cola(out))
    kodama = os.path.join(home, "Kodama")
    vpy = os.path.join(kodama, ".venv", "bin", "python")
    ok("~/Kodama existe con el programa", os.path.isfile(os.path.join(kodama, "companero_hub.py"))
       and os.path.isfile(os.path.join(kodama, "instalar.py")) and os.path.isfile(os.path.join(kodama, "arrancar_mac.py")))
    ok("la firma del paquete se verifico", "firma del paquete verificada" in out)
    ok("el venv existe", os.path.exists(vpy))
    ok("carpetas de datos (estado, respaldos, ts)", all(os.path.isdir(os.path.join(kodama, d)) for d in ("estado", "respaldos", "ts")))
    ok("claves y config creadas", all(os.path.exists(os.path.join(kodama, p)) for p in
                                       ("estado/local.key", "estado/vapid_private.pem", "estado/vapid_public.txt", "config.json")))
    binario = os.path.join(kodama, "escritorio-tauri", "src-tauri", "target", "release", "kodama")
    ok("el binario de la mascota es ejecutable", os.path.isfile(binario) and os.access(binario, os.X_OK))
    rc2, out2 = correr([vpy, "-c", "import config, kodama_plataforma, kodama_rutas, kodama_nucleo, companero_hub, companero_actualizar, "
                                   "pywebpush, segno, cryptography; print('IMPORT_OK')"], home, cwd=kodama)
    ok("el venv importa los modulos del hub", rc2 == 0 and "IMPORT_OK" in out2, cola(out2))

    st = json.load(open(settings, encoding="utf-8"))
    eventos = {"SessionStart", "UserPromptSubmit", "Notification", "Stop", "SessionEnd", "PermissionRequest", "PreToolUse", "PostToolUse"}
    ok("settings.json: hooks de Kodama en los 8 eventos", eventos <= set(st.get("hooks", {})))
    ok("settings.json: los hooks usan el python del venv", all(
        vpy in x["command"] for ev in eventos for e in st["hooks"][ev] for x in e["hooks"] if "companero_" in x["command"]))
    ok("settings.json: el hook ajeno sigue ahi", "echo hook-ajeno" in json.dumps(st["hooks"]["Stop"]))
    ok("settings.json: statusLine de Kodama con el padding de la persona",
       "companero_uso.py" in st["statusLine"]["command"] and st["statusLine"].get("padding") == 2)
    cfg = json.load(open(os.path.join(kodama, "config.json"), encoding="utf-8"))
    ok("statusLine anterior guardada para encadenar", (cfg.get("statusline_previa") or {}).get("command") == "echo mi-barra")
    ok("respaldo de settings.json con lo original", any(json.load(open(p, encoding="utf-8")) == original
                                                      for p in glob.glob(settings + ".bak-companero-*")))
    ok("Codex: hooks de Kodama y el ajeno", "companero_codex.py" in open(codex, encoding="utf-8").read()
       and "echo cx-ajeno" in open(codex, encoding="utf-8").read())
    ok("Antigravity: hook kodama con python del venv", vpy in json.dumps(json.load(open(gemini, encoding="utf-8")).get("kodama", {})))

    plist = os.path.join(home, "Library", "LaunchAgents", "app.kodama.plist")
    ok("LaunchAgent: plist escrito", os.path.exists(plist))
    if os.path.exists(plist):
        p = plistlib.load(open(plist, "rb"))
        ok("plist: etiqueta, python del venv y arrancar.pyw", p.get("Label") == "app.kodama" and p["ProgramArguments"][0] == vpy
           and p["ProgramArguments"][1] == os.path.join(kodama, "arrancar.pyw") and p.get("RunAtLoad") is True)
        rcl, outl = correr(["/usr/bin/plutil", "-lint", plist], home)
        ok("plist: plutil -lint", rcl == 0, outl)
    rcc, _ = correr(["/bin/launchctl", "print", f"gui/{os.getuid()}/app.kodama"], home)
    ok("--sin-launchctl: launchd NO lo cargo", rcc != 0)

    # ------------------------------------------------------------ 4. reinstalar (idempotente) y --revisar
    time.sleep(2)   # los respaldos llevan la hora al segundo
    rc, out = correr([vpy, os.path.join(kodama, "instalar.py"), "--acepto", "--si", "--sin-launchctl"], home, cwd=kodama)
    ok("reinstalar con instalar.py termina bien", rc == 0, cola(out))
    st = json.load(open(settings, encoding="utf-8"))
    n = sum(1 for e in st["hooks"]["SessionStart"] for x in e["hooks"] if "companero_hook.py" in x["command"])
    ok("reinstalar no duplica hooks", n == 1, str(n))
    ok("reinstalar deja la statusLine encadenada", (json.load(open(os.path.join(kodama, "config.json"), encoding="utf-8"))
                                                      .get("statusline_previa") or {}).get("command") == "echo mi-barra")
    rc, out = correr([vpy, os.path.join(kodama, "instalar.py"), "--revisar"], home, cwd=kodama)
    try:
        rev = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        rev = {}
    ok("--revisar: todo puesto", rc == 0 and rev.get("ok") is True, cola(out))

    # ------------------------------------------------------------ 5. --quitar
    time.sleep(2)
    rc, out = correr([vpy, os.path.join(kodama, "instalar.py"), "--quitar", "--sin-launchctl"], home, cwd=kodama)
    ok("--quitar termina bien", rc == 0, cola(out))
    ok("--quitar: settings.json vuelve a como estaba", json.load(open(settings, encoding="utf-8")) == original,
       json.dumps(json.load(open(settings, encoding="utf-8")))[:600])
    ok("--quitar: la statusLine anterior ya no queda guardada", "statusline_previa" not in
       json.load(open(os.path.join(kodama, "config.json"), encoding="utf-8")))
    ok("--quitar: plist borrado", not os.path.exists(plist))
    ok("--quitar: Codex sin hooks de Kodama (el ajeno queda)", "companero_codex" not in open(codex, encoding="utf-8").read()
       and "echo cx-ajeno" in open(codex, encoding="utf-8").read())
    ok("--quitar: Antigravity sin el hook kodama", "kodama" not in json.load(open(gemini, encoding="utf-8")))
    ok("--quitar: los datos se quedan en ~/Kodama/estado", os.path.isdir(os.path.join(kodama, "estado")))
finally:
    shutil.rmtree(trabajo, ignore_errors=True)

print()
print("TODO OK" if not fallos else "FALLARON: " + ", ".join(fallos))
sys.exit(1 if fallos else 0)
