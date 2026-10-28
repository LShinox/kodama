# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Los chats que Kodama sigue: sesiones, seleccion y grupos de la app, colores, chats ocultos o silenciados
y cual estas mirando ahora.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import re as _re
import time

import config
import grupos_app
import kodama_plataforma as plataforma
from kodama_plataforma import app_al_frente, segundos_sin_uso
from kodama_nucleo import (
    BASE, CELULAR, CHATS, COLORES_JSON, CONF, ELEGIDOS, GRUPOS_JSON, SES, SILENCIO, guardar_conf, log
)


def extras():
    try:
        return {k: tuple(v) for k, v in json.load(open(os.path.join(BASE, "sesiones_extra.json"), encoding="utf-8")).items()}
    except Exception:
        return {}


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


_MIR = {"t": 0, "v": None}


def mirando_chat():
    """(14-oct, pedido repetido en Coucou/Happy y sin resolver en ningun proyecto) cliSessionId del chat que estas
    MIRANDO ahora: la app de Claude al frente + usaste la PC hace < 2 min + el chat con "lastFocusedAt" mas reciente.
    Ese chat no te avisa (ni push, ni Telegram, ni la mascota se asoma): ya lo estas viendo. Memo de 2 s."""
    if time.time() - _MIR["t"] < 2:
        return _MIR["v"]
    v = None
    try:
        if segundos_sin_uso() < 120 and app_al_frente() == plataforma.NOMBRE_APP_CLAUDE:
            v = grupos_app.chat_enfocado()
    except Exception:
        v = None
    _MIR.update(t=time.time(), v=v)
    return v


def mirando_claude():
    """(issues de la competencia) no avisar al celular si estas frente a la PC con Claude al frente."""
    return segundos_sin_uso() < 60 and app_al_frente() in (plataforma.NOMBRE_APP_CLAUDE,)


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


def marcar_celular():
    """(14-oct) La app del celular esta abierta: lo usan el puente y los permisos como "estas lejos de la PC"."""
    try:
        os.utime(CELULAR, None)
    except OSError:
        open(CELULAR, "w").close()


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


def elegidos_por_cmd():
    return {v[0]: v for v in todos_elegidos().values()}


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
