"""(18-nov) Prueba el registro estructurado de despertar (kodama_cola._registrar / despertar_chat).
Sin red, sin abrir la app: la ruta del registro se redirige a una carpeta temporal dentro de
pruebas\\_tmp_despertar_log, que se borra al final."""
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

RAIZ_PROY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ_PROY)
import kodama_cola as kc

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_despertar_log")
os.makedirs(RAIZ, exist_ok=True)
TMP = tempfile.mkdtemp(dir=RAIZ)
REG = os.path.join(TMP, "despertar.jsonl")


def reset():
    for f in os.listdir(TMP):
        ruta = os.path.join(TMP, f)
        if os.path.isfile(ruta):
            os.remove(ruta)
    kc._MOTIVO.clear()


def leer_lineas(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def caso_a():
    """_registrar escribe una linea JSON valida con ts."""
    reset()
    with mock.patch.object(kc, "_ruta_registro", side_effect=lambda: REG):
        kc._registrar({"ev": "prueba", "chat": "chatA"})
    lineas = leer_lineas(REG)
    ok = len(lineas) == 1 and lineas[0]["ev"] == "prueba" and lineas[0]["chat"] == "chatA" and "ts" in lineas[0]
    return ok, f"lineas={len(lineas)}"


def caso_b():
    """Archivo mayor a 1 MB: se rota a .1 y el nuevo empieza con una sola linea."""
    reset()
    with open(REG, "w", encoding="utf-8") as f:
        f.write("x" * (1024 * 1024 + 10) + "\n")
    with mock.patch.object(kc, "_ruta_registro", side_effect=lambda: REG):
        kc._registrar({"ev": "nuevo"})
    rotado = os.path.exists(REG + ".1") and os.path.getsize(REG + ".1") > 1024 * 1024
    lineas = leer_lineas(REG)
    ok = rotado and len(lineas) == 1 and lineas[0]["ev"] == "nuevo"
    return ok, f"rotado={rotado} lineas_nuevas={len(lineas)}"


def caso_c():
    """Ruta no escribible (es una carpeta): no lanza."""
    reset()
    carpeta = os.path.join(TMP, "es_carpeta")
    os.makedirs(carpeta, exist_ok=True)
    try:
        with mock.patch.object(kc, "_ruta_registro", side_effect=lambda: carpeta):
            kc._registrar({"ev": "x"})
    except Exception as ex:
        return False, f"lanzo {type(ex).__name__}: {ex}"
    return True, "no lanzo"


def caso_d():
    """despertar_chat envuelve _despertar_chat: registra intento con abrio=False y motivo pc_en_uso."""
    reset()

    def falso(cmd):
        kc._MOTIVO[cmd] = "pc_en_uso"
        return False

    with mock.patch.object(kc, "_despertar_chat", side_effect=falso), \
            mock.patch.object(kc, "_ruta_registro", side_effect=lambda: REG):
        r = kc.despertar_chat("chatA")
    lineas = leer_lineas(REG)
    ok = r is False and len(lineas) == 1 and lineas[0]["ev"] == "intento" \
        and lineas[0]["abrio"] is False and lineas[0]["motivo"] == "pc_en_uso"
    return ok, f"r={r} lineas={lineas}"


if __name__ == "__main__":
    casos = [
        ("a) _registrar escribe una linea JSON con ts", caso_a),
        ("b) rotacion a .1 al pasar 1 MB", caso_b),
        ("c) ruta no escribible no lanza", caso_c),
        ("d) despertar_chat registra intento con motivo", caso_d),
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
        shutil.rmtree(RAIZ, ignore_errors=True)
    print(f"{ok_n}/{len(casos)} OK")
    sys.exit(0 if ok_n == len(casos) else 1)
