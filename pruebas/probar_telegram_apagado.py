# (06-nov) con telegram_avisos en False, enviar_aviso sigue mandando el push y no llama a Telegram. Todo con dobles: no envia nada real.
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodama_notificaciones as kn  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
    else:
        fallos += 1
        print("FALLA:", nombre)


llamadas, pushes = [], []
kn.api = lambda metodo, **p: (llamadas.append(metodo), {"ok": True, "result": {"message_id": 7}})[1]
kn.guardar_conf = lambda conf: None
kn.sesiones = lambda: [{"session_id": "s"}]
kn.info = lambda s: ("chat", "Chat", "")
kn.silenciado = lambda conf, cmd: False
kn.mirando_chat = lambda: None
kn.pendientes = lambda conf: 0
kn.push_a_todos = lambda *a, **k: pushes.append(a)
kn.kodama_prefs.silencio_ahora = lambda tipo: False


def aviso(prefs, texto):
    kn.kodama_prefs.leer = lambda ruta=None: prefs
    llamadas.clear()
    pushes.clear()
    r = kn.enviar_aviso({"dueno": 1}, {"session_id": "s", "evento": "Stop", "texto": texto})
    time.sleep(0.1)
    return r


r = aviso({"telegram_avisos": False}, "Primero listo")
ver("apagado: no llama a Telegram", llamadas == [])
ver("apagado: manda el push", len(pushes) == 1)
ver("apagado: devuelve el aviso", r == ("", "Chat", "termino") or (isinstance(r, tuple) and r[1] == "Chat"))

kn.kodama_prefs.silencio_ahora = lambda tipo: False
r = aviso({"telegram_avisos": True}, "Segundo listo")
ver("encendido: si llama a Telegram", "sendMessage" in llamadas)
ver("encendido: manda el push", len(pushes) == 1)

llamadas.clear()
pushes.clear()
kn.kodama_prefs.leer = lambda ruta=None: {"telegram_avisos": False}
kn.enviar_aviso = lambda conf, it, agrupado=False, reintento=0: (it.get("e", ""), it["n"], "termino")
kn.ESPERA[:] = [{"session_id": "a", "ts": 0, "n": "A"}, {"session_id": "b", "ts": 0, "n": "B"}]
kn.vaciar_espera({"dueno": 1}, forzar=True)
time.sleep(0.1)
ver("apagado: el resumen de grupo no va a Telegram", llamadas == [])
ver("apagado: el resumen de grupo si va a la app", len(pushes) == 1)

print(f"{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
