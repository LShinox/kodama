# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Historial de cada chat para la app (mensajes, fase, contexto, pasos) y las estadisticas de "Lo nuevo".

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import re as _re
import time

import config
import grupos_app
from kodama_nucleo import (
    BASE, COLA, COLORES_JSON, ELEGIDOS, FASE_DIR, GRUPOS_JSON, PERMISOS, PUENTE, RESP, SES, SILENCIO, WEB,
    _leer_json, leer_ultimas
)
from kodama_texto import _SECRETOS, clasificar
from kodama_chats import (
    _silencios, colores_app, elegidos, grupos_propios, info, mirando_chat, seleccion, sesiones, todos_elegidos,
    todos_los_chats
)
from kodama_permisos import permisos_pendientes
from kodama_medidor import _EST, uso_plan
from kodama_archivos import _archivos_de, _ficha_archivo


def _msg_hist(it, yo):
    """Un mensaje del historial tal como lo recibe la app (cola o respuestas)."""
    m = {"ts": it["ts"], "texto": _SECRETOS.sub("[clave oculta]", it["texto"][:6000]),
         "yo": yo or it.get("evento") == "UserPromptSubmit", "evento": it.get("evento", "Stop")}
    if m["evento"] == "Archivo":   # (27-oct) rutas + caption, sin copiar el archivo: la app arma miniaturas y enlaces
        cap, rutas = _archivos_de(it)
        if rutas:
            m["caption"] = _SECRETOS.sub("[clave oculta]", cap)
            m["archivos"] = [_ficha_archivo(r) for r in rutas]
    return m


def mensajes_anteriores(cmd, antes, n=30):
    """(14-oct) Los n mensajes de ese chat anteriores a `antes` (de la cola y tus respuestas, incluidos los .1 rotados)."""
    ses = {s["session_id"]: s for s in sesiones()}
    out = []
    for ruta, yo in ((COLA, False), (RESP, True)):
        for r in (ruta + ".1", ruta):
            if not os.path.exists(r):
                continue
            for l in open(r, encoding="utf-8"):
                try:
                    it = json.loads(l)
                except Exception:
                    continue
                if it.get("ts", 0) >= antes or it.get("evento", "Stop") not in ("Stop", "Notification", "yo", "UserPromptSubmit", "Archivo"):
                    continue
                c = it.get("chat") if yo else (info(ses.get(it.get("session_id"))) or (None,))[0]
                if c == cmd:
                    out.append(_msg_hist(it, yo))
    return sorted(sin_duplicados(out), key=lambda m: m["ts"])[-n:]


_DE_SISTEMA = _re.compile(r"\s*(<(task-notification|system-reminder|cross-session-message|local-command|command-name|"
                          r"command-message)\b|\[SYSTEM NOTIFICATION|Another Claude session sent a message)")


def sin_duplicados(msgs):
    """(15-oct) lo que mandas desde el celular o la mascota ya esta como "tuyo"; si Claude Code ademas lo registro como
    mensaje escrito en el chat (mismo texto, < 3 min), se muestra una sola vez. (16-oct) Tambien se sacan los avisos del
    sistema que quedaron guardados como si los hubieras escrito (fin de un subagente, mensajes de otro chat)."""
    mios = [m for m in msgs if m.get("evento") == "yo"]
    def repetido(m):
        if m.get("evento") != "UserPromptSubmit":
            return False
        if _DE_SISTEMA.match(m["texto"]):
            return True
        t = " ".join(m["texto"].split())
        return any(abs(m["ts"] - r["ts"]) < 180 and " ".join(r["texto"].split())[:200] in t for r in mios)
    return [m for m in msgs if not repetido(m)]


_USO = {}


def contexto_chat(cmd):
    """(15-oct) cuanto contexto lleva el chat: tokens de entrada del ultimo turno (entrada + cache) del transcript,
    sobre la ventana del modelo (1M si el modelo es de 1M, si no 200k). {"tokens", "max", "pct", "modelo"} o None."""
    cli = next((c for c, v in todos_elegidos().items() if v[0] == cmd), None)
    s = next((x for x in grupos_app.catalogo()["sesiones"].values() if x["cli"] == cli), None) if cli else None
    if not s or not s.get("cwd"):
        return None
    tr = os.path.join(config.HOME, ".claude", "projects", config.clave_carpeta(s["cwd"]), cli + ".jsonl")
    try:
        with open(tr, "rb") as f:
            f.seek(max(0, os.path.getsize(tr) - 400000)); cola = f.read().decode("utf-8", "ignore")
    except OSError:
        return None
    usos = [m for m in _re.finditer(r'"usage"\s*:\s*\{\s*"input_tokens"', cola)]   # trae objetos anidados: se mira un tramo
    if not usos:
        return None
    u = cola[usos[-1].start():usos[-1].start() + 700]
    n = lambda k: int((_re.search(r'"%s"\s*:\s*(\d+)' % k, u) or [0, 0])[1])
    tokens = n("input_tokens") + n("cache_creation_input_tokens") + n("cache_read_input_tokens")
    modelo = (list(_re.finditer(r'"model"\s*:\s*"([^"]+)"', cola)) or [None])[-1]
    modelo = modelo.group(1) if modelo else ""
    # (30-oct) los modelos actuales (4.6 en adelante, 5.x) traen 1M y el transcript no lo marca: 200k solo para los viejos
    viejo = _re.search(r"claude-(?:instant|2|3)|(?:opus|sonnet|haiku)-4-[0-5](?!\d)", modelo.lower())
    maximo = 200_000 if (viejo and "1m" not in modelo.lower() and tokens <= 200_000) else 1_000_000
    return {"tokens": tokens, "max": maximo, "pct": round(tokens * 100 / maximo, 1), "modelo": modelo}


def pasos_chat(cmd, turnos=15):
    """(19-oct, idea de jinbe/deck; LShinox: "lo que hace y no hace el chat", como "Ejecutó 3 comandos, leyó x…" de la
    app de Claude) Los pasos (herramientas) de los ultimos turnos del chat, leidos de su transcript (solo el final, sin
    gastar plan). Un turno = desde un mensaje tuyo hasta el siguiente. [{"fin": ts del ultimo paso, "pasos": [{h, d}]}]"""
    cli = next((c for c, v in todos_elegidos().items() if v[0] == cmd), None)
    s = next((x for x in grupos_app.catalogo()["sesiones"].values() if x["cli"] == cli), None) if cli else None
    if not s or not s.get("cwd"):
        return []
    tr = os.path.join(config.HOME, ".claude", "projects", config.clave_carpeta(s["cwd"]), cli + ".jsonl")
    try:
        with open(tr, "rb") as f:
            f.seek(max(0, os.path.getsize(tr) - 1_500_000)); lineas = f.read().decode("utf-8", "ignore").splitlines()[1:]
    except OSError:
        return []
    out, actual = [], None
    for l in lineas:
        try:
            x = json.loads(l)
        except ValueError:
            continue
        msg, tipo = x.get("message") or {}, x.get("type")
        cont = msg.get("content")
        if tipo == "user" and (isinstance(cont, str) or any(isinstance(c, dict) and c.get("type") == "text" for c in (cont or []))):
            if actual and actual["pasos"]:
                out.append(actual)
            actual = {"fin": 0, "pasos": []}
            continue
        if tipo != "assistant" or not isinstance(cont, list) or actual is None:
            continue
        for c in cont:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                i = c.get("input") or {}
                d = (i.get("description") or i.get("file_path") or i.get("path") or i.get("pattern") or i.get("query")
                     or i.get("url") or i.get("command") or i.get("prompt") or "")
                d = _SECRETOS.sub("[clave oculta]", str(d)).replace("\n", " ")
                actual["pasos"].append({"h": c.get("name") or "?", "d": d[:140]})
                try:
                    import datetime
                    actual["fin"] = datetime.datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
    if actual and actual["pasos"]:
        out.append(actual)
    return out[-turnos:]


_HIST = {"firma": None, "t": 0, "v": None}


def firma_estado():
    """Fechas de los archivos de los que sale el estado (sin leerlos). Si no cambian, el estado tampoco."""
    f = []
    for r in (COLA, RESP, SILENCIO, ELEGIDOS, PERMISOS, PUENTE, os.path.join(BASE, "uso.json"), COLORES_JSON, config.OCULTOS_JSON, GRUPOS_JSON):
        try:
            f.append(os.path.getmtime(r))
        except OSError:
            f.append(0)
    try:
        f.append(max((e.stat().st_mtime for e in os.scandir(SES)), default=0))
    except OSError:
        f.append(0)
    try:   # (27-oct) estado\fase\: "pensando" / "ejecutando"
        f.append(max((e.stat().st_mtime for e in os.scandir(FASE_DIR)), default=0))
    except OSError:
        f.append(0)
    # (19-oct) el uso del plan (estimado cada 60 s) tambien cuenta: antes el celular no lo veia cambiar si ningun chat
    # escribia nada (el SSE solo manda cuando cambia la firma)
    u = _EST.get("v") or {}
    # (27-oct) con algun chat "ejecutando", la firma cambia cada 15 s: asi el celular se entera de que a los 60 s volvio a "pensando"
    hv = _HIST.get("v") or {}
    ejec = any(isinstance(d, dict) and d.get("fase") == "ejecutando" for d in hv.values())
    return (tuple(f), seleccion(), round(((u.get("5h") or {}).get("pct") or 0)), round(((u.get("semana") or {}).get("pct") or 0)),
            int(time.time() // 15) if ejec else 0)


def historial():
    """(14-oct, rendimiento) Cache: solo se recalcula si cambio algun archivo o pasaron 20 s (por los "hace N min" y
    las caducidades). Antes se rearmaba entero cada 4 s por la mascota y cada cambio por el celular."""
    f = firma_estado()
    if _HIST["v"] is None or _HIST["firma"] != f or time.time() - _HIST["t"] >= 20:
        _HIST.update(firma=f, t=time.time(), v=_historial())
    v = _HIST["v"]
    # (14-oct) el chat que estas mirando en la app de Claude (cambia rapido: va fuera del cache)
    cli = mirando_chat()
    cmd = (elegidos().get(cli) or (None,))[0] if cli else None
    return dict(v, _mirando=cmd) if cmd else v


FASE_EJEC_SEG = 60                      # (27-oct) sin PostToolUse, "ejecutando" vuelve solo a "pensando" a los 60 s
FASE_TOL_SEG = 2                       # (28-oct) la hora del hook va redondeada a 0.01 s (hasta 5 ms "en el futuro") y en Windows el reloj avanza a saltos de ~16 ms
FASE_TIPOS = ("comando", "web", "subagente", "herramienta")


def fase_parse(txt, ahora=None):
    """"fase|categoria|ts" (lo escriben companero_hook_pre.py y companero_hook.py) -> ("pensando"|"ejecutando"|None, categoria|None).
    "ejecutando" sin un PostToolUse que lo cierre vuelve solo a "pensando" a los 60 s."""
    try:
        fase, cat, ts = (txt or "").strip().split("|")
        ts = float(ts)
    except ValueError:
        return None, None
    ahora = time.time() if ahora is None else ahora
    if fase == "ejecutando" and -FASE_TOL_SEG <= ahora - ts <= FASE_EJEC_SEG:
        return "ejecutando", (cat if cat in FASE_TIPOS else "herramienta")
    return ("pensando", None) if fase in ("pensando", "ejecutando") else (None, None)


def fase_de(s, ahora=None):
    """(27-oct, idea de clawd #1018) fase de un registro de sesion. Solo mientras el chat trabaja."""
    sid = (s or {}).get("session_id") or ""
    if not sid or len(sid) > 80 or not sid.replace("-", "").replace("_", "").isalnum() or s.get("estado") != "trabajando":
        return None, None
    try:
        with open(os.path.join(FASE_DIR, sid + ".txt"), encoding="utf-8") as f:
            return fase_parse(f.read(200), ahora)
    except OSError:
        return None, None


def _historial():
    """Por chat: estado, ultimo visto y ultimos 30 mensajes (del chat y tuyos)."""
    col, gr = colores_app(), grupos_propios()
    out = {cmd: {"mensajes": [], "nombre": nombre, "emoji": emo, "color": col.get(cmd) or config.COLORES.get(cmd),
                 "grupo": gr.get(cmd, "")} for cmd, nombre, emo in todos_los_chats()}
    ses = {s["session_id"]: s for s in sesiones()}
    for cmd in out:
        cands = [s for s in ses.values() if info(s)[0] == cmd]
        if cands:
            s = max(cands, key=lambda x: x.get("visto", 0))
            out[cmd].update(estado=s.get("estado"), visto=s.get("visto"), titulo=s.get("titulo"),
                            abrir=grupos_app.enlace(s.get("session_id")))   # (14-oct) abrir ese chat en la app de Claude
            try:   # (14-oct) el chat te esta esperando en el puente: tu respuesta (mascota/celular) cuenta como tuya
                esp = os.path.join(PUENTE, s.get("session_id", "") + ".esperando")
                if time.time() - os.path.getmtime(esp) < 540:
                    out[cmd]["esperando"] = os.path.getmtime(esp)
            except OSError:
                pass
            pend = permisos_pendientes().get(s.get("session_id"))
            if pend:
                out[cmd]["permiso"] = pend   # (14-oct) pedido de permiso esperando: Permitir / Denegar en la app
            if s.get("estado") == "trabajando" and time.time() - s.get("haciendo_ts", 0) < 180:
                out[cmd]["haciendo"] = s.get("haciendo")   # (14-oct) "editando x.py", "leyendo y.md"…
            fz, ft = fase_de(s)   # (27-oct) "pensando" / "ejecutando" + categoria (comando, web, subagente, herramienta)
            if fz:
                out[cmd]["fase"] = fz
                if ft:
                    out[cmd]["fase_tipo"] = ft
            # (26-oct) progreso "3 de 7" (lo escribe companero_hook.py con TaskCreate/TaskUpdate): solo conteos y el asunto de la
            # tarea en curso. Una lista ya terminada hace >30 min, o sin tocar hace >6 h, no se muestra.
            # (30-oct) Regla: se muestra la lista que todavia no esta completa solo si el chat esta "trabajando" y se toco hace
            # <6 h (una a medias en un chat que ya termino, p. ej. "0/2" con Claude sin marcar sus tareas, no queda para siempre).
            # La lista completa se muestra un destello de hasta 30 min en cualquier estado, y luego se oculta, aunque el chat trabaje.
            tz = s.get("tareas")
            if isinstance(tz, dict) and isinstance(tz.get("t"), int) and tz["t"] > 0:
                edad = time.time() - float(tz.get("ts") or 0)
                if (edad < 6 * 3600 and not (tz.get("h", 0) >= tz["t"] and edad > 1800)
                        and (s.get("estado") == "trabajando" or tz.get("h", 0) >= tz["t"])):
                    out[cmd]["tareas"] = {"h": int(tz.get("h") or 0), "t": tz["t"], "a": _SECRETOS.sub("[clave oculta]", str(tz.get("a") or ""))[:80]}
    for cmd, d in out.items():   # "trabajando" sin ningun evento en 90 min: probablemente se interrumpio el turno (Stop no corre)
        if d.get("estado") == "trabajando" and time.time() - (d.get("visto") or 0) > 5400:
            d["estado"] = "reposo"
    for ruta, yo in ((COLA, False), (RESP, True)):
        if not os.path.exists(ruta) and not os.path.exists(ruta + ".1"):
            continue
        for l in leer_ultimas(ruta):
            try:
                it = json.loads(l)
            except Exception:
                continue
            cmd = it.get("chat") if yo else (info(ses.get(it.get("session_id"))) or (None,))[0]
            if cmd in out and it.get("evento", "Stop") in ("Stop", "Notification", "yo", "UserPromptSubmit", "Archivo"):
                # (15-oct) "UserPromptSubmit" = lo que escribiste directo en la app de Claude de la PC: va como tuyo
                out[cmd]["mensajes"].append(_msg_hist(it, yo))
    for cmd, d in out.items():
        d["mensajes"] = sorted(sin_duplicados(d["mensajes"]), key=lambda m: m["ts"])[-30:]
        chat_msgs = [m for m in d["mensajes"] if not m["yo"] and m.get("evento") != "Archivo"]
        d["ultimo_ts"] = chat_msgs[-1]["ts"] if chat_msgs else 0
        if chat_msgs:
            d["tipo"], d["n"], d["linea"] = clasificar(chat_msgs[-1]["evento"], chat_msgs[-1]["texto"])
        else:
            d["tipo"], d["n"], d["linea"] = None, 0, ""
    # version de la app = ultima modificacion de los archivos web: si cambia, el iPhone se recarga solo
    sil = _silencios()
    for cmd, d in out.items():
        d["silencio"] = sil.get(cmd, 0)   # hasta cuando esta silenciado (0 = no)
    uso = uso_plan()
    if uso:
        out["_uso"] = uso
    out["_seleccion"] = seleccion()
    out["_version"] = str(int(max(os.path.getmtime(os.path.join(WEB, f)) for f in os.listdir(WEB))))
    return out


_STATS = {"t": 0.0, "v": None}


def estadisticas_semana():
    """(26-oct) "Lo nuevo": numeros de los ultimos 7 dias sacados de la cola de avisos y de respuestas.jsonl (y sus .1).
    SOLO conteos: cada linea se lee, se cuenta y se descarta; ningun texto de mensajes sale de aqui. Memo de 2 min."""
    if _STATS["v"] is not None and time.time() - _STATS["t"] < 120:
        return _STATS["v"]
    desde = time.time() - 7 * 86400
    avisos, chats, resp, resp_cel = 0, set(), 0, 0
    for ruta, es_resp in ((COLA + ".1", False), (COLA, False), (RESP + ".1", True), (RESP, True)):
        if not os.path.exists(ruta):
            continue
        try:
            with open(ruta, encoding="utf-8", errors="replace") as f:
                for l in f:
                    try:
                        it = json.loads(l)
                    except ValueError:
                        continue
                    if not isinstance(it, dict) or float(it.get("ts") or 0) < desde:
                        continue
                    if es_resp:
                        resp += 1
                        resp_cel += it.get("via") in ("celular", "telegram")
                    else:
                        avisos += it.get("evento") in ("Stop", "Notification")
                        if it.get("session_id"):
                            chats.add(it["session_id"])
        except OSError:
            continue
    _STATS.update(t=time.time(), v={"avisos": int(avisos), "respuestas": int(resp), "respuestas_celular": int(resp_cel), "chats": len(chats)})
    return _STATS["v"]


def lo_nuevo():
    """Version instalada + sus novedades (web\\lo-nuevo.json: version -> {es: [...], en: [...]}) + estadisticas locales."""
    cambios = (_leer_json(os.path.join(WEB, "lo-nuevo.json"), {}).get(config.VERSION))
    return {"version": config.VERSION, "cambios": cambios if isinstance(cambios, dict) else None, "stats": estadisticas_semana()}
