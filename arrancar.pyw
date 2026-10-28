# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Arranca (si no estan corriendo) el Tailscale del companero y el hub. Lo llama la tarea
programada "Kodama" al iniciar sesion y cada 10 min (vigilante). Sin ventanas.
Procesos desprendidos y fuera del job del que lanza, para que nada se los lleve al cerrarse."""
import os
import subprocess
import time

BASE = os.path.dirname(os.path.abspath(__file__))   # (14-oct) donde este instalado
TS_DIR = os.path.join(BASE, "ts")
LOG = os.path.join(BASE, "estado", "arrancar.log")
FLAGS = 0x00000008 | 0x00000200 | 0x01000000 | 0x08000000   # DETACHED | NEW_GROUP | BREAKAWAY_FROM_JOB | NO_WINDOW


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def corriendo(texto, exe):
    """PIDs de procesos `exe` cuya linea de comando contiene `texto` (solo mira, no toca nada).
    Filtra por nombre de ejecutable: si no, la propia consulta (que contiene el texto) se encuentra a si misma."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance Win32_Process -Filter \"Name='{exe}'\" | Where-Object {{ $_.CommandLine -like '*{texto}*' }}).ProcessId"],
                       capture_output=True, text=True, creationflags=0x08000000)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def lanzar(args, cwd, pidfile=None):
    try:
        p = subprocess.Popen(args, cwd=cwd, creationflags=FLAGS, close_fds=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError:   # si el job no permite "breakaway", sin esa bandera
        p = subprocess.Popen(args, cwd=cwd, creationflags=FLAGS & ~0x01000000, close_fds=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    if pidfile:
        open(pidfile, "w").write(str(p.pid))
    return p.pid


if not corriendo("companero-tailscaled", "tailscaled.exe"):
    pid = lanzar([r"C:\Program Files\Tailscale\tailscaled.exe", "--windows-mode=dev", "--tun=userspace-networking",
                  f"--statedir={TS_DIR}", r"--socket=\\.\pipe\companero-tailscaled", "--port=41642"],
                 TS_DIR, os.path.join(TS_DIR, "tailscaled.pid"))
    log(f"tailscaled arrancado pid={pid}")
    time.sleep(8)

ESC = os.path.join(BASE, "escritorio")
# (14-oct) mascota en Tauri (mas liviana): se usa si config.json dice "escritorio": "tauri" y el .exe existe;
# si no, Electron como siempre. Nunca las dos a la vez.
import json as _json
try:
    _usar_tauri = _json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8-sig")).get("escritorio") == "tauri"
except Exception:
    _usar_tauri = False
_REL = os.path.join(BASE, "escritorio-tauri", "src-tauri", "target", "release")
# (28-oct) el exe se llama kodama.exe; si no existe (PC de desarrollo que aun no recompila), se usa el viejo companero.exe
TAURI = os.path.join(_REL, "kodama.exe") if os.path.exists(os.path.join(_REL, "kodama.exe")) else os.path.join(_REL, "companero.exe")


def corriendo_mascota():
    """PIDs de la mascota viva, con el nombre nuevo (kodama.exe) o el viejo (companero.exe): asi no se lanza una segunda."""
    return corriendo("escritorio-tauri", "kodama.exe") + corriendo("escritorio-tauri", "companero.exe")


# (15-oct, contra #11) mientras se recompila la mascota, estado\no-relanzar (de menos de 15 min) frena el relanzar
_pausa = os.path.join(BASE, "estado", "no-relanzar")
_pausado = os.path.exists(_pausa) and time.time() - os.path.getmtime(_pausa) < 900
# (15-oct) OJO: la pausa frena la mascota ENTERA; antes caia al "elif" y arrancaba la de Electron (dos mascotas)
if _pausado:
    pass
elif _usar_tauri and os.path.exists(TAURI):
    # (20-oct) tras una suspension (Modern Standby) el WebView2 de la mascota puede morir: el exe sigue
    # vivo con la ventana en pantalla pero transparente, y el icono de la bandeja no la "muestra". Sano = tiene un
    # msedgewebview2.exe hijo. Si el proceso (el NUESTRO, por el PID de escritorio.pid) lleva >2 min sin hijo,
    # se cierra por PID y se relanza abajo.
    _pidf = os.path.join(BASE, "estado", "escritorio.pid")
    try:
        _pid = int(open(_pidf).read().strip())
    except (OSError, ValueError):
        _pid = 0
    if _pid and _pid in corriendo_mascota():
        _r = subprocess.run(["powershell", "-NoProfile", "-Command",
                             f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={_pid}'; "
                             f"$h=@(Get-CimInstance Win32_Process -Filter \"ParentProcessId={_pid} AND Name='msedgewebview2.exe'\").Count; "
                             f"\"$h $([int]((Get-Date)-$p.CreationDate).TotalSeconds)\""],
                            capture_output=True, text=True, creationflags=0x08000000)
        try:
            _hijos, _edad = (int(x) for x in _r.stdout.split()[:2])
        except ValueError:
            _hijos, _edad = 1, 0
        if _hijos == 0 and _edad > 120:
            subprocess.run(["taskkill", "/PID", str(_pid), "/F"], capture_output=True, creationflags=0x08000000)
            log(f"escritorio (tauri) pid={_pid} sin WebView2 (ventana en blanco): cerrado para relanzar")
            time.sleep(2)
    if not corriendo_mascota():
        pid = lanzar([TAURI], BASE, os.path.join(BASE, "estado", "escritorio.pid"))   # cwd = BASE: ahi busca estado\
        log(f"escritorio (tauri) arrancado pid={pid}")
elif os.path.exists(os.path.join(ESC, "node_modules", "electron", "dist", "electron.exe")) and not corriendo(ESC, "electron.exe"):
    pid = lanzar([os.path.join(ESC, "node_modules", "electron", "dist", "electron.exe"), ESC], ESC,
                 os.path.join(BASE, "estado", "escritorio.pid"))
    log(f"escritorio arrancado pid={pid}")

if not corriendo("companero_hub.py", "pythonw.exe"):
    pid = lanzar([os.path.join(BASE, ".venv", "Scripts", "pythonw.exe"), os.path.join(BASE, "companero_hub.py")], BASE)
    log(f"hub arrancado (lanzador pid={pid})")
