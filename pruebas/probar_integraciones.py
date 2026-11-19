# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Pruebas sin red ni estado real; el nucleo se sustituye antes de importar."""
import copy
import io
import json
import os
import sys
import tempfile
import types
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
    else:
        fallos += 1
        print("FALLA:", nombre)


def sin_red(*args, **kwargs):
    raise AssertionError("Red prohibida")


urllib.request.urlopen = sin_red
with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(__file__))) as td:
    registros = []
    nucleo = types.ModuleType("kodama_nucleo")
    nucleo.BASE, nucleo.log = td, registros.append
    sys.modules["kodama_nucleo"] = nucleo
    import kodama_integraciones as k

    fecha = "2026-11-05T12:00:00Z"
    secreto = "TOKEN_PRIVADO_987654"
    conf = dict(token=secreto, clave=secreto, url="https://n8n.example/")
    ejemplos = {
        "github": [{"id": "g1", "updated_at": fecha, "repository": {"full_name": "equipo/app"}, "subject": {"title": "Cambio"}}],
        "vercel": {"deployments": [{"uid": "v1", "name": "app", "state": "READY", "url": "app.example", "createdAt": 100000}]},
        "stripe": {"data": [{"id": "s1", "type": "charge.succeeded", "created": 100, "data": {"object": {"amount": 1250, "currency": "usd"}}}]},
        "resend": {"data": [{"id": "r1", "last_event": "bounced", "subject": "Hola", "created_at": fecha}]},
        "n8n": {"data": [{"id": 23, "workflowId": "flujo1", "startedAt": fecha}]},
        "notion": {"results": [{"id": "p1", "last_edited_time": fecha, "url": "https://notion.example/p1", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Pagina"}]}}}]},
        "calcom": {"data": [{"uid": "b1", "title": "Consulta", "start": fecha}]},
    }
    textos = ["Cambio", "Despliegue listo", "Pago recibido · 12.5 USD", "Rebotó: Hola", "Flujo con error: flujo1", "Pagina", "Reserva nueva: Consulta"]
    llamadas = []

    def falso(pid, datos=None):
        def http(metodo, url, cabeceras, cuerpo=None, timeout=20):
            llamadas.append((metodo, url, cabeceras, cuerpo))
            return copy.deepcopy(ejemplos[pid] if datos is None else datos)
        return http

    for pid, texto in zip(k.PROVEEDORES, textos):
        lector = getattr(k, "leer_" + pid)
        es = lector(conf, falso(pid))
        ver(pid + " normaliza", len(es) == 1 and es[0]["texto"] == texto and isinstance(es[0]["ts"], float))
        ver(pid + " sin secreto", secreto not in json.dumps(es))
        envoltura = None if pid == "github" else "deployments" if pid == "vercel" else "results" if pid == "notion" else "data"
        mal = [{} , None] if envoltura is None else {envoltura: [{}, None]}
        ver(pid + " faltan claves", lector(conf, falso(pid, mal)) == [])
        ver(pid + " respuesta vacia", lector(conf, falso(pid, {})) == [])
    ver("github cabeceras", llamadas[0][2]["X-GitHub-Api-Version"] == "2022-11-28" and llamadas[0][2]["Accept"] == "application/vnd.github+json")
    k.leer_notion(conf, falso("notion"))
    ver("notion peticion", llamadas[-1][0] == "POST" and llamadas[-1][3] == {"page_size": 10, "sort": {"direction": "descending", "timestamp": "last_edited_time"}})
    k.leer_n8n(conf, falso("n8n"))
    ver("n8n peticion", llamadas[-1][1] == "https://n8n.example/api/v1/executions?status=error&limit=10" and llamadas[-1][2] == {"X-N8N-API-KEY": secreto})
    k.leer_calcom(conf, falso("calcom"))
    ver("cal version", llamadas[-1][2]["cal-api-version"] == "2024-08-13")
    for estado in ("ERROR", "BUILDING"):
        d = copy.deepcopy(ejemplos["vercel"])
        d["deployments"][0].pop("state")
        d["deployments"][0]["readyState"] = estado
        es = k.leer_vercel(conf, falso("vercel", d))
        ver("vercel " + estado, (len(es) == 1 and es[0]["texto"] == "Despliegue con error") if estado == "ERROR" else es == [])
    for tipo, texto in [("charge.failed", "Pago fallido"), ("charge.refunded", "Reembolso"), ("charge.dispute.created", "Disputa"), ("invoice.payment_failed", "Factura sin pagar"), ("customer.created", "")]:
        d = {"data": [{"id": "s2", "type": tipo, "created": 2, "data": {"object": {"amount_due": 1500, "currency": "eur"}}}]}
        es = k.leer_stripe(conf, falso("stripe", d))
        ver("stripe " + tipo, es[0]["texto"].startswith(texto) if texto else es == [])
        if tipo == "invoice.payment_failed":
            ver("importe factura", es[0]["texto"] == "Factura sin pagar · 15 EUR")
    for estado, texto in [("complained", "Marcado como spam"), ("failed", "Falló"), ("delivered", "")]:
        d = {"data": [{"id": "r2", "last_event": estado, "subject": "Hola", "created_at": "rota"}]}
        es = k.leer_resend(conf, falso("resend", d))
        ver("resend " + estado, es[0]["texto"] == texto + ": Hola" and es[0]["ts"] == 0 if texto else es == [])
    d = copy.deepcopy(ejemplos["notion"])
    d["results"][0]["properties"] = {}
    ver("notion sin titulo", k.leer_notion(conf, falso("notion", d))[0]["texto"] == "Página editada")

    r, v, e = k.CONF, k.VISTOS, k.EVENTOS
    ver("conf ausente", k.leer_conf() == {})
    with open(r, "w", encoding="utf-8") as f:
        f.write("{roto")
    ver("conf rota", k.leer_conf() == {})
    k.guardar_proveedor("github", True, {"token": " " + secreto + " ", "ajeno": "x"})
    ver("publica", secreto not in json.dumps(k.vista_publica()) and k.vista_publica()[0]["configurado"])
    ver("orden", [p["id"] for p in k.vista_publica()] == list(k.PROVEEDORES))
    k.guardar_proveedor("github", campos={"token": " "})
    ver("vacio conserva", k.leer_conf()["github"]["token"] == secreto and "ajeno" not in k.leer_conf()["github"])
    k.guardar_proveedor("inventado", True, {"token": secreto})
    ver("pid desconocido", "inventado" not in k.leer_conf())
    k.guardar_proveedor("n8n", True, {"url": "ftp://malo", "clave": secreto})
    ver("url invalida", "url" not in k.leer_conf()["n8n"])
    k.guardar_proveedor("n8n", campos={"url": "https://n8n.example"})
    k.guardar_proveedor("n8n", campos={"url": "malo"})
    ver("url anterior conserva", k.leer_conf()["n8n"]["url"] == "https://n8n.example")
    k.quitar_proveedor("n8n")
    ver("quitar", "n8n" not in k.leer_conf())
    k.guardar_proveedor("resend", campos={"clave": "a" * 600})
    ver("limite campo", len(k.leer_conf()["resend"]["clave"]) == 500)

    avisos, ultimo = [], {}
    def ronda(t, http):
        k.revisar_una_vez(avisos.append, t, r, v, e, http, ultimo)

    ronda(0, falso("github"))
    ver("primera no avisa", avisos == [] and k._leer(v, {})["github"] == ["g1" + fecha])
    ejemplos["github"][0]["id"] = "g2"
    antes = len(llamadas)
    ronda(119, falso("github"))
    ver("cada respetado", len(llamadas) == antes)
    ronda(120, falso("github"))
    ver("nuevo avisa", len(avisos) == 1 and avisos[0]["proveedor"] == "github")
    ronda(240, falso("github"))
    ver("no repite", len(avisos) == 1)
    base = ejemplos["github"][0]
    ejemplos["github"] = [dict(base, id="extra" + str(i)) for i in range(9)]
    ronda(360, falso("github"))
    ver("maximo cinco", len(avisos) == 6)
    ver("historial todos", len(k.ultimos()) == 10)
    eventos = [dict(id=str(i), titulo="t", texto="x", url="", ts=float(i)) for i in range(350)]
    previo = {"github": []}
    sal, vistos = k.nuevos("github", eventos, previo)
    ver("300 y puro", len(vistos["github"]) == 300 and vistos["github"][-1] == "349" and previo == {"github": []})
    ver("dedup lote", len(k.nuevos("github", eventos[:1] * 2, previo)[0]) == 1)
    ver("primer lote cap", k.nuevos("github", eventos, {})[0] == [] and len(k.nuevos("github", eventos, {})[1]["github"]) == 300)

    k.guardar_proveedor("vercel", True, {"token": secreto})
    vistos["vercel"] = []
    k._guardar(v, vistos)
    def falla(metodo, url, cabeceras, cuerpo=None):
        if "github" in url:
            raise ValueError(secreto)
        return ejemplos["vercel"]
    ronda(480, falla)
    ver("aisla fallo", avisos[-1]["proveedor"] == "vercel")
    ver("error sin secreto", secreto not in json.dumps([registros, k.ERRORES]) and k.ERRORES["github"] == "integracion github: ValueError")
    ver("probar seguro", secreto not in json.dumps(k.probar("github", http=falla)))
    ver("probar ok", k.probar("vercel", http=falso("vercel")) == {"ok": True, "n": 1})
    def bien(metodo, url, cabeceras, cuerpo=None):
        return ejemplos["github"] if "github" in url else ejemplos["vercel"]
    ronda(600, bien)
    ver("limpia error", "github" not in k.ERRORES)

    formas = [(dict(titulo="Hola", texto="Texto", url="https://example.test"), "Hola", "Texto"),
              (dict(sender="Ana", message={"text": "Uno"}), "Ana", "Uno"),
              ({"from": "Luis", "message": {"body": "Dos"}}, "Luis", "Dos"),
              (dict(pushname="Eva", body="Tres"), "Eva", "Tres"),
              (dict(body="Cuatro"), "WhatsApp", "Cuatro")]
    for datos, titulo, texto in formas:
        ev = k.recibir_webhook("wa", datos)
        ver("webhook " + titulo, ev["titulo"] == titulo and ev["texto"] == texto and k.ultimos(1)[0] == ev)
        ver("hash estable " + titulo, ev["id"] == k.recibir_webhook("wa", datos)["id"])
    ev = k.recibir_webhook("wa", dict(titulo="x" * 100, texto="y" * 400))
    ver("trunca", len(ev["titulo"]) == 80 and len(ev["texto"]) == 300)
    for datos in ({}, {"body": " "}, {"message": {}}, None):
        ver("sin texto", k.recibir_webhook("wa", datos) is None)
    k.agregar_eventos([dict(x, proveedor="test") for x in eventos])
    ver("200 eventos orden", len(k.ultimos(500)) == 200 and k.ultimos(1)[0]["id"] == "349")
    ver("ErrorHttp seguro", str(k.ErrorHttp(401)) == "HTTP 401" and secreto not in str(k.ErrorHttp(401)))
    peticiones = []
    def abrir(req, timeout):
        peticiones.append((req, timeout))
        return io.BytesIO(b'{"ok": true}')
    urllib.request.urlopen = abrir
    ver("pedir json", k.pedir("POST", "https://example.test", {}, {"a": 1}) == {"ok": True})
    ver("pedir agente cuerpo", peticiones[0][0].get_header("User-agent") == "kodama" and json.loads(peticiones[0][0].data) == {"a": 1} and peticiones[0][1] == 20)
    def error_http(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, secreto, {"Token": secreto}, None)
    urllib.request.urlopen = error_http
    try:
        k.pedir("GET", "https://example.test?token=" + secreto, {"Authorization": secreto})
        ver("captura HTTP", False)
    except k.ErrorHttp as ex:
        ver("captura HTTP", ex.codigo == 403 and str(ex) == "HTTP 403" and ex.__suppress_context__)
    urllib.request.urlopen = sin_red
    ver("sin temporales pendientes", not any(n.endswith(".tmp") for n in os.listdir(td)))

print(f"{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
