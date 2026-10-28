# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Hilos vigilantes del hub: salud, actualizaciones, mantener la PC despierta, volcado de pilas, rotado de
logs y respaldos.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import sys
import threading
import time

import config
import grupos_app
import kodama_plataforma as plataforma
from kodama_plataforma import segundos_sin_uso
from kodama_nucleo import (
    ACTUALIZACION, AUTO_ACT, BASE, COLA, FASE_DIR, FOTOS, LOG, RESP, SES, api, cargar_conf, guardar_conf, log
)
from kodama_push import push_a_todos
from kodama_archivos import conservar


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


# ---- mantenimiento (14-oct): rotar archivos que crecen, purgar fotos, latido para el aviso de salud ----
TOPE_BYTES = 5 * 1024 * 1024


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


def mantener_despierta():
    """Dentro del horario de estado\\despierto.json (LShinox 13-oct: todos los dias 8-22) le pide a
    Windows que NO suspenda la PC (SetThreadExecutionState; la pantalla si puede apagarse).
    No toca la configuracion de energia: el pedido vive solo mientras corre este hilo."""
    activo = None
    while True:
        try:
            h = json.load(open(os.path.join(BASE, "despierto.json"), encoding="utf-8"))
            desde, hasta = int(h.get("desde", 8)), int(h.get("hasta", 22))
        except Exception:
            desde, hasta = 8, 22
        en = desde <= time.localtime().tm_hour < hasta
        if en != activo:
            plataforma.pedir_pc_despierta(continuo=True, sistema=en)
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
