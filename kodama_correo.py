# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov-2026) Correo de solo lectura por IMAP: cuentas, revision de no leidos y avisos de correos nuevos.
Nunca baja el cuerpo ni marca nada como leido: solo cabeceras (BODY.PEEK). La clave no sale nunca de este modulo."""
import email
import email.header
import imaplib
import json
import os
import re
import secrets
import time

from kodama_nucleo import BASE, log
import kodama_secreto

CONF = os.path.join(BASE, "correo.json")
VISTOS = os.path.join(BASE, "correo_vistos.json")
PRESETS = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "icloud": ("imap.mail.me.com", 993),
    "yahoo": ("imap.mail.yahoo.com", 993),
}
RESUMEN = {}          # cid -> {"no_leidos", "ts", "error"}: lo que muestra la app
MAX_TXT = 300
MAX_VISTOS = 300      # ids recordados por cuenta
MAX_AVISOS = 5        # avisos por cuenta y ronda
FETCH_CAB = "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])"


def _leer_json(ruta, defecto):
    try:
        d = json.load(open(ruta, encoding="utf-8"))
    except (OSError, ValueError):
        return defecto
    return d if isinstance(d, type(defecto)) else defecto


def _guardar_json(ruta, d):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, ruta)


def _txt(v):
    return str(v if v is not None else "").strip()[:MAX_TXT]


def leer_conf(ruta=None):
    """Cuentas guardadas. Archivo faltante o roto = sin cuentas."""
    d = kodama_secreto.leer(ruta or CONF, {})
    cuentas = d.get("cuentas") if isinstance(d, dict) else None
    if not isinstance(cuentas, list):
        return {"cuentas": []}
    return {"cuentas": [c for c in cuentas if isinstance(c, dict)]}


def guardar_cuenta(datos, ruta=None):
    """Crea o actualiza una cuenta. Clave vacia en una cuenta existente = se queda la vieja."""
    ruta = ruta or CONF
    cuentas = leer_conf(ruta)["cuentas"]
    cid = _txt(datos.get("id")) or secrets.token_hex(4)
    previa = next((c for c in cuentas if c.get("id") == cid), None)
    preset = _txt(datos.get("preset")).lower()
    if preset in PRESETS:
        servidor, puerto = PRESETS[preset]
    else:
        servidor = _txt(datos.get("servidor")) or (previa or {}).get("servidor", "")
        puerto = datos.get("puerto")
        if puerto in (None, ""):
            puerto = (previa or {}).get("puerto", 993)
        puerto = int(puerto)
    if not servidor:
        raise ValueError("falta servidor o preset")
    if not 1 <= int(puerto) <= 65535:
        raise ValueError("puerto fuera de rango")
    clave = _txt(datos.get("clave")) or (previa or {}).get("clave", "")
    registro = {
        "id": cid,
        "nombre": _txt(datos.get("nombre", (previa or {}).get("nombre", ""))),
        "servidor": servidor,
        "puerto": int(puerto),
        "usuario": _txt(datos.get("usuario", (previa or {}).get("usuario", ""))),
        "clave": clave,
        "activo": bool(datos["activo"]) if "activo" in datos else (previa or {}).get("activo", True),
    }
    cuentas = [c for c in cuentas if c.get("id") != cid] + [registro]
    kodama_secreto.guardar(ruta, {"cuentas": cuentas})
    return vista_publica(ruta)


def quitar_cuenta(cid, ruta=None):
    ruta = ruta or CONF
    cuentas = [c for c in leer_conf(ruta)["cuentas"] if c.get("id") != cid]
    kodama_secreto.guardar(ruta, {"cuentas": cuentas})
    return vista_publica(ruta)


def vista_publica(ruta=None):
    """Cuentas sin la clave; solo dice si hay clave guardada."""
    salida = []
    for c in leer_conf(ruta)["cuentas"]:
        publica = {k: v for k, v in c.items() if k != "clave"}
        publica["configurada"] = bool(c.get("clave"))
        salida.append(publica)
    return salida


def decodificar(h):
    """Cabecera RFC 2047 a texto. Nunca lanza."""
    try:
        if isinstance(h, bytes):
            h = h.decode("utf-8", "replace")
        trozos = []
        for parte, cod in email.header.decode_header(str(h or "")):
            if isinstance(parte, bytes):
                try:
                    parte = parte.decode(cod or "utf-8", "replace")
                except (LookupError, TypeError):
                    parte = parte.decode("utf-8", "replace")
            trozos.append(parte)
        return re.sub(r"[\r\n]+", " ", "".join(trozos)).strip()
    except Exception:
        return ""


def _cabeceras(datos):
    """Saca los bytes de las cabeceras de la respuesta de fetch."""
    for item in datos or []:
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
            return item[1]
    return b""


def revisar_cuenta(cuenta, conectar=imaplib.IMAP4_SSL, maximo=15):
    """Lee cabeceras de los no leidos (los mas nuevos primero). No baja cuerpos ni cambia flags."""
    imap = conectar(cuenta["servidor"], int(cuenta.get("puerto") or 993), timeout=20)
    try:
        imap.login(cuenta["usuario"], cuenta["clave"])
        imap.select("INBOX", readonly=True)
        typ, datos = imap.search(None, "UNSEEN")
        nums = datos[0].split() if typ == "OK" and datos and datos[0] else []
        mensajes = []
        for num in reversed(nums[-maximo:]):
            seq = num.decode() if isinstance(num, bytes) else str(num)
            typ, res = imap.fetch(seq, FETCH_CAB)
            msg = email.message_from_bytes(_cabeceras(res)) if typ == "OK" else email.message_from_bytes(b"")
            mid = decodificar(msg.get("Message-ID", "")) or seq
            mensajes.append({
                "id": mid,
                "de": decodificar(msg.get("From", "")),
                "asunto": decodificar(msg.get("Subject", "")),
                "fecha": decodificar(msg.get("Date", "")),
            })
        return {"no_leidos": len(nums), "mensajes": mensajes}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def nuevos(cid, mensajes, vistos):
    """Funcion pura. vistos = {cid: [ids]}. Primera vez: no avisa, solo recuerda. Devuelve (nuevos, vistos nuevo)."""
    vistos = dict(vistos or {})
    ids_actuales = [m["id"] for m in mensajes]
    if cid not in vistos:
        vistos[cid] = ids_actuales[:MAX_VISTOS]
        return [], vistos
    conocidos = set(vistos.get(cid) or [])
    salen = [m for m in mensajes if m["id"] not in conocidos]
    ids_nuevos = [m["id"] for m in salen]
    resto = [i for i in (vistos.get(cid) or []) if i not in set(ids_nuevos)]
    vistos[cid] = (ids_nuevos + resto)[:MAX_VISTOS]
    return salen, vistos


def revisar_todas(avisar, conf_ruta=None, vistos_ruta=None, conectar=imaplib.IMAP4_SSL):
    """Revisa cada cuenta activa con clave. Un fallo no para a las demas; el error no lleva clave ni usuario."""
    vistos_ruta = vistos_ruta or VISTOS
    vistos = _leer_json(vistos_ruta, {})
    for c in leer_conf(conf_ruta)["cuentas"]:
        if not c.get("activo") or not c.get("clave"):
            continue
        cid = c.get("id")
        try:
            r = revisar_cuenta(c, conectar=conectar)
            avisos, vistos = nuevos(cid, r["mensajes"], vistos)
            _guardar_json(vistos_ruta, vistos)
            for m in avisos[:MAX_AVISOS]:
                avisar(c.get("nombre") or cid, m)
            RESUMEN[cid] = {"no_leidos": r["no_leidos"], "ts": time.time(), "error": None}
        except Exception as e:
            RESUMEN[cid] = {"no_leidos": None, "ts": time.time(), "error": type(e).__name__}
            log(f"correo: {type(e).__name__}")
    return RESUMEN


def vigilar(avisar):
    """Bucle de fondo: primera revision a los 60 s, luego cada 180 s. Apagado en kodama_extras = no revisa (no hace falta reiniciar)."""
    import kodama_extras
    time.sleep(60)
    while True:
        if not kodama_extras.activo("correo"):
            time.sleep(30)
            continue
        try:
            revisar_todas(avisar)
        except Exception as e:
            log(f"correo: {type(e).__name__}")
        time.sleep(180)
