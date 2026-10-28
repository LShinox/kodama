# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Lo que llega desde Telegram: botones y mensajes de la persona (comandos, respuestas a un chat, fotos).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import os
import time
import urllib.request

import grupos_app
import kodama_nucleo
from kodama_nucleo import api, guardar_conf, log
from kodama_texto import RESPUESTAS, tr
from kodama_chats import cambiar_seleccion, info, seleccion, sesion_por_cmd, sesiones, silenciar, todos_los_chats
from kodama_permisos import PERM_TG, entregar, responder_permiso
from kodama_conexion import alarma, bloqueado, poner_bloqueo
from kodama_archivos import guardar_foto, texto_con_foto
from kodama_notificaciones import cerrar_avisos, registrar_respuesta


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
            with urllib.request.urlopen(f"https://api.telegram.org/file/bot{kodama_nucleo.TOKEN}/{ruta_tg}", timeout=60) as r:
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


AYUDA = ("Te aviso cuando tus chats te necesitan.\nPara responder: desliza sobre el mensaje del chat y escribe (o toca sus botones).\n"
         "/estado: cómo está cada chat · /siempre o /ausente: cuándo te aviso · /grupo: qué chats van al celular · /completo o /corto: cuánto texto mando.")
