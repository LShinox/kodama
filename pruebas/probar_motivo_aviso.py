# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov) Prueba que el aviso al celular ("Aún no pude entregar") diga el motivo cuando la PC esta en uso.
Reloj falso, cola en una carpeta temporal que se borra al final; push, log, abrir, entregar y sesiones son falsos."""
import os
import shutil
import sys
import tempfile
import threading
import time as _real_time
from unittest import mock

RAIZ_PROY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ_PROY)
import config
import kodama_cola as kc

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_motivo_aviso")
os.makedirs(RAIZ, exist_ok=True)
TMP = tempfile.mkdtemp(dir=RAIZ)
COLA = os.path.join(TMP, "pendientes")
os.makedirs(COLA, exist_ok=True)

T0 = 1_000_000.0
PUSHES = []


class _Reloj:
    t = T0


class _Tiempo:
    """Reemplaza el modulo time solo dentro de kodama_cola."""
    @staticmethod
    def time():
        return _Reloj.t

    @staticmethod
    def sleep(_s):
        pass

    localtime = staticmethod(_real_time.localtime)
    strftime = staticmethod(_real_time.strftime)


def _push(*args):
    PUSHES.append(args)


def _esperar_hilos():
    for h in threading.enumerate():
        if h is not threading.current_thread() and h.daemon:
            h.join(2)


def caso_pc_en_uso():
    """Con la PC en uso, a los 15 min el aviso al celular incluye la frase de pc_en_uso."""
    for f in os.listdir(COLA):
        os.remove(os.path.join(COLA, f))
    PUSHES.clear()
    kc._MOTIVO.clear()
    _Reloj.t = T0
    parches = [
        mock.patch.object(config, "IDIOMA", "es"),
        mock.patch.object(kc, "PENDIENTES_DIR", COLA),
        mock.patch.object(kc, "time", _Tiempo),
        mock.patch.object(kc, "segundos_sin_uso", lambda: 10),
        mock.patch.object(kc, "elegidos_por_cmd", lambda: {"chatA": ("cliA", "Chat A")}),
        mock.patch.object(kc, "todos_elegidos", lambda: {"cliA": ("chatA", "Chat A")}),
        mock.patch.object(kc, "sesion_por_cmd", lambda c: {"socket": None, "session_id": "S"}),
        mock.patch.object(kc, "entregar", lambda *a, **k: "sin socket"),
        mock.patch.object(kc, "push_a_todos", _push),
        mock.patch.object(kc, "log", lambda m: None),
        mock.patch.object(kc, "_registrar", lambda ev: None),
        mock.patch.object(kc.grupos_app, "chat_enfocado", lambda: None),
        mock.patch.object(kc.grupos_app, "enlace", lambda c: "claude://a"),
    ]
    for p in parches:
        p.start()
    try:
        kc.poner_pendiente("chatA", "hola", "m", None)
        kc._una_vuelta()            # 1.a pasada: fija el motivo pc_en_uso en _MOTIVO y en el json
        _esperar_hilos()
        _Reloj.t = T0 + 901          # 15 min despues: aviso al celular
        kc._una_vuelta()
        _esperar_hilos()
    finally:
        for p in reversed(parches):
            p.stop()
    avisos =[a[0] for a in PUSHES if a[0].startswith("⏳")]
    esperado = "tu PC está en uso; lo entrego cuando la dejes 2 min"
    ok = len(avisos) == 1 and esperado in avisos[0] and "Aún no pude entregar a Chat A" in avisos[0]
    return ok, f"avisos={avisos}"


if __name__ == "__main__":
    casos = [("a) aviso al celular con el motivo pc_en_uso", caso_pc_en_uso)]
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
