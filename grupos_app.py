# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Grupos y favoritos de la app de escritorio de Claude (14-oct-2026), SOLO LECTURA.

LShinox: "deben respetar los grupos que tenemos aca en la app". La app guarda:
- en %APPDATA%\\Claude\\claude_desktop_config.json -> preferences.epitaxyPrefs:
    dframe-group-scopes.<ambito>.groups       [{id, name}]
    dframe-group-scopes.<ambito>.assignments  {"code:local_xxx": id_de_grupo}
    starred-local-code-sessions               favoritos (vacio al 14-oct: formato sin confirmar)
- en %APPDATA%\\Claude\\claude-code-sessions\\<a>\\<b>\\local_xxx.json -> sessionId, cliSessionId (= el
  session_id que ven los hooks), title, cwd, isArchived.
Es un formato interno de la app: si cambia, catalogo() devuelve vacio y el Companero sigue con "Personales".
"""
import glob
import re
import json
import os
import time

# La app de Claude es MSIX: su %APPDATA%\Claude real vive en el paquete. Los procesos que lanza la app (las
# terminales de Claude) lo ven en Roaming\Claude por virtualizacion; el hub (lanzado por la tarea programada) NO.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
APP = config.dir_app_claude()
_CACHE = {"t": 0, "v": None}
ERROR = []   # ultimo error al leer la config de la app (para /api/grupos)


def _id(x):
    return str(x).split(":", 1)[-1] if isinstance(x, str) else None


_CAMPOS = ("sessionId", "cliSessionId", "title", "cwd", "isArchived", "lastActivityAt")
_POR_ARCHIVO = {}   # ruta -> (mtime, datos)
_PREVIOS_RE = re.compile(r'"priorCliSessionIds"\s*:\s*\[([^\]]*)\]')
_CAMPO_RE = re.compile(r'"(sessionId|cliSessionId|title|cwd|isArchived|lastActivityAt)"\s*:\s*("(?:[^"\\]|\\.)*"|true|false|null|-?\d+(?:\.\d+)?)')


def _sesion(ruta):
    """(14-oct, rendimiento) Los local_*.json pesan ~31 MB en total (lista de herramientas): leerlos enteros cada 30 s
    se comia ~8 % de un nucleo. Ahora: solo si cambio el archivo, y solo los primeros 16 KB (los campos que usamos
    van al principio); si falta alguno, se lee entero como antes."""
    try:
        mt = os.path.getmtime(ruta)
    except OSError:
        return None
    viejo = _POR_ARCHIVO.get(ruta)
    if viejo and viejo[0] == mt:
        return viejo[1]
    d = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            cabeza = f.read(16384)
        for k, v in _CAMPO_RE.findall(cabeza):
            d.setdefault(k, json.loads(v))
        if not all(k in d for k in ("sessionId", "cliSessionId")):
            d = json.load(open(ruta, encoding="utf-8"))
            d = {k: d.get(k) for k in _CAMPOS + ("priorCliSessionIds",)}
        else:
            # (20-oct) la app CAMBIA el cliSessionId de un chat (al compactar / reanudar) y guarda los viejos en
            # priorCliSessionIds; suele estar despues de la lista de herramientas, asi que se busca en todo el archivo
            m = _PREVIOS_RE.search(cabeza)
            if not m:
                with open(ruta, encoding="utf-8") as f:
                    m = _PREVIOS_RE.search(f.read())
            d["priorCliSessionIds"] = re.findall(r'"([0-9a-f\-]{36})"', m.group(1)) if m else []
    except Exception:
        return None
    _POR_ARCHIVO[ruta] = (mt, d)
    return d


_FOCO = {}   # ruta -> (mtime, lastFocusedAt, cliSessionId)
_FOCO_RE = re.compile(r'"(lastFocusedAt|cliSessionId)"\s*:\s*"?([^",}]+)')


def chat_enfocado():
    """(14-oct) cliSessionId del chat que la app de Claude tiene abierto: el de "lastFocusedAt" mas reciente (la app
    lo reescribe al entrar a un chat). Rapido: solo relee los archivos que cambiaron (primeros 16 KB)."""
    mejor = (0, None)
    try:
        for f in glob.glob(os.path.join(APP, "claude-code-sessions", "*", "*", "local_*.json")):
            try:
                m = os.path.getmtime(f)
            except OSError:
                continue
            c = _FOCO.get(f)
            if not c or c[0] != m:
                try:
                    with open(f, "rb") as h:
                        d = dict(_FOCO_RE.findall(h.read(16384).decode("utf-8", "ignore")))
                    c = (m, int(d.get("lastFocusedAt") or 0), d.get("cliSessionId"))
                except (OSError, ValueError):
                    c = (m, 0, None)
                _FOCO[f] = c
            if c[1] > mejor[0]:
                mejor = (c[1], c[2])
    except Exception:
        return None
    return mejor[1]


def catalogo(max_edad=30):
    """{"grupos": [{id, nombre}], "favoritos": set(local_id), "sesiones": {local_id: {...}}}; cache 30 s."""
    if _CACHE["v"] is not None and time.time() - _CACHE["t"] < max_edad:
        return _CACHE["v"]
    grupos, asign, favs, ses = [], {}, set(), {}
    try:
        e = json.load(open(os.path.join(APP, "claude_desktop_config.json"), encoding="utf-8"))["preferences"]["epitaxyPrefs"]
        for amb in (e.get("dframe-group-scopes") or {}).values():
            for g in amb.get("groups") or []:
                if g.get("id") and all(x["id"] != g["id"] for x in grupos):
                    grupos.append({"id": g["id"], "nombre": g.get("name") or "Grupo"})
            for k, gid in (amb.get("assignments") or {}).items():
                asign[_id(k)] = gid
        for x in e.get("starred-local-code-sessions") or []:
            favs.add(_id(x if isinstance(x, str) else (x or {}).get("id") or (x or {}).get("sessionId")))
        ERROR[:] = []
    except Exception as ex:
        ERROR[:] = [f"{type(ex).__name__}: {str(ex)[:200]}"]
    for ruta in glob.glob(os.path.join(APP, "claude-code-sessions", "*", "*", "local_*.json")):
        d = _sesion(ruta)
        if not d or d.get("isArchived") or not d.get("cliSessionId"):
            continue
        sid = d.get("sessionId")
        ses[sid] = {"cli": d["cliSessionId"], "titulo": d.get("title") or "Chat", "cwd": d.get("cwd"),
                    "grupo": asign.get(sid), "actividad": d.get("lastActivityAt") or 0,
                    "previos": d.get("priorCliSessionIds") or []}
    _CACHE.update(t=time.time(), v={"grupos": grupos, "favoritos": favs, "sesiones": ses})
    return _CACHE["v"]


def opciones():
    """Lo que se puede llevar al celular: Personales (fijo), Favoritos (si hay) y cada grupo de la app."""
    c = catalogo()
    ops = [{"id": "personales", "nombre": "Personales"}]
    if c["favoritos"]:
        ops.append({"id": "favoritos", "nombre": "⭐ Favoritos"})
    if not config.GRUPOS_APP:
        return ops
    ops += [{"id": "g:" + g["id"], "nombre": g["nombre"]} for g in c["grupos"]
            if any(s["grupo"] == g["id"] for s in c["sesiones"].values())]
    return ops


def actual(cli_sid):
    """(20-oct) El id ACTUAL de un chat a partir de uno viejo (la app cambia el cliSessionId al compactar/reanudar:
    lo que el Companero tenia guardado con el viejo — Instalaciones fija, nombres, ocultos — quedaba apuntando a un
    chat "dormido" sin buzon). Si no es viejo de nadie, devuelve el mismo."""
    for s in catalogo()["sesiones"].values():
        if cli_sid in s.get("previos", ()):
            return s["cli"]
    return cli_sid


def previos_de(cli_sid):
    return next((s.get("previos") or [] for s in catalogo()["sesiones"].values() if s["cli"] == cli_sid), [])


def enlace(cli_sid, archivados=False):
    """Enlace que abre esa sesion en la app de Claude (claude://…/local_xxx), o None si no esta en la app.
    (22-oct) archivados=True la busca tambien entre los chats archivados (el Medidor puede estar archivado)."""
    for local, s in catalogo()["sesiones"].items():
        if s["cli"] == cli_sid:
            return "claude://claude.ai/epitaxy/" + local
    if archivados:
        for ruta in glob.glob(os.path.join(APP, "claude-code-sessions", "*", "*", "local_*.json")):
            d = _sesion(ruta)
            if d and d.get("isArchived") and d.get("cliSessionId") == cli_sid and d.get("sessionId"):
                return "claude://claude.ai/epitaxy/" + d["sessionId"]
    return None


def local_de(cli_sid):
    """(22-oct) id de la app (local_…) de un chat a partir del de los hooks: lo que piden archive/unarchive_session."""
    for local, s in catalogo()["sesiones"].items():
        if s["cli"] == cli_sid or cli_sid in s.get("previos", ()):
            return local
    return None


def archivados(maximo=30):
    """(22-oct) [{local, titulo, actividad}] de los chats ARCHIVADOS en la app, el mas reciente primero."""
    out, activos = [], set()
    for ruta in glob.glob(os.path.join(APP, "claude-code-sessions", "*", "*", "local_*.json")):
        d = _sesion(ruta)
        if not d or not d.get("sessionId"):
            continue
        if not d.get("isArchived"):
            activos.add((d.get("title") or "").strip().lower())
            continue
        out.append({"local": d["sessionId"], "titulo": d.get("title") or "Chat", "actividad": d.get("lastActivityAt") or 0,
                    "carpeta": os.path.basename((d.get("cwd") or "").rstrip("\\/"))})
    # (22-oct) un archivado puede llamarse igual que un chat ACTIVO (sesion vieja del mismo tema): se avisa
    for x in out:
        x["duplicado"] = x["titulo"].strip().lower() in activos
    return sorted(out, key=lambda x: -x["actividad"])[:maximo]


def archivado(cli_sid):
    """(22-oct) True/False si la app tiene ese chat archivado; None si no lo encuentra."""
    for ruta in glob.glob(os.path.join(APP, "claude-code-sessions", "*", "*", "local_*.json")):
        d = _sesion(ruta)
        if d and d.get("cliSessionId") == cli_sid:
            return bool(d.get("isArchived"))
    return None


def sesiones_de(seleccion):
    """[(cliSessionId, titulo)] de la seleccion (un grupo o favoritos), lo mas reciente primero."""
    c = catalogo()
    if seleccion == "favoritos":
        elegidas = [s for k, s in c["sesiones"].items() if k in c["favoritos"]]
    elif str(seleccion).startswith("g:"):
        elegidas = [s for s in c["sesiones"].values() if s["grupo"] == seleccion[2:]]
    else:
        return []
    return [(s["cli"], s["titulo"]) for s in sorted(elegidas, key=lambda s: -s["actividad"])]


def sesiones_en(carpetas):
    """(14-oct) [(cliSessionId, titulo, carpeta)] de TODAS las sesiones (no archivadas) cuya carpeta es una de
    `carpetas` o esta dentro: asi cada chat nuevo que abras en una carpeta personal aparece solo."""
    norm = lambda p: os.path.normcase(os.path.normpath(p or "")).rstrip("\\/")
    raices = [(norm(c), c) for c in carpetas]
    out = []
    for s in sorted(catalogo()["sesiones"].values(), key=lambda s: -s["actividad"]):
        cwd = norm(s.get("cwd"))
        raiz = next((orig for r, orig in raices if cwd == r or cwd.startswith(r + os.sep)), None)
        if raiz:
            out.append((s["cli"], s["titulo"], s.get("cwd") or raiz))
    return out
