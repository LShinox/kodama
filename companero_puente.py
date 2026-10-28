# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Puente del celular (14-oct-2026): responder desde el celular SIN el parrafo "This came from another Claude
session…" que Claude Code agrega a todo lo que entra por el buzon entre sesiones.

Hook Stop (NO async, timeout ~9 min, config global). Cuando un chat termina su turno:
- si el chat no va al celular, o la PC se esta usando (<2 min sin mouse/teclado): sale enseguida (turno normal);
- si no: deja estado\\puente\\<sesion>.esperando y espera hasta 8 min. Si en ese rato respondes desde el
  celular, el hub escribe <sesion>.respuesta en vez de usar el buzon, y este hook devuelve
  {"decision": "block", "reason": <tu texto>}: Claude sigue con tu respuesta.
- si tocas la PC mientras espera, o pasan los 8 min, sale sin decidir nada y el turno termina normal; lo que
  respondas despues va por el buzon de siempre (con el parrafo).
Si algo falla, sale con 0 sin imprimir nada: nunca deja un chat trabado.
"""
import json
import os
import sys
import time

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import config
import kodama_plataforma as plataforma
from kodama_comun import celular_abierto, va_al_celular  # noqa: E402,F401
BASE = config.ESTADO
PUENTE = os.path.join(BASE, "puente")
PERSONALES = config.PERSONALES
ESPERA_MAX = 480          # 8 min si el chat solo termino (lejos de la PC)
# (21-oct, LShinox: "¿se puede adaptar solo?") espera adaptable: si el chat termino PREGUNTANDO algo y estas lejos,
# hasta 20 min (es cuando mas probable es que contestes desde el celular); y mientras tengas la app del celular
# ABIERTA, cada vuelta la estira 2 min mas, con un tope de 30 min. El timeout del hook (settings.json) es 1900 s.
ESPERA_PREGUNTA = 1200
ESPERA_TOPE = 1800
EN_PC_MAX = 180           # (19-oct) pregunta con la PC en uso: 3 min como mucho
SIN_USO_MIN = 120         # solo si la PC lleva 2 min sin uso


def sin_uso():
    return float(plataforma.segundos_sin_uso())   # (Mac-F2) por plataforma


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    sid = d.get("session_id")
    proy = os.path.basename(os.path.dirname(d.get("transcript_path") or ""))
    prueba = os.environ.get("COMPANERO_PUENTE_PRUEBA") == "1"   # solo para probar sin alejarse de la PC
    lejos = sin_uso() >= SIN_USO_MIN or celular_abierto() or prueba   # (14-oct) o la app del celular abierta ahora
    # (14-oct, LShinox: "que se pueda resolver desde la mascota y ya") si el chat TERMINO PREGUNTANDO algo (pide una
    # decision u OK), espera aunque estes en la PC: asi el "OK" de la mascota cuenta como tuyo. Se libera con ✕ en la
    # mascota/celular (estado\puente\<sesion>.liberar) o a los 8 min. Si mientras tanto escribes en el chat de la app,
    # ese mensaje espera a que se libere (sin confirmar como lo muestra la app).
    pregunta = es_pregunta(d.get("last_assistant_message") or "")
    if not sid or not va_al_celular(sid, proy) or not (lejos or pregunta):
        return
    os.makedirs(PUENTE, exist_ok=True)
    esp, resp, lib = (os.path.join(PUENTE, sid + x) for x in (".esperando", ".respuesta", ".liberar"))
    for viejo in (resp, lib):           # algo que quedo de antes no cuenta
        try:
            os.remove(viejo)
        except OSError:
            pass
    open(esp, "w").write(json.dumps({"ts": time.time(), "pregunta": pregunta}))
    inicio = time.time()
    en_pc = None if lejos else inicio   # desde cuando estas en la PC (cuenta para el tope de 3 min de las preguntas)
    # (14-oct) si escribes en el chat de la app de Claude mientras esto espera, tu mensaje queda en cola: Claude Code
    # anota {"type":"queue-operation","operation":"enqueue"} en el transcript. Al verlo, el puente se suelta YA y tu
    # mensaje entra enseguida (antes esperaba hasta 8 min).
    tr = d.get("transcript_path") or ""
    try:
        pos = os.path.getsize(tr)
    except OSError:
        tr, pos = "", 0
    fin = inicio + (ESPERA_PREGUNTA if pregunta else ESPERA_MAX)
    try:
        while time.time() < fin:
            if celular_abierto():   # lo estas mirando en el celular: sigue esperando (tope 30 min)
                fin = min(max(fin, time.time() + 120), inicio + ESPERA_TOPE)
            if tr:
                try:
                    if os.path.getsize(tr) > pos:
                        with open(tr, "rb") as f:
                            f.seek(pos); nuevo = f.read(); pos += len(nuevo)
                        if b'"queue-operation"' in nuevo and b'"enqueue"' in nuevo:
                            return
                except OSError:
                    pass
            if os.path.exists(resp):
                texto = open(resp, encoding="utf-8").read().strip()
                os.remove(resp)
                if texto:
                    # (14-oct) additionalContext en vez de decision:block: Claude sigue igual y la app lo muestra como
                    # "Stop hook feedback" sin la palabra "error" (doc hooks, "Stop decision control"). ASCII: la consola rompe emojis
                    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": f"Respuesta de {config.NOMBRE}: " + texto}})); sys.stdout.flush()
                return
            if os.path.exists(lib):     # ✕ "liberar" desde la mascota o el celular
                return
            if not pregunta and sin_uso() < 3 and not prueba and not celular_abierto():   # volviste a la PC: se libera
                return
            # (19-oct, LShinox: "un punto medio") una PREGUNTA ya no retiene el chat 8 min con la PC en uso (la app de
            # Claude lo mostraba "trabajando"): estando en la PC espera como mucho 3 min para contestar desde la mascota;
            # si estabas lejos, al volver a la PC le quedan como mucho 3 min mas. Despues se suelta y se ve terminado.
            if pregunta and not prueba:
                if sin_uso() < 3 and not celular_abierto():
                    en_pc = en_pc or time.time()
                if en_pc and time.time() - en_pc > EN_PC_MAX:
                    return
            if mirando_este(sid):   # (15-oct) abriste ESTE chat en la app de Claude: se suelta y lo ves terminado
                return
            time.sleep(1)
    finally:
        for f in (esp, lib):
            try:
                os.remove(f)
            except OSError:
                pass


_MIR = {"t": 0}


def mirando_este(sid):
    """(15-oct) Mientras el puente espera, para la app de Claude el turno sigue en curso (el chat se ve trabajando).
    Si lo abres en la app (app al frente + usaste la PC hace < 30 s + es el chat enfocado), el puente se suelta:
    asi solo se ve "en curso" mientras NO lo estas mirando. Se mira cada 2 s."""
    if time.time() - _MIR["t"] < 2:
        return False
    _MIR["t"] = time.time()
    try:
        if sin_uso() > 30:
            return False
        if plataforma.app_al_frente() != plataforma.NOMBRE_APP_CLAUDE:   # (Mac-F2) por plataforma
            return False
        import grupos_app
        return grupos_app.chat_enfocado() == sid
    except Exception:
        return False


def es_pregunta(texto):
    """¿El turno termino pidiendo una decision / OK? Usa el mismo clasificador que los avisos (kodama_texto)."""
    if not texto.strip():
        return False
    try:
        from kodama_texto import clasificar   # (28-oct) antes importaba el hub entero
        return clasificar("Stop", texto)[0] in ("pregunta", "permiso")
    except BaseException:           # sin hub importable (p. ej. sin token de Telegram): lo minimo
        return texto.rstrip().endswith("?")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
