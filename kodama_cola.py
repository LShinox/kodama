# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Cola de mensajes pendientes para chats dormidos y como despertarlos (abrir el chat, mantener la PC
despierta).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import secrets
import threading
import time

import grupos_app
import kodama_plataforma as plataforma
from kodama_plataforma import segundos_sin_uso
from kodama_nucleo import BASE, PENDIENTES_DIR, log
from kodama_texto import tr
from kodama_push import push_a_todos
from kodama_chats import elegidos_por_cmd, sesion_por_cmd, todos_elegidos
from kodama_permisos import entregar


def poner_pendiente(cmd, texto, marca, socket_viejo):
    os.makedirs(PENDIENTES_DIR, exist_ok=True)
    nombre = f"{int(time.time() * 1000)}-{secrets.token_hex(3)}.json"
    json.dump({"ts": time.time(), "chat": cmd, "texto": texto, "marca": marca, "socket": socket_viejo, "intento": 0},
              open(os.path.join(PENDIENTES_DIR, nombre), "w", encoding="utf-8"), ensure_ascii=False)


_DESP_CHAT = {}   # (09-nov) por chat (cmd): {"t": cuando se desperto por ultima vez, "n": cuantas veces}


def _quedan_mensajes(cmd):
    """(09-nov) True si todavia hay algun mensaje en cola para ese chat (si no se puede leer, asume que si)."""
    try:
        for g in os.listdir(PENDIENTES_DIR):
            if g.endswith(".json"):
                with open(os.path.join(PENDIENTES_DIR, g), encoding="utf-8") as fh:
                    if json.load(fh).get("chat") == cmd:
                        return True
        return False
    except Exception:
        return True


def _una_vuelta():
    """(08-nov) Una pasada de la cola (la llama entregar_pendientes cada 10 s)."""
    try:
        archivos = sorted(f for f in os.listdir(PENDIENTES_DIR) if f.endswith(".json"))
    except OSError:
        return
    for f in archivos:
        ruta = os.path.join(PENDIENTES_DIR, f)
        try:
            p = json.load(open(ruta, encoding="utf-8"))
            if time.time() - p["ts"] > 86400:
                os.remove(ruta); log(f"mensaje en cola para {p['chat']} descartado (24 h sin despertar)"); continue
            # (08-nov) aviso al celular si pasan 15 min sin entregar: una sola vez por mensaje
            if time.time() - p["ts"] > 900 and not p.get("avisado"):
                p["avisado"] = True
                json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                nombre_av = (elegidos_por_cmd().get(p["chat"]) or ("", p["chat"]))[1]
                motivo = _MOTIVO.get(p["chat"]) or p.get("motivo")   # (18-nov) el celular dice por que no entrega
                if motivo in _MOTIVO_TXT and motivo != "escalonado":
                    aviso = tr("Aún no pude entregar a {n}: {m}", n=nombre_av, m=tr(_MOTIVO_TXT[motivo]))
                else:
                    aviso = tr("Aún no pude entregar a {n}; sigo intentando", n=nombre_av)
                threading.Thread(target=push_a_todos, args=("⏳ " + aviso, p["texto"][:120], p["chat"]), daemon=True).start()
                log(f"aviso al celular: {p['chat']} sigue sin entregar")
            s = sesion_por_cmd(p["chat"])
            if not s:
                continue
            nuevo = s.get("socket") and s.get("socket") != p.get("socket")
            # (08-nov) diagnostico: la primera vez que el chat registra buzon nuevo tras el despertar
            if nuevo and not p.get("vio_buzon"):
                log(f"buzón nuevo de {p['chat']}: el chat despertó")
                _registrar({"ev": "buzon_nuevo", "chat": p["chat"], "s_desde_despertar": int(time.time() - p["despertado"]) if p.get("despertado") else None})
                p["vio_buzon"] = True
                json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
            previo = grupos_app.chat_enfocado()
            # (08-nov) los 3 primeros despertares cada 3 min; despues cada 10 min (antes siempre 10 min)
            # (09-nov) el intervalo se lleva por CHAT: con 3 mensajes en cola se despierta una sola vez
            d = _DESP_CHAT.get(p["chat"], {"t": 0, "n": 0})
            intervalo = 180 if d["n"] < 3 else 600
            if not nuevo and time.time() - d["t"] > intervalo:
                if despertar_chat(p["chat"]):
                    _DESP_CHAT[p["chat"]] = {"t": time.time(), "n": d["n"] + 1}
                    p["despertado"] = time.time(); p["previo"] = previo
                    p["despertares"] = p.get("despertares", 0) + 1   # (08-nov)
                    json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    continue   # en ~6 s registra su buzon nuevo y la proxima vuelta lo entrega
                # (08-nov) por que no se desperto: se loguea una vez por motivo (no "escalonado", que es normal)
                motivo = _MOTIVO.get(p["chat"])
                if motivo and motivo != p.get("motivo"):
                    if motivo != "escalonado":
                        log(f"no despierto {p['chat']}: {_MOTIVO_TXT[motivo]}")
                    p["motivo"] = motivo
                    json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
            if not nuevo and time.time() - p.get("ult", 0) < 60:
                continue
            p["ult"] = time.time(); p["intento"] = p.get("intento", 0) + 1
            err = entregar(s, p["texto"], p.get("marca", "📱 "))
            if err:
                json.dump(p, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                continue
            os.remove(ruta)
            if not _quedan_mensajes(p["chat"]):
                _DESP_CHAT.pop(p["chat"], None)   # (09-nov) ya no hay nada en cola para ese chat
            log(f"mensaje en cola ENTREGADO a {p['chat']} (intento {p['intento']})")
            # (15-oct, contra #22) la app de Claude vuelve al chat que tenias abierto (si sigues lejos de la PC)
            if p.get("previo") and p["previo"] != s.get("session_id") and segundos_sin_uso() >= 60:
                try:
                    u = grupos_app.enlace(p["previo"])
                    if u:
                        plataforma.abrir(u)
                except Exception:
                    pass
            nombre = (elegidos_por_cmd().get(p["chat"]) or ("", p["chat"]))[1]
            threading.Thread(target=push_a_todos, args=("✓ " + tr("Entregado a {n}", n=nombre), p["texto"][:120], p["chat"]), daemon=True).start()
        except Exception as e:
            log(f"cola de entregas: {type(e).__name__}")


def entregar_pendientes():
    """Cada 10 s: si el chat de un mensaje en cola registro un buzon NUEVO (desperto) o paso 1 min del ultimo intento,
    se reintenta. Entregado -> se borra y se avisa. Mas de 24 h -> se descarta (queda en el historial como tuyo)."""
    while True:
        time.sleep(10)
        _una_vuelta()


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
    plataforma.pedir_pc_despierta(pantalla=True)   # pantalla + sistema, de una vez
    return True


def despierta_hasta_entregar(cmd, maximo=180):
    """Pide pantalla + sistema de forma continua (solo este hilo) mientras quede un mensaje en cola para `cmd`."""
    inicio = time.time()
    fin = time.time() + maximo
    plataforma.pedir_pc_despierta(continuo=True, pantalla=True)   # continuo: pantalla + sistema
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
        _registrar({"ev": "resultado", "chat": cmd, "entregado": not quedan, "segundos": int(time.time() - inicio)})
    finally:
        plataforma.pedir_pc_despierta(continuo=True, sistema=False)   # suelta el pedido de este hilo


_ULTIMO_ABRIR = {"t": 0.0}   # (08-nov) cuando se abrio la ultima app de Claude para despertar un chat
_MOTIVO = {}                 # (08-nov) por cmd: por que despertar_chat no abrio el chat la ultima vez
# (18-nov) textos para el celular (push) y para el log; el push los pasa por tr() (ver kodama_texto._EN)
_MOTIVO_TXT = {"pc_en_uso": "tu PC está en uso; lo entrego cuando la dejes 2 min",
               "sin_enlace": "ese chat no está en la app de Claude (o está archivado)",
               "escalonado": "estoy despertando otro chat; sigo en unos segundos"}


def _ruta_registro():
    return os.path.join(BASE, "despertar.jsonl")


def _registrar(ev):
    """(18-nov) Una linea JSON por intento/resultado de despertar, para medir antes de tocar nada. Nunca lanza."""
    try:
        ruta = _ruta_registro()
        if os.path.exists(ruta) and os.path.getsize(ruta) > 1024 * 1024:
            os.replace(ruta, ruta + ".1")
        ev = dict(ev, ts=time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass


def despertar_chat(cmd):
    """(18-nov) Envoltorio: registra el resultado del intento en despertar.jsonl."""
    ok = _despertar_chat(cmd)
    _registrar({"ev": "intento", "chat": cmd, "abrio": bool(ok), "motivo": _MOTIVO.get(cmd)})
    return ok


def _despertar_chat(cmd):
    """(15-oct) Despierta un chat dormido abriendolo en la app de Claude (su enlace claude://…): la app vuelve a
    levantar su proceso y en ~6 s tiene buzon nuevo (probado con Documental). Abrir la app le quita la pantalla a lo
    que estes haciendo en la PC, asi que SOLO si no la usas hace 2 min o mas. True si lo intento."""
    _MOTIVO.pop(cmd, None)   # (08-nov)
    try:
        if segundos_sin_uso() < 120:
            _MOTIVO[cmd] = "pc_en_uso"   # (08-nov)
            return False
        cli = next((c for c, v in todos_elegidos().items() if v[0] == cmd), None)
        url = grupos_app.enlace(cli) if cli else None
        if not url or not url.startswith("claude://"):
            _MOTIVO[cmd] = "sin_enlace"   # (08-nov)
            return False
        # (08-nov) escalonado: no abrir dos chats con menos de 20 s de diferencia; la proxima pasada reintenta
        if time.time() - _ULTIMO_ABRIR["t"] < 20:
            _MOTIVO[cmd] = "escalonado"
            return False
        # (09-nov) si ese chat es el que la app tiene EN PANTALLA, la app no lo revive: primero se abre otro chat
        if cli and grupos_app.chat_enfocado() == cli:
            otra_url = None
            for otro in todos_elegidos():
                if otro == cli:
                    continue
                u2 = grupos_app.enlace(otro)
                if u2 and u2.startswith("claude://"):
                    otra_url = u2
                    break
            if otra_url:
                plataforma.abrir(otra_url)
                time.sleep(3)
                log(f"{cmd} estaba en pantalla: abro otro chat antes para que la app lo reviva")
        if prender_pantalla():
            # (19-oct) el 18-oct la PC salia de la suspension pero a los 30 s volvia a entrar (22 veces, 11:35-13:17)
            # sin que el chat alcanzara a revivir: ahora se la mantiene despierta hasta entregar (max. 3 min)
            threading.Thread(target=despierta_hasta_entregar, args=(cmd,), daemon=True).start()
            time.sleep(3)   # que Windows termine de salir de la suspension antes de abrir el enlace
        plataforma.abrir(url)
        _ULTIMO_ABRIR["t"] = time.time()   # (08-nov)
        log(f"despertando {cmd} (PC sin uso): abro su chat en la app de Claude")
        return True
    except Exception as e:
        log(f"no pude despertar {cmd}: {type(e).__name__}")
        return False
