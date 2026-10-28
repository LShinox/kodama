# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Hub del companero (etapa 1, 13-oct-2026): puente Telegram <-> 3 chats personales.

- Lee la cola que deja companero_hook.py y manda a Telegram lo que el chat le escribio a LShinox.
- Lo que LShinox responde en Telegram lo entrega en el buzon de ese chat (cross-session messaging).
- Solo atiende al chat de Telegram emparejado con /start <codigo>. Nunca escribe el token en logs.

Comandos en Telegram: /start <codigo>, /estado, /siempre, /ausente, /juegos|/musica|/dnd <texto>.
Para responder: deslizar (responder) sobre el mensaje del chat, o usar el comando del chat.

(28-oct-2026) Este archivo es solo el ARRANQUE (servir_web y main). El resto se dividio por responsabilidad en
modulos kodama_*.py (nucleo, texto, push, chats, permisos, conexion, cola, medidor, archivos, historial,
notificaciones, telegram, vigilantes y rutas) y lo propio de Windows en kodama_plataforma.py.
"""
import importlib
import os
import random
import threading
import time
import types
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import config
import kodama_plataforma as plataforma
import kodama_conexion
import kodama_nucleo
from kodama_nucleo import BASE, BOT, COLA, LATIDO, SALUD, SES, api, cargar_conf, guardar_conf, log
from kodama_texto import tr
from kodama_chats import publicar_elegidos, sync_seleccion
from kodama_permisos import vigilar_permisos_caducados
from kodama_conexion import elegir_servidor, escribir_puerto, vigilar_tailscale
from kodama_cola import entregar_pendientes
from kodama_medidor import estimar_uso
from kodama_notificaciones import cerrar_avisos, procesar_cola, reintentar_avisos, vaciar_espera
from kodama_telegram import atender, atender_boton
from kodama_vigilantes import (
    mantener_despierta, mantenimiento, vigilar_actualizaciones, vigilar_auto_actualizacion, vigilar_salud,
    volcar_pilas
)
from kodama_rutas import CERRAR, Web

# (28-oct) FACHADA: `import companero_hub as h` sigue sirviendo para LEER y REEMPLAZAR cualquier nombre de los modulos
# kodama_* (lo usan las pruebas): leer busca el nombre en los modulos; asignar `h.nombre = valor` lo escribe en el modulo
# que lo define y en los que lo importaron por nombre, igual que cuando todo estaba en este archivo.
_PARTES = tuple(importlib.import_module(n) for n in (
    "kodama_plataforma", "kodama_nucleo", "kodama_texto",
    "kodama_push", "kodama_chats", "kodama_permisos",
    "kodama_conexion", "kodama_cola", "kodama_medidor",
    "kodama_archivos", "kodama_historial", "kodama_notificaciones",
    "kodama_telegram", "kodama_vigilantes", "kodama_rutas"))


def __getattr__(nombre):
    for m in _PARTES:
        if nombre in m.__dict__:
            return m.__dict__[nombre]
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


class _Fachada(types.ModuleType):
    def __setattr__(self, nombre, valor):
        duenos = [m for m in _PARTES if nombre in m.__dict__]
        for m in duenos:
            setattr(m, nombre, valor)
        if not duenos or nombre in self.__dict__:
            super().__setattr__(nombre, valor)


_sys.modules[__name__].__class__ = _Fachada


def servir_web():
    """(21-oct, Coucou #853: un accept()/connect() fallido mataba su servidor y los permisos caian al terminal sin aviso)
    Si serve_forever se cae por lo que sea, se registra y se vuelve a levantar a los 2 s, sin tirar el hub (primero en el
    mismo puerto; si ya no se puede, en el siguiente libre: ver elegir_servidor). (26-oct) puerto de respaldo 8788..8799."""
    def bucle():
        while True:
            srv = None
            try:
                orden = [kodama_conexion.PUERTO_WEB] + [p for p in config.PUERTOS_HUB if p != kodama_conexion.PUERTO_WEB]
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


def main():
    # (20-oct) UNA sola instancia: el 20-oct el vigilante levanto un segundo hub (su consulta de procesos fallo) y
    # los dos se peleaban Telegram (getUpdates 409 cada 6 s) y procesaban la cola dos veces (avisos duplicados).
    # Un mutex con nombre lo frena aunque el que lanza no lo detecte; se libera solo al morir el proceso.
    if not plataforma.instancia_unica("companero_hub_unico"):
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
    recien_prendida = plataforma.ms_desde_arranque_pc() < 15 * 60 * 1000   # tras prender la PC no hace falta avisar
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
        if kodama_nucleo.TOKEN:
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
