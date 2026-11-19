import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import marco  # noqa: E402

resultados = []


def check(nombre, ok):
    resultados.append(bool(ok))
    print(("OK    " if ok else "FALLA ") + nombre)


def escribir(ruta, datos=b"x"):
    with open(ruta, "wb") as f:
        f.write(datos)


tmp = tempfile.mkdtemp(dir=BASE, prefix="tmp_prueba_")
srv = None
try:
    fotos = os.path.join(tmp, "fotos")
    puente = os.path.join(tmp, "puente")
    conf = os.path.join(tmp, "conf")
    latido = os.path.join(tmp, "latido")
    for d in (fotos, puente, conf):
        os.makedirs(d)
    escribir(os.path.join(fotos, "a.jpg"))
    escribir(os.path.join(fotos, "b.jpg"))
    escribir(os.path.join(fotos, "nota.txt"))

    srv = marco.crear_servidor(8791, carpeta=conf, fotos=fotos, puente=puente, latido=latido)
    clave = srv.cfg["clave"]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:8791"

    def pedir(ruta, con_clave=True):
        url = base + ruta
        if con_clave:
            url += ("&" if "?" in ruta else "?") + "k=" + clave
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    # a) sin clave -> 403
    st, _ = pedir("/", con_clave=False)
    check("a) sin clave -> 403", st == 403)

    # b) con clave -> 200 y HTML sin JS prohibido
    st, cuerpo = pedir("/")
    html = cuerpo.decode("utf-8", "replace")
    limpio = not any(x in html for x in ["=>", "let ", "const ", "fetch(", "`"])
    check("b) con clave -> 200 y HTML ES5 sin => let const fetch backtick", st == 200 and limpio)

    # c) /api/fotos lista solo imagenes
    st, cuerpo = pedir("/api/fotos")
    lista = json.loads(cuerpo.decode("utf-8")).get("fotos") if st == 200 else None
    check("c) /api/fotos lista solo .jpg", st == 200 and lista == ["a.jpg", "b.jpg"])

    # d) traversal -> 403
    st, _ = pedir("/foto/../marco.json")
    check("d) /foto/../marco.json -> 403", st == 403)

    # e) 2 archivos .esperando -> esperan 2 (latido fresco)
    escribir(os.path.join(puente, "uno.esperando"))
    escribir(os.path.join(puente, "dos.esperando"))
    escribir(os.path.join(puente, "otro.txt"))
    escribir(latido)
    st, cuerpo = pedir("/api/estado")
    dat = json.loads(cuerpo.decode("utf-8")) if st == 200 else {}
    check("e) /api/estado con 2 .esperando -> esperan 2", dat.get("esperan") == 2)

    # f) latido viejo -> kodama_vivo false
    viejo = time.time() - 500
    os.utime(latido, (viejo, viejo))
    st, cuerpo = pedir("/api/estado")
    dat = json.loads(cuerpo.decode("utf-8")) if st == 200 else {}
    check("f) latido viejo -> kodama_vivo false", dat.get("kodama_vivo") is False)
finally:
    if srv is not None:
        srv.shutdown()
        srv.server_close()
    shutil.rmtree(tmp, ignore_errors=True)

total = len(resultados)
print("%d/%d OK" % (sum(resultados), total))
