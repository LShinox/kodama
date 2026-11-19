# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov) Chat con proveedores de IA. HTTP falso y urlopen parcheado; todo va a una carpeta temporal y el log se captura."""
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kodama_ia as ki  # noqa: E402

ok = fallos = 0
LOGS = []
ki.log = LOGS.append


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
    else:
        fallos += 1
        print("FALLA:", nombre)


class FakeHTTP:
    """Guarda cada llamada y devuelve la respuesta preparada (o lanza la excepcion dada)."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta = respuesta
        self.error = error
        self.llamadas = []

    def __call__(self, metodo, url, cabeceras, cuerpo=None, timeout=120):
        self.llamadas.append({"metodo": metodo, "url": url, "cab": dict(cabeceras), "cuerpo": cuerpo})
        if self.error is not None:
            raise self.error
        return self.respuesta


class FakeResp:
    def __init__(self, datos):
        self.datos = datos

    def read(self):
        return self.datos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


CLAVE_OPENAI = "SK_SECRETA_OPENAI"
CLAVE_ANTH = "SK_SECRETA_ANTH"

with tempfile.TemporaryDirectory() as td:
    conf = os.path.join(td, "ia.json")

    # Forma openai y cabeceras.
    ki.guardar("openai", clave=CLAVE_OPENAI, modelo="gpt-x", ruta=conf)
    f = FakeHTTP({"choices": [{"message": {"content": "hola"}}]})
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="openai", ruta=conf, http=f)
    c = f.llamadas[-1]
    ver("openai texto", r == {"ok": True, "texto": "hola", "modelo": "gpt-x"})
    ver("openai url y metodo", c["metodo"] == "POST" and c["url"] == "https://api.openai.com/v1/chat/completions")
    ver("openai bearer", c["cab"].get("Authorization") == "Bearer " + CLAVE_OPENAI)
    ver("openai cuerpo", c["cuerpo"] == {"model": "gpt-x", "messages": [{"role": "user", "content": "hi"}], "stream": False})

    # Forma anthropic y cabeceras.
    ki.guardar("anthropic", clave=CLAVE_ANTH, modelo="claude-x", ruta=conf)
    f = FakeHTTP({"content": [{"type": "text", "text": "A"}, {"type": "tool_use"}, {"type": "text", "text": "B"}]})
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="anthropic", ruta=conf, http=f)
    c = f.llamadas[-1]
    ver("anthropic concatena texto", r["ok"] and r["texto"] == "AB")
    ver("anthropic url", c["url"] == "https://api.anthropic.com/v1/messages")
    ver("anthropic cabeceras", c["cab"].get("x-api-key") == CLAVE_ANTH and c["cab"].get("anthropic-version") == "2023-06-01" and "Authorization" not in c["cab"])
    ver("anthropic cuerpo", c["cuerpo"]["max_tokens"] == 2048 and c["cuerpo"]["model"] == "claude-x")

    # Lista de modelos en los dos formatos, ordenada y sin repetidos.
    f = FakeHTTP({"data": [{"id": "z"}, {"id": "a"}, {"id": "a"}, "raro"]})
    ver("modelos openai", ki.modelos("openai", ruta=conf, http=f) == ["a", "z"])
    ver("modelos openai bearer", f.llamadas[-1]["url"] == "https://api.openai.com/v1/models" and f.llamadas[-1]["cab"].get("Authorization") == "Bearer " + CLAVE_OPENAI)
    ki.modelos("anthropic", ruta=conf, http=f)
    ver("modelos anthropic cabeceras", f.llamadas[-1]["cab"].get("x-api-key") == CLAVE_ANTH and f.llamadas[-1]["cab"].get("anthropic-version") == "2023-06-01")
    f = FakeHTTP({"data": [{"id": f"m{i:03d}"} for i in range(250)]})
    ver("modelos maximo 200", len(ki.modelos("openai", ruta=conf, http=f)) == 200)

    # Local: sin cabecera de autorizacion aunque haya clave guardada.
    ki.guardar("ollama", modelo="llama3", ruta=conf)
    f = FakeHTTP({"choices": [{"message": {"content": "local"}}]})
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="ollama", ruta=conf, http=f)
    ver("local responde", r["ok"] and r["texto"] == "local")
    ver("local sin Authorization", "Authorization" not in f.llamadas[-1]["cab"] and f.llamadas[-1]["cab"] == {})
    ver("ollama sin razonamiento", f.llamadas[-1]["cuerpo"].get("reasoning_effort") == "none")
    with_lm = FakeHTTP({"choices": [{"message": {"content": "x"}}]})
    ki.guardar("lmstudio", modelo="m", ruta=conf)
    ki.preguntar([{"role": "user", "content": "hi"}], pid="lmstudio", ruta=conf, http=with_lm)
    ver("otros locales sin ese campo", "reasoning_effort" not in with_lm.llamadas[-1]["cuerpo"])
    f = FakeHTTP({"data": []})
    ki.modelos("lmstudio", ruta=conf, http=f)
    ver("local modelos sin cabecera", f.llamadas[-1]["cab"] == {})

    # Falta la clave o el modelo: no se llama a la red.
    ki.guardar("groq", modelo="m1", ruta=conf)
    f = FakeHTTP({})
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="groq", ruta=conf, http=f)
    ver("falta clave", r == {"ok": False, "error": "falta la clave"} and f.llamadas == [])
    ki.guardar("deepseek", clave="DS_SECRETA", ruta=conf)
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="deepseek", ruta=conf, http=f)
    ver("falta modelo", r == {"ok": False, "error": "falta elegir modelo"} and f.llamadas == [])
    r = ki.preguntar([{"role": "user", "content": "hi"}], pid="deepseek", modelo="dm", ruta=conf, http=FakeHTTP({"choices": [{"message": {"content": "ok"}}]}))
    ver("modelo por parametro", r["ok"] and r["modelo"] == "dm")

    # Respuestas mal formadas.
    for nombre, pid, resp in [
        ("openai sin choices", "openai", {"foo": 1}),
        ("openai contenido no texto", "openai", {"choices": [{"message": {"content": None}}]}),
        ("anthropic content no lista", "anthropic", {"content": "x"}),
        ("anthropic sin bloques de texto", "anthropic", {"content": [{"type": "tool_use"}]}),
        ("respuesta lista", "openai", [1, 2]),
    ]:
        r = ki.preguntar([{"role": "user", "content": "hi"}], pid=pid, ruta=conf, http=FakeHTTP(resp))
        ver("rara: " + nombre, r == {"ok": False, "error": "respuesta rara"})

    # Filtro de mensajes: solo user/assistant con texto, ultimos 30, tope 60000.
    datos = [{"role": "system", "content": "x"}, {"role": "user", "content": 5}, 3]
    datos += [{"role": "user", "content": f"m{i}"} for i in range(35)]
    f = FakeHTTP({"choices": [{"message": {"content": "ok"}}]})
    ki.preguntar(datos, pid="openai", ruta=conf, http=f)
    enviados = f.llamadas[-1]["cuerpo"]["messages"]
    ver("filtra y 30 ultimos", len(enviados) == 30 and enviados[0]["content"] == "m5" and enviados[-1]["content"] == "m34")
    grandes = [{"role": "user", "content": "1" * 25000}, {"role": "assistant", "content": "2" * 25000}, {"role": "user", "content": "3" * 25000}]
    f = FakeHTTP({"choices": [{"message": {"content": "ok"}}]})
    ki.preguntar(grandes, pid="openai", ruta=conf, http=f)
    enviados = f.llamadas[-1]["cuerpo"]["messages"]
    ver("tope 60000 quita el mas viejo", len(enviados) == 2 and enviados[0]["content"] == "2" * 25000 and enviados[1]["content"] == "3" * 25000)
    r = ki.preguntar([{"role": "system", "content": "x"}], pid="openai", ruta=conf, http=FakeHTTP({}))
    ver("sin mensajes validos", r == {"ok": False, "error": "sin mensajes"})

    # Vista publica sin clave; elegido; clave vacia conserva la vieja.
    ki.elegir("openai", ruta=conf)
    v = ki.vista_publica(conf)
    ver("elegido visible", v["elegido"] == "openai" and len(v["proveedores"]) == 8)
    ver("vista sin clave", CLAVE_OPENAI not in json.dumps(v) and CLAVE_ANTH not in json.dumps(v) and all("clave" not in p for p in v["proveedores"]))
    ver("configurado por clave", next(p for p in v["proveedores"] if p["id"] == "openai")["configurado"] is True)
    ver("local sin clave configurado", next(p for p in v["proveedores"] if p["id"] == "ollama")["configurado"] is True)
    ki.guardar("openai", clave="", ruta=conf)
    ver("clave vacia conserva", ki.leer_conf(conf)["config"]["openai"]["clave"] == CLAVE_OPENAI)
    ki.guardar("openai", modelo="gpt-y", ruta=conf)
    ver("modelo se guarda sin tocar clave", ki.leer_conf(conf)["config"]["openai"] == {"clave": CLAVE_OPENAI, "modelo": "gpt-y"})
    try:
        ki.guardar("inventado", clave="x", ruta=conf)
        ver("pid desconocido falla", False)
    except ValueError:
        ver("pid desconocido falla", True)
    ver("conf rota = vacia", ki.leer_conf(os.path.join(td, "no.json"))["elegido"] is None)

    # ErrorIA: solo codigo o nombre de excepcion, aunque la excepcion real lleve URL y clave.
    realurl = "https://api.openai.com/v1/models?key=" + CLAVE_OPENAI
    original = urllib.request.urlopen
    capturas = {}

    def abre_http(err):
        def falso(req, timeout=None, **kw):
            capturas["req"], capturas["kw"] = req, kw
            raise err
        urllib.request.urlopen = falso

    try:
        abre_http(urllib.error.HTTPError(realurl, 401, "Unauthorized " + CLAVE_OPENAI, {}, None))
        try:
            ki.pedir_json("GET", realurl, {"Authorization": "Bearer " + CLAVE_OPENAI})
            ver("http error lanza", False)
        except ki.ErrorIA as e:
            ver("HTTP error texto", str(e) == "HTTP 401" and CLAVE_OPENAI not in str(e) and "http" not in str(e))
        ver("sin contexto SSL especial", "context" not in capturas["kw"])
        ver("user agent kodama", capturas["req"].get_header("User-agent") == "kodama")

        abre_http(urllib.error.URLError("no route to " + realurl + " " + CLAVE_OPENAI))
        try:
            ki.pedir_json("GET", realurl, {})
            ver("url error lanza", False)
        except ki.ErrorIA as e:
            ver("URLError texto", str(e) == "URLError" and CLAVE_OPENAI not in str(e))

        abre_http(RuntimeError("boom " + CLAVE_OPENAI))
        try:
            ki.pedir_json("GET", realurl, {})
            ver("excepcion lanza", False)
        except ki.ErrorIA as e:
            ver("excepcion texto", str(e) == "RuntimeError" and CLAVE_OPENAI not in str(e))

        urllib.request.urlopen = lambda req, timeout=None, **kw: FakeResp(b'{"ok": 1}')
        ver("pedir_json exito", ki.pedir_json("POST", realurl, {}, {"a": 1}) == {"ok": 1})

        # preguntar con error de red: ok False, sin clave en la salida ni en el log.
        LOGS.clear()
        ki.guardar("openai", modelo="gpt-y", ruta=conf)
        abre_http(urllib.error.HTTPError(realurl, 500, "x", {}, None))
        r = ki.preguntar([{"role": "user", "content": "hi"}], ruta=conf)
        ver("preguntar error HTTP", r == {"ok": False, "error": "HTTP 500"})
        ver("sin clave en salida ni log", CLAVE_OPENAI not in json.dumps(r) and not any(CLAVE_OPENAI in x for x in LOGS))
    finally:
        urllib.request.urlopen = original

print(f"{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
