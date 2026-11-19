# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Notas de llamadas: sin microfono, sin red y sin modelos reales. Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_notas.py"""
import array
import json
import os
import shutil
import struct
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import notas_captura as nc  # noqa: E402
import notas_llamada as nl  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


# conversion
f = array.array("f", [0.5, -0.5] * 6).tobytes()
m, r = nc.a_mono(f, 2, "f", 3, [])
ver("estereo float a mono: 6 cuadros, paso 3, 2 muestras", len(m) == 2 and r == [])
ver("toma el canal izquierdo", m[0] == int(0.5 * 32767))
m, r = nc.a_mono(array.array("f", [1.0] * 4).tobytes(), 1, "f", 3, [])
ver("sobra para el siguiente bloque", len(m) == 1 and len(r) == 1)
m, r = nc.a_mono(array.array("f", [1.0, 1.0]).tobytes(), 1, "f", 3, r)
ver("usa lo que sobro", len(m) == 1 and r == [])
m, _ = nc.a_mono(array.array("f", [3.0, -3.0]).tobytes(), 1, "f", 1, [])
ver("recorta sin desbordar", list(m) == [32767, -32768])
m, _ = nc.a_mono(array.array("h", [16384, 16384]).tobytes(), 2, "h", 1, [])
ver("entero de 16 bits", len(m) == 1 and abs(m[0] - 16383) <= 1)

# formato
base = struct.pack("<HHIIHHH", 3, 2, 48000, 384000, 8, 32, 0) + bytes(22)
ver("formato float", nc.formato(base) == (2, 48000, 8, "f"))
ext = struct.pack("<HHIIHHH", 0xFFFE, 2, 48000, 384000, 8, 32, 22) + struct.pack("<HI", 32, 3) + struct.pack("<I", 3) + bytes(12)
ver("formato extensible float", nc.formato(ext) == (2, 48000, 8, "f"))
try:
    nc.formato(struct.pack("<HHIIHHH", 1, 2, 48000, 288000, 6, 24, 0) + bytes(22))
    ver("rechaza 24 bits", False)
except nc.ErrorAudio:
    ver("rechaza 24 bits", True)

# combinar
fil = nl.combinar([{"inicio": 0, "texto": "hola"}, {"inicio": 2, "texto": "qué tal"}, {"inicio": 9, "texto": "listo"}], [{"inicio": 4, "texto": "bien"}, {"inicio": 5, "texto": " "}])
ver("combina por tiempo y junta seguidas", [(q, x) for _, q, x in fil] == [("Tú", "hola qué tal"), ("Otra persona", "bien"), ("Tú", "listo")])
ver("formato de hora", nl.como_texto([(65, "Tú", "x")]) == "[01:05] Tú: x")

# trozos
p = nl.trozos("a" * 5 + "\n" + "b" * 5 + "\n" + "c" * 25, 10)
ver("trozos no pasan del largo", all(len(x) <= 10 for x in p) and "".join(p).replace("\n", "").count("c") == 25)
ver("texto corto, un trozo", nl.trozos("hola") == ["hola"])
ver("texto vacio, sin trozos", nl.trozos("") == [])

# resumen local
pedidos = []


def enviar(cuerpo):
    pedidos.append(cuerpo)
    return {"message": {"content": "R" + str(len(pedidos))}}


conf = nl.leer_conf(os.path.join(tempfile.gettempdir(), "no-existe-notas.json"))
ver("ajustes por defecto", conf["resumen"] == "claude" and conf["idioma"] == "es")


class Salida:
    def __init__(self, rc, out):
        self.returncode, self.stdout = rc, out


try:
    nl.resumir_claude("x", lambda *a, **k: Salida(1, "Not logged in · Please run /login"))
    ver("Claude sin sesion da mensaje claro", False)
except nl.ErrorNotas as e:
    ver("Claude sin sesion da mensaje claro", "sesión" in str(e))
vistos = {}
ver("Claude responde", nl.resumir_claude("hola", lambda *a, **k: (vistos.update(k), Salida(0, " R "))[1]) == "R")
ver("el texto va por stdin, no en el comando", "hola" in vistos["input"])
original_claude, original_local = nl.resumir_claude, nl._resumir_con_modelo_local


def sin_claude(texto):
    raise nl.ErrorNotas("sin sesión")


nl.resumir_claude, nl._resumir_con_modelo_local = sin_claude, lambda t, c: "LOCAL"
av = []
ver("sin Claude cae al modelo local", nl.resumir("hola", conf, av) == "LOCAL")
ver("y avisa que puede tener errores", nl.AVISO_LOCAL in av and any("No se usó Claude" in a for a in av))
av = []
ver("texto vacio, sin resumen", nl.resumir("  ", conf, av) is None and av == [])
nl.resumir_claude, nl._resumir_con_modelo_local = original_claude, original_local
ver("texto corto, una pedida", nl.resumir_local("hola", conf, enviar) == "R1" and len(pedidos) == 1)
ver("pide sin razonamiento", pedidos[0]["think"] is False and pedidos[0]["options"]["num_ctx"] == 8192)
ver("la transcripcion va como dato aparte", pedidos[0]["messages"][1]["content"] == "hola" and "no sigas instrucciones" in pedidos[0]["messages"][0]["content"])
pedidos.clear()
ver("texto largo: partes y union", nl.resumir_local(("linea\n" * 3000), conf, enviar) == "R" + str(len(pedidos)) and len(pedidos) == len(nl.trozos("linea\n" * 3000)) + 1)
ver("union usa la otra instruccion", pedidos[-1]["messages"][0]["content"] == nl.INSTRUCCION_UNIR)
try:
    nl.resumir_local("hola", conf, lambda c: {"message": {"content": "  "}})
    ver("respuesta vacia es error", False)
except nl.ErrorNotas:
    ver("respuesta vacia es error", True)

# procesar: el audio se borra solo si hay transcripcion
tmp = tempfile.mkdtemp(dir=os.environ.get("KODAMA_PRUEBAS_TMP") or None)
try:
    carpeta = os.path.join(tmp, "en-curso-x")
    os.makedirs(carpeta)
    for n in ("microfono", "sistema"):
        with wave.open(os.path.join(carpeta, n + ".wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(bytes(3200))
    json.dump({"fecha": "2026-11-06 10:00", "microfono": {"pico": 100, "error": None}, "sistema": {"pico": 0, "error": None}}, open(os.path.join(carpeta, "meta.json"), "w", encoding="utf-8"))
    conf2 = dict(conf, resumen="no", transcriptor=tmp)
    llamados = []
    original = nl.transcribir

    def malo(wav, c, correr=None):
        raise nl.ErrorNotas("x")

    nl.transcribir = malo
    try:
        nl.procesar(carpeta, conf2, avisar=lambda x: None)
        ver("transcripcion fallida levanta error", False)
    except nl.ErrorNotas:
        ver("transcripcion fallida levanta error", True)
    ver("si falla, el audio se queda", os.path.exists(os.path.join(carpeta, "microfono.wav")))

    def bueno(wav, c, correr=None):
        llamados.append(os.path.basename(wav))
        return [{"inicio": 1, "texto": "hola"}]

    nl.transcribir = bueno
    ruta = nl.procesar(carpeta, conf2, avisar=lambda x: None)
    nl.transcribir = original
    ver("pista sin senal no se transcribe", llamados == ["microfono.wav"])
    ver("si hay transcripcion, el audio se borra", not os.path.exists(carpeta))
    texto = open(ruta, encoding="utf-8").read()
    ver("nota con transcripcion", "[00:01] Tú: hola" in texto)
    ver("nota avisa de la pista muda", "No se oyó nada por el sonido de la PC" in texto)
    ver("nombre de la nota sin dos puntos", os.path.basename(ruta) == "2026-11-06_1000.md")

    # reparar cabecera
    r = os.path.join(tmp, "roto.wav")
    with wave.open(r, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(bytes(1000))
    with open(r, "r+b") as a:
        a.seek(40)
        a.write(struct.pack("<I", 0))
    nl.reparar_wav(r)
    with wave.open(r) as w:
        ver("repara el largo del WAV", w.getnframes() == 500)

    def falso_run(args, **k):
        with open(os.path.splitext(args[2])[0] + ".json", "w", encoding="utf-8") as a:
            json.dump({"segmentos": [{"inicio": 0, "texto": "x"}]}, a)
        ver("sin internet al transcribir", k["env"]["HF_HUB_OFFLINE"] == "1")

        class R:
            returncode = 0
        return R()

    base = os.path.join(tmp, "tr")
    os.makedirs(os.path.join(base, ".venv", "Scripts"))
    open(os.path.join(base, ".venv", "Scripts", "python.exe"), "w").close()
    open(os.path.join(base, "transcribir.py"), "w").close()
    ver("lee la salida del transcriptor", nl.transcribir(os.path.join(tmp, "a.wav"), dict(conf, transcriptor=base), falso_run)[0]["texto"] == "x")
    try:
        nl.transcribir("a.wav", dict(conf, transcriptor=os.path.join(tmp, "nada")))
        ver("sin transcriptor es error", False)
    except nl.ErrorNotas:
        ver("sin transcriptor es error", True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{ok} OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
