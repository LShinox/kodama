# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(09-nov) Prueba el despertar UNA vez por chat y el caso de "chat que la app tiene en pantalla" (kodama_cola),
y que app.html / i18n.js tengan el interruptor de respuestas rápidas. Sin red, sin abrir la app: todo lo externo
(abrir, pantalla, entregar, sesiones, log, push) se reemplaza con mock. La cola va a una carpeta temporal dentro de
pruebas\\_tmp_despertar2, que se borra al final."""
import os
import shutil
import sys
import tempfile
import time
from unittest import mock

RAIZ_PROY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ_PROY)
import kodama_cola as kc
kc._ruta_registro = lambda: os.path.join(tempfile.gettempdir(), "kodama-prueba-despertar.jsonl")

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_despertar2")
os.makedirs(RAIZ, exist_ok=True)
TMP = tempfile.mkdtemp(dir=RAIZ)
COLA = os.path.join(TMP, "pendientes")
os.makedirs(COLA, exist_ok=True)

# Dos chats: "chatA" (cliA) y "chatB" (cliB), cada uno con enlace claude://
ENLACES = {"cliA": "claude://a", "cliB": "claude://b"}
ELEGIDOS = {"cliA": ("chatA", "Chat A"), "cliB": ("chatB", "Chat B")}


def reset():
    kc._DESP_CHAT.clear()
    kc._MOTIVO.clear()
    kc._ULTIMO_ABRIR["t"] = 0.0
    for f in os.listdir(COLA):
        os.remove(os.path.join(COLA, f))


class Entorno:
    """Reemplaza todo lo externo de kodama_cola y registra las llamadas a plataforma.abrir y a log."""

    def __init__(self, enfocado=None, entregar_ok=False):
        self.enfocado = enfocado
        self.entregar_ok = entregar_ok
        self.abrir = []
        self.logs = []

    def __enter__(self):
        self.parches = [
            mock.patch.object(kc, "PENDIENTES_DIR", COLA),
            mock.patch.object(kc.plataforma, "abrir", side_effect=lambda u: self.abrir.append(u)),
            mock.patch.object(kc.grupos_app, "chat_enfocado", side_effect=lambda: self.enfocado),
            mock.patch.object(kc.grupos_app, "enlace", side_effect=lambda c: ENLACES.get(c)),
            mock.patch.object(kc, "todos_elegidos", side_effect=lambda: dict(ELEGIDOS)),
            mock.patch.object(kc, "elegidos_por_cmd", side_effect=lambda: dict(ELEGIDOS)),
            mock.patch.object(kc, "segundos_sin_uso", side_effect=lambda: 999),
            mock.patch.object(kc, "prender_pantalla", side_effect=lambda: False),
            mock.patch.object(kc, "entregar",
                              side_effect=lambda *a, **k: None if self.entregar_ok else "sin socket"),
            mock.patch.object(kc, "sesion_por_cmd", side_effect=lambda c: {"socket": None, "session_id": "S"}),
            mock.patch.object(kc, "push_a_todos", side_effect=lambda *a, **k: None),
            mock.patch.object(kc, "log", side_effect=lambda m: self.logs.append(m)),
            mock.patch("kodama_cola.time.sleep"),
        ]
        for p in self.parches:
            p.start()
        return self

    def __exit__(self, *args):
        for p in reversed(self.parches):
            p.stop()


def caso_a():
    """3 mensajes en cola para el mismo chat dormido -> una sola llamada a abrir en la vuelta."""
    reset()
    with Entorno() as e:
        for i in range(3):
            kc.poner_pendiente("chatA", f"msg{i}", "m", None)
        kc._una_vuelta()
        n = len(e.abrir)
    return n == 1, f"abrir={n}"


def caso_b():
    """Segunda vuelta inmediata -> ninguna llamada nueva (no pasó el intervalo)."""
    with Entorno() as e:
        antes = len(e.abrir)
        kc._una_vuelta()
        nuevas = len(e.abrir) - antes
    return nuevas == 0, f"nuevas={nuevas}"


def caso_c():
    """El chat a despertar es el enfocado -> primero el enlace del otro chat, luego el suyo, y log 'estaba en pantalla'."""
    reset()
    with Entorno(enfocado="cliA") as e:
        kc.poner_pendiente("chatA", "x", "m", None)
        kc._una_vuelta()
        orden = list(e.abrir)
        log_ok = any("estaba en pantalla" in m for m in e.logs)
    return orden == ["claude://b", "claude://a"] and log_ok, f"abrir={orden} log={log_ok}"


def caso_d():
    """El chat a despertar NO es el enfocado -> 1 sola llamada (su enlace)."""
    reset()
    with Entorno(enfocado="cliB") as e:
        kc.poner_pendiente("chatA", "x", "m", None)
        kc._una_vuelta()
        orden = list(e.abrir)
    return orden == ["claude://a"], f"abrir={orden}"


def caso_e():
    """Al entregar el último mensaje del chat, _DESP_CHAT ya no tiene ese chat."""
    reset()
    with Entorno(entregar_ok=True) as e:
        kc._DESP_CHAT["chatA"] = {"t": time.time(), "n": 1}
        kc.poner_pendiente("chatA", "x", "m", None)
        kc._una_vuelta()
        queda_en_cola = any(f.endswith(".json") for f in os.listdir(COLA))
        quedo = "chatA" in kc._DESP_CHAT
    return (not quedo) and (not queda_en_cola), f"en_desp={quedo} en_cola={queda_en_cola}"


def caso_f():
    """app.html contiene respRapidas y id="chips"; i18n.js contiene "Quick replies"."""
    app = open(os.path.join(RAIZ_PROY, "web", "app.html"), encoding="utf-8").read()
    i18n = open(os.path.join(RAIZ_PROY, "web", "i18n.js"), encoding="utf-8").read()
    ok = "respRapidas" in app and 'id="chips"' in app and "Quick replies" in i18n
    return ok, f"app_respRapidas={'respRapidas' in app} i18n={'Quick replies' in i18n}"


if __name__ == "__main__":
    casos = [
        ("a) 3 mensajes, una sola llamada a abrir", caso_a),
        ("b) segunda vuelta inmediata, 0 llamadas", caso_b),
        ("c) chat enfocado: abre otro primero y log", caso_c),
        ("d) chat no enfocado: 1 llamada", caso_d),
        ("e) entrega ultimo mensaje: sale de _DESP_CHAT", caso_e),
        ("f) app.html y i18n.js con lo nuevo", caso_f),
    ]
    ok_n = 0
    try:
        for nombre, f in casos:
            try:
                ok, detalle = f()
            except Exception as ex:
                ok, detalle = False, f"error {type(ex).__name__}: {ex}"
            print(f"{nombre}: {'OK' if ok else 'FALLA'}" + ("" if ok else f" ({detalle})"))
            ok_n += bool(ok)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
        try:
            os.rmdir(RAIZ)
        except OSError:
            pass
    print(f"{ok_n}/{len(casos)} OK")
    sys.exit(0 if ok_n == len(casos) else 1)
