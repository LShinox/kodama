# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Avisos a Telegram: cola de eventos de los hooks, ventana de espera, reintentos y cierre de avisos.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import html as _html
import json
import os
import threading
import time

import config
from kodama_plataforma import segundos_sin_uso
from kodama_nucleo import AUSENTE_SEG, BASE, CHATS, COLA, RESP, api, guardar_conf, leer_ultimas, log
from kodama_texto import clasificar, es_entrega_kodama, pendientes, redactar, titulo_aviso, tr
from kodama_push import push_a_todos
from kodama_chats import info, mirando_chat, mirando_claude, sesiones, silenciado
from kodama_permisos import PERM_TG


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
# (28-oct, "Etiqueta") la etiqueta nueva ("📱 Nombre (Kodama, responde aquí): ", o "reply here") y la antigua se reconocen en kodama_texto.
def entregado_por_kodama(texto, cmd):
    t = (texto or "").strip()
    if es_entrega_kodama(t):
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
