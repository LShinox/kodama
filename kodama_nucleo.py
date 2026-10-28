# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Lo que todos los modulos del hub comparten: rutas de la carpeta estado, registro (hub.log),
configuracion del hub (hub.json) y el cliente de la API de Telegram.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import time
import urllib.parse
import urllib.request

import config


BASE = config.ESTADO
SES = os.path.join(BASE, "sesiones")
COLA = os.path.join(BASE, "cola.jsonl")
CONF = os.path.join(BASE, "hub.json")
LOG = os.path.join(BASE, "hub.log")
TOKEN_FILE = config.TOKEN_TELEGRAM

CHATS = config.CHATS   # carpeta del proyecto -> (comando, nombre, emoji); sale de config.json (14-oct)
ELEGIDOS = os.path.join(BASE, "elegidos.json")   # lo lee el hook: de que sesiones guardar los mensajes

ACTUALIZACION = os.path.join(BASE, "actualizacion.json")
AUTO_ACT = os.path.join(BASE, "actualizar_auto.json")

# ---- (15-oct) grupos propios del Companero (opcion B de LShinox): cada chat a un grupo con nombre; "Sincronizar"
# copia los grupos de la app de Claude. estado\grupos.json = {"asignado": {id de chat: "Nombre del grupo"}}
GRUPOS_JSON = os.path.join(config.ESTADO, "grupos.json")

# (14-oct) color de cada chat elegido desde la app (Ajustes > Chats que se ven); manda sobre "colores" de config.json
COLORES_JSON = os.path.join(config.ESTADO, "colores.json")

AUSENTE_SEG = 120      # modo "ausente": solo avisa si la PC lleva 2 min sin uso
MAX_TXT = 3500


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


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


PERMISOS = os.path.join(BASE, "permisos")
CELULAR = os.path.join(BASE, "celular_activo")

REGLAS_PERMISO = os.path.join(BASE, "reglas_permiso.json")

BOT = {}   # (21-oct) {"u": usuario del bot de Telegram} para el enlace de emparejar del asistente


def poner_token(tok, bot):
    """(21-oct) Telegram configurado desde el asistente: el hub empieza a usarlo sin reiniciarse."""
    global TOKEN
    TOKEN = tok
    BOT["u"] = bot


PUENTE = os.path.join(BASE, "puente")

# ---- silenciar un chat suelto (14-oct): no avisa por Telegram ni push; la app y el escritorio lo siguen mostrando ----
SILENCIO = os.path.join(BASE, "silencio.json")
LATIDO = os.path.join(BASE, "latido")
ARRANQUE = time.time()
SALUD = {"telegram_ok": 0, "push_error": None}

# ---- (15-oct) mensajes para chats dormidos: quedan en cola y se entregan solos cuando el chat despierta ----
PENDIENTES_DIR = os.path.join(BASE, "pendientes")


def leer_ultimas(ruta, n=400):
    """Ultimas n lineas, mirando tambien el .1 si el archivo se acaba de rotar."""
    lineas = []
    for r in (ruta + ".1", ruta):
        if os.path.exists(r):
            lineas += open(r, encoding="utf-8").read().splitlines()[-n:]
    return lineas[-n:]


WEB = config.WEB
RESP = os.path.join(BASE, "respuestas.jsonl")

# (26-oct, LShinox: "deberia ser solo un cel") aparato del celular: ademas de la cuenta, se mira QUE aparato de la red
# personal pide (tailscale whois de la IP que pone `serve` en X-Forwarded-For). El primero queda registrado; otro
# aparato con la misma cuenta no entra y dispara la alarma. Bloqueo de emergencia: corta todo lo que entra del celular
# (app y Telegram); se activa desde el celular o la PC y solo se quita en la PC.
APARATOS = os.path.join(BASE, "aparatos.json")
BLOQUEO = os.path.join(BASE, "bloqueo_celular.json")


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


MEDIDOR_DIR = config.CHAT_DIR   # (22-oct) antes APP_DIR\medidor

LECTURA = os.path.join(BASE, "lectura_exacta.json")

FASE_DIR = os.path.join(BASE, "fase")

SUSC = os.path.join(BASE, "suscripciones.json")
FOTOS = os.path.join(BASE, "fotos")
CONSERVAR_JSON = os.path.join(config.ESTADO, "conservar.json")   # (16-oct) {"conservar": true}: nunca proponer ni purgar
