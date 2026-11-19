# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(08-nov) Prueba la cola de entregas y el despertar de chats (kodama_cola) con reloj falso y sin tocar nada real:
la cola va a una carpeta temporal en el scratchpad; abrir, pantalla, entregar, push, log y sesiones son falsos."""
import json, os, shutil, sys, tempfile, threading, time as _real_time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import grupos_app
import kodama_cola as kc
import kodama_plataforma as plataforma
kc._ruta_registro = lambda: os.path.join(tempfile.gettempdir(), "kodama-prueba-despertar.jsonl")

BASE = os.path.join(tempfile.gettempdir(), "companero-prueba-despertar")
PEND = os.path.join(BASE, "pendientes")
os.makedirs(PEND, exist_ok=True)


class Reloj:
    t = 1_000_000.0


class _Tiempo:
    """Reemplaza el modulo time solo dentro de kodama_cola."""
    @staticmethod
    def time():
        return Reloj.t

    @staticmethod
    def sleep(_s):
        pass

    localtime = staticmethod(_real_time.localtime)


ESTADO = {"sin_uso": 500, "entregar_err": None, "chats": set(), "sesiones": {}, "abiertos": [], "logs": [],
          "pushes": [], "entregas": []}


def _entregar(s, texto, marca):
    ESTADO["entregas"].append(texto)
    return ESTADO["entregar_err"]


def _push(*args):
    ESTADO["pushes"].append(args)


def _log(msg):
    ESTADO["logs"].append(msg)


def _abrir(url):
    ESTADO["abiertos"].append((Reloj.t, url))


ORIGINALES = {
    "PENDIENTES_DIR": kc.PENDIENTES_DIR, "time": kc.time, "segundos_sin_uso": kc.segundos_sin_uso,
    "sesion_por_cmd": kc.sesion_por_cmd, "todos_elegidos": kc.todos_elegidos, "elegidos_por_cmd": kc.elegidos_por_cmd,
    "entregar": kc.entregar, "push_a_todos": kc.push_a_todos, "log": kc.log, "prender_pantalla": kc.prender_pantalla,
    "enlace": grupos_app.enlace, "chat_enfocado": grupos_app.chat_enfocado, "abrir": plataforma.abrir,
    "pedir": plataforma.pedir_pc_despierta,
}

kc.PENDIENTES_DIR = PEND
kc.time = _Tiempo
kc.segundos_sin_uso = lambda: ESTADO["sin_uso"]
kc.sesion_por_cmd = lambda cmd: ESTADO["sesiones"].get(cmd)
kc.todos_elegidos = lambda: {"cli-" + c: (c, "Nombre-" + c) for c in ESTADO["chats"]}
kc.elegidos_por_cmd = lambda: {c: ("cli-" + c, "Nombre-" + c) for c in ESTADO["chats"]}
kc.entregar = _entregar
kc.push_a_todos = _push
kc.log = _log
kc.prender_pantalla = lambda: False
grupos_app.enlace = lambda cli: "claude://chat/" + cli[4:] if cli and cli.startswith("cli-") else None
grupos_app.chat_enfocado = lambda: None
plataforma.abrir = _abrir
plataforma.pedir_pc_despierta = lambda **kw: None

resultados = []


def chequeo(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def esperar_hilos():
    for h in threading.enumerate():
        if h is not threading.current_thread() and h.daemon:
            h.join(2)


def pasada():
    kc._una_vuelta()
    esperar_hilos()


def caso(sin_uso=500, err=None, chats=(), sesiones=None):
    for f in os.listdir(PEND):
        os.remove(os.path.join(PEND, f))
    kc._ULTIMO_ABRIR["t"] = 0.0
    kc._MOTIVO.clear()
    Reloj.t = 1_000_000.0
    ESTADO.update(sin_uso=sin_uso, entregar_err=err, abiertos=[], logs=[], pushes=[], entregas=[])
    ESTADO["chats"] = set(chats)
    ESTADO["sesiones"] = dict(sesiones or {c: {"socket": "S1", "session_id": "s-" + c} for c in chats})


def pendiente(nombre, chat, ts=None, socket="S1"):
    p = {"ts": Reloj.t if ts is None else ts, "chat": chat, "texto": "hola " + nombre, "marca": "📱 ",
         "socket": socket, "intento": 0}
    json.dump(p, open(os.path.join(PEND, nombre + ".json"), "w", encoding="utf-8"), ensure_ascii=False)


def leer(nombre):
    return json.load(open(os.path.join(PEND, nombre + ".json"), encoding="utf-8"))


def existe(nombre):
    return os.path.exists(os.path.join(PEND, nombre + ".json"))


def logs_con(texto):
    return [m for m in ESTADO["logs"] if texto in m]


try:
    # a. PC en uso: un solo log, no se repite en la pasada siguiente
    caso(sin_uso=10, err="err", chats=["A"])
    pendiente("a", "A")
    pasada()
    chequeo("a: PC en uso no abre el chat", ESTADO["abiertos"] == [])
    chequeo("a: loguea 'no despierto A: tu PC está en uso' una vez", len(logs_con("no despierto A: tu PC está en uso")) == 1)
    Reloj.t += 10
    pasada()
    chequeo("a: segunda pasada no repite el log", len(logs_con("no despierto A")) == 1)
    chequeo("a: motivo guardado en el json", leer("a").get("motivo") == "pc_en_uso")

    # b. Escalonado: 20 s entre aperturas de chats distintos
    caso(err="err", chats=["A", "B"])
    pendiente("a", "A")
    pendiente("b", "B")
    pasada()
    chequeo("b: primer chat se abre una vez", [u for _, u in ESTADO["abiertos"]] == ["claude://chat/A"])
    chequeo("b: el segundo (<20 s) no se abre", len(ESTADO["abiertos"]) == 1)
    chequeo("b: 'escalonado' no se loguea", not logs_con("espero 20 s"))
    Reloj.t += 5
    pasada()
    chequeo("b: a los 5 s sigue sin abrir B", len(ESTADO["abiertos"]) == 1)
    Reloj.t += 16
    pasada()
    chequeo("b: a los 21 s abre B", [u for _, u in ESTADO["abiertos"]] == ["claude://chat/A", "claude://chat/B"])

    # c. Intervalos: 2.o y 3.er despertar tras 180 s (codigo: "> 180"), 4.o tras 600 s
    caso(err="err", chats=["C"])
    pendiente("c", "C")
    t0 = Reloj.t
    pasada()
    chequeo("c: 1.er despertar inmediato", len(ESTADO["abiertos"]) == 1)
    Reloj.t = t0 + 179
    pasada()
    chequeo("c: a los 179 s no despierta de nuevo", len(ESTADO["abiertos"]) == 1)
    Reloj.t = t0 + 181
    pasada()
    chequeo("c: 2.o despertar a los 181 s", len(ESTADO["abiertos"]) == 2)
    Reloj.t = t0 + 181 + 181
    pasada()
    chequeo("c: 3.er despertar a los 181 s mas", len(ESTADO["abiertos"]) == 3)
    t3 = Reloj.t
    Reloj.t = t3 + 599
    pasada()
    chequeo("c: 4.o despertar no antes de 600 s", len(ESTADO["abiertos"]) == 3)
    Reloj.t = t3 + 601
    pasada()
    chequeo("c: 4.o despertar a los 600 s", len(ESTADO["abiertos"]) == 4)
    chequeo("c: contador despertares = 4", leer("c").get("despertares") == 4)

    # d. Socket nuevo: log una vez y entrega con push
    caso(err="err", chats=["D"], sesiones={"D": {"socket": "S2", "session_id": "s-D"}})
    pendiente("d", "D", socket="S1")
    pasada()
    chequeo("d: 'buzón nuevo' logueado", len(logs_con("buzón nuevo de D: el chat despertó")) == 1)
    chequeo("d: vio_buzon persistido", leer("d").get("vio_buzon") is True)
    ESTADO["entregar_err"] = None
    pasada()
    chequeo("d: el buzon nuevo no se loguea dos veces", len(logs_con("buzón nuevo de D")) == 1)
    chequeo("d: archivo borrado tras entregar", not existe("d"))
    chequeo("d: push 'Entregado a' enviado",
            any(a[0].startswith("✓") and a[0].endswith("Nombre-D") for a in ESTADO["pushes"]))

    # e. Aviso al celular a los 900 s, una sola vez
    caso(sin_uso=10, err="err", chats=["E"])
    pendiente("e", "E", ts=Reloj.t - 901)
    pasada()
    avisos = [a for a in ESTADO["pushes"] if a[0].startswith("⏳")]
    chequeo("e: aviso 'Aún no pude entregar' enviado", len(avisos) == 1 and "Nombre-E" in avisos[0][0])
    Reloj.t += 60
    pasada()
    Reloj.t += 600
    pasada()
    avisos = [a for a in ESTADO["pushes"] if a[0].startswith("⏳")]
    chequeo("e: no se repite en pasadas siguientes", len(avisos) == 1)
    chequeo("e: avisado persistido y log", leer("e").get("avisado") is True and len(logs_con("aviso al celular: E")) == 1)

    # f. Mas de 24 h: se descarta sin entregar
    caso(err=None, chats=["F"])
    pendiente("f", "F", ts=Reloj.t - 86401)
    pasada()
    chequeo("f: archivo descartado", not existe("f"))
    chequeo("f: log de descarte", len(logs_con("mensaje en cola para F descartado")) == 1)
    chequeo("f: no se intenta entregar", ESTADO["entregas"] == [])
finally:
    kc.PENDIENTES_DIR = ORIGINALES["PENDIENTES_DIR"]
    kc.time = ORIGINALES["time"]
    kc.segundos_sin_uso = ORIGINALES["segundos_sin_uso"]
    kc.sesion_por_cmd = ORIGINALES["sesion_por_cmd"]
    kc.todos_elegidos = ORIGINALES["todos_elegidos"]
    kc.elegidos_por_cmd = ORIGINALES["elegidos_por_cmd"]
    kc.entregar = ORIGINALES["entregar"]
    kc.push_a_todos = ORIGINALES["push_a_todos"]
    kc.log = ORIGINALES["log"]
    kc.prender_pantalla = ORIGINALES["prender_pantalla"]
    grupos_app.enlace = ORIGINALES["enlace"]
    grupos_app.chat_enfocado = ORIGINALES["chat_enfocado"]
    plataforma.abrir = ORIGINALES["abrir"]
    plataforma.pedir_pc_despierta = ORIGINALES["pedir"]
    shutil.rmtree(BASE, ignore_errors=True)
    print("limpio:", not os.path.exists(BASE))

total = len(resultados)
ok = sum(resultados)
print(f"\nResultado: {ok}/{total} OK")
sys.exit(0 if ok == total and total > 0 else 1)
