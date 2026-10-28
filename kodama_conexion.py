# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Conexion con el celular: Tailscale propio, aparato registrado, bloqueo y alarma, y el puerto del
servidor web.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import http.server
import json
import os
import subprocess
import sys
import threading
import time

import config
import kodama_plataforma as plataforma
import kodama_nucleo
from kodama_nucleo import APARATOS, BASE, BLOQUEO, _guardar_json, _leer_json, api, cargar_conf, log
from kodama_texto import tr
from kodama_push import push_a_todos


def vigilar_tailscale():
    """(14-oct) el Tailscale propio del companero (el que conecta el celular) se cae a veces con cambios de red; la
    tarea programada lo levanta cada 10 min. Este vigilante mira cada 30 s si su PID sigue vivo y, si no, corre
    arrancar.pyw (que solo arranca lo que falta). Mirar un PID no gasta nada."""
    pidf = os.path.join(config.TS_DIR, "tailscaled.pid")
    lanz = os.path.join(config.APP_DIR, "arrancar.pyw")
    pyw = plataforma.python_del_venv(config.APP_DIR, sin_consola=True)
    while True:
        time.sleep(30)
        try:
            pid = int(open(pidf).read().strip())
            vivo = plataforma.proceso_vivo(pid)
            if not vivo and os.path.exists(lanz):
                log("tailscale del companero caido: lo relanzo")
                subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, lanz], cwd=config.APP_DIR,
                                 close_fds=True, **plataforma.desprendido(sin_ventana=True))
                time.sleep(60)   # que arranque antes de volver a mirar
        except Exception:
            pass


PUERTO_WEB = config.PUERTO_BASE   # (26-oct) 8787; si no se puede abrir, servir_web() prueba 8788..8799 y deja aca el real
PUERTO_TXT = os.path.join(BASE, "puerto.txt")


def permitido(login):
    try:
        dueno_web = json.load(open(os.path.join(BASE, "web.json"), encoding="utf-8")).get("dueno_web", "")
    except Exception:
        dueno_web = ""
    return bool(dueno_web) and login.lower() == dueno_web.lower()


TS_EXE = plataforma.ruta_tailscale_cli()
TS_SOCKET = plataforma.socket_tailscale()
_WHOIS = {}     # ip -> (vence, id estable, nombre)
_ALARMAS = {}   # clave -> ultima alarma


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
    if kodama_nucleo.TOKEN and conf.get("dueno"):
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
                           timeout=6, **plataforma.sin_ventana())
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
                               timeout=40, **plataforma.sin_ventana())
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
