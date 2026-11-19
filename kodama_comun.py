# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Lo que comparten los hooks de Claude Code (companero_permiso, companero_puente, companero_codex y
companero_antigravity). Claude Code los corre como scripts sueltos, asi que este modulo vive junto a ellos (sin paquetes)
y va en el zip. Solo usa config y la biblioteca estandar."""
import json
import os
import shutil
import subprocess
import threading
import time

import config

BASE = config.ESTADO


def celular_abierto():
    """La app del celular esta abierta ahora (el hub toca estado/celular_activo mientras la usas)."""
    try:
        return time.time() - os.path.getmtime(os.path.join(BASE, "celular_activo")) < 30
    except OSError:
        return False


def va_al_celular(sid, proy):
    """True si el chat `sid` (de la carpeta `proy`) va al celular: es personal, esta fijo, o lo elegiste en la app."""
    if sid not in config.OCULTAR and (config.es_personal(proy) or sid in config.FIJAS):
        return True
    for f, campo in (("sesiones_extra.json", None), ("elegidos.json", "sesiones")):
        try:
            x = json.load(open(os.path.join(BASE, f), encoding="utf-8"))
            if sid in (x.get(campo) if campo else x):
                return True
        except Exception:
            pass
    return False


_DESPERTANDO = {}   # sid -> Popen del `opencode run` que lanzo el hub para despertar ese chat


def opencode_exe():
    """(16-nov) El ejecutable REAL de OpenCode (nunca .cmd/.ps1: el texto va como argumento y cmd.exe lo interpretaria)."""
    cands = [os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "opencode-ai", "bin", "opencode.exe"),
             os.path.join(os.path.expanduser("~"), ".opencode", "bin", "opencode.exe" if os.name == "nt" else "opencode")]
    w = shutil.which("opencode")
    if w and (os.name != "nt" or w.lower().endswith(".exe")):
        cands.append(w)
    return next((c for c in cands if c and os.path.isfile(c)), None)


def _lanzar(exe, sid, cwd, texto):
    env = dict(os.environ, KODAMA_DESPERTAR="1")
    flags = (0x08000000 | 0x00000200) if os.name == "nt" else 0   # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen([exe, "run", "-s", sid, "--dir", cwd, "--", texto], cwd=cwd, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, start_new_session=(os.name != "nt"))

    def tope():
        # (17-nov) `opencode run` no sale si el modelo da error (p. ej. "Free usage limit reached"): a los 15 min se cierra
        # ESTE proceso (lo lanzo el hub; se cierra por su propio handle, nunca por nombre)
        try:
            p.wait(timeout=900)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except OSError:
                pass
    threading.Thread(target=tope, daemon=True).start()
    return p


def _despertar(exe, sid, cwd, texto):
    """(16-nov) Chat de OpenCode cerrado: el hub corre `opencode run -s <sesion>` sin ventana con tu mensaje. Si ya hay uno
    corriendo para esa sesion, este espera a que termine (max. 15 min) y sale despues, para no pisarse."""
    previo = _DESPERTANDO.get(sid)
    if previo is not None and previo.poll() is None:
        def luego():
            try:
                previo.wait(timeout=900)
            except Exception:
                pass
            _DESPERTANDO[sid] = _lanzar(exe, sid, cwd, texto)
        threading.Thread(target=luego, daemon=True).start()
        return
    _DESPERTANDO[sid] = _lanzar(exe, sid, cwd, texto)


def _abierta(d, sid):
    """(16-nov) True si hay una OpenCode abierta con esa sesion: un vivo-<pid>.json de hace menos de 10 s que la lista."""
    ahora = time.time()
    for n in os.listdir(d):
        if not (n.startswith("vivo-") and n.endswith(".json")):
            continue
        try:
            ruta = os.path.join(d, n)
            if ahora - os.path.getmtime(ruta) >= 10:
                continue
            with open(ruta, encoding="utf-8") as f:
                if sid in json.load(f):
                    return True
        except (OSError, ValueError, TypeError):
            continue
    return False


def _escribir_respuesta(d, sid, texto):
    r = os.path.join(d, f"{sid}.{time.time_ns()}.respuesta")
    with open(r + ".tmp", "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(r + ".tmp", r)


def opencode_encolar(sid, texto, cwd=None):
    """(04-nov) Deja una respuesta para el plugin de OpenCode. Devuelve:
    "entregado": hay una OpenCode abierta con esa sesion; el plugin la entrega en <= 2 s.
    "despertando": estaba cerrada y se lanzo `opencode run -s <sesion>` sin ventana con el texto (cwd = carpeta del chat).
    "en_cola": no se pudo despertar; queda el .respuesta para cuando se abra."""
    if not sid.replace("-", "").replace("_", "").isalnum():
        raise ValueError("sesion")
    d = os.path.join(BASE, "opencode")
    os.makedirs(d, exist_ok=True)
    abierta = _abierta(d, sid)
    if not abierta and cwd and os.path.isdir(cwd):
        exe = opencode_exe()
        if exe:
            _despertar(exe, sid, cwd, texto)
            return "despertando"
    _escribir_respuesta(d, sid, texto)
    return "entregado" if abierta else "en_cola"


def cuadro_final(sid, vigencia=120):
    """(04-nov) El cuadro de fin de turno de la app de escritorio (lo anota companero_hook_pre.py), si tiene menos de `vigencia` s: {"recap", "ask", "acciones"} o None."""
    try:
        c = json.load(open(os.path.join(BASE, "wrapup", sid + ".json"), encoding="utf-8"))
        return c if time.time() - c["ts"] < vigencia else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def texto_con_cuadro(texto, c):
    """(04-nov) El ultimo mensaje + la pregunta del cuadro y sus botones como lista numerada: la mascota y el celular ya convierten esa lista en botones (chipsPara)."""
    partes = [(texto or "").strip() or c.get("recap") or ""]
    if c["ask"] not in partes[0]:
        partes.append(c["ask"])
    if len(c.get("acciones") or []) >= 2:
        partes.append("\n".join(f"{i}. {a}" for i, a in enumerate(c["acciones"], 1)))
    return "\n\n".join(p for p in partes if p)


def lineas_finales(ruta, tope=300000):
    """Las lineas del final de un archivo (los ultimos `tope` bytes), para leer el ultimo mensaje de un transcript JSONL
    sin cargarlo entero. None si no se puede leer."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, os.path.getsize(ruta) - tope))
            return f.read().decode("utf-8", "ignore").splitlines()
    except (OSError, TypeError):
        return None
