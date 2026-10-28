# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Hub del companero (etapa 1, 13-oct-2026): puente Telegram <-> 3 chats personales.

- Lee la cola que deja companero_hook.py y manda a Telegram lo que el chat le escribio a LShinox.
- Lo que LShinox responde en Telegram lo entrega en el buzon de ese chat (cross-session messaging).
- Solo atiende al chat de Telegram emparejado con /start <codigo>. Nunca escribe el token en logs.

Comandos en Telegram: /start <codigo>, /estado, /siempre, /ausente, /juegos|/musica|/dnd <texto>.
Para responder: deslizar (responder) sobre el mensaje del chat, o usar el comando del chat.
"""
import ctypes
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
BASE = config.ESTADO
SES = os.path.join(BASE, "sesiones")
COLA = os.path.join(BASE, "cola.jsonl")
CONF = os.path.join(BASE, "hub.json")
LOG = os.path.join(BASE, "hub.log")
TOKEN_FILE = config.TOKEN_TELEGRAM

CHATS = config.CHATS   # carpeta del proyecto -> (comando, nombre, emoji); sale de config.json (14-oct)
def extras():
    try:
        return {k: tuple(v) for k, v in json.load(open(os.path.join(BASE, "sesiones_extra.json"), encoding="utf-8")).items()}
    except Exception:
        return {}


# ---- que chats van al celular (14-oct): "Personales" (los de siempre) o un grupo / los favoritos de la app de Claude ----
import grupos_app
ELEGIDOS = os.path.join(BASE, "elegidos.json")   # lo lee el hook: de que sesiones guardar los mensajes


_SEL = []


def seleccion():
    if not _SEL:
        try:
            _SEL.append(json.load(open(CONF, encoding="utf-8")).get("seleccion", "personales"))
        except Exception:
            _SEL.append("personales")
        if _SEL[0] not in [o["id"] for o in grupos_app.opciones()]:   # p. ej. grupos de la app apagados en config
            _SEL[0] = "personales"
    return _SEL[0]


def cambiar_seleccion(sel):
    """sel: "personales", "favoritos" o "g:<id de grupo>". Devuelve el nombre o None si no existe.
    Se puede llamar desde el hilo web: el bucle principal guarda la eleccion en hub.json (sync_seleccion)."""
    op = next((o for o in grupos_app.opciones() if o["id"] == sel), None)
    if not op:
        return None
    seleccion(); _SEL[:] = [sel]
    publicar_elegidos(); log(f"seleccion -> {op['nombre']}")
    return op["nombre"]


def sync_seleccion(conf):
    if conf.get("seleccion", "personales") != seleccion():
        conf["seleccion"] = seleccion()
        conf["pendientes"] = {}      # el numero del icono pasa a ser de la seleccion nueva
        guardar_conf(conf)


def personales():
    """(14-oct) {session_id: (comando, nombre, emoji)} de "Personales": cada sesion de una carpeta personal
    (config: raices_personales menos excluir_carpetas; LShinox: todo Videos\\<X> menos Claude) + las sesiones fijas
    (Direccion e Instalaciones). Sin las ocultas. Los chats nuevos aparecen solos (la lista de la app se relee cada 30 s)."""
    out = {}
    for cli, titulo, cwd in sesiones_base():
        # (20-oct) la app le cambia el id al chat al compactar/reanudar: lo guardado con un id viejo sigue valiendo
        ids = [cli] + grupos_app.previos_de(cli)
        if any(i in config.OCULTAR for i in ids):
            continue
        # (16-oct, LShinox) el nombre es el que tiene el chat en la app de Claude; config.json "nombres" solo pone el emoji
        # (y el nombre si la app no tiene titulo)
        # (16-oct, LShinox: "no asignemos nada por nuestra cuenta") sin emoji inventado: si el chat lo tiene, va en su titulo
        nombre = (next((config.NOMBRES[i] for i in ids if i in config.NOMBRES), None) or (titulo,))[0]
        out[cli] = ("s" + cli[:8], titulo or nombre, "")
    for cli, (cmd, nombre, emo) in config.FIJAS.items():
        if cli not in config.OCULTAR:
            out[grupos_app.actual(cli)] = (cmd, nombre, "")
    for cli, v in migrar_extras().items():   # compatibilidad: sesiones_extra.json
        out.setdefault(cli, v)
    return out


def migrar_extras():
    """(20-oct) sesiones_extra.json con ids viejos (p. ej. Instalaciones = e41181aa cuando el chat ya es 0843a226) se
    reescribe con el id actual, conservando el comando: asi el hook vuelve a guardar sus mensajes y el celular le
    escribe al chat vivo en vez de dejar todo "en cola (chat dormido)"."""
    x = extras()
    nuevo = {grupos_app.actual(k): v for k, v in x.items()}
    if nuevo != x:
        ruta = os.path.join(BASE, "sesiones_extra.json")
        try:
            tmp = ruta + ".tmp"
            json.dump({k: list(v) for k, v in nuevo.items()}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, ruta)
            log("sesiones_extra: ids actualizados " + ", ".join(f"{k[:8]}->{grupos_app.actual(k)[:8]}" for k in x if grupos_app.actual(k) != k))
        except OSError:
            pass
    return nuevo


def sesiones_base():
    """(15-oct) [(cli, titulo, cwd)] de los chats que PUEDEN ir a la app. Con "raices_personales" en config.json (LShinox:
    todo Videos\\<X> menos Claude) solo esas carpetas; sin esa regla (cualquier otro usuario) TODAS las sesiones no
    archivadas de la app de Claude, y cada uno apaga en Ajustes > Chats que se ven las que no quiera."""
    c = grupos_app.catalogo()
    if not c["sesiones"]:
        # (20-oct) MODO BASICO: si la app de Claude cambio sus archivos internos y no se leen, los chats salen de lo
        # que mandan los hooks oficiales (id, titulo, carpeta): avisos, permisos y respuestas siguen andando
        return sesiones_por_hooks()
    if config.RAICES:
        return [x for x in grupos_app.sesiones_en(config.RAICES) if config.es_personal(config.clave_carpeta(x[2])) is not False]
    return [(x["cli"], x["titulo"], x.get("cwd") or "") for x in sorted(c["sesiones"].values(), key=lambda x: -x["actividad"])]


def sesiones_por_hooks(dias=7):
    """[(cli, titulo, cwd)] de los registros que escriben los hooks (estado\\sesiones), de los ultimos `dias`."""
    out, desde = [], time.time() - dias * 86400
    norm = lambda p: os.path.normcase(os.path.normpath(p or "")).rstrip("\\/")
    raices = [norm(r) for r in config.RAICES]
    for n in os.listdir(SES) if os.path.isdir(SES) else []:
        if not n.endswith(".json"):
            continue
        try:
            x = json.load(open(os.path.join(SES, n), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cwd = x.get("cwd") or ""
        if (x.get("visto") or 0) < desde or x.get("agente"):
            continue
        if raices and not any(norm(cwd) == r or norm(cwd).startswith(r + os.sep) for r in raices):
            continue
        if raices and config.es_personal(config.clave_carpeta(cwd)) is False:
            continue
        out.append((x.get("session_id") or n[:-5], x.get("titulo") or os.path.basename(cwd) or "Chat", cwd, x.get("visto") or 0))
    return [t[:3] for t in sorted(out, key=lambda t: -t[3])]


# ---- (20-oct) chequeo de salud: la app de Claude puede cambiar sus archivos internos sin aviso (el 20-oct mudo sus
# datos de carpeta y cambio ids de chats). Revisa cada 5 min, sin gastar plan, y avisa UNA vez por problema por dia.
_SALUD = {}


def chequear_salud():
    problemas = []
    c = grupos_app.catalogo(max_edad=0)
    if not c["sesiones"]:
        problemas.append(("catalogo", "No encuentro los chats en los archivos de la app de Claude (¿se actualizó?). "
                                      "Sigo en modo básico: avisos, permisos y respuestas andan; nombres, grupos y "
                                      "abrir chats no. Instalaciones lo revisa."))
    else:
        conocidos = set()
        for s in c["sesiones"].values():
            conocidos.add(s["cli"]); conocidos.update(s.get("previos") or [])
        perdidos = []
        for n in os.listdir(SES) if os.path.isdir(SES) else []:
            try:
                x = json.load(open(os.path.join(SES, n), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if time.time() - (x.get("visto") or 0) < 600 and not x.get("agente") and x.get("session_id") not in conocidos \
                    and x.get("socket"):   # con buzon = chat de la app de Claude (los de terminal no tienen)
                perdidos.append(x.get("titulo") or n[:8])
        if len(perdidos) >= 2:
            problemas.append(("ids", f"Hay {len(perdidos)} chats trabajando que no encuentro en la app de Claude "
                                     f"({', '.join(perdidos[:3])}): puede que la app cambió cómo los guarda."))
    hist = os.path.join(grupos_app.APP, "plan-usage-history.json")
    try:
        viejo = time.time() - os.path.getmtime(hist)
    except OSError:
        viejo = None
    hubo_uso = any(time.time() - os.path.getmtime(os.path.join(SES, n)) < 3600 for n in os.listdir(SES)) if os.path.isdir(SES) else False
    if hubo_uso and (viejo is None or viejo > 3 * 3600):
        problemas.append(("uso", "El uso del plan dejó de actualizarse en los archivos de la app de Claude: "
                                 "el porcentaje del celular pasa a ser estimado."))
    return problemas


def vigilar_salud():
    time.sleep(120)
    while True:
        try:
            for clave, texto in chequear_salud():
                if time.time() - _SALUD.get(clave, 0) < 86400:
                    continue
                _SALUD[clave] = time.time()
                log(f"salud: {clave}: {texto}")
                conf = cargar_conf()
                if conf.get("dueno"):
                    api("sendMessage", chat_id=conf["dueno"], text="⚠️ " + texto)
                push_a_todos("⚠️ Kodama", texto, "")
        except Exception as e:
            log(f"salud: {type(e).__name__}: {e}")
        time.sleep(300)


ACTUALIZACION = os.path.join(BASE, "actualizacion.json")
AUTO_ACT = os.path.join(BASE, "actualizar_auto.json")


def actualizar_sola():
    """(22-oct, LShinox) "Actualizar sola" en Ajustes: APAGADO por defecto (una actualizacion toca la config de Claude)."""
    try:
        return bool(json.load(open(AUTO_ACT, encoding="utf-8")).get("activa"))
    except (OSError, ValueError):
        return False


def actualizar_ahora():
    import companero_actualizar as ca
    info = ca.buscar()
    if not info:
        return {"ok": False, "error": "no hay versión nueva"}
    zipv = ca.descargar(info)
    if not zipv:
        return {"ok": False, "error": "la descarga no pasó la verificación (ver estado\\actualizar.log)"}
    log(f"actualizando a {info['version']}")
    ca.lanzar_aplicar(zipv)
    return {"ok": True, "version": info["version"]}


def vigilar_auto_actualizacion():
    """(22-oct) Con "Actualizar sola" prendido: instala la version nueva de NOCHE (1 a 5 h) y con la PC sin usar 30 min."""
    while True:
        time.sleep(600)
        try:
            if actualizar_sola() and os.path.exists(ACTUALIZACION) and 1 <= time.localtime().tm_hour < 5 \
                    and segundos_sin_uso() >= 1800:
                log("actualizar sola: es de noche y la PC no se usa")
                r = actualizar_ahora()
                if not r.get("ok"):
                    log(f"actualizar sola: {r.get('error')}")
        except Exception as e:
            log(f"actualizar sola: {type(e).__name__}: {e}")


def vigilar_actualizaciones():
    """(21-oct) Cada 12 h mira el ultimo release de GitHub. Si hay version nueva: la anota en estado\\actualizacion.json
    (la mascota muestra "Actualizar a vX" en su menu; el celular, un punto rojo en Ajustes) y avisa UNA vez por version.
    Solo instala sola si se prendio "Actualizar sola" (vigilar_auto_actualizacion)."""
    time.sleep(300)
    while True:
        try:
            import companero_actualizar as ca
            info = ca.buscar()
            try:
                previa = json.load(open(ACTUALIZACION, encoding="utf-8")).get("version")
            except (OSError, ValueError):
                previa = None
            if info:
                open(ACTUALIZACION + ".tmp", "w", encoding="utf-8").write(json.dumps(info, ensure_ascii=False))
                os.replace(ACTUALIZACION + ".tmp", ACTUALIZACION)
                if info["version"] != previa:
                    log(f"version nueva disponible: {info['version']}")
                    push_a_todos("Kodama", f"Hay una versión nueva ({info['version']}): actualiza en Ajustes > Actualizaciones o desde el menú del gato.", "")
            elif previa and os.path.exists(ACTUALIZACION):
                os.remove(ACTUALIZACION)   # ya instalada (o retirada)
        except Exception as e:
            log(f"actualizaciones: {type(e).__name__}: {e}")
        time.sleep(12 * 3600)


# ---- (15-oct) grupos propios del Companero (opcion B de LShinox): cada chat a un grupo con nombre; "Sincronizar"
# copia los grupos de la app de Claude. estado\grupos.json = {"asignado": {id de chat: "Nombre del grupo"}}
GRUPOS_JSON = os.path.join(config.ESTADO, "grupos.json")


def grupos_propios():
    try:
        a = json.load(open(GRUPOS_JSON, encoding="utf-8")).get("asignado") or {}
        return {str(k): str(v)[:30] for k, v in a.items() if v}
    except (OSError, ValueError, AttributeError):
        return {}


def poner_grupo(asignado):
    tmp = GRUPOS_JSON + ".tmp"
    json.dump({"asignado": asignado}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, GRUPOS_JSON)


def sincronizar_grupos():
    """Los grupos de la app de Claude pasan a ser los del Companero (los chats sin grupo en la app quedan como estaban)."""
    c = grupos_app.catalogo()
    nombres = {g["id"]: g["nombre"] for g in c["grupos"]}
    por_cli = {x["cli"]: x for x in c["sesiones"].values()}
    a, n = grupos_propios(), 0
    for x in candidatos():
        g = (por_cli.get(x["id"]) or {}).get("grupo")
        if g and nombres.get(g):
            a[x["chat"]] = nombres[g][:30]; n += 1
    poner_grupo(a)
    log(f"grupos sincronizados con la app de Claude: {n} chats")
    return n


def candidatos():
    """(14-oct) Ajustes > Chats que se ven: TODOS los chats que podrian ir a la app (personales por carpeta + fijos),
    ocultos incluidos, el mas reciente primero."""
    out, ya = [], set()
    act = {s["cli"]: s.get("actividad") or 0 for s in grupos_app.catalogo()["sesiones"].values()}
    for cli, titulo, cwd in sesiones_base():
        if cli in ya:
            continue
        ya.add(cli)
        nombre = titulo or (config.NOMBRES.get(cli) or ("",))[0]   # (16-oct) el de la app de Claude
        out.append({"id": cli, "chat": "s" + cli[:8], "nombre": nombre, "carpeta": os.path.basename(os.path.normpath(cwd)),
                    "oculto": cli in config.OCULTAR, "actividad": act.get(cli, 0)})
    for cli, (cmd, nombre, emo) in config.FIJAS.items():
        if cli not in ya:
            out.append({"id": cli, "chat": cmd, "nombre": nombre, "carpeta": "", "oculto": cli in config.OCULTAR, "actividad": act.get(cli, 0)})
    col, gr = colores_app(), grupos_propios()
    for x in out:
        x["color"] = col.get(x["chat"]) or config.COLORES.get(x["chat"])
        x["grupo"] = gr.get(x["chat"], "")
    return sorted(out, key=lambda x: -x["actividad"])


# (14-oct) color de cada chat elegido desde la app (Ajustes > Chats que se ven); manda sobre "colores" de config.json
COLORES_JSON = os.path.join(config.ESTADO, "colores.json")


def colores_app():
    try:
        return {k: v for k, v in json.load(open(COLORES_JSON, encoding="utf-8")).items() if _re.fullmatch(r"#[0-9a-fA-F]{6}", str(v))}
    except (OSError, ValueError, AttributeError):
        return {}


def poner_color(cmd, color):
    c = colores_app()
    if color:
        c[cmd] = color
    else:
        c.pop(cmd, None)
    tmp = COLORES_JSON + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8")); os.replace(tmp, COLORES_JSON)
    log(f"color {cmd}: {color or 'el de siempre'}")


def ocultar_chat(cli, oculto):
    try:
        actuales = set(json.load(open(config.OCULTOS_JSON, encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        actuales = set()
    (actuales.add if oculto else actuales.discard)(cli)
    tmp = config.OCULTOS_JSON + ".tmp"
    json.dump(sorted(actuales), open(tmp, "w", encoding="utf-8")); os.replace(tmp, config.OCULTOS_JSON)
    # (16-oct) los ocultos de config.json "ocultar" se prenden anotandolos en visibles.json (antes volvian a apagarse)
    try:
        vis = set(json.load(open(config.VISIBLES_JSON, encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        vis = set()
    (vis.discard if oculto else vis.add)(cli)
    tmp = config.VISIBLES_JSON + ".tmp"
    json.dump(sorted(vis), open(tmp, "w", encoding="utf-8")); os.replace(tmp, config.VISIBLES_JSON)
    _ELEG["t"] = 0   # que la lista se rearme ya
    publicar_elegidos()
    log(f"chat {'oculto' if oculto else 'visible'}: {cli[:8]}")


_ELEG = {"t": 0, "sel": None, "v": {}}


def elegidos():
    """{session_id: (comando, nombre, emoji)} de la seleccion actual (Personales o un grupo/favoritos de la app).
    Memo de 5 s: info() la pide por cada sesion y el SSE cada 3 s."""
    sel = seleccion()
    if _ELEG["sel"] == sel and time.time() - _ELEG["t"] < 5:
        return _ELEG["v"]
    v = personales() if sel == "personales" else \
        {cli: ("s" + cli[:8], titulo, "💬") for cli, titulo in grupos_app.sesiones_de(sel)}
    _ELEG.update(t=time.time(), sel=sel, v=v)
    return v


def publicar_elegidos():
    """Escribe estado\\elegidos.json para los hooks (solo si cambio): de que sesiones guardar texto, puente y permisos."""
    sel = seleccion()
    nuevo = json.dumps({"seleccion": sel, "sesiones": sorted(elegidos())})
    try:
        if open(ELEGIDOS, encoding="utf-8").read() == nuevo:
            return
    except OSError:
        pass
    open(ELEGIDOS + ".tmp", "w", encoding="utf-8").write(nuevo); os.replace(ELEGIDOS + ".tmp", ELEGIDOS)


def info(s):
    """(comando, nombre, emoji) del chat de esa sesion, o None si no es uno de los nuestros."""
    if not s:
        return None
    sid = s.get("session_id")
    r = elegidos().get(sid)
    if r or seleccion() != "personales" or sid in config.OCULTAR:
        return r
    # sesion personal que la app todavia no listo (recien abierta): por su carpeta
    if config.es_personal(s.get("proyecto")):
        carpeta = (s.get("cwd") or "").rstrip("\\/").split("\\")[-1].split("/")[-1]
        return ("s" + sid[:8], s.get("titulo") or carpeta, "")
    return CHATS.get(s.get("proyecto"))


def todos_los_chats():
    return list(elegidos().values())


AUSENTE_SEG = 120      # modo "ausente": solo avisa si la PC lleva 2 min sin uso
MAX_TXT = 3500


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


# (27-oct, lanzamiento) en el lanzamiento solo se elige el gato. El código de Brote sigue: poner True lo vuelve a mostrar.
MOSTRAR_BROTE = False


def _pj_visible(p):
    """Al LEER personaje.json: un Brote guardado se entrega como gato (el resto del archivo no cambia, ni se reescribe)."""
    if not MOSTRAR_BROTE and str(p.get("pj", "")).startswith("brote"):
        p = dict(p, pj="gatoPro", florCactus=True)
    return p


def leer_token():
    """(21-oct) Sin Telegram el hub ARRANCA igual (antes moria al importar: quien elige "solo la app del celular" no
    tenia mascota). Devuelve "" si no hay archivo o no tiene un token; se configura despues en "Conectar celular"."""
    try:
        t = open(TOKEN_FILE, encoding="utf-8-sig").read().strip()
    except OSError:
        return ""
    for linea in t.splitlines():          # admite "TOKEN=..." o el token solo
        linea = linea.strip()
        if ":" in linea and " " not in linea:
            return linea.split("=", 1)[-1].strip()
    return ""


TOKEN = leer_token()


def api(metodo, **params):
    if not TOKEN:   # (21-oct) sin Telegram configurado: no se llama a nada
        return {"ok": False}
    data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                                   for k, v in params.items()}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{metodo}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=70) as r:
            res = json.load(r)
            SALUD["telegram_ok"] = time.time()
            return res
    except Exception as e:                # nunca loguear la URL (lleva el token)
        log(f"error {metodo}: {type(e).__name__}")
        return {"ok": False}


def cargar_conf():
    if not os.path.exists(CONF):
        return {}
    return json.load(open(CONF, encoding="utf-8"))   # (auditoria 13-oct) si falla, que NO siga: nunca tratarlo como vacio


def guardar_conf(c):
    tmp = CONF + ".tmp"   # escritura atomica: un corte a mitad ya no deja el archivo roto
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CONF)


def segundos_sin_uso():
    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    lii = LII(); lii.cbSize = ctypes.sizeof(LII)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000


_MIR = {"t": 0, "v": None}


def mirando_chat():
    """(14-oct, pedido repetido en Coucou/Happy y sin resolver en ningun proyecto) cliSessionId del chat que estas
    MIRANDO ahora: la app de Claude al frente + usaste la PC hace < 2 min + el chat con "lastFocusedAt" mas reciente.
    Ese chat no te avisa (ni push, ni Telegram, ni la mascota se asoma): ya lo estas viendo. Memo de 2 s."""
    if time.time() - _MIR["t"] < 2:
        return _MIR["v"]
    v = None
    try:
        if segundos_sin_uso() < 120 and app_al_frente() == "claude.exe":
            v = grupos_app.chat_enfocado()
    except Exception:
        v = None
    _MIR.update(t=time.time(), v=v)
    return v


def app_al_frente():
    """Nombre del ejecutable de la ventana que tienes al frente (p.ej. 'claude.exe')."""
    try:
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
        hp = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
        buf = ctypes.create_unicode_buffer(520); n = ctypes.c_ulong(520)
        k.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n)); k.CloseHandle(hp)
        return os.path.basename(buf.value).lower()
    except Exception:
        return ""


class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


class _MINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]


def pantalla_completa():
    """True si la ventana al frente cubre todo su monitor (juego, video, presentacion). Ignora el escritorio."""
    try:
        u = ctypes.windll.user32
        hw = u.GetForegroundWindow()
        if not hw:
            return False
        cls = ctypes.create_unicode_buffer(64); u.GetClassNameW(hw, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False
        r = _RECT(); u.GetWindowRect(hw, ctypes.byref(r))
        mi = _MINFO(); mi.cbSize = ctypes.sizeof(_MINFO)
        u.GetMonitorInfoW(u.MonitorFromWindow(hw, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        return r.l <= m.l and r.t <= m.t and r.r >= m.r and r.b >= m.b
    except Exception:
        return False


def mirando_claude():
    """(issues de la competencia) no avisar al celular si estas frente a la PC con Claude al frente."""
    return segundos_sin_uso() < 60 and app_al_frente() in ("claude.exe",)


def sesiones():
    out = []
    for n in os.listdir(SES) if os.path.isdir(SES) else []:
        if n.endswith(".json"):
            try:
                s = json.load(open(os.path.join(SES, n), encoding="utf-8"))
                if info(s):
                    out.append(s)
            except Exception:
                pass
    return out


def sesion_por_cmd(cmd):
    cands = [s for s in sesiones() if info(s)[0] == cmd]
    return max(cands, key=lambda s: s.get("visto", 0)) if cands else None


PERMISOS = os.path.join(BASE, "permisos")
CELULAR = os.path.join(BASE, "celular_activo")


def marcar_celular():
    """(14-oct) La app del celular esta abierta: lo usan el puente y los permisos como "estas lejos de la PC"."""
    try:
        os.utime(CELULAR, None)
    except OSError:
        open(CELULAR, "w").close()


REGLAS_PERMISO = os.path.join(BASE, "reglas_permiso.json")


def leer_reglas():
    try:
        r = json.load(open(REGLAS_PERMISO, encoding="utf-8"))
    except (OSError, ValueError):
        r = {}
    return {"siempre": list(r.get("siempre") or []), "tarea": dict(r.get("tarea") or {})}


def guardar_reglas(r):
    tmp = REGLAS_PERMISO + ".tmp"
    json.dump(r, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, REGLAS_PERMISO)


def responder_permiso(pid, decision, motivo="", alcance=""):
    """Deja la decision para el hook companero_permiso.py. False si el pedido ya no existe (caduco o se decidio).
    (22-oct, mejora 6, idea de Nudge) al denegar puede ir un motivo corto: Claude lo recibe y cambia de rumbo.
    (22-oct, mejora 2) decision "pc" = que lo decida la PC; allow + alcance "siempre"/"tarea" guarda una regla con el
    comando exacto (o herramienta + archivo) para no volver a preguntarlo."""
    if not _re.fullmatch(r"[0-9a-f]{8}", pid or "") or decision not in ("allow", "deny", "pc"):
        return False
    ped = os.path.join(PERMISOS, pid + ".pedido")
    if not os.path.exists(ped):
        return False
    if decision == "allow" and alcance in ("siempre", "tarea"):
        try:
            p = json.load(open(ped, encoding="utf-8"))
            clave, ses = p.get("regla"), p.get("sesion")
            if clave:
                reg = leer_reglas()
                if alcance == "siempre" and clave not in reg["siempre"]:
                    reg["siempre"].append(clave)
                elif alcance == "tarea" and ses and clave not in reg["tarea"].setdefault(ses, []):
                    reg["tarea"][ses].append(clave)
                guardar_reglas(reg); log(f"regla nueva ({alcance}): {clave[:80]}")
        except Exception as e:
            log(f"regla: {type(e).__name__}")
    r = os.path.join(PERMISOS, pid + ".respuesta")
    motivo = " ".join(str(motivo or "").split())[:300] if decision == "deny" else ""
    open(r + ".tmp", "w", encoding="utf-8").write(json.dumps({"decision": decision, "motivo": motivo}, ensure_ascii=False))
    os.replace(r + ".tmp", r)
    log(f"permiso {pid}: {decision}")
    return True


def responder_pregunta(pid, respuestas):
    """(19-oct) Respuesta a una pregunta con opciones (AskUserQuestion): {pregunta: etiqueta}. El hook valida que cada
    etiqueta sea una de las opciones antes de dársela al chat."""
    if not _re.fullmatch(r"[0-9a-f]{8}", pid or "") or not isinstance(respuestas, dict) or not respuestas:
        return False
    ped = os.path.join(PERMISOS, pid + ".pedido")
    if not os.path.exists(ped):
        return False
    limpio = {str(k)[:500]: str(v)[:600] for k, v in list(respuestas.items())[:4]}
    r = os.path.join(PERMISOS, pid + ".respuesta")
    open(r + ".tmp", "w", encoding="utf-8").write(json.dumps({"decision": "answer", "respuestas": limpio}, ensure_ascii=False))
    os.replace(r + ".tmp", r)
    log(f"pregunta {pid}: respondida desde el celular")
    return True


BOT = {}   # (21-oct) {"u": usuario del bot de Telegram} para el enlace de emparejar del asistente


def poner_token(tok, bot):
    """(21-oct) Telegram configurado desde el asistente: el hub empieza a usarlo sin reiniciarse."""
    global TOKEN
    TOKEN = tok
    BOT["u"] = bot
PERM_TG = {}   # permiso_id -> (chat, message_id, enviado): mensajes de Telegram con Permitir/Denegar o pregunta abiertos


def vigilar_permisos_caducados():
    """(21-oct, Coucou #857: botones muertos que despues rechazan el permiso siguiente) Cada 5 s: si el pedido ya no
    existe (el hook espero 110 s y se pregunto en la PC, o se respondio en la PC) y nadie lo respondio desde el
    celular, el mensaje de Telegram pasa a "⌛ Caducó" y sus botones dejan de servir. La app y la mascota ya lo
    sacan solas (permisos_pendientes() solo lista pedidos vivos)."""
    while True:
        time.sleep(5)
        for pid, (chat, mid, t0) in list(PERM_TG.items()):
            if os.path.exists(os.path.join(PERMISOS, pid + ".pedido")) and time.time() - t0 < 180:
                continue
            PERM_TG.pop(pid, None)
            try:
                api("editMessageReplyMarkup", chat_id=chat, message_id=mid,
                    reply_markup={"inline_keyboard": [[{"text": tr("⌛ Ya caducó: se preguntó en la PC"), "callback_data": "x|x|x"}]]})
            except Exception as e:
                log(f"permisos caducados: {type(e).__name__}")


def permisos_pendientes():
    """{session_id: {id, texto, ts}} de los pedidos que esperan respuesta (para la app y el escritorio)."""
    # (22-oct, mejora 1) un mismo chat puede pedir dos permisos a la vez (subagentes en paralelo): antes se mostraba uno
    # cualquiera y el otro se perdia de vista. Ahora va primero el MAS VIEJO y "cola" dice cuantos esperan en total;
    # al contestarlo aparece el siguiente. Cada pedido sigue esperando su propia respuesta en su hook.
    todos = {}
    for f in os.listdir(PERMISOS) if os.path.isdir(PERMISOS) else []:
        if f.endswith(".pedido"):
            try:
                p = json.load(open(os.path.join(PERMISOS, f), encoding="utf-8"))
                if time.time() - p["ts"] < 115:
                    todos.setdefault(p["sesion"], []).append(p)
            except Exception:
                pass
    out = {}
    for ses, lista in todos.items():
        p = min(lista, key=lambda x: x["ts"])
        out[ses] = {"id": p["id"], "texto": redactar(p["texto"]), "ts": p["ts"], "cola": len(lista)}
        if p.get("preguntas"):   # (19-oct) pregunta con opciones: la app muestra botones por opcion
            out[ses]["preguntas"] = p["preguntas"]
            out[ses]["plan"] = bool(p.get("plan"))   # (20-oct) aprobar el plan: la app muestra el plan
    return out


PUENTE = os.path.join(BASE, "puente")


def por_puente(s, texto):
    """(14-oct) Si el chat esta esperando en el hook Stop del puente (companero_puente.py), la respuesta va por
    ahi: le llega a Claude como decision del hook, sin el parrafo "This came from another Claude session…".
    Devuelve True si el hook la tomo (borra el archivo en <=1 s); si no la toma en 4 s, se usa el buzon."""
    sid = s.get("session_id") or ""
    esp, resp = os.path.join(PUENTE, sid + ".esperando"), os.path.join(PUENTE, sid + ".respuesta")
    try:
        if not sid or time.time() - os.path.getmtime(esp) > 540:
            return False
    except OSError:
        return False
    open(resp + ".tmp", "w", encoding="utf-8").write(texto); os.replace(resp + ".tmp", resp)
    for _ in range(40):
        time.sleep(0.1)
        if not os.path.exists(resp):
            try:   # Claude sigue trabajando con tu respuesta: que el estado lo diga
                p = os.path.join(SES, sid + ".json"); reg = json.load(open(p, encoding="utf-8"))
                reg.update(estado="trabajando", visto=time.time())
                open(p + ".tmp", "w", encoding="utf-8").write(json.dumps(reg, ensure_ascii=False)); os.replace(p + ".tmp", p)
            except Exception:
                pass
            log(f"respuesta por el puente -> {sid[:8]}")
            return True
    try:
        os.remove(resp)
    except OSError:
        pass
    return False


def entregar(s, texto, marca="📱 "):
    """Entrega el texto: por el puente si el chat te esta esperando; si no, en el buzon (named pipe) de la sesion."""
    if por_puente(s, texto):
        return None
    if not (s.get("socket") and s.get("token")):
        return "ese chat todavía no registró su buzón (escribile algo desde la PC una vez)"
    if not str(s["socket"]).lower().startswith("\\\\.\\pipe\\"):   # (auditoria) solo \\.\pipe\..., nunca un archivo
        return "buzón inválido"
    # (14-oct) el buzon es una tuberia con nombre: entre una conexion y la siguiente puede no haber instancia libre
    # un instante (FileNotFoundError / ocupada). Se reintenta hasta ~4 s antes de dar error.
    for intento in range(8):
        try:
            p = open(s["socket"], "r+b", buffering=0)
            break
        except (FileNotFoundError, PermissionError, OSError) as e:
            if intento == 7:
                return f"no pude entregarlo ({type(e).__name__}); ¿el chat sigue abierto?"
            time.sleep(0.5)
    # (21-oct) por el buzon, Claude Code lo envuelve como "mensaje de OTRA sesion": un chat (Rol) contesto "no pude
    # responderle a esa sesion" sin saber que era LShinox desde el celular. La marca ahora dice quien escribe y donde
    # contestar. (Sigue sin contar como aprobacion: eso solo pasa por el puente, cuando el chat te estaba esperando.)
    quien = (f"{config.NOMBRE}, desde la mascota del escritorio" if marca.startswith("🐾")
             else f"{config.NOMBRE}, desde el celular")
    etiqueta = f"{marca.strip()} [{quien}, con Kodama; contéstale aquí en este chat] "
    try:
        with p:
            p.write((json.dumps({"type": "auth", "token": s["token"]}) + "\n").encode())
            p.write((json.dumps({"type": "user", "message": {"role": "user", "content":
                    etiqueta + texto}},   # 14-oct: marca (📱 celular/Telegram, 🐾 mascota del escritorio); 21-oct: + quien
                    ensure_ascii=False) + "\n").encode())
        return None
    except Exception as e:
        return f"no pude entregarlo ({type(e).__name__}); ¿el chat sigue abierto?"


# clasificar v2 (13-oct, calibrado con 60 mensajes reales: 82 % -> 100 % en muestra; re-medir con mensajes nuevos)
import html as _html
import re as _re

RESPUESTAS = {"ok": "OK, adelante.", "sigue": "Sigue con lo que ibas.",
              "para": "Para ahí y espera mis instrucciones.", "corto": "Explícame lo anterior en 3 líneas, sin jerga."}


def _limpio(txt):
    txt = _re.sub(r"```[\s\S]*?```", " ", txt)
    txt = _re.sub(r"`[^`]*`", " ", txt)
    txt = "\n".join(l for l in txt.splitlines() if not l.strip().startswith("|"))
    return _re.sub(r"[*_#>]+", "", txt)


# Peticiones directas al usuario (voseo y tuteo). Las condicionales tipo
# "si ves algo, dime" NO cuentan: son opcionales.
_PIDE = _re.compile(
    r"(lo que necesito de ti|necesito de ti|necesito tu (ok|visto bueno|aprobaci[oó]n|confirmaci[oó]n|respuesta|decisi[oó]n)"
    r"|\bnecesito:"
    r"|\b(decime|dime) si (arranco|lo hago|lo armo|sigo|sigo con|procedo|avanzo|lanzo|empiezo|quieres|querés)"
    r"|\bresp[oó]nd(e|é)me\b|\bcontestame\b"
    # (14-oct) pedidos de prueba/confirmacion que no llevan "?" ("dime si te gusta", "confirmame que la ves"): asi el
    # puente espera y tu respuesta llega sin el parrafo en ingles
    r"|\b(dime|decime|cu[eé]ntame|av[ií]same|avisame) (si|que|c[oó]mo|qu[eé])\b|\bconf[ií]rm(a|á)me\b|\bconf[ií]rmame\b"
    r"|\bpru[eé]ba(la|lo|las|los)\b y (dime|me dices|av[ií]same)|\b(me dices|me cuentas|me avisas) (si|qu[eé]|c[oó]mo)\b"
    r"|\b(quieres|querés) que\b|\bte parece\b|\bconfirm(as|ás) (si|que)\b|\bcu[aá]l (de|prefieres|preferís)\b"
    r"|\bnecesito que (me )?(digas|confirmes|elijas|digás|confirmés|elijás)\b"
    # (14-oct, revision de 50 reales: 12 "termino" que eran pedidos, casi todos con el pedido AL PRINCIPIO)
    r"|\bnecesito (un|una|dos|tres|cuatro|\d+|tus|tu) (ok|oks|decisi[oó]n|decisiones|respuesta|confirmaci[oó]n)"
    r"|\b(me )?(digas|digás) (si|qu[eé]|cu[aá]l)\b|\b(dime|decime) (qu[eé]|cu[aá]l)\b|\bque elij(as|ás)\b"
    r"|\bsi lo confirm(as|ás)\b|\b(p[aá]same|pasame|m[aá]ndame|env[ií]ame) (el|la|los|las|un|una)\b"
    # (14-oct) ingles
    r"|\bi need your (ok|approval|decision|answer|confirmation)\b|\b(let me know|tell me) (if|which|what)\b"
    r"|\bshould i (go ahead|proceed|continue|start)\b|\bdo you want me to\b|\bplease (confirm|choose|pick)\b)", _re.I)
# Verbo de acción al INICIO de una línea ("Aceptá en la PC...", "Elegí uno").
_ORDEN = _re.compile(r"(^|\n)\s*(acept[aá]|aprob[aá]|confirm[aá]|eleg[ií]|elige|resolv[eé]|autoriz[aá])\b", _re.I)
_LISTA = _re.compile(r"(^|\n)\s*(\d+[.)]|[ab]\)|[-•]\s)")


def clasificar(evento, texto):
    """(tipo, cuantas_preguntas, linea) — tipo: error > permiso > pregunta > termino.
    v2 (calibrada 2026-10-13 con 60 mensajes reales)."""
    t0 = (texto or "").strip()
    inicio = t0[:200]
    if evento == "StopFailure" or _re.match(r"^(error|falló|no pude|no se pudo|límite|rate limit)", inicio, _re.I) \
            or _re.search(r"Traceback|API Error|overloaded| 429 | 529 ", inicio):
        return "error", 0, _corta(inicio)
    if evento in ("Notification", "PermissionRequest"):
        return "permiso", 0, _corta(t0)
    limpio = _limpio(t0)
    parrafos = [p.strip() for p in _re.split(r"\n\s*\n", limpio) if p.strip()]
    ultimo = (parrafos[-1] if parrafos else "")[-400:]
    lineas = [l.strip() for l in ultimo.splitlines() if l.strip()]
    cola = limpio[-700:]
    pregunta = None
    if lineas and lineas[-1].endswith("?"):
        pregunta = lineas[-1]
    elif any(l.endswith("?") for l in lineas[-2:]):
        pregunta = next(l for l in reversed(lineas[-2:]) if l.endswith("?"))
    else:
        m = _re.search(r"¿[^?]{3,200}\?", ultimo)
        if m and len(ultimo[m.end():].strip()) <= 140:
            pregunta = m.group(0)
    if pregunta is None:
        # (A) la pregunta ABRE el mensaje ("lo que necesito de ti va primero"): "¿Lanzo un estudio…? Solo investiga…"
        m = _re.match(r"\s*¿[^?]{3,200}\?", limpio)
        if m:
            pregunta = m.group(0).strip()
    if pregunta is None:
        # (B) petición directa en la cola ("lo que necesito de ti", "respóndeme ok", "decime si arranco", "Aceptá …")
        # (14-oct) lo que va entre comillas es una cita, no un pedido («dime si…» nombrado como ejemplo)
        sin_citas = lambda x: _re.sub(r"«[^»]{0,120}»|\"[^\"\n]{0,120}\"|“[^”]{0,120}”", "",
                                      _re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", x))   # los links [texto](ruta) quedan en su texto
        cabeza, cola = sin_citas(limpio[:400]), sin_citas(cola)   # la regla de LShinox: "lo que necesitás de mí va PRIMERO"
        m = _PIDE.search(cola) or _ORDEN.search(cola)
        donde = cola
        if not m:
            m, donde = _PIDE.search(cabeza), cabeza
        if m:
            # (14-oct) la ORACION entera donde esta el pedido (antes una ventana de caracteres: "uando terminan…avis")
            ini = max(donde.rfind(x, 0, m.start()) for x in (". ", "! ", "? ", "\n", ": ")) + 1
            fin = min([i for i in (donde.find(x, m.end()) for x in (".", "!", "?", "\n")) if i >= 0] or [len(donde)])
            pregunta = " ".join(donde[ini:fin + 1].split())
    n_bloque = 0
    if pregunta is not None and pregunta.rstrip().endswith(":"):
        # (20-oct) el pedido es un TITULO ("Necesito de ti:") y las preguntas van debajo: la linea pasa a ser la primera
        # pregunta del bloque (antes el aviso y el globo decian solo "Necesito de ti:") y se cuentan las preguntas
        i = limpio.find(pregunta.rstrip(": ").split()[-1] + ":")
        bloque = _re.split(r"\n\s*\n", limpio[i:] if i >= 0 else "", maxsplit=1)[0].splitlines()[1:]
        items = [l.strip() for l in bloque if l.strip()]
        if items:
            n_bloque = sum(1 for l in items if "?" in l) or len(items)
            pregunta = next((l for l in items if "?" in l), items[0])
    if pregunta is not None:
        n = n_bloque or max(1, min(3, ultimo.count("¿")))
        frase = _re.sub(r"^[-•\d.)\s]+", "", pregunta)
        return "pregunta", n, _corta(frase)
    oraciones = [o.strip() for o in _re.split(r"(?<=[.!?])\s+|\n", limpio) if len(o.strip()) > 8]
    return "termino", 0, _corta(oraciones[0] if oraciones else " ".join(limpio.split()))


def _corta(s, n=110):
    """Recorta en una palabra entera, con "…" si sobra (nunca a mitad de palabra)."""
    s = _re.sub(r"^[-•*]\s+", "", " ".join((s or "").split()))   # sin la viñeta del principio
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:·-") + "…"




# ---- idioma de Telegram y de los avisos (14-oct): config.json "idioma": "es" (por defecto) o "en" ----
_EN = {
    "No hay imágenes, páginas ni PDF que se puedan abrir en esta carpeta.": "No images, pages or PDFs that can be opened in this folder.",
    "Entregado a {n}": "Delivered to {n}",
    "{n} se atoró": "{n} got stuck", "{e} {n} pide permiso": "{e} {n} needs permission",
    "{e} {n} te hace una pregunta": "{e} {n} has a question", "{e} {n} te hace {k} preguntas": "{e} {n} has {k} questions",
    "✅ {n} terminó": "✅ {n} is done", "pregunta": "question", "permiso": "permission", "se atoró": "stuck", "terminó": "done",
    "{k} chats te esperan": "{k} chats are waiting", "✅ Permitir": "✅ Allow", "⛔ Denegar": "⛔ Deny",
    "Caduca en ~2 min; si no respondes, se pregunta en la PC.": "Expires in ~2 min; if you don't answer, it asks on the PC.",
    "OK ✅": "OK ✅", "Sigue ▶": "Go on ▶", "Para ⏸": "Stop ⏸", "Explícame corto": "Explain briefly", "Abrir app": "Open app",
    "↪ Hay un mensaje más nuevo": "↪ There's a newer message", "⌛ Botón vencido: responde en el chat o la app": "⌛ Expired: reply in the chat or the app",
    "✓ Respondiste": "✓ You replied", "✓ Respondiste en la PC": "✓ You replied on the PC", "✅ Permitido": "✅ Allowed", "⛔ Denegado": "⛔ Denied",
    "⌛ Ya caducó: se preguntó en la PC": "⌛ Expired: it asked on the PC", "🔕 Silenciado {h} h": "🔕 Muted {h} h",
    "📱 Al celular: {n}": "📱 On your phone: {n}", "Ese grupo ya no existe; manda /grupo de nuevo.": "That group no longer exists; send /grupo again.",
    "¡Listo! Quedé emparejado solo contigo.": "Done! I'm paired only with you.",
    "Telegram: mensajes completos (Instalaciones sigue en corto).": "Telegram: full messages.",
    "Telegram: solo el aviso corto; el texto completo en la app.": "Telegram: short notice only; full text in the app.",
    "Modo: siempre (aviso todo)": "Mode: always (I notify everything)",
    "Modo: ausente (aviso solo si la PC lleva 2 min sin uso)": "Mode: away (I notify only if the PC is idle for 2 min)",
    "¿Qué chats llevo al celular?": "Which chats go to your phone?", "✗ No pude bajar la foto.": "✗ I couldn't download the photo.",
    "Escribe el mensaje después del comando: /{c} …": "Write the message after the command: /{c} …",
    "¿Para qué chat? Responde deslizando sobre su mensaje.": "Which chat? Reply by swiping on its message.",
    "✓ Enviado a {e} {n}": "✓ Sent to {e} {n}",
    "Te aviso cuando tus chats te necesitan.\nPara responder: desliza sobre el mensaje del chat y escribe (o toca sus botones).\n/estado: cómo está cada chat · /siempre o /ausente: cuándo te aviso · /grupo: qué chats van al celular · /completo o /corto: cuánto texto mando.":
        "I let you know when your chats need you.\nTo reply: swipe on the chat's message and type (or tap its buttons).\n/estado: status of each chat · /siempre or /ausente: when I notify you · /grupo: which chats go to your phone · /completo or /corto: how much text I send.",
    "🔄 Kodama volvió: estuvo caído ~{m} min (desde las {d}). Lo de los últimos 15 min te lo aviso ahora; lo anterior está en la app.":
        "🔄 Kodama is back: it was down ~{m} min (since {d}). I'll send what came in the last 15 min now; older items are in the app.",
    "OK, adelante.": "OK, go ahead.", "Sigue con lo que ibas.": "Carry on with what you were doing.",
    "Para ahí y espera mis instrucciones.": "Stop there and wait for my instructions.",
    "Explícame lo anterior en 3 líneas, sin jerga.": "Explain the above in 3 lines, no jargon.",
}


def tr(es, **kw):
    """Texto en el idioma de config.json; las llaves {x} se completan con kw."""
    txt = _EN.get(es, es) if config.IDIOMA == "en" else es
    return txt.format(**kw) if kw else txt


def titulo_aviso(emo, nombre, tipo, n):
    return {"error": "⚠️ " + tr("{n} se atoró", n=nombre), "permiso": tr("{e} {n} pide permiso", e=emo, n=nombre),
            "pregunta": tr("{e} {n} te hace una pregunta", e=emo, n=nombre) if n <= 1 else tr("{e} {n} te hace {k} preguntas", e=emo, n=nombre, k=n),
            "termino": tr("✅ {n} terminó", n=nombre)}[tipo].strip()   # (16-oct) sin emoji queda un espacio adelante


def pendientes(conf):
    return len(conf.get("pendientes", {}))


# ---- privacidad (14-oct): lo que SALE de la PC (Telegram, Web Push) va sin claves y sin la ruta de tu usuario ----
_SECRETOS = _re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{30,}|\b\d{8,10}:[A-Za-z0-9_-]{30,}\b|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"
    r"|(?i:(?:password|passwd|contrase[nñ]a|token|api[_-]?key|secret)\s*[:=]\s*)\S{6,}"
    r"|\b[A-Fa-f0-9]{40,}\b|\b[A-Za-z0-9+/]{48,}={0,2}"
    r"|\b1000\.[a-f0-9]{32}\.[a-f0-9]{32}\b|\bya29\.[A-Za-z0-9_-]{20,}|\b(?=[A-Za-z0-9 ]{0,28}\d)(?=[A-Za-z0-9 ]{0,28}[A-Z])(?:[A-Za-z0-9]{4} ){5}[A-Za-z0-9]{4}\b"
    r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@))")
_RUTA_USUARIO = _re.compile(r"[\\/]+".join(_re.escape(x) for x in _re.split(r"[\\/]+", config.HOME)), _re.I)   # tu carpeta de usuario, con \ o /


def redactar(txt):
    return _RUTA_USUARIO.sub("~", _SECRETOS.sub("[clave oculta]", txt or ""))


# ---- silenciar un chat suelto (14-oct): no avisa por Telegram ni push; la app y el escritorio lo siguen mostrando ----
SILENCIO = os.path.join(BASE, "silencio.json")


def _silencios():
    try:
        return {k: v for k, v in json.load(open(SILENCIO, encoding="utf-8")).items() if v > time.time()}
    except Exception:
        return {}


def silenciar(cmd, horas):
    s = _silencios()
    if horas > 0:
        s[cmd] = time.time() + horas * 3600
    else:
        s.pop(cmd, None)
    open(SILENCIO + ".tmp", "w", encoding="utf-8").write(json.dumps(s)); os.replace(SILENCIO + ".tmp", SILENCIO)
    log(f"silencio {cmd}: {horas} h")


def silenciado(conf, cmd):
    return _silencios().get(cmd, 0) > time.time()


REINTENTAR = []   # avisos de Telegram que fallaron: se reintentan a 1, 3 y 10 min (14-oct)
ESPERAS_REINTENTO = (60, 180, 600)


def reintentar_avisos(conf):
    ahora = time.time()
    for r in [r for r in REINTENTAR if r["t"] <= ahora]:
        REINTENTAR.remove(r)
        if enviar_aviso(conf, r["item"], r["agrupado"], reintento=r["n"]) == "fallo":
            log(f"aviso sin enviar tras {r['n']} reintentos (se descarta)")


def enviar_aviso(conf, item, agrupado=False, reintento=0):
    """Manda UN aviso. Con agrupado=True: el push lo manda el resumen del grupo y Telegram va sin sonido.
    Devuelve (emo, nombre, tipo) si se mando, None si se filtro, "fallo" si Telegram fallo (queda para reintentar).
    reintento>0: es un reintento de Telegram (ya paso los filtros y ya se mando el push)."""
    s = next((x for x in sesiones() if x["session_id"] == item["session_id"]), None)
    if not s:
        return None
    cmd, nombre, emo = info(s)
    tipo, n, linea = clasificar(item["evento"], item["texto"])
    if item.get("pregunta"):   # (19-oct) AskUserQuestion: es una pregunta, no un permiso
        tipo, n, linea = "pregunta", 1, item["texto"].split("\n", 1)[0][:200]
    linea = redactar(linea)
    ahora = time.time()
    titulo = titulo_aviso(emo, nombre, tipo, n)
    if not reintento and silenciado(conf, cmd):   # chat silenciado: no avisa (la app lo sigue mostrando)
        return None
    if not reintento and mirando_chat() == item["session_id"]:   # (14-oct) lo estas mirando en la app de Claude
        log(f"sin aviso: estas mirando {cmd}")
        return None
    if not reintento:
        ult = conf.setdefault("ultimo_aviso", {})
        clave = f"{cmd}|{tipo}"
        if tipo == "termino" and ahora - ult.get(clave, 0) < 300:      # "terminó": uno por chat cada 5 min
            return None
        if tipo != "termino" and not item.get("permiso_id") and ahora - ult.get(clave + "|" + linea, 0) < 120:   # mismo aviso repetido en 2 min
            return None
        ult[clave] = ult[clave + "|" + linea] = ahora
        pend = conf.setdefault("pendientes", {})
        if tipo in ("pregunta", "permiso", "error"):
            pend[cmd] = ahora
        else:
            pend.pop(cmd, None)
        if not agrupado:
            # (22-oct, mejora 4, idea de Perch) Permitir/Denegar en el propio aviso, pero SOLO si el aviso muestra el
            # pedido COMPLETO (la auditoria del 14-oct: no aprobar algo que no se ve entero). Si es largo, se abre la app.
            pid = None if item.get("pregunta") else item.get("permiso_id")
            txt = redactar(item.get("texto") or "") if pid else ""
            completo = bool(pid) and 0 < len(txt) <= 180
            threading.Thread(target=push_a_todos, args=(titulo, txt if completo else linea, cmd, tipo, pendientes(conf)),
                             kwargs={"permiso": pid, "completo": completo}, daemon=True).start()
    # Telegram: titular + la linea clave + el resto plegado (blockquote expandable) + botones
    resto = redactar(item["texto"].strip())
    if len(resto) > 3000:
        resto = resto[:3000] + "\n…(sigue en la app)"
    cuerpo = (f"{_html.escape(titulo.split(' ', 1)[1] if tipo == 'termino' or tipo == 'error' else titulo)}"
              if False else f"<b>{_html.escape(titulo)}</b>")
    texto_tg = f"{cuerpo}\n<blockquote>{_html.escape(linea)}</blockquote>\n<blockquote expandable>{_html.escape(resto)}</blockquote>"
    if s.get("proyecto") not in CHATS or not conf.get("tg_completo"):   # privacidad por defecto (13-oct): solo el aviso corto; /completo para ver todo (Instalaciones y los chats de grupos de la app SIEMPRE corto, 14-oct)
        texto_tg = f"{cuerpo}\n<blockquote>{_html.escape(linea)}</blockquote>\n<i>El texto completo está en la app.</i>"
        resto = linea
    if item.get("pregunta"):   # (19-oct) pregunta con opciones: se responde en la app tocando una opcion
        texto_tg = (f"<b>{_html.escape(titulo)}</b>\n<blockquote>{_html.escape(redactar(item['texto'])[:600])}</blockquote>\n"
                    f"<i>{tr('Respóndela en la app (2 min); si no, se pregunta en la PC.')}</i>")
        botones = {"inline_keyboard": [[{"text": tr("Abrir app"), "url": f"{config.URL_PUBLICA}/#{cmd}"}]]}
    elif item.get("permiso_id"):   # (14-oct) pedido de permiso: Permitir / Denegar en vez de las respuestas de texto
        pid = item["permiso_id"]
        texto_tg = f"<b>{_html.escape(titulo)}</b>\n<code>{_html.escape(redactar(item['texto'])[:300])}</code>\n<i>{tr("Caduca en ~2 min; si no respondes, se pregunta en la PC.")}</i>"
        botones = {"inline_keyboard": [[{"text": tr("✅ Permitir"), "callback_data": f"a|{pid}|allow"},
                                        {"text": tr("⛔ Denegar"), "callback_data": f"a|{pid}|deny"}]]}
    else:
        botones = None
    botones = botones or {"inline_keyboard": [
        [{"text": tr("OK ✅"), "callback_data": f"r|{cmd}|ok"}, {"text": tr("Sigue ▶"), "callback_data": f"r|{cmd}|sigue"},
         {"text": tr("Para ⏸"), "callback_data": f"r|{cmd}|para"}],
        [{"text": tr("Explícame corto"), "callback_data": f"r|{cmd}|corto"},
         {"text": "🔕 1 h", "callback_data": f"s|{cmd}|1"},
         {"text": tr("Abrir app"), "url": f"{config.URL_PUBLICA}/#{cmd}"}]]}
    r = api("sendMessage", chat_id=conf["dueno"], text=texto_tg, parse_mode="HTML", reply_markup=botones,
            disable_notification="true" if (tipo == "termino" or agrupado or reintento) else "false",
            link_preview_options={"is_disabled": True})
    if not r.get("ok"):   # si el HTML fallara, texto plano
        r = api("sendMessage", chat_id=conf["dueno"], text=f"{titulo}\n\n{linea}\n\n{resto}")
    if not r.get("ok"):   # Telegram caido o sin red: no se pierde, se reintenta
        if reintento < len(ESPERAS_REINTENTO):
            REINTENTAR.append({"item": item, "agrupado": agrupado, "n": reintento + 1, "t": ahora + ESPERAS_REINTENTO[reintento]})
        guardar_conf(conf)
        return "fallo"
    if r.get("ok") and item.get("permiso_id"):   # (21-oct, Coucou #857) para apagar sus botones si caduca sin respuesta
        PERM_TG[item["permiso_id"]] = (conf["dueno"], r["result"]["message_id"], time.time())
    if r.get("ok"):
        # los botones de avisos VIEJOS de este chat se apagan: solo el ultimo puede responder (auditoria 13-oct)
        abiertos = conf.setdefault("tg_abiertos", {})
        for mid in abiertos.get(cmd, [])[-10:]:
            api("editMessageReplyMarkup", chat_id=conf["dueno"], message_id=mid,
                reply_markup={"inline_keyboard": [[{"text": tr("↪ Hay un mensaje más nuevo"), "callback_data": "x|x|x"}]]})
        abiertos[cmd] = [r["result"]["message_id"]]
        mapa = conf.setdefault("mapa", {})
        mapa[str(r["result"]["message_id"])] = item["session_id"]
        if len(mapa) > 300:
            for k in sorted(mapa, key=int)[:-300]:
                mapa.pop(k)
    guardar_conf(conf)
    return (emo, nombre, tipo)


def atender_boton(conf, cq):
    api("answerCallbackQuery", callback_query_id=cq["id"])
    if cq.get("from", {}).get("id") != conf.get("dueno"):
        return
    if bloqueado():
        return
    if cq.get("data", "").startswith("a|"):   # (14-oct) Permitir / Denegar un pedido de permiso
        _, pid, dec = cq["data"].split("|")
        m = cq.get("message") or {}
        if m and time.time() - m.get("date", 0) < 1:   # anti-toque: el boton recien aparecio
            return
        ok = responder_permiso(pid, dec)
        PERM_TG.pop(pid, None)   # (21-oct) respondido: el vigilante de caducados ya no lo toca
        if m:
            api("editMessageReplyMarkup", chat_id=m["chat"]["id"], message_id=m["message_id"],
                reply_markup={"inline_keyboard": [[{"text": (tr("✅ Permitido") if dec == "allow" else tr("⛔ Denegado")) if ok
                                                    else tr("⌛ Ya caducó: se preguntó en la PC"), "callback_data": "x|x|x"}]]})
        return
    if cq.get("data", "").startswith("s|"):   # 🔕 silenciar ese chat 1 h (14-oct)
        _, cmd, horas = cq["data"].split("|")
        silenciar(cmd, float(horas))
        m = cq.get("message") or {}
        if m:
            api("editMessageReplyMarkup", chat_id=m["chat"]["id"], message_id=m["message_id"],
                reply_markup={"inline_keyboard": [[{"text": tr("🔕 Silenciado {h} h", h=horas), "callback_data": "x|x|x"}]]})
        return
    if cq.get("data", "").startswith("g|"):   # /grupo: elegir que chats van al celular
        nombre = cambiar_seleccion(cq["data"].split("|")[1])
        m = cq.get("message") or {}
        if m:
            api("editMessageText", chat_id=m["chat"]["id"], message_id=m["message_id"],
                text=tr("📱 Al celular: {n}", n=nombre) if nombre else tr("Ese grupo ya no existe; manda /grupo de nuevo."))
        return
    try:
        _, cmd, clave = cq.get("data", "").split("|")
    except ValueError:
        return
    s = sesion_por_cmd(cmd)
    texto = RESPUESTAS.get(clave)
    texto = tr(texto) if texto else texto
    if not s or not texto:
        return
    m = cq.get("message") or {}
    # boton vencido: no es el ultimo aviso de ese chat, o tiene mas de 10 min -> no responde nada
    ultimo = (conf.get("tg_abiertos", {}).get(cmd) or [None])[-1]
    if m and (m.get("message_id") != ultimo or time.time() - m.get("date", 0) > 600):
        api("editMessageReplyMarkup", chat_id=m["chat"]["id"], message_id=m["message_id"],
            reply_markup={"inline_keyboard": [[{"text": tr("⌛ Botón vencido: responde en el chat o la app"), "callback_data": "x|x|x"}]]})
        return
    err = entregar(s, texto)
    if not err:
        registrar_respuesta(cmd, texto)
        cerrar_avisos(conf, cmd, texto)
    if m:
        api("editMessageReplyMarkup", chat_id=m["chat"]["id"], message_id=m["message_id"],
            reply_markup={"inline_keyboard": [[{"text": ("✗ " + err) if err else f"✅ Enviado: {texto}", "callback_data": "x|x|x"}]]})


def cerrar_avisos(conf, cmd, texto="", etiqueta=None):
    """Al responder (por la app, el escritorio o Telegram), los avisos pendientes de ese chat en Telegram
    pierden los botones y quedan marcados como respondidos; y ese chat deja de contar en el numero del icono.
    (27-oct) etiqueta = texto fijo del boton (p. ej. "✓ Respondiste en la PC"). Devuelve cuantos avisos cerro (0 = nada que cerrar)."""
    conf.setdefault("pendientes", {}).pop(cmd, None)
    ids = conf.setdefault("tg_abiertos", {}).pop(cmd, [])
    marca = etiqueta or (tr("✓ Respondiste") + (f": {texto[:30]}" if texto else ""))
    for mid in ids[-10:]:
        api("editMessageReplyMarkup", chat_id=conf["dueno"], message_id=mid,
            reply_markup={"inline_keyboard": [[{"text": marca, "callback_data": "x|x|x"}]]})
    guardar_conf(conf)
    return len(ids[-10:])


# (27-oct, idea de clawd #1062: "el aviso de permiso se queda aunque Codex lo resolvio en nativo") Si le escribes a un chat directo en la
# app de Claude de la PC (el hook manda UserPromptSubmit a la cola), sus avisos pendientes se cierran igual que si respondieras desde Kodama.
# Lo que Kodama mismo entrego (buzon o puente) NO cuenta: ya cerro sus avisos al responder, y asi no hay un cierre duplicado.
_MARCAS_KODAMA = ("📱", "🐾")
_ENTREGA_KODAMA = "con Kodama; contéstale aquí"


def entregado_por_kodama(texto, cmd):
    t = (texto or "").strip()
    if t.startswith(_MARCAS_KODAMA) or _ENTREGA_KODAMA in t[:200]:
        return True
    try:   # respuesta por el puente (sin marca): igual a una que Kodama registro hace menos de 2 min para ese chat
        for l in leer_ultimas(RESP, 40):
            r = json.loads(l)
            if r.get("chat") == cmd and time.time() - r.get("ts", 0) < 120 and (r.get("texto") or "").strip() == t:
                return True
    except Exception:
        pass
    return False


def cerrar_por_respuesta_en_pc(conf, item):
    """item = linea de la cola con evento UserPromptSubmit. Devuelve True si cerro avisos."""
    s = next((x for x in sesiones() if x.get("session_id") == item.get("session_id")), None)
    r = info(s) if s else None
    if not r:
        return False
    cmd = r[0]
    if entregado_por_kodama(item.get("texto"), cmd):
        return False
    ts = item.get("ts", 0)
    ESPERA[:] = [it for it in ESPERA if not (it.get("session_id") == item.get("session_id") and it.get("ts", 0) <= ts)]   # avisos aun sin mandar: ya no hacen falta
    if cmd not in conf.get("pendientes", {}) and not conf.get("tg_abiertos", {}).get(cmd):
        return False   # nada abierto: no se toca nada (ni se guarda hub.json)
    n = cerrar_avisos(conf, cmd, etiqueta=tr("✓ Respondiste en la PC"))
    log(f"respondiste en la PC: {n} aviso(s) de {cmd} cerrados")
    return True


def registrar_respuesta(cmd, texto):
    with open(os.path.join(BASE, "respuestas.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "evento": "yo", "chat": cmd, "texto": texto, "via": "telegram"}, ensure_ascii=False) + "\n")   # (26-oct) "via": para las estadisticas de "Lo nuevo"


def procesar_cola(conf, pos):
    if not os.path.exists(COLA):
        return pos
    tam = os.path.getsize(COLA)
    if tam < pos:
        pos = 0
    if tam == pos:
        return pos
    with open(COLA, "rb") as f:
        f.seek(pos)
        bloque = f.read()
    datos, _, _ = bloque.rpartition(b"\n")
    if not datos and not bloque.endswith(b"\n"):
        return pos                      # solo hay una linea a medio escribir: esperar
    pos += len(datos) + 1
    lineas = datos.decode("utf-8", errors="replace").splitlines()
    for l in lineas:
        try:
            item = json.loads(l)
        except Exception:
            continue
        if time.time() - item.get("ts", 0) > VIEJO_SEG:    # tras un corte largo no se manda una avalancha de avisos viejos
            continue
        if item.get("evento") in ("UserPromptSubmit", "Archivo"):   # (15-oct) lo que TU escribiste en la PC / archivos que te mando: se muestra, no se avisa
            if item.get("evento") == "UserPromptSubmit":   # (27-oct) ... y cierra los avisos pendientes de ese chat
                try:
                    cerrar_por_respuesta_en_pc(conf, item)
                except Exception as e:
                    log(f"error cerrar por respuesta en la PC: {type(e).__name__}: {e}")
            continue
        if item.get("permiso_id"):   # pedido de permiso: el hook ya vio que estas lejos y espera 110 s -> sin ventana
            if time.time() - item.get("ts", 0) < 100:
                enviar_aviso(conf, item)
            continue
        if conf.get("dueno") and (conf.get("modo") == "siempre" or segundos_sin_uso() >= AUSENTE_SEG) and not mirando_claude():
            ESPERA.append(item)
    vaciar_espera(conf)
    return pos


ESPERA = []          # avisos esperando a ver si llegan mas en la ventana
VENTANA_SEG = 30
VIEJO_SEG = 900      # al volver de un corte, se avisa lo de los ultimos 15 min; lo anterior queda en la app


# ---- mantenimiento (14-oct): rotar archivos que crecen, purgar fotos, latido para el aviso de salud ----
TOPE_BYTES = 5 * 1024 * 1024
LATIDO = os.path.join(BASE, "latido")
ARRANQUE = time.time()
SALUD = {"telegram_ok": 0, "push_error": None}


# (27-oct) el ovillo de dos lunas: cada log guarda solo el vivo y su .1; lo que pasa de ahi se pisa, no se acumula.
def rotar(ruta):
    """Si pasa de 5 MB, lo renombra a .1 (pisando el .1 anterior). Devuelve True si roto."""
    try:
        if os.path.exists(ruta) and os.path.getsize(ruta) > TOPE_BYTES:
            os.replace(ruta, ruta + ".1")
            return True
    except OSError:      # otro proceso lo tiene abierto en ese instante: se intenta en la proxima vuelta
        pass
    return False


RESPALDOS = config.RESPALDOS


def respaldar():
    """(14-oct) Una vez por dia: zip con el estado que no se puede rehacer (hub.json, claves VAPID, suscripciones,
    clave local, ajustes, registro de sesiones) + el estado del Tailscale del companero (ts\\, su identidad en la
    red). Sin fotos ni capturas. Se guardan los ultimos 7."""
    import zipfile
    os.makedirs(RESPALDOS, exist_ok=True)
    destino = os.path.join(RESPALDOS, time.strftime("%Y-%m-%d") + ".zip")
    if os.path.exists(destino):
        return
    fuera = {"fotos", "puente", "escritorio-captura.png", "escritorio-captura.txt", "latido", "hub.pid", "escritorio.pid",
             "local.key"}   # (15-oct, contra #14) la clave local no va al respaldo: si falta, el hub crea otra
    try:
        with zipfile.ZipFile(destino + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
            for raiz, etiqueta in ((BASE, "estado"), (config.TS_DIR, "ts")):
                for dirpath, dirs, files in os.walk(raiz):
                    dirs[:] = [x for x in dirs if x not in fuera]
                    for f in files:
                        if f in fuera or f.endswith((".tmp", ".1")):
                            continue
                        p = os.path.join(dirpath, f)
                        try:
                            z.write(p, os.path.join(etiqueta, os.path.relpath(p, raiz)))
                        except OSError:     # archivo en uso (log de tailscaled): se salta
                            pass
        os.replace(destino + ".tmp", destino)
        for viejo in sorted(f for f in os.listdir(RESPALDOS) if f.endswith(".zip"))[:-7]:
            os.remove(os.path.join(RESPALDOS, viejo))
        log(f"respaldo {os.path.basename(destino)} ({os.path.getsize(destino) // 1024} KB)")
    except Exception as e:
        log(f"respaldo fallo: {type(e).__name__}")


# ---- (15-oct) mensajes para chats dormidos: quedan en cola y se entregan solos cuando el chat despierta ----
PENDIENTES_DIR = os.path.join(BASE, "pendientes")


def poner_pendiente(cmd, texto, marca, socket_viejo):
    os.makedirs(PENDIENTES_DIR, exist_ok=True)
    nombre = f"{int(time.time() * 1000)}-{secrets.token_hex(3)}.json"
    json.dump({"ts": time.time(), "chat": cmd, "texto": texto, "marca": marca, "socket": socket_viejo, "intento": 0},
              open(os.path.join(PENDIENTES_DIR, nombre), "w", encoding="utf-8"), ensure_ascii=False)


def entregar_pendientes():
    """Cada 10 s: si el chat de un mensaje en cola registro un buzon NUEVO (desperto) o paso 1 min del ultimo intento,
    se reintenta. Entregado -> se borra y se avisa. Mas de 24 h -> se descarta (queda en el historial como tuyo)."""
    while True:
        time.sleep(10)
        try:
            archivos = sorted(f for f in os.listdir(PENDIENTES_DIR) if f.endswith(".json"))
        except OSError:
            continue
        for f in archivos:
            ruta = os.path.join(PENDIENTES_DIR, f)
            try:
                p = json.load(open(ruta, encoding="utf-8"))
                if time.time() - p["ts"] > 86400:
                    os.remove(ruta); log(f"mensaje en cola para {p['chat']} descartado (24 h sin despertar)"); continue
                s = sesion_por_cmd(p["chat"])
                if not s:
                    continue
                nuevo = s.get("socket") and s.get("socket") != p.get("socket")
                previo = grupos_app.chat_enfocado()
                # (16-oct) se reintenta despertar cada 10 min (antes una sola vez: si la PC estaba suspendida, no llegaba)
                if not nuevo and time.time() - p.get("despertado", 0) > 600 and despertar_chat(p["chat"]):
                    p["despertado"] = time.time(); p["previo"] = previo
                    json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    continue   # en ~6 s registra su buzon nuevo y la proxima vuelta lo entrega
                if not nuevo and time.time() - p.get("ult", 0) < 60:
                    continue
                p["ult"] = time.time(); p["intento"] = p.get("intento", 0) + 1
                err = entregar(s, p["texto"], p.get("marca", "📱 "))
                if err:
                    json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    continue
                os.remove(ruta)
                log(f"mensaje en cola ENTREGADO a {p['chat']} (intento {p['intento']})")
                # (15-oct, contra #22) la app de Claude vuelve al chat que tenias abierto (si sigues lejos de la PC)
                if p.get("previo") and p["previo"] != s.get("session_id") and segundos_sin_uso() >= 60:
                    try:
                        u = grupos_app.enlace(p["previo"])
                        if u:
                            os.startfile(u)
                    except Exception:
                        pass
                nombre = (elegidos_por_cmd().get(p["chat"]) or ("", p["chat"]))[1]
                threading.Thread(target=push_a_todos, args=("✓ " + tr("Entregado a {n}", n=nombre), p["texto"][:120], p["chat"]), daemon=True).start()
            except Exception as e:
                log(f"cola de entregas: {type(e).__name__}")


def prender_pantalla():
    """(16-oct) Esta laptop (Modern Standby) se suspende al apagarse la pantalla y en suspension la app de Claude no
    revive un chat dormido: un mensaje del celular de las 16:02 llego recien a las 19:52. Probado el 16-oct 21:20: un
    pedido de pantalla (SetThreadExecutionState DISPLAY+SYSTEM, de una vez) SACA a la PC de la suspension (evento 507
    "Reason: SetThreadExecutionState"). Solo en el horario de estado\\despierto.json (8-22); despues la pantalla se
    vuelve a apagar sola con el tiempo de Windows. True si lo pidio."""
    try:
        h = json.load(open(os.path.join(BASE, "despierto.json"), encoding="utf-8"))
        desde, hasta = int(h.get("desde", 8)), int(h.get("hasta", 22))
    except Exception:
        desde, hasta = 8, 22
    if not desde <= time.localtime().tm_hour < hasta:
        return False
    ctypes.windll.kernel32.SetThreadExecutionState(0x00000002 | 0x00000001)   # ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
    return True


def despierta_hasta_entregar(cmd, maximo=180):
    """Pide pantalla + sistema de forma continua (solo este hilo) mientras quede un mensaje en cola para `cmd`."""
    k, fin = ctypes.windll.kernel32, time.time() + maximo
    k.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)   # CONTINUOUS | DISPLAY | SYSTEM
    try:
        while time.time() < fin:
            time.sleep(5)
            try:
                quedan = any(json.load(open(os.path.join(PENDIENTES_DIR, f), encoding="utf-8")).get("chat") == cmd
                             for f in os.listdir(PENDIENTES_DIR) if f.endswith(".json"))
            except Exception:
                quedan = True
            if not quedan:
                break
        log(f"despierta para {cmd}: {'entregado' if not quedan else 'sin entregar en 3 min'}; la PC vuelve a su ritmo")
    finally:
        k.SetThreadExecutionState(0x80000000)   # suelta el pedido de este hilo


def despertar_chat(cmd):
    """(15-oct) Despierta un chat dormido abriendolo en la app de Claude (su enlace claude://…): la app vuelve a
    levantar su proceso y en ~6 s tiene buzon nuevo (probado con Documental). Abrir la app le quita la pantalla a lo
    que estes haciendo en la PC, asi que SOLO si no la usas hace 2 min o mas. True si lo intento."""
    try:
        if segundos_sin_uso() < 120:
            return False
        cli = next((c for c, v in todos_elegidos().items() if v[0] == cmd), None)
        url = grupos_app.enlace(cli) if cli else None
        if not url or not url.startswith("claude://"):
            return False
        if prender_pantalla():
            # (19-oct) el 18-oct la PC salia de la suspension pero a los 30 s volvia a entrar (22 veces, 11:35-13:17)
            # sin que el chat alcanzara a revivir: ahora se la mantiene despierta hasta entregar (max. 3 min)
            threading.Thread(target=despierta_hasta_entregar, args=(cmd,), daemon=True).start()
            time.sleep(3)   # que Windows termine de salir de la suspension antes de abrir el enlace
        os.startfile(url)
        log(f"despertando {cmd} (PC sin uso): abro su chat en la app de Claude")
        return True
    except Exception as e:
        log(f"no pude despertar {cmd}: {type(e).__name__}")
        return False


def elegidos_por_cmd():
    return {v[0]: v for v in todos_elegidos().values()}


def vigilar_tailscale():
    """(14-oct) el Tailscale propio del companero (el que conecta el celular) se cae a veces con cambios de red; la
    tarea programada lo levanta cada 10 min. Este vigilante mira cada 30 s si su PID sigue vivo y, si no, corre
    arrancar.pyw (que solo arranca lo que falta). Mirar un PID no gasta nada."""
    pidf = os.path.join(config.TS_DIR, "tailscaled.pid")
    lanz = os.path.join(config.APP_DIR, "arrancar.pyw")
    pyw = os.path.join(config.APP_DIR, ".venv", "Scripts", "pythonw.exe")
    k = ctypes.windll.kernel32
    while True:
        time.sleep(30)
        try:
            pid = int(open(pidf).read().strip())
            h = k.OpenProcess(0x1000, False, pid)                     # PROCESS_QUERY_LIMITED_INFORMATION
            vivo = False
            if h:
                code = ctypes.c_ulong()
                vivo = bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
                k.CloseHandle(h)
            if not vivo and os.path.exists(lanz):
                log("tailscale del companero caido: lo relanzo")
                subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, lanz], cwd=config.APP_DIR,
                                 creationflags=0x08000000 | 0x00000008, close_fds=True)
                time.sleep(60)   # que arranque antes de volver a mirar
        except Exception:
            pass


def mantenimiento(conf, pos):
    """Cada hora y al arrancar. La cola solo se rota si ya se proceso entera (pos == tamaño)."""
    respaldar()
    for r in (LOG, RESP, os.path.join(BASE, "bench.jsonl")):
        rotar(r)
    if os.path.exists(COLA) and pos >= os.path.getsize(COLA) and rotar(COLA):
        pos = 0
        conf["cola_pos"] = 0; guardar_conf(conf)
    if os.path.isdir(FOTOS) and not conservar():   # fotos del celular: se borran a los 14 dias (salvo "Conservar siempre")
        for f in os.listdir(FOTOS):
            p = os.path.join(FOTOS, f)
            try:
                if time.time() - os.path.getmtime(p) > 14 * 86400:
                    os.remove(p)
            except OSError:
                pass
    if os.path.isdir(FASE_DIR):   # (27-oct) archivitos de "pensando/ejecutando" de sesiones que ya no se usan: a las 24 h
        for f in os.listdir(FASE_DIR):
            p = os.path.join(FASE_DIR, f)
            try:
                if time.time() - os.path.getmtime(p) > 86400:
                    os.remove(p)
            except OSError:
                pass
    return pos


def leer_ultimas(ruta, n=400):
    """Ultimas n lineas, mirando tambien el .1 si el archivo se acaba de rotar."""
    lineas = []
    for r in (ruta + ".1", ruta):
        if os.path.exists(r):
            lineas += open(r, encoding="utf-8").read().splitlines()[-n:]
    return lineas[-n:]


def vaciar_espera(conf, forzar=False):
    if not ESPERA:
        return
    if not forzar and time.time() - ESPERA[0]["ts"] < VENTANA_SEG:
        return
    lote = ESPERA[:]; ESPERA.clear()
    chats = {it["session_id"] for it in lote}
    if len(chats) == 1:                         # un solo chat: cada aviso normal (el filtro de frecuencia decide)
        for it in lote:
            enviar_aviso(conf, it)
        return
    enviados = [r for r in (enviar_aviso(conf, it, agrupado=True) for it in lote) if r and r != "fallo"]
    if not enviados:
        return
    PRIO = {"error": 0, "permiso": 1, "pregunta": 2, "termino": 3}
    enviados.sort(key=lambda r: PRIO.get(r[2], 9))
    ETQ = {k: tr(v) for k, v in {"pregunta": "pregunta", "permiso": "permiso", "error": "se atoró", "termino": "terminó"}.items()}
    lista = " · ".join(f"{emo} {nombre} ({ETQ.get(tipo, tipo)})".strip() for emo, nombre, tipo in enviados)
    titulo = tr("{k} chats te esperan", k=len(enviados)) if len(enviados) > 1 else f"{enviados[0][0]} {enviados[0][1]}"
    threading.Thread(target=push_a_todos, args=(titulo, lista, "", "grupo", pendientes(conf)), daemon=True).start()
    if len(enviados) > 1:
        api("sendMessage", chat_id=conf["dueno"], text=f"🔔 <b>{_html.escape(titulo)}</b>\n{_html.escape(lista)}", parse_mode="HTML")


def estado_txt():
    filas = []
    for cmd, nombre, emo in todos_los_chats():
        cands = [s for s in sesiones() if info(s)[0] == cmd]
        if not cands:
            filas.append(f"{emo} {nombre}: sin actividad registrada".strip())
            continue
        s = max(cands, key=lambda x: x.get("visto", 0))
        hace = int((time.time() - s.get("visto", 0)) / 60)
        filas.append(f"{emo} {nombre}: {s.get('estado', '?')} (hace {hace} min)".strip() +
                     (f" · {s['titulo']}" if s.get("titulo") else ""))
    return "\n".join(filas)


def atender(conf, msg):
    chat = msg.get("chat", {}).get("id")
    texto = (msg.get("text") or "").strip()
    if conf.get("dueno") and conf.get("codigo"):   # (auditoria) ya emparejado: el codigo no sirve mas
        conf.pop("codigo", None); guardar_conf(conf)
    if not conf.get("dueno"):
        if conf.get("codigo") and texto == f"/start {conf.get('codigo')}":
            conf["dueno"] = chat
            conf.pop("codigo", None)
            guardar_conf(conf)
            api("sendMessage", chat_id=chat, text=tr("¡Listo! Quedé emparejado solo contigo.") + "\n\n" + tr(AYUDA))
            log("emparejado")
        return
    if chat != conf["dueno"]:                        # cualquier otro: silencio, pero (26-oct) con alarma al dueno
        alarma(tr("Alguien escribió al bot de Kodama desde otro Telegram. No le respondí."), f"tg:{chat}")
        return
    if bloqueado():
        if texto == "/bloquear":
            api("sendMessage", chat_id=chat, text=tr("Kodama ya está bloqueado. Se desbloquea desde la PC.")); return
        api("sendMessage", chat_id=chat, text=tr("🔒 Kodama está bloqueado: no entrego mensajes. Se desbloquea desde la PC.")); return
    if texto == "/bloquear":
        poner_bloqueo(True, "telegram")
        api("sendMessage", chat_id=chat, text=tr("🔒 Bloqueado. No entrego nada que llegue del celular hasta que lo desbloquees en la PC.")); return
    if texto in ("/estado", "/start"):
        api("sendMessage", chat_id=chat, text=estado_txt()); return
    if texto in ("/completo", "/corto"):
        conf["tg_completo"] = texto == "/completo"; guardar_conf(conf)
        api("sendMessage", chat_id=chat, text=tr("Telegram: mensajes completos (Instalaciones sigue en corto).") if conf["tg_completo"] else tr("Telegram: solo el aviso corto; el texto completo en la app.")); return
    if texto in ("/siempre", "/ausente"):
        conf["modo"] = texto[1:]; guardar_conf(conf)
        api("sendMessage", chat_id=chat, text=tr("Modo: siempre (aviso todo)") if conf["modo"] == "siempre" else tr("Modo: ausente (aviso solo si la PC lleva 2 min sin uso)")); return
    if texto == "/grupo":
        ops = grupos_app.opciones(); sel = seleccion()
        api("sendMessage", chat_id=chat, text=tr("¿Qué chats llevo al celular?"),
            reply_markup={"inline_keyboard": [[{"text": ("● " if o["id"] == sel else "") + o["nombre"],
                                                "callback_data": f"g|{o['id']}|x"}] for o in ops]})
        return
    if texto in ("/ayuda", "/help"):
        api("sendMessage", chat_id=chat, text=tr(AYUDA)); return
    destino, cuerpo = None, texto
    if msg.get("photo") or (msg.get("document") or {}).get("mime_type", "").startswith("image/"):
        fid = msg["photo"][-1]["file_id"] if msg.get("photo") else msg["document"]["file_id"]
        info_f = api("getFile", file_id=fid)
        try:
            ruta_tg = info_f["result"]["file_path"]
            with urllib.request.urlopen(f"https://api.telegram.org/file/bot{TOKEN}/{ruta_tg}", timeout=60) as r:
                ruta = guardar_foto(r.read(), os.path.splitext(ruta_tg)[1] or ".jpg")
        except Exception as e:
            log(f"error foto telegram: {type(e).__name__}")
            api("sendMessage", chat_id=chat, text=tr("✗ No pude bajar la foto.")); return
        texto = cuerpo = (msg.get("caption") or "").strip()
        foto_txt = lambda t: texto_con_foto(ruta, t)
    else:
        foto_txt = None
    rep = msg.get("reply_to_message")
    if rep:
        sid = conf.get("mapa", {}).get(str(rep.get("message_id")))
        destino = next((s for s in sesiones() if s["session_id"] == sid), None)
    if texto.startswith("/"):
        cmd, _, cuerpo = texto[1:].partition(" ")
        if cmd.lower() in [c for c, _, _ in todos_los_chats()]:
            destino = sesion_por_cmd(cmd.lower())
            if not cuerpo.strip() and not foto_txt:
                api("sendMessage", chat_id=chat, text=tr("Escribe el mensaje después del comando: /{c} …", c=cmd)); return
    if not destino:
        api("sendMessage", chat_id=chat, text=tr("¿Para qué chat? Responde deslizando sobre su mensaje.")); return
    cuerpo = foto_txt(cuerpo.strip()) if foto_txt else cuerpo.strip()
    err = entregar(destino, cuerpo)
    if not err:
        cerrar_avisos(conf, info(destino)[0], cuerpo)
    cmd, nombre, emo = info(destino)
    api("sendMessage", chat_id=chat, text=f"✗ {nombre}: {err}" if err else tr("✓ Enviado a {e} {n}", e=emo, n=nombre).replace("  ", " "))


# ---------- servidor web para la app del iPhone (etapa 2) ----------
# Escucha SOLO en 127.0.0.1; desde el iPhone se llega por `tailscale serve` (segundo Tailscale,
# red personal). Serve agrega Tailscale-User-Login: solo se atiende a la cuenta de LShinox.
import http.server
import threading

WEB = config.WEB
RESP = os.path.join(BASE, "respuestas.jsonl")
PUERTO_WEB = config.PUERTO_BASE   # (26-oct) 8787; si no se puede abrir, servir_web() prueba 8788..8799 y deja aca el real
PUERTO_TXT = os.path.join(BASE, "puerto.txt")
HOSTS_VISTOS = set()
POSTS = []   # horas de los ultimos POST (tope de frecuencia)
CERRAR = []   # respuestas hechas por la web/escritorio: el bucle principal cierra sus avisos de Telegram
import hmac
import secrets
_KEY = os.path.join(BASE, "local.key")
if not os.path.exists(_KEY):
    open(_KEY, "w").write(secrets.token_hex(24))
CLAVE_LOCAL = open(_KEY).read().strip()
TICKETS = {}   # ticket de un solo uso -> vence (abrir el panel de animaciones sin poner la clave en la URL)
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/manifest+json",
         ".png": "image/png", ".css": "text/css"}


def permitido(login):
    try:
        dueno_web = json.load(open(os.path.join(BASE, "web.json"), encoding="utf-8")).get("dueno_web", "")
    except Exception:
        dueno_web = ""
    return bool(dueno_web) and login.lower() == dueno_web.lower()


# (26-oct, LShinox: "deberia ser solo un cel") aparato del celular: ademas de la cuenta, se mira QUE aparato de la red
# personal pide (tailscale whois de la IP que pone `serve` en X-Forwarded-For). El primero queda registrado; otro
# aparato con la misma cuenta no entra y dispara la alarma. Bloqueo de emergencia: corta todo lo que entra del celular
# (app y Telegram); se activa desde el celular o la PC y solo se quita en la PC.
APARATOS = os.path.join(BASE, "aparatos.json")
BLOQUEO = os.path.join(BASE, "bloqueo_celular.json")
TS_EXE = r"C:\Program Files\Tailscale\tailscale.exe"
TS_SOCKET = r"\\.\pipe\companero-tailscaled"
_WHOIS = {}     # ip -> (vence, id estable, nombre)
_ALARMAS = {}   # clave -> ultima alarma


def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else defecto
    except Exception:
        return defecto


def _guardar_json(ruta, d):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def bloqueado():
    return bool(_leer_json(BLOQUEO, {}).get("activo"))


def poner_bloqueo(si, desde):
    _guardar_json(BLOQUEO, {"activo": bool(si), "desde": desde, "hora": time.strftime("%Y-%m-%d %H:%M:%S")})
    log(f"bloqueo del celular {'ACTIVADO' if si else 'quitado'} desde {desde}")


def alarma(texto, clave):
    """Aviso urgente por Telegram y push (una vez cada 30 min por clave). Va al celular registrado: si alguien
    intenta entrar con otro aparato, el dueno se entera en el suyo."""
    if time.time() - _ALARMAS.get(clave, 0) < 1800:
        return
    _ALARMAS[clave] = time.time()
    log(f"ALARMA: {texto}")
    threading.Thread(target=_mandar_alarma, args=(texto,), daemon=True).start()   # Telegram + push tardan ~9 s: no frenar el pedido


def _mandar_alarma(texto):
    conf = cargar_conf()
    if TOKEN and conf.get("dueno"):
        try:
            api("sendMessage", chat_id=conf["dueno"], text="🚨 " + texto + "\n\n" + tr("Si no fuiste tú: menú de la mascota → Bloquear celular."))
        except Exception as e:
            log(f"alarma por Telegram fallo: {e}")
    try:
        push_a_todos("🚨 Kodama", texto, "", tipo="error")
    except Exception as e:
        log(f"alarma por push fallo: {e}")


def _whois(ip):
    c = _WHOIS.get(ip)
    if c and c[0] > time.time():
        return c[1], c[2]
    try:
        r = subprocess.run([TS_EXE, f"--socket={TS_SOCKET}", "whois", "--json", ip], capture_output=True, text=True,
                           timeout=6, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        n = json.loads(r.stdout).get("Node") or {}
        sid, nombre = n.get("StableID", ""), n.get("ComputedName") or n.get("Name", "")
    except Exception as e:
        log(f"whois {ip} fallo: {e}")
        return "", ""
    if sid:
        _WHOIS[ip] = (time.time() + 600, sid, nombre)
    return sid, nombre


def aparato_ok(ip):
    """(ok, motivo). Sin whois no se entra (falla cerrado)."""
    sid, nombre = _whois(ip) if ip else ("", "")
    if not sid:
        return False, "aparato sin identificar"
    reg = _leer_json(APARATOS, {})
    lista = reg.get("aparatos") or []
    if not lista:   # el primero que entra queda registrado (hoy: el iPhone ya emparejado)
        reg["aparatos"] = [{"id": sid, "nombre": nombre, "desde": time.strftime("%Y-%m-%d %H:%M")}]
        _guardar_json(APARATOS, reg)
        log(f"aparato registrado: {nombre}")
        return True, ""
    if any(a.get("id") == sid for a in lista):
        return True, ""
    alarma(tr("Un aparato que no es tu celular ({n}) intentó entrar a Kodama. No lo dejé pasar.", n=nombre or "?"), "ap:" + sid)
    return False, "aparato no registrado"


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


def uso_plan():
    """(15-oct) % del plan (5 h y semana). Lo calcula el hilo estimar_uso() con estimador.py: exacto si hay un dato de
    menos de 20 min (app de Claude o chat Medidor), si no ESTIMADO con lo que gastaron los chats (sin gastar plan).
    {"5h": {"pct", "estimado"?}, "semana": {...}, "ts", "base_ts"?} o None."""
    return _EST.get("v")


_EST = {"v": None, "pedido5h": 0}


def estimar_uso():
    """Cada 60 s: lee lo nuevo de los transcripts y recalcula. Si el estimado de 5 h pasa de 80 % y no estas en la PC,
    pide UNA lectura exacta al chat Medidor (una sola vez por ventana de 5 h): es lo unico que gasta plan."""
    import estimador
    while True:
        try:
            estimador.actualizar()
            v = estimador.estimar(grupos_app.APP)
            _EST["v"] = v
            p5 = ((v or {}).get("5h") or {})
            if p5.get("estimado") and p5.get("pct", 0) >= 80 and segundos_sin_uso() >= 120 and lectura_exacta_activa() \
                    and time.time() - _EST["pedido5h"] > 5 * 3600:
                _EST["pedido5h"] = time.time()
                log(f"estimado 5 h {p5['pct']} %: pido lectura exacta al Medidor")
                pedir_medicion()
        except Exception as e:
            log(f"estimador: {type(e).__name__}: {e}")
        time.sleep(60)


MEDIDOR_DIR = config.CHAT_DIR   # (22-oct) antes APP_DIR\medidor
# las instrucciones van EN el pedido: asi el Medidor funciona aunque se haya creado en otra carpeta (sin su CLAUDE.md)
PEDIDO_MEDIR = ('MEDIR. Llama UNA vez a la herramienta mcp__ccd_session_mgmt__get_usage y responde SOLO esta linea JSON, sin '
                'nada mas: {"medidor": 1, "5h": <percentUsed de "5-hour limit">, "semana": <percentUsed de "Weekly · all '
                'models">, "reinicia5h": "<resetsAt de "5-hour limit">"}. Si falla: {"medidor": 1, "error": "<motivo>"}.')


def regs_medidor():
    """Registros del chat Medidor: el de estado\\medidor.json ({"sid": ...}) o cualquiera abierto en la carpeta medidor."""
    try:
        sid = json.load(open(os.path.join(BASE, "medidor.json"), encoding="utf-8")).get("sid")
    except (OSError, ValueError):
        sid = None
    clave, out = config.clave_carpeta(MEDIDOR_DIR), []
    for n in os.listdir(SES) if os.path.isdir(SES) else []:   # todos los registros (sesiones() solo trae chats de la app)
        if n.endswith(".json"):
            try:
                x = json.load(open(os.path.join(SES, n), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if x.get("session_id") == sid or x.get("proyecto") == clave:
                out.append(x)
    # (22-oct) si hay chat en la carpeta de Kodama, manda ese: el de medidor.json puede ser uno viejo (el Medidor de antes)
    propios = [x for x in out if x.get("proyecto") == clave]
    return propios or out


LECTURA = os.path.join(BASE, "lectura_exacta.json")


def lectura_exacta_activa():
    """(22-oct, LShinox) la lectura exacta por el chat de Kodama es un EXTRA de Ajustes, apagado por defecto: gasta un
    poco de plan y cambia de chat unos segundos. Sin ajuste guardado: activa solo si ese chat ya existe (esta PC)."""
    try:
        return bool(json.load(open(LECTURA, encoding="utf-8")).get("activa"))
    except (OSError, ValueError):
        return bool(regs_medidor())


def activar_lectura_exacta(on):
    """Guarda el ajuste y, al activar, deja lista la carpeta del chat (CLAUDE.md + permisos) sin pisar una que exista."""
    json.dump({"activa": bool(on)}, open(LECTURA, "w", encoding="utf-8"))
    if on and not os.path.exists(os.path.join(MEDIDOR_DIR, "CLAUDE.md")):
        import shutil
        shutil.copytree(os.path.join(config.APP_DIR, "plantillas", "kodama-chat"), MEDIDOR_DIR, dirs_exist_ok=True)
        log("carpeta del chat de Kodama creada")
    return estado_lectura()


def estado_lectura():
    return {"ok": True, "activa": lectura_exacta_activa(), "carpeta": MEDIDOR_DIR, "chat_listo": bool(regs_medidor())}


def ordenar_kodama(orden):
    """(22-oct) ARCHIVAR/DESARCHIVAR <local_…> al chat de Kodama (sus herramientas oficiales de la app). Lo pediste
    vos desde la mascota, asi que se despierta el chat aunque estes en la PC (forzar). None si se mando, o el motivo."""
    if not _re.fullmatch(r"(ARCHIVAR|DESARCHIVAR) local_[0-9a-f-]{36}", orden or ""):
        return "orden inválida"
    log(f"Kodama: {orden.split()[0].lower()}")
    return pedir_medicion(forzar=True, pedido=orden)


def pedir_medicion(forzar=False, pedido=PEDIDO_MEDIR):
    """Manda el pedido de lectura exacta al chat Medidor. La app de Claude duerme ese chat enseguida (sin buzon), asi que
    casi siempre hay que despertarlo abriendo su enlace: eso cambia el chat que muestra la app de Claude por unos
    segundos. Solo se hace si no usas la PC, o si lo pediste con el boton "Actualizar" (forzar). Al terminar, la app
    vuelve al chat que tenias abierto. Devuelve None si se pidio, o el motivo si no se pudo."""
    if pedido == PEDIDO_MEDIR and not lectura_exacta_activa():
        return "la lectura exacta está apagada (Ajustes > Lectura exacta del uso)"
    regs = regs_medidor()
    if not regs:
        return "falta abrir el chat de Kodama (Ajustes > Lectura exacta del uso)"
    sid = max(regs, key=lambda x: x.get("visto", 0)).get("session_id")
    # (22-oct, probado) un chat ARCHIVADO no responde: la app muestra "Esta sesion esta archivada. Desarchivala para
    # seguir trabajando en ella". Se avisa enseguida en vez de quedarse "pidiendo el dato exacto…".
    if grupos_app.archivado(sid):
        log("el Medidor esta archivado: no se puede leer")
        return "el chat Medidor está archivado: desarchívalo en la app de Claude"
    if not entregar(max(regs, key=lambda x: x.get("visto", 0)), pedido, ""):
        log("pedido al chat de Kodama" if pedido != PEDIDO_MEDIR else "lectura exacta pedida al Medidor")
        return None
    if not forzar and segundos_sin_uso() < 120:
        return "el chat Medidor esta dormido y estas usando la PC"
    url = grupos_app.enlace(sid)
    if not url:
        return "no encuentro el chat Medidor en la app de Claude"
    previo = grupos_app.chat_enfocado()
    try:
        if forzar and prender_pantalla():   # solo si lo pediste ("Actualizar"); la lectura automatica no prende la PC
            time.sleep(3)
        os.startfile(url); log("despertando al Medidor")
    except Exception as e:
        return f"no pude despertar al Medidor ({type(e).__name__})"

    def seguir():
        antes = os.path.getsize(estimador_exactos()) if os.path.exists(estimador_exactos()) else 0
        enviado = False
        for _ in range(12):
            time.sleep(4)
            if not enviado:
                r = regs_medidor()
                if r and not entregar(max(r, key=lambda x: x.get("visto", 0)), pedido, ""):
                    enviado = True; log("pedido al chat de Kodama (despues de despertarlo)")
                    if pedido != PEDIDO_MEDIR:
                        time.sleep(8); break   # archivar/desarchivar: no hay lectura que esperar
            elif os.path.exists(estimador_exactos()) and os.path.getsize(estimador_exactos()) > antes:
                break
        if previo and previo != sid:   # la app de Claude vuelve al chat que tenias abierto
            try:
                u = grupos_app.enlace(previo)
                if u:
                    os.startfile(u)
            except Exception:
                pass
        if not enviado:
            log("el Medidor no desperto a tiempo")
    threading.Thread(target=seguir, daemon=True).start()
    return None


def estimador_exactos():
    return os.path.join(BASE, "uso_exacto.jsonl")

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
    maximo = 1_000_000 if ("1m" in modelo.lower() or tokens > 200_000) else 200_000
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
FASE_TIPOS = ("comando", "web", "subagente", "herramienta")


FASE_DIR = os.path.join(BASE, "fase")


def fase_parse(txt, ahora=None):
    """"fase|categoria|ts" (lo escriben companero_hook_pre.py y companero_hook.py) -> ("pensando"|"ejecutando"|None, categoria|None).
    "ejecutando" sin un PostToolUse que lo cierre vuelve solo a "pensando" a los 60 s."""
    try:
        fase, cat, ts = (txt or "").strip().split("|")
        ts = float(ts)
    except ValueError:
        return None, None
    ahora = time.time() if ahora is None else ahora
    if fase == "ejecutando" and 0 <= ahora - ts <= FASE_EJEC_SEG:
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
            tz = s.get("tareas")
            if isinstance(tz, dict) and isinstance(tz.get("t"), int) and tz["t"] > 0:
                edad = time.time() - float(tz.get("ts") or 0)
                if edad < 6 * 3600 and not (tz.get("h", 0) >= tz["t"] and edad > 1800):
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


# (14-oct) pestaña "Archivos" del celular: los HTML que hacen tus chats (los artifacts quedan solo locales), para
# abrirlos desde el cel. Se buscan en la carpeta de cada chat personal + config "carpetas_archivos". Se sirven en
# /ver/<id de carpeta>/<ruta> (asi sus imagenes y css relativos cargan) y SOLO tipos de pagina web: nunca .json, .md,
# .py ni claves. Van con CSP "sandbox": corren con origen propio y no pueden usar la API del compañero.
import hashlib
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
_TEMP_CLAUDE = os.path.normcase(os.path.join("AppData", "Local", "Temp", "claude"))


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
    if not partes[0].lower() == "appdata" and not any(
            os.path.normcase(archivo).startswith(os.path.normcase(r) + os.sep) for r in raices_links()):
        return None
    if partes[0].lower() == "appdata" and not os.path.normcase(rel).startswith(_TEMP_CLAUDE + os.sep):
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


def cwd_de(cmd):
    """Carpeta de trabajo del chat `cmd` (para los links relativos de sus mensajes)."""
    try:
        cli = next((cli for cli, v in todos_elegidos().items() if v[0] == cmd), None)
        s = next((s for s in grupos_app.catalogo()["sesiones"].values() if s["cli"] == cli), None) if cli else None
        return (s or {}).get("cwd")
    except Exception:
        return None


def todos_elegidos():
    return {**personales(), **elegidos()}


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


class Web(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _abrir(self):
        """/abrir?chat=<id>&r=<ruta>: un link a un archivo dentro de un mensaje (C:\\..., ~\\... o relativo a la
        carpeta del chat). Si se puede ver, redirige a /ver/h/<ruta desde HOME>; si no, una pagina corta que lo dice."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        r, cmd = (q.get("r") or [""])[0].strip(), (q.get("chat") or [""])[0]
        r = r.split("#")[0]
        if r.startswith("~"):
            r = HOME_N + r[1:]
        elif not os.path.isabs(r):
            base = cwd_de(cmd)
            r = os.path.join(base, r) if base else ""
        if r and os.path.isdir(r):
            return self._galeria(r)
        rel = ver_permitido(r) if r else None
        if not rel:
            b = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                 "<body style='font:17px system-ui;padding:24px;background:#1e1c1a;color:#f1ece4'>"
                 + _html.escape(tr("Ese archivo no se puede abrir desde el celular (no existe, o no es una página, imagen o PDF)."))
                 + "</body>").encode()
            self.send_response(404); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        self.send_response(302)
        self.send_header("Location", "/ver/h/" + urllib.parse.quote(rel.replace(os.sep, "/")))
        self.send_header("Content-Length", "0"); self.end_headers()

    def _galeria(self, carpeta):
        """(15-oct) Un link a una CARPETA (p. ej. "las imagenes estan en Cuentos\\flow"): pagina con miniaturas de lo
        que se puede ver adentro (imagenes, paginas, PDF; sin subcarpetas), lo mas nuevo primero. Mismas reglas que un
        archivo suelto (ver_permitido)."""
        items = []
        try:
            for n in os.listdir(carpeta):
                p = os.path.join(carpeta, n)
                rel = ver_permitido(p) if os.path.isfile(p) else None
                if rel:
                    items.append((os.path.getmtime(p), n, rel))
        except OSError:
            pass
        items.sort(reverse=True)
        imgs = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
        celdas = []
        for _t, n, rel in items[:120]:
            url = "/ver/h/" + urllib.parse.quote(rel.replace(os.sep, "/"))
            if n.lower().endswith(imgs):
                celdas.append(f"<a href='{url}' target='_blank'><img src='{url}' loading='lazy' alt=''><span>{_html.escape(n)}</span></a>")
            else:
                celdas.append(f"<a href='{url}' target='_blank' class='doc'><b>{_html.escape(os.path.splitext(n)[1][1:].upper())}</b><span>{_html.escape(n)}</span></a>")
        vacio = "" if celdas else "<p>" + _html.escape(tr("No hay imágenes, páginas ni PDF que se puedan abrir en esta carpeta.")) + "</p>"
        b = ("<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             "<title>" + _html.escape(os.path.basename(carpeta.rstrip("\\/"))) + "</title><style>"
             "body{margin:0;padding:14px;background:#1e1c1a;color:#f1ece4;font:15px system-ui}h1{font-size:17px;margin:0 0 12px}"
             ".g{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.g a{color:inherit;text-decoration:none;background:#2a2724;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}"
             ".g img{width:100%;aspect-ratio:1;object-fit:cover;display:block}.g span{font-size:12px;padding:6px 8px;color:#b3a99d;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
             ".g .doc b{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:20px;color:#8fcf5f}</style>"
             "<h1>" + _html.escape(os.path.basename(carpeta.rstrip("\\/"))) + f" · {len(items)}</h1>{vacio}<div class=g>" + "".join(celdas) + "</div></html>").encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _ver(self, resto):
        """/ver/<id>/<ruta>: un archivo de la carpeta de un chat (solo tipos de pagina web), en sandbox."""
        rid, _, rel = resto.partition("/")
        if rid == "h":   # (14-oct) links de los mensajes: cualquier archivo que pase ver_permitido()
            archivo = os.path.normpath(os.path.join(HOME_N, rel))
            if not rel or not ver_permitido(archivo):
                return self._json(404, {"ok": False})
            archivo = os.path.realpath(archivo)
            ext = os.path.splitext(archivo)[1].lower()
        else:
            base = (raices_archivos().get(rid) or (None,))[0]
            if not base or not rel:
                return self._json(404, {"ok": False})
            base = os.path.realpath(base)
            archivo = os.path.realpath(os.path.normpath(os.path.join(base, rel)))
            ext = os.path.splitext(archivo)[1].lower()
            if not archivo.lower().startswith(base.lower().rstrip("\\/") + os.sep) or ext not in VER_TIPOS or not os.path.isfile(archivo):
                return self._json(404, {"ok": False})
            if any(p in _SALTAR or p.startswith(".") for p in os.path.relpath(archivo, base).split(os.sep)[:-1]):
                return self._json(404, {"ok": False})
        self.send_response(200)
        self.send_header("Content-Type", VER_TIPOS[ext])
        self.send_header("Content-Length", str(os.path.getsize(archivo)))
        self.send_header("Cache-Control", "no-cache"); self.send_header("X-Content-Type-Options", "nosniff")
        if ext in (".html", ".htm", ".svg"):   # lo que puede correr codigo va aislado (el PDF no: el visor del iPhone no lo abre en sandbox)
            self.send_header("Content-Security-Policy", "sandbox allow-scripts allow-popups allow-forms allow-modals")
        self.end_headers()
        with open(archivo, "rb") as f:
            while True:
                b = f.read(65536)
                if not b:
                    break
                self.wfile.write(b)

    # (14-oct) la mascota en Tauri es una pagina con origen propio que le pide al hub con fetch: CORS SOLO para ese origen
    ORIGENES_TAURI = ("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost")

    def end_headers(self):
        o = self.headers.get("Origin", "") if hasattr(self, "headers") and self.headers else ""
        if o in self.ORIGENES_TAURI:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Headers", "X-Companero-Local, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Vary", "Origin")
        # (14-oct, auditoria) otra pagina no puede enmarcar la app ni cargar sus .js/.json; /ver queda afuera porque sus
        # paginas corren en sandbox (origen "null") y cargan sus imagenes/css de aca mismo
        if not getattr(self, "path", "").lstrip("/").startswith("ver/"):
            # (22-oct) SAMEORIGIN (antes DENY): el visor de archivos de la app (iframe) abre /abrir; otro sitio sigue sin poder
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            if o not in self.ORIGENES_TAURI:
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def do_OPTIONS(self):   # pedido previo del navegador (CORS); solo se contesta al origen de la mascota
        if self.headers.get("Origin", "") not in self.ORIGENES_TAURI:
            return self._json(403, {"ok": False})
        self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()

    def _largo(self):   # (14-oct, auditoria) un Content-Length negativo o basura colgaba el hilo
        try:
            return max(0, int(self.headers.get("Content-Length", 0)))
        except (TypeError, ValueError):
            return 0

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _autorizado(self):
        # app de escritorio (misma PC): clave local en estado\local.key (solo la lee tu usuario)
        loc = self.headers.get("X-Companero-Local", "")
        if loc and CLAVE_LOCAL and hmac.compare_digest(loc, CLAVE_LOCAL):
            return True
        # (14-oct) panel de animaciones abierto en el navegador de la PC: ?k=<clave> una vez -> cookie de la sesion
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("k", [""])[0]
        # (15-oct, contra #14) ?t=<ticket de un solo uso, 60 s> en vez de ?k=<clave>: la clave ya no queda en el historial
        tk = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t", [""])[0]
        if tk and self.client_address[0] == "127.0.0.1" and TICKETS.pop(tk, 0) > time.time():
            self._poner_cookie = True
            return True
        ck = dict(x.strip().split("=", 1) for x in self.headers.get("Cookie", "").split(";") if "=" in x).get("companero_k", "")
        if CLAVE_LOCAL and self.client_address[0] == "127.0.0.1" and \
                ((q and hmac.compare_digest(q, CLAVE_LOCAL)) or (ck and hmac.compare_digest(ck, CLAVE_LOCAL))):
            self._poner_cookie = bool(q)
            return True
        if permitido(self.headers.get("Tailscale-User-Login", "")):
            host = (self.headers.get("Host", "") + " | " + self.headers.get("X-Forwarded-Host", "")).strip()
            if host not in HOSTS_VISTOS:
                HOSTS_VISTOS.add(host); log(f"host visto: {host}")
            self._via_celular = True
            marcar_celular()
            # (14-oct, auditoria) solo por la direccion publica configurada (lo que pone `tailscale serve`)
            esperado = urllib.parse.urlparse(config.URL_PUBLICA).hostname if config.URL_PUBLICA else None
            if esperado and self.headers.get("Host", "").split(":")[0].lower() != esperado.lower():
                log(f"rechazado host {self.headers.get('Host', '')[:60]}")
                self._json(403, {"ok": False, "error": "no autorizado"})
                return False
            ok, motivo = aparato_ok(self.headers.get("X-Forwarded-For", "").split(",")[0].strip())
            if not ok:
                log(f"rechazado: {motivo}")
                self._json(403, {"ok": False, "error": "no autorizado"})
                return False
            if bloqueado() and self.path.split("?")[0] not in ("/", "/app.html", "/api/bloqueo") and \
                    not self.path.split("?")[0].endswith((".js", ".css", ".png", ".json")):
                self._json(423, {"ok": False, "error": "bloqueado", "bloqueado": True})
                return False
            return True
        if self.headers.get("Tailscale-User-Login"):   # cuenta de Tailscale ajena
            alarma(tr("Una cuenta que no es la tuya intentó entrar a Kodama. No la dejé pasar."), "cta:" + self.headers.get("Tailscale-User-Login", "")[:60])
        self._json(403, {"ok": False, "error": "no autorizado"})
        return False

    def do_GET(self):
        if not self._autorizado():
            return
        ruta = self.path.split("?")[0].lstrip("/") or "app.html"
        # (14-oct, auditoria) pedidos que el navegador marca como de otro sitio: fuera (menos /ver y la mascota Tauri)
        # Abrir la app tocando un link desde otro sitio (navegacion de pagina entera) SI vale: no lee nada ajeno y la
        # app no se puede enmarcar (X-Frame-Options)
        navega = self.headers.get("Sec-Fetch-Mode", "") == "navigate" and self.headers.get("Sec-Fetch-Dest", "") in ("document", "")
        if self.headers.get("Sec-Fetch-Site", "") in ("cross-site", "same-site") and not ruta.startswith("ver/") \
                and not navega and self.headers.get("Origin", "") not in self.ORIGENES_TAURI:
            log(f"GET cruzado rechazado: {ruta[:40]}")
            return self._json(403, {"ok": False, "error": "no autorizado"})
        if ruta == "api/bloqueo":
            return self._json(200, {"bloqueado": bloqueado(), **{k: v for k, v in _leer_json(BLOQUEO, {}).items() if k in ("desde", "hora")}})
        if ruta == "api/estado":
            return self._json(200, self._recortar(historial()))
        if ruta == "api/eventos":   # (14-oct) SSE: la app recibe cada cambio al instante en vez de preguntar cada 4 s
            return self._eventos()
        if ruta == "api/grupos":   # que se puede llevar al celular (grupos de la app de Claude) y que esta elegido
            ops = grupos_app.opciones()
            return self._json(200, {"actual": seleccion(), "opciones": ops, "error": grupos_app.ERROR[:1] or None,
                                    "sesiones": len(grupos_app.catalogo()["sesiones"])})
        if ruta == "api/conectar":   # (21-oct) asistente "Conectar celular" (solo desde la PC)
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            conf = cargar_conf()
            enlace = f"https://t.me/{BOT['u']}?start={conf.get('codigo')}" if BOT.get("u") and conf.get("codigo") else ""
            return self._json(200, {"telegram": {"token": bool(TOKEN), "bot": BOT.get("u", ""), "emparejado": bool(conf.get("dueno")),
                                                 "enlace": enlace},
                                    "tailscale": cc.estado_tailscale()})
        if ruta == "api/qr":   # (21-oct) QR en SVG, solo para los enlaces del asistente
            if not self._en_pc():
                return self._json(403, {"ok": False})
            t = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t", [""])[0]
            if not (t.startswith("https://t.me/") or t in ("https://tailscale.com/download",) or (config.URL_PUBLICA and t == config.URL_PUBLICA)):
                return self._json(400, {"ok": False})
            import companero_conectar as cc
            b = cc.qr_svg(t)
            self.send_response(200); self.send_header("Content-Type", "image/svg+xml"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        if ruta == "api/lo-nuevo":   # (26-oct) novedades de la version instalada + estadisticas de la ultima semana (solo numeros)
            return self._json(200, lo_nuevo())
        if ruta == "api/actualizacion":   # (21-oct) version nueva disponible (la escribe vigilar_actualizaciones)
            try:
                return self._json(200, dict(json.load(open(ACTUALIZACION, encoding="utf-8")), actual=config.VERSION))
            except (OSError, ValueError):
                return self._json(200, {"actual": config.VERSION})
        if ruta == "api/salud":   # para revisar de un vistazo si el hub esta sano (14-oct)
            tam = os.path.getsize(COLA) if os.path.exists(COLA) else 0
            return self._json(200, {"pid": os.getpid(), "arranque": ARRANQUE, "ahora": time.time(),
                                    "telegram_ok": SALUD["telegram_ok"], "push_error": SALUD["push_error"],
                                    "reintentos_pendientes": len(REINTENTAR), "cola_sin_procesar": max(0, tam - SALUD.get("pos", 0))})
        if ruta == "api/anteriores":   # (14-oct) "cargar anteriores" en el celular: ?chat=<id>&antes=<ts>&n=30
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                cmd, antes, n = q["chat"][0], float(q.get("antes", ["9e12"])[0]), min(int(q.get("n", ["30"])[0]), 100)
            except (KeyError, ValueError):
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            return self._json(200, {"ok": True, "mensajes": mensajes_anteriores(cmd, antes, n)})
        if ruta == "api/inactivo":   # (14-oct) segundos sin mouse/teclado en Windows (la mascota en Tauri lo pide aca)
            return self._json(200, {"segundos": segundos_sin_uso()})
        if ruta == "api/pantalla":
            return self._json(200, {"completa": pantalla_completa()})
        if ruta == "api/vapid":
            return self._json(200, {"clave": open(os.path.join(BASE, "vapid_public.txt")).read().strip()})
        if ruta == "api/info":   # (15-oct) info del chat en el celular: contexto usado y uso del plan (5 h / semana)
            cmd = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("chat") or [""])[0]
            return self._json(200, {"ok": True, "contexto": contexto_chat(cmd), "uso": uso_plan()})
        if ruta == "api/pasos":   # (19-oct) Ajustes > "Mostrar lo que hizo el chat": pasos por turno del chat abierto
            cmd = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("chat") or [""])[0]
            return self._json(200, {"ok": True, "turnos": pasos_chat(cmd)})
        if ruta == "api/candidatos":   # (14-oct) Ajustes > Chats que se ven
            return self._json(200, {"ok": True, "chats": candidatos()})
        if ruta == "api/limpieza":   # (16-oct) Ajustes > Espacio: lo que guardo el Companero, el mas pesado primero
            if "solo=ajuste" in self.path:
                return self._json(200, {"ok": True, "conservar": conservar()})
            return self._json(200, {"ok": True, **escanear_limpieza()})
        if ruta == "api/archivos":   # (14-oct) pestaña Archivos del celular
            return self._json(200, {"ok": True, "archivos": listar_archivos()})
        if ruta.startswith("ver/"):
            return self._ver(urllib.parse.unquote(ruta[4:]))
        if ruta == "abrir":   # (14-oct) link a un archivo dentro de un mensaje
            return self._abrir()
        archivo = os.path.normpath(os.path.join(WEB, ruta))
        if not archivo.startswith(os.path.normpath(WEB) + os.sep) or not os.path.isfile(archivo):
            return self._json(404, {"ok": False})
        b = open(archivo, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(os.path.splitext(archivo)[1], "application/octet-stream"))
        self.send_header("Cache-Control", "no-cache")   # que el iPhone tome siempre la versión nueva
        if getattr(self, "_poner_cookie", False):   # panel abierto con ?k=: la cookie autoriza sus pedidos siguientes
            self.send_header("Set-Cookie", f"companero_k={CLAVE_LOCAL}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _recortar(self, h):
        """?ligero=1: solo los ultimos 3 mensajes de cada chat (la mascota cada 4 s, el celular en cada cambio), salvo el
        chat que el celular tiene abierto (?abierto=<id>), que va completo. (14-oct, rendimiento) el estado entero pesa
        ~100 KB y el celular lo recibia cada 3 s mientras algun chat trabajaba; asi baja a ~25 KB."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if (q.get("ligero") or [""])[0] != "1":
            return h
        ab = (q.get("abierto") or [""])[0]
        return {k: (dict(v, mensajes=v.get("mensajes", [])[-3:]) if isinstance(v, dict) and "mensajes" in v and k != ab else v)
                for k, v in h.items()}

    def _eventos(self):
        """Mantiene la conexion abierta: mira cada 1 s si cambio algo (fechas de archivos, sin leerlos) y entonces
        manda el estado entero. Latido cada 25 s para que el proxy de Tailscale no la corte. Max 30 min por conexion
        (el navegador reconecta solo)."""
        firma = firma_estado
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        ultima, latido, inicio = None, 0, time.time()
        try:
            while time.time() - inicio < 1800:
                f = firma()
                if f != ultima and time.time() - latido >= 3:   # max. 1 envio cada 3 s (el "que esta haciendo" cambia seguido)
                    ultima = f
                    self.wfile.write(b"data: " + json.dumps(self._recortar(historial()), ensure_ascii=False).encode() + b"\n\n"); self.wfile.flush()
                    latido = time.time()
                elif time.time() - latido > 20:
                    self.wfile.write(b"event: latido\ndata: 1\n\n"); self.wfile.flush(); latido = time.time()   # evento (no comentario): la app lo ve y sabe que el flujo esta vivo
                    if getattr(self, "_via_celular", False):
                        marcar_celular()   # se pudo escribir: la app del celular sigue abierta
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _en_pc(self):
        """(21-oct) Pedido hecho en ESTA PC (navegador o mascota), no desde el celular por `tailscale serve` (que tambien
        llega desde 127.0.0.1, pero trae Tailscale-User-Login)."""
        return self.client_address[0] == "127.0.0.1" and not self.headers.get("Tailscale-User-Login")

    def _cuerpo(self):
        try:
            d = json.loads(self.rfile.read(min(self._largo(), 20000)).decode() or "{}")
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def do_POST(self):
        if not self._autorizado():
            return
        # (14-oct) contra pedidos cruzados: una pagina de otro sitio abierta en el celular (o un HTML de la pestaña
        # Archivos, que corre en sandbox con origen "null") podria mandar un POST simple con tu identidad de Tailscale.
        # Solo se aceptan POST sin Origin (scripts locales) o desde la propia app, la PC o la mascota.
        o = self.headers.get("Origin", "")
        publico = config.URL_PUBLICA.rstrip("/").lower() if config.URL_PUBLICA else ""
        if o and o.lower() not in (publico, *self.ORIGENES_TAURI) and \
                not _re.match(r"^http://(127\.0\.0\.1|localhost):%d$" % PUERTO_WEB, o, _re.I):
            log(f"POST rechazado por origen {o[:60]}")
            return self._json(403, {"ok": False, "error": "origen no permitido"})
        # (14-oct, auditoria) tope de frecuencia: 60 pedidos por minuto en total (un toque humano no llega ni cerca)
        ahora = time.time()
        POSTS[:] = [t for t in POSTS if ahora - t < 60]
        if len(POSTS) >= 60:
            return self._json(429, {"ok": False, "error": "demasiados pedidos seguidos; espera un minuto"})
        POSTS.append(ahora)
        if self.path == "/api/bloqueo":   # (26-oct) bloqueo de emergencia: se pone desde el celular o la PC; se quita SOLO en la PC
            si, en_pc = bool(self._cuerpo().get("activo")), self._en_pc()
            if not si and not en_pc:
                return self._json(403, {"ok": False, "error": "se desbloquea desde la PC"})
            poner_bloqueo(si, "pc" if en_pc else "celular")
            return self._json(200, {"ok": True, "bloqueado": si})
        if self.path in ("/api/ticket", "/api/reporte", "/api/actualizar", "/api/probar", "/api/medir"):
            self._cuerpo()   # (21-oct) no usan el cuerpo, pero si queda sin leer, Windows corta la conexion (RST) y el pedido falla a veces
        if self.path == "/api/ajustes":   # panel web/ajustes.html: guarda los valores de animacion
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 20000)).decode())
                assert isinstance(d, dict)
                limpio = {sec: {k: float(v) for k, v in vals.items() if isinstance(v, (int, float))}
                          for sec, vals in d.items() if isinstance(vals, dict) and len(sec) < 30}
            except Exception:
                return self._json(400, {"ok": False, "error": "ajustes inválidos"})
            tmp = os.path.join(WEB, "ajustes.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(limpio, f, ensure_ascii=False, indent=1)
            os.replace(tmp, os.path.join(WEB, "ajustes.json"))
            log("ajustes de animacion guardados")
            return self._json(200, {"ok": True})
        if self.path == "/api/liberar":   # {"chat": cmd}: ✕ en la mascota/celular -> el chat deja de esperarte
            try:
                cmd = str(json.loads(self.rfile.read(min(self._largo(), 2000)).decode())["chat"])
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            s = sesion_por_cmd(cmd)
            if s and os.path.exists(os.path.join(PUENTE, s["session_id"] + ".esperando")):
                open(os.path.join(PUENTE, s["session_id"] + ".liberar"), "w").close()
                return self._json(200, {"ok": True})
            return self._json(200, {"ok": False, "error": "ese chat no te estaba esperando"})
        if self.path == "/api/permiso":   # {"id": "ab12cd34", "decision": "allow" | "deny"}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ok = responder_permiso(str(d.get("id")), str(d.get("decision")), str(d.get("motivo") or ""),
                                   str(d.get("alcance") or ""))
            return self._json(200, {"ok": ok} if ok else {"ok": False, "error": "ya caducó: se preguntó en la PC"})
        if self.path == "/api/reglas":   # (22-oct, mejora 2) {} = listar; {"borrar": clave, "sesion": sid|""} = quitar una
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 4000)).decode() or "{}")
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            reg = leer_reglas()
            if d.get("borrar"):
                if d.get("sesion"):
                    reg["tarea"][d["sesion"]] = [c for c in reg["tarea"].get(d["sesion"], []) if c != d["borrar"]]
                    if not reg["tarea"][d["sesion"]]:
                        reg["tarea"].pop(d["sesion"])
                else:
                    reg["siempre"] = [c for c in reg["siempre"] if c != d["borrar"]]
                guardar_reglas(reg); log("regla quitada")
            nombres = {s.get("session_id"): s.get("titulo") or "" for s in sesiones()} if reg["tarea"] else {}
            return self._json(200, {"ok": True, "siempre": reg["siempre"],
                                    "tarea": [{"sesion": k, "chat": nombres.get(k, k[:8]), "claves": v} for k, v in reg["tarea"].items()]})
        if self.path == "/api/pregunta":   # (19-oct) {"id": "ab12cd34", "respuestas": {"pregunta": "etiqueta"}}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 8000)).decode())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ok = responder_pregunta(str(d.get("id")), d.get("respuestas"))
            return self._json(200, {"ok": ok} if ok else {"ok": False, "error": "ya caducó: se preguntó en la PC"})
        if self.path == "/api/probar":   # (14-oct) boton de diagnostico.html: aviso de prueba a todos los celulares
            try:
                n = len(json.load(open(SUSC, encoding="utf-8")))
            except Exception:
                n = 0
            if not n:
                return self._json(200, {"ok": False, "error": "no hay celulares registrados (activa los avisos en la app)"})
            threading.Thread(target=push_a_todos, args=("Kodama", "Aviso de prueba ✅ — si lo ves, los avisos andan.", ""), daemon=True).start()
            return self._json(200, {"ok": True, "celulares": n})
        if self.path == "/api/ticket":   # (15-oct) solo la mascota (con su clave): ticket de 60 s para abrir el panel
            if not hmac.compare_digest(self.headers.get("X-Companero-Local", ""), CLAVE_LOCAL or "-"):
                return self._json(403, {"ok": False})
            for k in [k for k, v in TICKETS.items() if v < time.time()]:
                del TICKETS[k]
            t = secrets.token_urlsafe(18); TICKETS[t] = time.time() + 60
            return self._json(200, {"ok": True, "ticket": t})
        if self.path in ("/api/hooks", "/api/desinstalar"):   # (22-oct, mejora 5) revisar / arreglar / desinstalar
            d = self._cuerpo()
            py = os.path.join(config.APP_DIR, ".venv", "Scripts", "python.exe")
            py = py if os.path.exists(py) else sys.executable.replace("pythonw.exe", "python.exe")
            ins = os.path.join(config.APP_DIR, "instalar.py")
            if self.path == "/api/desinstalar":
                if not self._en_pc():   # desinstalar NUNCA desde el celular
                    return self._json(403, {"ok": False, "error": "Desinstalar se hace desde la PC."})
                args = [py, ins, "--quitar"] + (["--restaurar"] if d.get("restaurar") else [])
                r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                                   creationflags=0x08000000)
                log(f"desinstalado desde Ajustes (restaurar={bool(d.get('restaurar'))}): {r.returncode}")
                return self._json(200, {"ok": r.returncode == 0, "detalle": [x.strip() for x in r.stdout.splitlines() if x.strip()][-8:]})
            if d.get("arreglar"):
                r = subprocess.run([py, ins, "--arreglar-hooks"], capture_output=True, timeout=60, creationflags=0x08000000)
                log(f"hooks arreglados desde Ajustes: {r.returncode}")
            r = subprocess.run([py, ins, "--revisar"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=30, creationflags=0x08000000)
            try:
                return self._json(200, json.loads(r.stdout.strip().splitlines()[-1]))
            except Exception:
                return self._json(200, {"ok": False, "error": "no pude revisar"})
        if self.path == "/api/conectar/telegram":   # (21-oct) el token se pega en la PC, nunca en un chat
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            tok = str(self._cuerpo().get("token") or "").strip()
            bot = cc.probar_token(tok)
            if not bot:
                return self._json(200, {"ok": False, "error": "Telegram no reconoce ese token: cópialo de nuevo del mensaje de @BotFather."})
            cc.guardar_token(tok); poner_token(tok, bot)
            log(f"telegram configurado (bot @{bot})")
            return self._json(200, {"ok": True, "bot": bot})
        if self.path == "/api/conectar/tailscale":   # {"accion": "login" | "publicar"}
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            acc = self._cuerpo().get("accion")
            if acc == "login":
                return self._json(200, {"ok": True, "tailscale": cc.iniciar_sesion_tailscale()})
            if acc == "publicar":
                r = cc.publicar(BASE)
                if r.get("ok"):
                    log(f"app del celular publicada en {r['url']}")
                return self._json(200, r)
            return self._json(400, {"ok": False})
        if self.path == "/api/reporte":   # (21-oct) "Reportar un problema": zip en el Escritorio + formulario del issue
            try:
                import companero_reporte
                ruta = companero_reporte.reportar(chequear_salud(), redactar)
                log(f"reporte armado: {os.path.basename(ruta)}")
                return self._json(200, {"ok": True, "archivo": os.path.basename(ruta)})
            except Exception as e:
                log(f"reporte: {type(e).__name__}: {e}")
                return self._json(200, {"ok": False, "error": f"{type(e).__name__}"})
        if self.path == "/api/actualizar":   # (21-oct) bajar, verificar firma y sha256, e instalar
            # (22-oct) tambien desde Ajustes del celular (el dueno, ya autorizado arriba por Tailscale), no solo la mascota
            r = actualizar_ahora()
            return self._json(200, r)
        if self.path == "/api/actualizar-auto":   # (22-oct) {} = estado; {"activar": bool} = "Actualizar sola" (apagado por defecto)
            d = self._cuerpo()
            if "activar" in d:
                json.dump({"activa": bool(d["activar"])}, open(AUTO_ACT, "w", encoding="utf-8")); log(f"actualizar sola: {bool(d['activar'])}")
            try:
                nueva = json.load(open(ACTUALIZACION, encoding="utf-8"))
            except (OSError, ValueError):
                nueva = None
            return self._json(200, {"ok": True, "activa": actualizar_sola(), "actual": config.VERSION, "nueva": nueva})
        if self.path == "/api/medir":   # (15-oct) boton "Actualizar" del celular: lectura exacta del uso del plan
            err = pedir_medicion(forzar=True)
            return self._json(200, {"ok": not err, "error": err})
        if self.path == "/api/grupo-chat":   # (15-oct) {"chat": id, "grupo": "Nombre" o "" (sin grupo)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, g = str(d["chat"]), " ".join(str(d.get("grupo") or "").split())[:30]
                assert any(c["chat"] == cmd for c in candidatos())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            a = grupos_propios()
            if g:
                a[cmd] = g
            else:
                a.pop(cmd, None)
            poner_grupo(a)
            return self._json(200, {"ok": True})
        if self.path == "/api/sincronizar-grupos":
            return self._json(200, {"ok": True, "chats": sincronizar_grupos()})
        if self.path == "/api/color":   # (14-oct) {"chat": <id de chat>, "color": "#rrggbb" o "" (el de siempre)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, color = str(d["chat"]), str(d.get("color") or "")
                assert color == "" or _re.fullmatch(r"#[0-9a-fA-F]{6}", color)
                assert any(c["chat"] == cmd for c in candidatos())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            poner_color(cmd, color)
            return self._json(200, {"ok": True})
        if self.path == "/api/ocultar":   # (14-oct) {"id": <session id de candidatos()>, "oculto": true|false}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cli, oculto = str(d["id"]), bool(d.get("oculto"))
                assert any(c["id"] == cli for c in candidatos())   # solo chats de la lista, nada inventado
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ocultar_chat(cli, oculto)
            return self._json(200, {"ok": True})
        if self.path == "/api/silenciar":   # {"chat": cmd, "horas": 1 | 8 | 0 (quitar)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, horas = str(d["chat"]), max(0.0, min(float(d.get("horas", 1)), 72.0))
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            silenciar(cmd, horas)
            return self._json(200, {"ok": True})
        if self.path == "/api/personaje":   # (22-oct) la MISMA mascota en la PC y el celular: {} = leer; {pj, color, florCactus} = guardar
            d, ruta = self._cuerpo(), os.path.join(BASE, "personaje.json")
            if d.get("pj"):
                # (27-oct, lanzamiento) la cápsula se elige SOLO en la PC: si quien guarda (el celular) no manda capsulaColor,
                # se conserva el que ya estaba en el archivo (antes se pisaba con "blanca")
                try: antes = json.load(open(ruta, encoding="utf-8"))
                except (OSError, ValueError): antes = {}
                cap = d.get("capsulaColor")
                if cap not in ("blanca", "negra"): cap = "negra" if antes.get("capsulaColor") == "negra" else "blanca"
                nuevo = {"pj": str(d["pj"])[:40], "color": str(d.get("color") or "negro")[:20],
                         "florCactus": d.get("florCactus") is not False,
                         # (26-oct, LShinox) color de la cápsula elegido por el usuario (en la PC)
                         "capsulaColor": cap, "ts": time.time()}
                json.dump(nuevo, open(ruta, "w", encoding="utf-8")); log(f"personaje: {nuevo['pj']} {nuevo['color']}")
                return self._json(200, {"ok": True, **_pj_visible(nuevo)})
            try:
                return self._json(200, {"ok": True, **_pj_visible(json.load(open(ruta, encoding="utf-8")))})
            except (OSError, ValueError):
                return self._json(200, {"ok": True})
        if self.path == "/api/lectura-exacta":   # (22-oct) {} = estado; {"activar": true|false}
            d = self._cuerpo()
            return self._json(200, activar_lectura_exacta(d["activar"]) if "activar" in d else estado_lectura())
        if self.path in ("/api/archivar", "/api/archivados"):   # (22-oct) archivar/desarchivar por el chat de Kodama
            d = self._cuerpo()
            if self.path == "/api/archivar":   # {"chat": cmd}
                s = sesion_por_cmd(str(d.get("chat") or ""))
                local = grupos_app.local_de(s.get("session_id")) if s else None
                if not local:
                    return self._json(200, {"ok": False, "error": "no encuentro ese chat en la app de Claude"})
                if local == grupos_app.local_de((max(regs_medidor(), key=lambda x: x.get("visto", 0)) if regs_medidor() else {}).get("session_id")):
                    return self._json(200, {"ok": False, "error": "el chat de Kodama no se archiva"})
                err = ordenar_kodama("ARCHIVAR " + local)
                return self._json(200, {"ok": not err, "error": err})
            if d.get("desarchivar"):   # {"desarchivar": "local_…"}
                err = ordenar_kodama("DESARCHIVAR " + str(d["desarchivar"]))
                return self._json(200, {"ok": not err, "error": err})
            return self._json(200, {"ok": True, "chats": grupos_app.archivados()})
        if self.path == "/api/grupo":
            try:
                sel = json.loads(self.rfile.read(min(self._largo(), 2000)).decode()).get("id")
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            nombre = cambiar_seleccion(sel)
            return self._json(200, {"ok": True, "nombre": nombre} if nombre else {"ok": False, "error": "ese grupo no existe"})
        if self.path == "/api/bench":   # resultados de web/bench.html (prueba de rendimiento en el iPhone)
            datos = self.rfile.read(min(self._largo(), 20000)).decode(errors="replace")
            with open(os.path.join(BASE, "bench.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "datos": datos}, ensure_ascii=False) + "\n")
            log("bench recibido")
            return self._json(200, {"ok": True})
        if self.path == "/api/suscribir":
            try:
                sub = json.loads(self.rfile.read(min(self._largo(), 20000)).decode())
                host = urllib.parse.urlparse(sub.get("endpoint", "")).hostname or ""
                assert sub["endpoint"].startswith("https://") and "keys" in sub and \
                    _re.search(r"(^|\.)(push\.apple\.com|fcm\.googleapis\.com|push\.services\.mozilla\.com|notify\.windows\.com)$", host)
            except Exception:
                return self._json(400, {"ok": False, "error": "suscripción inválida"})
            try:
                subs = json.load(open(SUSC, encoding="utf-8"))
            except Exception:
                subs = []
            subs = [s for s in subs if s.get("endpoint") != sub["endpoint"]] + [sub]
            json.dump(subs, open(SUSC, "w", encoding="utf-8"))
            log("suscripción push guardada")
            threading.Thread(target=push_a_todos, args=("Kodama", "¡Listo! Ya te puedo avisar desde acá.", ""), daemon=True).start()
            return self._json(200, {"ok": True})
        if self.path == "/api/conservar":   # (16-oct) {"conservar": true|false}
            try:
                v = bool(json.loads(self.rfile.read(min(self._largo(), 2000)).decode()).get("conservar"))
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            tmp = CONSERVAR_JSON + ".tmp"
            json.dump({"conservar": v}, open(tmp, "w", encoding="utf-8")); os.replace(tmp, CONSERVAR_JSON)
            log(f"conservar siempre los archivos: {'SI' if v else 'no'}")
            return self._json(200, {"ok": True, "conservar": v})
        if self.path == "/api/limpieza":   # (16-oct) {"ids": [...]} de la ultima revision -> a la Papelera de reciclaje
            try:
                ids = json.loads(self.rfile.read(min(self._largo(), 200000)).decode()).get("ids") or []
                assert isinstance(ids, list)
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            return self._json(200, {"ok": True, **borrar_limpieza([str(i) for i in ids][:2000])})
        if self.path == "/api/subir":   # (16-oct) videos del celular: el archivo crudo (no base64), directo a disco por partes
            ext = VIDEO_TIPOS.get((self.headers.get("Content-Type") or "").split(";")[0].strip().lower())
            largo = self._largo()
            if not ext:
                return self._json(415, {"ok": False, "error": "solo videos (mp4, mov, webm, 3gp)"})
            if not largo or largo > VIDEO_MAX:
                return self._json(413, {"ok": False, "error": "video demasiado grande (máx. 5 GB)"})
            import shutil
            if shutil.disk_usage(BASE).free < largo + 8 * 1024 ** 3:   # nunca dejar el disco con menos de 8 GB libres
                return self._json(507, {"ok": False, "error": "no hay espacio en la PC para ese video"})
            os.makedirs(FOTOS, exist_ok=True)
            nombre = time.strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}{ext}"
            ruta, falta = os.path.join(FOTOS, nombre), largo
            try:
                with open(ruta + ".parcial", "wb") as f:
                    while falta > 0:
                        b = self.rfile.read(min(1 << 20, falta))
                        if not b:
                            raise ConnectionError("corte")
                        f.write(b); falta -= len(b)
                os.replace(ruta + ".parcial", ruta)
            except Exception as e:
                try:
                    os.remove(ruta + ".parcial")
                except OSError:
                    pass
                return self._json(400, {"ok": False, "error": f"no llegó entero ({type(e).__name__})"})
            log(f"video del celular guardado: {nombre} ({largo // (1024 * 1024)} MB)")
            return self._json(200, {"ok": True, "archivo": nombre})
        if self.path != "/api/responder":
            return self._json(404, {"ok": False})
        try:
            largo = self._largo()
            if largo > 8 * 1024 * 1024:   # tope: una foto del celular ya comprimida entra holgada
                return self._json(413, {"ok": False, "error": "demasiado grande (máx. 8 MB)"})
            d = json.loads(self.rfile.read(largo).decode())
            cmd, texto = d.get("chat"), (d.get("texto") or "").strip()[:4000]
        except Exception:
            return self._json(400, {"ok": False, "error": "pedido inválido"})
        s = sesion_por_cmd(cmd) if cmd else None
        foto = d.get("foto") or ""
        if foto.startswith("data:image/"):
            try:
                import base64
                ruta = guardar_foto(base64.b64decode(foto.split(",", 1)[1]), carpeta=carpeta_medios(cmd))
                texto = texto_con_foto(ruta, texto)
            except Exception as e:
                return self._json(400, {"ok": False, "error": f"foto inválida ({type(e).__name__})"})
        video = str(d.get("video") or "")   # (16-oct) nombre que devolvio /api/subir (solo el nombre, nunca una ruta)
        if video:
            ruta = os.path.join(FOTOS, os.path.basename(video))
            if os.path.basename(video) != video or not os.path.isfile(ruta) or os.path.splitext(video)[1] not in VIDEO_TIPOS.values():
                return self._json(400, {"ok": False, "error": "video inválido"})
            destino = carpeta_medios(cmd)   # se subio a estado\fotos (sin saber el chat): ahora va a la carpeta del chat
            if destino != FOTOS:
                try:
                    os.makedirs(destino, exist_ok=True)
                    import shutil
                    ruta = shutil.move(ruta, os.path.join(destino, video))
                except OSError as e:
                    log(f"video: no lo pude mover a {destino} ({type(e).__name__}); queda en estado\\fotos")
            texto = texto_con_video(os.path.normpath(ruta), texto)
        if s and s.get("agente") == "codex":   # (20-oct) Codex etapa 1: avisos y permisos, todavia sin responder
            return self._json(400, {"ok": False, "error": "a los chats de Codex todavía no se les puede escribir desde aquí; los permisos sí se aprueban"})
        if s and s.get("agente") == "antigravity":   # (20-oct) Antigravity etapa 1: solo avisos
            return self._json(400, {"ok": False, "error": "a los chats de Antigravity todavía no se les puede escribir desde aquí"})
        if not s or not texto:
            log(f"respuesta NO entregada a {cmd}: {'sin sesion registrada' if not s else 'texto vacio'}")   # (15-oct) diagnostico
            return self._json(400, {"ok": False, "error": "chat o texto vacío"})
        marca = "📱 " if getattr(self, "_via_celular", False) else "🐾 "
        err = entregar(s, texto, marca)
        if err and ("FileNotFoundError" in err or "no registró su buzón" in err):
            # (15-oct) el chat esta DORMIDO (la app de Claude apago su proceso por inactividad): no hay buzon. El
            # mensaje queda en cola y se entrega solo apenas el chat despierte (al abrirlo en la PC)
            poner_pendiente(cmd, texto, marca, s.get("socket"))
            with open(RESP, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "evento": "yo", "chat": cmd, "texto": texto,
                                    "via": "celular" if getattr(self, "_via_celular", False) else "pc"}, ensure_ascii=False) + "\n")
            log(f"respuesta EN COLA para {cmd} (chat dormido)")
            return self._json(200, {"ok": True, "pendiente": True, "despertando": segundos_sin_uso() >= 120})
        if err:
            log(f"respuesta NO entregada a {cmd}: {err}")
            return self._json(200, {"ok": False, "error": err})
        with open(RESP, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "evento": "yo", "chat": cmd, "texto": texto,
                                "via": "celular" if getattr(self, "_via_celular", False) else "pc"}, ensure_ascii=False) + "\n")
        log(f"respuesta web -> {cmd}")
        CERRAR.append((cmd, texto))
        return self._json(200, {"ok": True})


SUSC = os.path.join(BASE, "suscripciones.json")
FOTOS = os.path.join(BASE, "fotos")


def carpeta_medios(cmd):
    """(16-oct, LShinox) lo que mandas desde el celular va a la carpeta DEL CHAT (<carpeta del chat>\\del-celular), no a
    estado\\fotos: ahi queda para siempre y el chat lo encuentra junto a su trabajo. Sin carpeta conocida: estado\\fotos."""
    cwd = cwd_de(cmd) if cmd else None
    return os.path.join(cwd, "del-celular") if cwd and os.path.isdir(cwd) else FOTOS


# ---- (16-oct, LShinox) Ajustes > Espacio: revisar lo que guardo el Companero y mandar a la Papelera lo que ya no se usa.
# Solo estas carpetas: <carpeta de cada chat>\del-celular, estado\fotos y respaldos\ (nunca el codigo ni el estado vivo).
LIMPIEZA = {"ids": {}}
CONSERVAR_JSON = os.path.join(config.ESTADO, "conservar.json")   # (16-oct) {"conservar": true}: nunca proponer ni purgar


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


def a_papelera(ruta):
    """A la Papelera de reciclaje de Windows (se puede recuperar), no borrado definitivo."""
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int), ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p)]
    op = SHFILEOPSTRUCTW(None, 3, ruta + "\0", None, 0x0004 | 0x0010 | 0x0040 | 0x0400, 0, None, None)   # DELETE + ALLOWUNDO, sin dialogos
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted


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


def push_a_todos(titulo, cuerpo, chat, tipo="", n=0, solo=None, intento=0, permiso=None, completo=False):
    """Web Push a la app del iPhone (si la venv tiene pywebpush y hay suscripciones).
    Si una suscripcion falla por red o 5xx, se reintenta SOLO esa a los 1 y 5 min (14-oct)."""
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return
    try:
        subs = json.load(open(SUSC, encoding="utf-8"))
    except Exception:
        return
    vivas, fallidas = [], []
    for s in subs:
        if solo is not None and s.get("endpoint") not in solo:
            vivas.append(s)
            continue
        try:
            datos = {"web_push": 8030,   # formato declarativo de iOS 18.4+ (lo muestra el sistema) + el propio
                     "notification": {"title": titulo, "body": cuerpo, "lang": "es",
                                      "navigate": f"{config.URL_PUBLICA}/#{chat}", "app_badge": str(n)},
                     "titulo": titulo, "cuerpo": cuerpo, "chat": chat, "tipo": tipo, "n": n,
                     "permiso": permiso, "completo": completo}   # (14-oct) Android: botones en el aviso (Si/No, OK/Sigue, Permitir/Denegar)
            webpush(subscription_info=s, data=json.dumps(datos, ensure_ascii=False),
                    vapid_private_key=os.path.join(BASE, "vapid_private.pem"),
                    vapid_claims={"sub": config.URL_PUBLICA or "mailto:companero@localhost"}, ttl=3600)
            vivas.append(s)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            log(f"push error {code}"); SALUD["push_error"] = f"{time.strftime('%H:%M')} {code}"
            if code not in (404, 410):
                vivas.append(s)
                if code is None or code >= 500 or code == 429:
                    fallidas.append(s.get("endpoint"))
        except Exception as e:
            log(f"push error {type(e).__name__}"); SALUD["push_error"] = f"{time.strftime('%H:%M')} {type(e).__name__}"
            vivas.append(s); fallidas.append(s.get("endpoint"))
    if len(vivas) != len(subs):   # escritura atomica (hoja de ruta #10)
        json.dump(vivas, open(SUSC + ".tmp", "w", encoding="utf-8")); os.replace(SUSC + ".tmp", SUSC)
    if fallidas and intento < 2:
        threading.Timer((60, 300)[intento], push_a_todos, args=(titulo, cuerpo, chat, tipo, n),
                        kwargs={"solo": fallidas, "intento": intento + 1, "permiso": permiso, "completo": completo}).start()


def mantener_despierta():
    """Dentro del horario de estado\\despierto.json (LShinox 13-oct: todos los dias 8-22) le pide a
    Windows que NO suspenda la PC (SetThreadExecutionState; la pantalla si puede apagarse).
    No toca la configuracion de energia: el pedido vive solo mientras corre este hilo."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    activo = None
    while True:
        try:
            h = json.load(open(os.path.join(BASE, "despierto.json"), encoding="utf-8"))
            desde, hasta = int(h.get("desde", 8)), int(h.get("hasta", 22))
        except Exception:
            desde, hasta = 8, 22
        en = desde <= time.localtime().tm_hour < hasta
        if en != activo:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if en else 0))
            activo = en
            log(f"mantener despierta: {'SI' if en else 'no'} ({desde}-{hasta} h)")
        time.sleep(60)


def volcar_pilas():
    """(16-oct, diagnostico) Si existe estado\\volcar-pilas, escribe en estado\\pilas.txt donde esta cada hilo (con su
    id del sistema, para cruzarlo con el CPU por hilo) y borra la bandera. Mirar si existe un archivo no gasta nada."""
    import traceback
    flag, out = os.path.join(BASE, "volcar-pilas"), os.path.join(BASE, "pilas.txt")
    while True:
        time.sleep(5)
        if not os.path.exists(flag):
            continue
        try:
            nat = {t.ident: (t.name, t.native_id) for t in threading.enumerate()}
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"===== {time.strftime('%H:%M:%S')}\n")
                for ident, fr in sys._current_frames().items():
                    n, tid = nat.get(ident, ("?", "?"))
                    f.write(f"--- hilo {n} tid={tid}\n" + "".join(traceback.format_stack(fr)[-6:]))
            os.remove(flag)
        except Exception as e:
            log(f"volcar_pilas: {type(e).__name__}: {e}")


def elegir_servidor(clase, puertos, escribir, host="127.0.0.1"):
    """(26-oct, clawd #1261: en Windows hay puertos reservados y el bind da EACCES) Prueba los puertos en orden y devuelve
    (servidor, puerto) con el primero que se pueda abrir. `escribir(puerto)` se llama DESPUES de reservar el puerto y ANTES de
    empezar a escuchar: asi quien lee estado\\puerto.txt nunca ve un puerto en el que el hub todavia no esta. Si `escribir`
    falla, se cierra ese servidor y se prueba el siguiente. Sin SO_REUSEADDR: en Windows dejaria abrir un puerto ya usado."""
    ultimo = None
    for p in puertos:
        srv = http.server.ThreadingHTTPServer((host, p), clase, bind_and_activate=False)
        srv.allow_reuse_address = False
        try:
            srv.server_bind()
            escribir(p)
            srv.server_activate()
        except OSError as e:   # EACCES (puerto reservado por Windows) o en uso
            ultimo = e
            try:
                srv.server_close()
            except Exception:
                pass
            log(f"puerto {p} no disponible ({type(e).__name__}: {getattr(e, 'winerror', None) or e.errno}); pruebo el siguiente")
            continue
        srv.daemon_threads = True
        return srv, p
    raise OSError(f"ningun puerto libre entre {puertos[0]} y {puertos[-1]}: {ultimo}")


def repuntar_tailscale(puerto):
    """`tailscale serve --bg <puerto>` en el Tailscale PROPIO del companero (siempre con --socket; el de la empresa no se toca),
    para que el celular siga entrando cuando el hub no quedo en el 8787. En un hilo aparte: tarda unos segundos."""
    def hacer():
        try:
            r = subprocess.run([TS_EXE, f"--socket={TS_SOCKET}", "serve", "--bg", str(puerto)], capture_output=True, text=True,
                               timeout=40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            log(f"tailscale serve -> {puerto}: {'ok' if r.returncode == 0 else 'fallo ' + (r.stderr or r.stdout).strip()[:200]}")
        except Exception as e:
            log(f"tailscale serve -> {puerto} fallo: {type(e).__name__}: {e}")
    threading.Thread(target=hacer, daemon=True).start()


def escribir_puerto(p, repuntar=repuntar_tailscale):
    """Escribe estado\\puerto.txt. Si el puerto es distinto del de siempre, o distinto del que habia anotado antes, el serve
    del Tailscale propio se re-apunta (si no, el celular seguiria entrando al puerto viejo)."""
    global PUERTO_WEB
    try:
        antes = int(open(PUERTO_TXT, encoding="utf-8").read().strip())
    except (OSError, ValueError):
        antes = None
    tmp = PUERTO_TXT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(p))
    os.replace(tmp, PUERTO_TXT)
    PUERTO_WEB = p
    if p != config.PUERTO_BASE or (antes is not None and antes != p):
        repuntar(p)


def servir_web():
    """(21-oct, Coucou #853: un accept()/connect() fallido mataba su servidor y los permisos caian al terminal sin aviso)
    Si serve_forever se cae por lo que sea, se registra y se vuelve a levantar a los 2 s, sin tirar el hub (primero en el
    mismo puerto; si ya no se puede, en el siguiente libre: ver elegir_servidor). (26-oct) puerto de respaldo 8788..8799."""
    def bucle():
        while True:
            srv = None
            try:
                orden = [PUERTO_WEB] + [p for p in config.PUERTOS_HUB if p != PUERTO_WEB]
                srv, p = elegir_servidor(Web, orden, escribir_puerto)
                log(f"web en 127.0.0.1:{p}")
                srv.serve_forever()
            except Exception as e:
                log(f"web caida ({type(e).__name__}: {e}); la levanto de nuevo en 2 s")
            try:
                srv.server_close()
            except Exception:
                pass
            time.sleep(2)
    threading.Thread(target=bucle, daemon=True).start()


AYUDA = ("Te aviso cuando tus chats te necesitan.\nPara responder: desliza sobre el mensaje del chat y escribe (o toca sus botones).\n"
         "/estado: cómo está cada chat · /siempre o /ausente: cuándo te aviso · /grupo: qué chats van al celular · /completo o /corto: cuánto texto mando.")


_MUTEX = None


def main():
    # (20-oct) UNA sola instancia: el 20-oct el vigilante levanto un segundo hub (su consulta de procesos fallo) y
    # los dos se peleaban Telegram (getUpdates 409 cada 6 s) y procesaban la cola dos veces (avisos duplicados).
    # Un mutex con nombre lo frena aunque el que lanza no lo detecte; se libera solo al morir el proceso.
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\companero_hub_unico")
    if ctypes.windll.kernel32.GetLastError() == 183:   # ERROR_ALREADY_EXISTS
        log(f"ya hay un hub corriendo: este (pid={os.getpid()}) se cierra")
        return
    os.makedirs(SES, exist_ok=True)
    conf = cargar_conf()
    if not conf.get("dueno") and not conf.get("codigo"):
        conf["codigo"] = str(random.randint(1000, 9999))
    conf.setdefault("modo", "ausente")
    guardar_conf(conf)
    open(os.path.join(BASE, "hub.pid"), "w").write(str(os.getpid()))
    me = api("getMe")
    BOT["u"] = me.get("result", {}).get("username", "") if me.get("ok") else ""
    log(f"arranca pid={os.getpid()} bot={me.get('result', {}).get('username')} modo={conf['modo']}")
    servir_web()
    threading.Thread(target=mantener_despierta, daemon=True).start()
    threading.Thread(target=vigilar_tailscale, daemon=True).start()
    threading.Thread(target=entregar_pendientes, daemon=True).start()
    threading.Thread(target=estimar_uso, daemon=True).start()
    threading.Thread(target=volcar_pilas, daemon=True).start()
    threading.Thread(target=vigilar_salud, daemon=True).start()
    threading.Thread(target=vigilar_actualizaciones, daemon=True).start()
    threading.Thread(target=vigilar_auto_actualizacion, daemon=True).start()
    threading.Thread(target=vigilar_permisos_caducados, daemon=True).start()
    # la posicion en la cola se guarda en hub.json: un reinicio ya no salta los avisos que llegaron mientras
    # el hub estaba caido (los de mas de 15 min se descartan en procesar_cola)
    tam = os.path.getsize(COLA) if os.path.exists(COLA) else 0
    pos = conf.get("cola_pos", tam)
    if not isinstance(pos, int) or pos > tam:
        pos = tam
    # aviso de salud: si el ultimo latido es de hace mas de 3 min, el hub estuvo caido
    try:
        caido = time.time() - os.path.getmtime(LATIDO)
    except OSError:
        caido = 0
    recien_prendida = ctypes.windll.kernel32.GetTickCount64() < 15 * 60 * 1000   # tras prender la PC no hace falta avisar
    if caido > 180 and conf.get("dueno") and not recien_prendida:
        desde = time.strftime("%H:%M", time.localtime(time.time() - caido))
        api("sendMessage", chat_id=conf["dueno"], disable_notification="true",
            text=tr("🔄 Kodama volvió: estuvo caído ~{m} min (desde las {d}). Lo de los últimos 15 min te lo aviso ahora; lo anterior está en la app.", m=int(caido // 60), d=desde))
        log(f"volvio tras {int(caido)} s caido")
    pos = mantenimiento(conf, pos)
    publicar_elegidos()
    ult_mant = ult_latido = ult_grupos = time.time()
    open(LATIDO, "w").close()
    offset = conf.get("offset", 0)
    while True:
        if TOKEN:
            r = api("getUpdates", offset=offset, timeout=2)
        else:   # (21-oct) sin Telegram: el getUpdates largo era lo que pausaba el bucle; sin el, pausa a mano
            time.sleep(2); r = {}
        for u in r.get("result", []) if r.get("ok") else []:
            offset = u["update_id"] + 1
            conf["offset"] = offset
            if "callback_query" in u:
                try:
                    atender_boton(conf, u["callback_query"])
                except Exception as e:
                    log(f"error boton: {type(e).__name__}: {e}")
            if "message" in u:
                try:
                    atender(conf, u["message"])
                except Exception as e:
                    log(f"error atender: {type(e).__name__}: {e}")
            guardar_conf(conf)
        try:
            antes = pos
            pos = procesar_cola(conf, pos)
            if pos != antes:
                conf["cola_pos"] = pos; guardar_conf(conf)
            SALUD["pos"] = pos
            vaciar_espera(conf)
            reintentar_avisos(conf)
            sync_seleccion(conf)
            if time.time() - ult_grupos > 30:   # si moviste chats entre grupos en la app, el hook se entera
                publicar_elegidos(); ult_grupos = time.time()
            if time.time() - ult_latido > 60:
                os.utime(LATIDO, None) if os.path.exists(LATIDO) else open(LATIDO, "w").close()
                ult_latido = time.time()
            if time.time() - ult_mant > 3600:
                pos = mantenimiento(conf, pos); ult_mant = time.time()
            while CERRAR:
                cerrar_avisos(conf, *CERRAR.pop(0))
        except Exception as e:
            log(f"error cola: {type(e).__name__}: {e}")
        if not r.get("ok"):
            time.sleep(5)


if __name__ == "__main__":
    main()
