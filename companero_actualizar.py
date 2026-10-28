# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(21-oct-2026) Actualizador del Companero, por los "releases" del repo publico de GitHub (config.REPO).

Cada release `vX.Y.Z` trae dos archivos que arma herramientas\\publicar_version.py:
  kodama-X.Y.Z.zip      el programa (sin estado\\, respaldos\\, ts\\, .venv\\ ni config.json)
  kodama-X.Y.Z.json     {"version", "sha256", "firma", "notas"}: firma Ed25519 del sha256 con la clave privada de LShinox
Solo se instala si el sha256 coincide Y la firma valida contra clave_publica.txt (viene con el programa). Sin esa
clave, no se instala nada: un zip cambiado en GitHub no puede meterse en la PC de nadie.

Nunca se instala solo: el hub avisa que hay version nueva y la persona elige "Actualizar" (bandeja de la mascota).

  python companero_actualizar.py --buscar            -> muestra si hay version nueva (no toca nada)
  python companero_actualizar.py --aplicar <zip>     -> lo usa el hub: para el Companero, instala y lo relanza
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

APP = config.APP_DIR
EST = config.ESTADO
CARPETA = os.path.join(EST, "actualizacion")
INFO = os.path.join(EST, "actualizacion.json")
LOG = os.path.join(EST, "actualizar.log")
CLAVE_PUBLICA = os.path.join(APP, "clave_publica.txt")
# lo de la persona: nunca se pisa ni se borra al actualizar
PROTEGIDO = ("estado/", "respaldos/", "ts/", ".venv/", "config.json", ".claude/")
UA = {"User-Agent": "Companero-actualizador", "Accept": "application/vnd.github+json"}


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def _num(v):
    try:
        return tuple(int(x) for x in str(v).lstrip("vV").split("-")[0].split("."))
    except ValueError:
        return (0,)


def _get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def buscar():
    """Mira el ultimo release. Devuelve {"version", "notas", "zip", "manifiesto", "pagina"} si es mas nuevo; si no, None.
    Sin repo, sin releases o sin internet: None (no es un error para la persona)."""
    try:
        rel = json.loads(_get(f"https://api.github.com/repos/{config.REPO}/releases/latest"))
    except Exception:
        return None
    v = str(rel.get("tag_name") or "").lstrip("vV")
    if not v or _num(v) <= _num(config.VERSION):
        return None
    a = {x.get("name"): x.get("browser_download_url") for x in rel.get("assets") or []}
    # (28-oct) el release se llama kodama-X.zip; los anteriores, companero-X.zip: se aceptan los dos
    z = a.get(f"kodama-{v}.zip") or a.get(f"companero-{v}.zip")
    m = a.get(f"kodama-{v}.json") or a.get(f"companero-{v}.json")
    if not z or not m:
        return None
    return {"version": v, "notas": (rel.get("body") or "")[:1500], "zip": z, "manifiesto": m, "pagina": rel.get("html_url")}


def verificar(ruta_zip, manifiesto):
    """True si el sha256 del zip coincide con el manifiesto y la firma Ed25519 del sha256 es valida."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    try:
        pub = base64.b64decode(open(CLAVE_PUBLICA, encoding="utf-8").read().strip())
    except OSError:
        log("no hay clave_publica.txt: no se instala nada sin firma")
        return False
    h = hashlib.sha256(open(ruta_zip, "rb").read()).hexdigest()
    if h != manifiesto.get("sha256"):
        log(f"sha256 distinto: {h} != {manifiesto.get('sha256')}")
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(base64.b64decode(manifiesto.get("firma") or ""), h.encode())
        return True
    except (InvalidSignature, ValueError):
        log("firma invalida")
        return False


def descargar(info):
    """Baja y verifica. Devuelve la ruta del zip listo para aplicar, o None."""
    os.makedirs(CARPETA, exist_ok=True)
    try:
        man = json.loads(_get(info["manifiesto"]))
        ruta = os.path.join(CARPETA, f"kodama-{info['version']}.zip")
        with open(ruta, "wb") as f:
            f.write(_get(info["zip"], timeout=300))
    except Exception as e:
        log(f"descarga fallida: {type(e).__name__}: {e}")
        return None
    if str(man.get("version")) != info["version"] or not verificar(ruta, man):
        os.remove(ruta)
        return None
    log(f"descargada y verificada {info['version']}")
    return ruta


def lanzar_aplicar(ruta_zip):
    """El hub no puede reemplazarse a si mismo: lanza este archivo aparte, sin ventana, y ese proceso hace el resto."""
    pyw = os.path.join(APP, ".venv", "Scripts", "pythonw.exe")
    subprocess.Popen([pyw, os.path.abspath(__file__), "--aplicar", ruta_zip], cwd=APP,
                     creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED | NEW_PROCESS_GROUP


def _parar(pidfile, texto):
    """Para SOLO el proceso de Kodama cuyo PID esta en estado\\<pidfile> (y si su linea de comando lo confirma)."""
    try:
        pid = int(open(os.path.join(EST, pidfile)).read().strip())
    except (OSError, ValueError):
        return
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                         capture_output=True, text=True, timeout=30, creationflags=0x08000000).stdout
    if any(t in out for t in ((texto,) if isinstance(texto, str) else texto)):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)
        log(f"parado PID {pid} ({texto})")


def _miembros_tamizados(z):
    return [n for n in z.namelist() if not n.endswith("/") and not n.replace("\\", "/").startswith(PROTEGIDO)
            and ".." not in n and not os.path.isabs(n)]


def aplicar(ruta_zip):
    bandera = os.path.join(EST, "no-relanzar")
    open(bandera, "w").close()   # que arrancar.pyw no lo relance a mitad
    respaldo = os.path.join(config.RESPALDOS, f"programa-{config.VERSION}-{time.strftime('%Y%m%d-%H%M')}.zip")
    try:
        time.sleep(2)   # que el hub termine de responder
        _parar("hub.pid", "companero_hub.py")
        _parar("escritorio.pid", ("kodama.exe", "companero.exe"))
        time.sleep(2)
        req_viejo = open(os.path.join(APP, "requirements.txt"), "rb").read() if os.path.exists(os.path.join(APP, "requirements.txt")) else b""
        with zipfile.ZipFile(ruta_zip) as z:
            nombres = _miembros_tamizados(z)
            os.makedirs(config.RESPALDOS, exist_ok=True)
            with zipfile.ZipFile(respaldo, "w", zipfile.ZIP_DEFLATED) as r:   # copia de lo que se va a pisar
                for n in nombres:
                    p = os.path.join(APP, n)
                    if os.path.exists(p):
                        r.write(p, n)
            for n in nombres:
                destino = os.path.join(APP, n)
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(n) as src, open(destino + ".nuevo", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.replace(destino + ".nuevo", destino)
        if open(os.path.join(APP, "requirements.txt"), "rb").read() != req_viejo:
            subprocess.run([os.path.join(APP, ".venv", "Scripts", "python.exe"), "-m", "pip", "install", "-q", "-r",
                            os.path.join(APP, "requirements.txt")], capture_output=True, timeout=600, creationflags=0x08000000)
        log(f"instalada {open(os.path.join(APP, 'VERSION')).read().strip()} (respaldo: {os.path.basename(respaldo)})")
        os.remove(ruta_zip)
    except Exception as e:
        log(f"fallo al instalar: {type(e).__name__}: {e} -> vuelvo a la version anterior")
        try:
            with zipfile.ZipFile(respaldo) as r:
                r.extractall(APP)
            log("version anterior restaurada")
        except Exception as e2:
            log(f"no pude restaurar: {type(e2).__name__}: {e2}")
    finally:
        try:
            os.remove(bandera)
        except OSError:
            pass
        subprocess.Popen([os.path.join(APP, ".venv", "Scripts", "pythonw.exe"), os.path.join(APP, "arrancar.pyw")], cwd=APP,
                         creationflags=0x00000008, close_fds=True)


if __name__ == "__main__":
    if "--aplicar" in sys.argv:
        aplicar(sys.argv[sys.argv.index("--aplicar") + 1])
    else:
        print(json.dumps(buscar(), ensure_ascii=False, indent=1) or "sin version nueva (o sin repo/releases)")
