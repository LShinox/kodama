# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(Mac-F2, 28-oct-2026) Arranque automatico de Kodama en macOS: un LaunchAgent (`~/Library/LaunchAgents/app.kodama.plist`).
Es el equivalente de la tarea programada "Kodama" de Windows: corre arrancar.pyw al iniciar sesion y cada 10 minutos
(arrancar.pyw solo lanza lo que falta: el hub y la mascota).

NO se ejecuta solo: lo llama el instalador (F3) o a mano:
  python arrancar_mac.py --plist        muestra el plist que se escribiria (no escribe nada)
  python arrancar_mac.py --instalar     escribe el plist y lo carga con launchctl
  python arrancar_mac.py --quitar       lo descarga y borra el plist
  python arrancar_mac.py --estado       dice si el plist existe y si launchd lo tiene cargado
ESCRITO SIN UN MAC A MANO: --plist y su estructura se prueban en cualquier sistema (pruebas\\probar_plataforma_mac.py);
cargarlo de verdad con launchctl esta por verificar en un Mac."""
import os
import plistlib
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kodama_plataforma as plataforma  # noqa: E402

ETIQUETA = "app.kodama"
INTERVALO_S = 600   # como la tarea de Windows: cada 10 minutos
_LAUNCHCTL = "/bin/launchctl"


def ruta_plist():
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", ETIQUETA + ".plist")


def armar_plist(app_dir=None, python=None):
    """El contenido del plist (un dict). Sin tocar el disco."""
    app_dir = os.path.abspath(app_dir or AQUI)
    py = python or plataforma.python_del_venv(app_dir)
    if not python and not os.path.exists(py):
        py = sys.executable   # sin venv todavia: el python que corre ahora
    return {
        "Label": ETIQUETA,
        "ProgramArguments": [py, os.path.join(app_dir, "arrancar.pyw")],
        "WorkingDirectory": app_dir,
        "RunAtLoad": True,                 # al iniciar sesion
        "StartInterval": INTERVALO_S,      # y cada 10 min (vigilante)
        "AbandonProcessGroup": True,       # que launchd NO se lleve al hub ni a la mascota cuando arrancar.pyw termine
        "ProcessType": "Background",
        "StandardOutPath": os.path.join(app_dir, "estado", "launchd.log"),
        "StandardErrorPath": os.path.join(app_dir, "estado", "launchd.log"),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"},
    }


def plist_bytes(app_dir=None, python=None):
    return plistlib.dumps(armar_plist(app_dir, python), fmt=plistlib.FMT_XML)


def _launchctl(*args):
    r = subprocess.run([_LAUNCHCTL, *args], capture_output=True, text=True, timeout=30)
    return r.returncode, (r.stdout + r.stderr).strip()


def _dominio():
    return f"gui/{os.getuid()}"


def estado():
    """{'escrito': el plist existe, 'cargado': launchd lo tiene cargado}. Solo mira."""
    cargado = False
    if sys.platform == "darwin":
        try:
            cargado = _launchctl("print", f"{_dominio()}/{ETIQUETA}")[0] == 0
        except (OSError, subprocess.SubprocessError):
            cargado = False
    return {"escrito": os.path.exists(ruta_plist()), "cargado": cargado}


def instalar(app_dir=None, python=None):
    """Escribe el plist y lo carga (reemplazando uno anterior). Devuelve {'ok', 'ruta', 'detalle'}."""
    if sys.platform != "darwin":
        return {"ok": False, "ruta": ruta_plist(), "detalle": "solo en macOS"}
    ruta = ruta_plist()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    os.makedirs(os.path.join(os.path.abspath(app_dir or AQUI), "estado"), exist_ok=True)   # ahi va launchd.log
    tmp = ruta + ".tmp"
    with open(tmp, "wb") as f:
        f.write(plist_bytes(app_dir, python))
    os.replace(tmp, ruta)
    os.chmod(ruta, 0o644)
    try:
        _launchctl("bootout", f"{_dominio()}/{ETIQUETA}")   # si ya estaba cargado, se recarga con lo nuevo (si no, da error: se ignora)
        rc, msg = _launchctl("bootstrap", _dominio(), ruta)
        if rc != 0:   # macOS viejo: la forma antigua
            rc, msg = _launchctl("load", "-w", ruta)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "ruta": ruta, "detalle": f"plist escrito, launchctl fallo: {type(e).__name__}"}
    return {"ok": rc == 0, "ruta": ruta, "detalle": msg or "cargado"}


def quitar():
    """Lo descarga y borra el plist. Devuelve {'ok', 'detalle'}."""
    if sys.platform != "darwin":
        return {"ok": False, "detalle": "solo en macOS"}
    try:
        _launchctl("bootout", f"{_dominio()}/{ETIQUETA}")
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        os.remove(ruta_plist())
    except FileNotFoundError:
        pass
    return {"ok": True, "detalle": "quitado"}


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a == "--plist":
        sys.stdout.write(plist_bytes().decode("utf-8"))
    elif a == "--instalar":
        print(instalar())
    elif a == "--quitar":
        print(quitar())
    elif a == "--estado":
        print(estado())
    else:
        print(__doc__)
