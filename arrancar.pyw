# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Arranca (si no estan corriendo) el Tailscale del companero y el hub. Lo llama la tarea
programada "Kodama" al iniciar sesion y cada 10 min (vigilante). Sin ventanas.
Procesos desprendidos y fuera del job del que lanza, para que nada se los lleve al cerrarse."""
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))   # (14-oct) donde este instalado
sys.path.insert(0, BASE)   # (28-oct) kodama_plataforma.py esta al lado: lo propio de Windows vive ahi
import kodama_plataforma as plataforma
TS_DIR = os.path.join(BASE, "ts")
LOG = os.path.join(BASE, "estado", "arrancar.log")


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


# (28-oct) buscar procesos y lanzarlos desprendidos: en kodama_plataforma (lo propio de Windows)
corriendo = plataforma.pids_por_linea
lanzar = plataforma.lanzar_desprendido


if not corriendo("companero-tailscaled", plataforma.nombre_proceso_tailscaled()):
    pid = lanzar(plataforma.comando_tailscaled(TS_DIR), TS_DIR, os.path.join(TS_DIR, "tailscaled.pid"))
    log(f"tailscaled arrancado pid={pid}")
    time.sleep(8)

# (14-oct) mascota en Tauri: se usa si config.json dice "escritorio": "tauri" y el .exe existe. (28-oct) Electron ya no existe.
import json as _json
try:
    _usar_tauri = _json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8-sig")).get("escritorio") == "tauri"
except Exception:
    _usar_tauri = False
# (28-oct) el exe se llama kodama.exe; si no existe (PC de desarrollo que aun no recompila), se usa el viejo companero.exe
TAURI = plataforma.ruta_exe_mascota(BASE)


def corriendo_mascota():
    """PIDs de la mascota viva, con el nombre nuevo (kodama.exe) o el viejo (companero.exe): asi no se lanza una segunda."""
    return [pid for exe in plataforma.NOMBRES_EXE_MASCOTA for pid in corriendo("escritorio-tauri", exe)]


# (15-oct, contra #11) mientras se recompila la mascota, estado\no-relanzar (de menos de 15 min) frena el relanzar
_pausa = os.path.join(BASE, "estado", "no-relanzar")
_pausado = os.path.exists(_pausa) and time.time() - os.path.getmtime(_pausa) < 900
# (15-oct) OJO: la pausa frena la mascota ENTERA (si no, se podria arrancar una segunda)
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
        _hijos, _edad = plataforma.hijos_webview_y_edad(_pid)
        if _hijos == 0 and _edad > 120:
            plataforma.terminar_pid(_pid)   # por PID (el nuestro, de escritorio.pid), nunca por nombre
            log(f"escritorio (tauri) pid={_pid} sin WebView2 (ventana en blanco): cerrado para relanzar")
            time.sleep(2)
    if not corriendo_mascota():
        pid = lanzar([TAURI], BASE, os.path.join(BASE, "estado", "escritorio.pid"))   # cwd = BASE: ahi busca estado\
        log(f"escritorio (tauri) arrancado pid={pid}")

if not corriendo("companero_hub.py", plataforma.nombre_proceso_python()):
    pid = lanzar([plataforma.python_del_venv(BASE, sin_consola=True), os.path.join(BASE, "companero_hub.py")], BASE)
    log(f"hub arrancado (lanzador pid={pid})")
