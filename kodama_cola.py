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
                            plataforma.abrir(u)
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
    plataforma.pedir_pc_despierta(pantalla=True)   # pantalla + sistema, de una vez
    return True


def despierta_hasta_entregar(cmd, maximo=180):
    """Pide pantalla + sistema de forma continua (solo este hilo) mientras quede un mensaje en cola para `cmd`."""
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
    finally:
        plataforma.pedir_pc_despierta(continuo=True, sistema=False)   # suelta el pedido de este hilo


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
        plataforma.abrir(url)
        log(f"despertando {cmd} (PC sin uso): abro su chat en la app de Claude")
        return True
    except Exception as e:
        log(f"no pude despertar {cmd}: {type(e).__name__}")
        return False
