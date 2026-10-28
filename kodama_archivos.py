# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Archivos que un chat menciona o manda: cuales se pueden ver desde el celular, la pestana Archivos, la
limpieza de lo que se acumula y las fotos y videos que llegan por Telegram.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import hashlib
import html as _html
import json
import os
import random
import re as _re
import secrets
import time

import config
import grupos_app
import kodama_plataforma as plataforma
from kodama_plataforma import a_papelera
from kodama_nucleo import COLA, CONSERVAR_JSON, FOTOS, log
from kodama_chats import cwd_de, todos_elegidos


_IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _archivos_de(it):
    """(27-oct) Archivos que un chat te manda con SendUserFile: (caption, [ruta]). Los eventos nuevos los traen en `archivos` y
    `caption` (companero_hook.py); los de antes solo en el texto ("caption\\n\\n`ruta`\\n`ruta`"), se leen de ahi."""
    rutas, cap = it.get("archivos"), it.get("caption")
    if not isinstance(rutas, list):
        lineas, rutas = (it.get("texto") or "").split("\n"), []
        while lineas:
            m = _re.fullmatch(r"`(.+)`", lineas[-1].strip())
            if not m:
                break
            rutas.insert(0, m.group(1)); lineas.pop()
        cap = "\n".join(lineas).strip()
    return str(cap or "").strip()[:2000], [r for r in rutas if isinstance(r, str) and r.strip()][:12]


def _ficha_archivo(ruta):
    """{r: ruta, n: nombre, t: img|otro, ok: se puede abrir desde el celular}. `ok` usa EXACTAMENTE ver_permitido (la misma
    seguridad que el visor /abrir y /ver): si no pasa, la app muestra el nombre sin miniatura ni enlace."""
    ext = os.path.splitext(ruta)[1].lower()
    try:
        ok = bool(ver_permitido(ruta))
    except Exception:
        ok = False
    return {"r": ruta, "n": os.path.basename(ruta.replace("\\", "/")) or ruta, "t": "img" if ext in _IMG_EXT else "otro", "ok": ok}


VER_TIPOS = {".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
             ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon",
             ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp4": "video/mp4", ".webm": "video/webm",
             ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf"}
_SALTAR = {"node_modules", ".venv", "venv", ".git", "target", "dist", "build", "__pycache__", ".claude", "site-packages"}
_ARCH = {"t": 0, "raices": {}, "lista": []}


def raices_archivos():
    """{id: (carpeta, nombre)}. Memo de 30 s."""
    if time.time() - _ARCH["t"] < 30:
        return _ARCH["raices"]
    out = {}

    def agregar(c, n):
        c = os.path.normpath(c)
        if os.path.isdir(c):
            out.setdefault(hashlib.sha1(c.lower().encode()).hexdigest()[:10], (c, n))
    try:
        for cli, titulo, cwd in grupos_app.sesiones_en(config.RAICES):
            if cli in config.OCULTAR or config.es_personal(config.clave_carpeta(cwd)) is False:
                continue
            agregar(cwd, os.path.basename(os.path.normpath(cwd)))
    except Exception as e:
        log(f"archivos: {e}")
    for x in config.CARPETAS_ARCHIVOS:
        agregar(x["carpeta"], x.get("nombre") or os.path.basename(os.path.normpath(x["carpeta"])))
    _ARCH["raices"] = out
    return out


def listar_archivos(dias=45, tope=80):
    """[{raiz, ruta, nombre, titulo, carpeta, ts}] de los .html recientes, el mas nuevo primero (hasta 4 niveles)."""
    raices = raices_archivos()
    if _ARCH.get("lt") and time.time() - _ARCH["lt"] < 30:
        return _ARCH["lista"]
    desde, out = time.time() - dias * 86400, []
    for rid, (base, nombre) in raices.items():
        prof0 = base.rstrip("\\/").count(os.sep)
        for raiz, dirs, archivos in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _SALTAR and not d.startswith(".")]
            if raiz.count(os.sep) - prof0 >= 4:
                dirs[:] = []
            for a in archivos:
                if not a.lower().endswith((".html", ".htm")):
                    continue
                ruta = os.path.join(raiz, a)
                try:
                    ts = os.path.getmtime(ruta)
                except OSError:
                    continue
                if ts >= desde:
                    out.append({"raiz": rid, "ruta": os.path.relpath(ruta, base).replace("\\", "/"), "nombre": a,
                                "carpeta": nombre, "ts": ts, "_abs": ruta})
    out.sort(key=lambda x: -x["ts"])
    out = out[:tope]
    for x in out:   # el <title> de la pagina, si tiene: es mas claro que el nombre del archivo
        try:
            m = _re.search(r"<title[^>]*>([^<]{1,120})</title>", open(x["_abs"], encoding="utf-8", errors="ignore").read(6000), _re.I)
            x["titulo"] = _html.unescape(m.group(1)).strip() if m else ""
        except OSError:
            x["titulo"] = ""
        del x["_abs"]
    _ARCH.update(lista=out, lt=time.time())
    return out


VER_TIPOS[".pdf"] = "application/pdf"
HOME_N = os.path.realpath(os.path.normpath(config.HOME))
_TEMP_CLAUDE = plataforma.temp_claude_relativa()


def ver_permitido(archivo):
    """(14-oct) un archivo que un chat menciona se puede abrir desde el celular si: esta dentro de tu carpeta de
    usuario, es un tipo de pagina web/imagen/pdf, ninguna carpeta del camino empieza con "." (.ssh, .aws,
    .claude…) y, dentro de AppData, solo los scratchpads de Claude. Devuelve la ruta relativa a HOME o None."""
    try:
        archivo = os.path.realpath(os.path.normpath(archivo))   # (auditoria) sin alias 8.3 ni junctions/symlinks
    except (OSError, ValueError):
        return None
    if os.path.splitext(archivo)[1].lower() not in VER_TIPOS:
        return None
    if not os.path.normcase(archivo).startswith(os.path.normcase(HOME_N) + os.sep):
        return None
    rel = os.path.relpath(archivo, HOME_N)
    partes = rel.split(os.sep)
    # (27-oct, dueño) las rutas EXACTAS que un chat mando con SendUserFile (las que el hook anoto en la cola) tambien se
    # pueden abrir, aunque esten en una carpeta con "." (.claude\...\tool-results) o fuera de las carpetas de chats
    # (Apps\companero\animacion). Solo ESA ruta (no la carpeta ni sus vecinos), mismas extensiones, y NUNCA estado\.
    if os.path.normcase(archivo) in _enviados() and not _en_estado(archivo):
        return rel if os.path.isfile(archivo) else None
    if any(p.startswith(".") or p == ".." for p in partes):
        return None
    # (15-oct, contra #7) ademas, dentro de la carpeta de algun chat de la app (o carpetas_archivos, o los scratchpads
    # de Claude): ya no cualquier lugar de tu carpeta de usuario
    if not partes[0].lower() == plataforma.carpeta_datos_usuario().lower() and not any(
            os.path.normcase(archivo).startswith(os.path.normcase(r) + os.sep) for r in raices_links()):
        return None
    if partes[0].lower() == plataforma.carpeta_datos_usuario().lower() and not os.path.normcase(rel).startswith(_TEMP_CLAUDE + os.sep):
        return None
    return rel if os.path.isfile(archivo) else None


_ESTADO_N = os.path.normcase(os.path.realpath(os.path.normpath(config.ESTADO)))
_ENV = {"firma": None, "t": 0, "v": frozenset()}


def _en_estado(archivo):
    """True si la ruta esta dentro de estado\\ (claves, tokens, registros): jamas se abre, ni siquiera si un chat la "mando"."""
    n = os.path.normcase(os.path.realpath(os.path.normpath(archivo)))
    return n == _ESTADO_N or n.startswith(_ESTADO_N + os.sep)


def _enviados():
    """(27-oct) Rutas EXACTAS (realpath, normcase) que algun chat mando con SendUserFile: los eventos "Archivo" de la cola (y la
    rotada .1), que escribe companero_hook.py. Memo: se relee solo si la cola cambio (tamano/fecha)."""
    rutas = [COLA + ".1", COLA]
    try:
        firma = tuple((os.path.getsize(r), os.path.getmtime(r)) if os.path.exists(r) else None for r in rutas)
    except OSError:
        return _ENV["v"]
    if firma == _ENV["firma"]:
        return _ENV["v"]
    out = set()
    for r in rutas:
        if not os.path.exists(r):
            continue
        try:
            with open(r, encoding="utf-8", errors="replace") as f:
                for l in f:
                    if '"Archivo"' not in l:
                        continue
                    try:
                        it = json.loads(l)
                    except Exception:
                        continue
                    if it.get("evento") != "Archivo":
                        continue
                    for ruta in _archivos_de(it)[1]:
                        if os.path.isabs(ruta):
                            out.add(os.path.normcase(os.path.realpath(os.path.normpath(ruta))))
        except OSError:
            continue
    _ENV.update(firma=firma, v=frozenset(out))
    return _ENV["v"]


_RL = {"t": 0, "v": []}


def raices_links():
    """Carpetas desde donde se puede abrir un archivo nombrado en un mensaje: la de cada chat de la app (personales,
    fijos y del grupo elegido) + config "carpetas_archivos". Memo de 60 s."""
    if time.time() - _RL["t"] < 60:
        return _RL["v"]
    out = set()
    try:
        c = grupos_app.catalogo()
        clis = set(todos_elegidos())
        for s in c["sesiones"].values():
            if s["cli"] in clis and s.get("cwd"):
                out.add(os.path.realpath(os.path.normpath(s["cwd"])))
    except Exception:
        pass
    for rid, (base, _n) in raices_archivos().items():
        out.add(os.path.realpath(base))
    out.discard(HOME_N)   # nunca la carpeta de usuario entera
    _RL.update(t=time.time(), v=sorted(out))
    return _RL["v"]


def carpeta_medios(cmd):
    """(16-oct, LShinox) lo que mandas desde el celular va a la carpeta DEL CHAT (<carpeta del chat>\\del-celular), no a
    estado\\fotos: ahi queda para siempre y el chat lo encuentra junto a su trabajo. Sin carpeta conocida: estado\\fotos."""
    cwd = cwd_de(cmd) if cmd else None
    return os.path.join(cwd, "del-celular") if cwd and os.path.isdir(cwd) else FOTOS


# ---- (16-oct, LShinox) Ajustes > Espacio: revisar lo que guardo el Companero y mandar a la Papelera lo que ya no se usa.
# Solo estas carpetas: <carpeta de cada chat>\del-celular, estado\fotos y respaldos\ (nunca el codigo ni el estado vivo).
LIMPIEZA = {"ids": {}}


def conservar():
    """(16-oct, LShinox) Ajustes > "Conservar siempre los archivos": apagado por defecto. Prendido, la revision no marca
    nada para borrar y las fotos temporales no se borran solas a los 14 dias."""
    try:
        return bool(json.load(open(CONSERVAR_JSON, encoding="utf-8")).get("conservar"))
    except (OSError, ValueError, AttributeError):
        return False


def raices_limpieza():
    out = [(FOTOS, "Kodama · fotos temporales", 7), (config.RESPALDOS, "Kodama · respaldos", 30)]
    vistos = set()
    try:
        for s in grupos_app.catalogo()["sesiones"].values():
            cwd = s.get("cwd")
            if cwd and os.path.normcase(cwd) not in vistos:
                vistos.add(os.path.normcase(cwd))
                d = os.path.join(cwd, "del-celular")
                if os.path.isdir(d):
                    out.append((d, os.path.basename(os.path.normpath(cwd)) + " · del celular", 30))
    except Exception:
        pass
    return out


def escanear_limpieza():
    """Todos los archivos de esas carpetas, el mas pesado primero. Recomienda borrar lo que no se toco hace mas de N dias
    (7 en fotos temporales, 30 en el resto). El celular solo recibe un id por archivo, nunca la ruta para borrar."""
    ahora, archivos, ids, guardar = time.time(), [], {}, conservar()
    for raiz, etiqueta, dias in raices_limpieza():
        dias = float("inf") if guardar else dias
        for base, dirs, fs in os.walk(raiz):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in fs:
                p = os.path.join(base, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                edad = (ahora - max(st.st_mtime, st.st_atime if st.st_atime <= ahora else 0)) / 86400
                i = secrets.token_hex(8); ids[i] = p
                archivos.append({"id": i, "nombre": f, "donde": etiqueta, "bytes": st.st_size, "dias": int(edad),
                                 "recomendado": edad > dias,
                                 "motivo": (f"sin usar hace {int(edad)} días" if edad > dias else "")})
    archivos.sort(key=lambda a: -a["bytes"])
    LIMPIEZA["ids"] = ids
    return {"archivos": archivos[:500], "total": sum(a["bytes"] for a in archivos), "cuantos": len(archivos), "conservar": guardar}


def borrar_limpieza(ids):
    raices = [os.path.normcase(os.path.realpath(r)) + os.sep for r, _, _ in raices_limpieza()]
    hechos, fallos, liberado = 0, 0, 0
    for i in ids:
        p = LIMPIEZA["ids"].get(i)
        if not p:
            fallos += 1; continue
        real = os.path.normcase(os.path.realpath(p))
        if not any(real.startswith(r) for r in raices) or not os.path.isfile(p):   # solo dentro de esas carpetas
            fallos += 1; continue
        try:
            tam = os.path.getsize(p)
        except OSError:
            tam = 0
        if a_papelera(p):
            hechos += 1; liberado += tam; LIMPIEZA["ids"].pop(i, None)
        else:
            fallos += 1
    log(f"limpieza: {hechos} archivos a la papelera ({liberado // (1024 * 1024)} MB), {fallos} sin poder")
    return {"hechos": hechos, "fallos": fallos, "liberado": liberado}


def guardar_foto(datos, ext=".jpg", carpeta=None):
    carpeta = carpeta or FOTOS
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, time.strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}{ext}")
    open(ruta, "wb").write(datos)
    return os.path.normpath(ruta)


def texto_con_foto(ruta, texto):
    return (f"Te mandé una foto (captura) desde el celular; está en: {ruta} — abrila con la herramienta Read para verla."
            + (f"\n\n{texto}" if texto else ""))


# (16-oct) videos desde el celular: tipo que manda el navegador -> extension. Quedan en estado\fotos (se borran a los 14 dias)
VIDEO_TIPOS = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "video/3gpp": ".3gp", "video/x-m4v": ".m4v"}
VIDEO_MAX = 5 * 1024 * 1024 * 1024   # (16-oct, LShinox) 5 GB


def texto_con_video(ruta, texto):
    aviso = (" (esa carpeta se borra a los 14 días: si lo vas a usar, copialo a tu carpeta)"
             if os.path.normcase(os.path.dirname(ruta)) == os.path.normcase(os.path.normpath(FOTOS)) else "")
    return f"Te mandé un video desde el celular; está en: {ruta}{aviso}." + (f"\n\n{texto}" if texto else "")
