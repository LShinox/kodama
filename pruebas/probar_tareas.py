# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(30-oct) Prueba de cuando se muestra el progreso de tareas ("1/4") en el historial de cada chat.
Regla: se muestra si el chat esta "trabajando" y la lista se toco hace <6 h, o si la lista esta completa y se toco hace <=30 min.
Todo en una carpeta temporal y con sesiones SINTETICAS: NO toca estado\\, ni PUENTE/COLA/RESP reales, ni el hub.
Cubre:
  1) trabajando, 1/4, hace 1 min -> se muestra;
  2) termino (esperando al usuario), 0/2, hace 1 min -> no se muestra;
  3) termino, 4/4 (completa), hace 10 min -> se muestra;
  4) termino, 4/4, hace 40 min -> no se muestra;
  5) trabajando, 2/5, hace 7 h -> no se muestra.
Uso: python probar_tareas.py"""
import os, shutil, sys, tempfile, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import kodama_historial as kh  # noqa: E402

fallos = []


def ok(nombre, cond, extra=""):
    print(("OK   " if cond else "FALLA"), nombre, ("" if cond else extra))
    if not cond:
        fallos.append(nombre)


TMP = tempfile.mkdtemp(prefix="kodama-tareas-")
try:
    ahora = time.time()
    # (cmd, estado, tareas h/t, hace cuanto se toco la lista en segundos, caso)
    casos = [
        ("caso1", "trabajando", 1, 4, 60, True),
        ("caso2", "termino", 0, 2, 60, False),
        ("caso3", "termino", 4, 4, 600, True),
        ("caso4", "termino", 4, 4, 2400, False),
        ("caso5", "trabajando", 2, 5, 7 * 3600, False),
    ]
    sesiones_falsas = []
    for cmd, estado, h, t, hace, _ in casos:
        sesiones_falsas.append({
            "session_id": "sid-" + cmd, "_cmd": cmd, "estado": estado, "visto": ahora - 5,   # visto reciente: no se pasa a reposo
            "titulo": cmd, "tareas": {"h": h, "t": t, "a": "tarea de prueba", "ts": ahora - hace, "items": {}}})

    # aislar: nada de sesiones, colores, permisos, fases, puente ni colas reales
    kh.sesiones = lambda: sesiones_falsas
    kh.info = lambda s: (s["_cmd"], s["_cmd"], "") if s else None
    kh.todos_los_chats = lambda: [(c, c, "") for c, *_ in casos]
    kh.colores_app = lambda: {}
    kh.grupos_propios = lambda: {}
    kh.permisos_pendientes = lambda: {}
    kh.fase_de = lambda s, ahora=None: (None, None)
    kh.PUENTE = os.path.join(TMP, "puente")
    kh.COLA = os.path.join(TMP, "cola.jsonl")
    kh.RESP = os.path.join(TMP, "respuestas.jsonl")
    kh.grupos_app.enlace = lambda sid: ""

    salida = kh._historial()
    for cmd, estado, h, t, hace, esperado in casos:
        d = salida.get(cmd, {})
        mostrado = "tareas" in d
        ok("%s (%s, %d/%d, hace %d s): %s" % (cmd, estado, h, t, hace, "se muestra" if esperado else "oculta"),
           mostrado == esperado, str(d.get("tareas")))
        if mostrado:
            ok("%s: conteos correctos" % cmd, (d["tareas"]["h"], d["tareas"]["t"]) == (h, t), str(d["tareas"]))
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("TODO BIEN" if not fallos else "FALLARON: " + ", ".join(fallos))
sys.exit(1 if fallos else 0)
