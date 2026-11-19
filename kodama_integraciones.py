# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Servicios conectados: consulta, deduplicacion y avisos locales."""
import datetime
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request

try:
    from kodama_nucleo import BASE, log
except ImportError:
    BASE = tempfile.gettempdir()
    def log(*args):
        pass
import kodama_secreto

CONF = os.path.join(BASE, "integraciones.json")
VISTOS = os.path.join(BASE, "integraciones_vistos.json")
EVENTOS = os.path.join(BASE, "integraciones_eventos.json")
PROVEEDORES = {
    "github": {"nombre": "GitHub", "campos": ["token"], "cada": 120},
    "vercel": {"nombre": "Vercel", "campos": ["token"], "cada": 120},
    "stripe": {"nombre": "Stripe", "campos": ["clave"], "cada": 120},
    "resend": {"nombre": "Resend", "campos": ["clave"], "cada": 300},
    "n8n": {"nombre": "n8n", "campos": ["url", "clave"], "cada": 120},
    "notion": {"nombre": "Notion", "campos": ["token"], "cada": 300},
    "calcom": {"nombre": "Cal.com", "campos": ["clave"], "cada": 300},
}
ERRORES, ULTIMO = {}, {}


class ErrorHttp(Exception):
    def __init__(self, codigo):
        self.codigo = int(codigo)
        super().__init__(f"HTTP {self.codigo}")


def pedir(metodo, url, cabeceras, cuerpo=None, timeout=20):
    h = dict(cabeceras)
    h["User-Agent"] = "kodama"
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(url, data=datos, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ErrorHttp(e.code) from None


def _leer(ruta, defecto):
    """Archivos sin secretos (eventos, vistos): JSON plano."""
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, type(defecto)) else defecto
    except (OSError, ValueError):
        return defecto


def _guardar(ruta, datos):
    """Archivos sin secretos (eventos, vistos): JSON plano."""
    ruta = os.fspath(ruta)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(ruta + ".tmp", ruta)


def _guardar_conf(ruta, datos):
    """integraciones.json (con tokens): cifrado con kodama_secreto."""
    kodama_secreto.guardar(ruta, datos)


def leer_conf(ruta=None):
    d = kodama_secreto.leer(ruta or CONF, {})
    return d if isinstance(d, dict) else {}


def guardar_proveedor(pid, activo=None, campos=None, ruta=None):
    if pid in PROVEEDORES:
        d = leer_conf(ruta)
        c = d.get(pid, {})
        c = dict(c) if isinstance(c, dict) else {}
        if isinstance(activo, bool):
            c["activo"] = activo
        for k, v in (campos.items() if isinstance(campos, dict) else []):
            if k not in PROVEEDORES[pid]["campos"] or not isinstance(v, str):
                continue
            v = v.strip()[:500]
            if v and (k != "url" or v.startswith(("http://", "https://"))):
                c[k] = v
        d[pid] = c
        _guardar_conf(ruta or CONF, d)
    return vista_publica(ruta)


def quitar_proveedor(pid, ruta=None):
    d = leer_conf(ruta)
    if pid in d:
        del d[pid]
        _guardar_conf(ruta or CONF, d)


def vista_publica(ruta=None):
    d, salida = leer_conf(ruta), []
    for pid, p in PROVEEDORES.items():
        c = d.get(pid, {})
        c = c if isinstance(c, dict) else {}
        salida.append(dict(id=pid, nombre=p["nombre"], activo=c.get("activo") is True,
                           configurado=all(isinstance(c.get(k), str) and c[k].strip() for k in p["campos"]),
                           campos=list(p["campos"])))
    return salida


def _ts(v):
    try:
        d = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d.replace(tzinfo=d.tzinfo or datetime.timezone.utc).timestamp()
    except (ValueError, TypeError, AttributeError, OverflowError):
        return 0.0


def _evento(i, titulo, texto, url, ts):
    return dict(id=str(i), titulo=str(titulo), texto=str(texto), url=str(url or ""), ts=float(ts))


def _lista(datos, clave=None):
    datos = datos.get(clave, []) if clave and isinstance(datos, dict) else datos
    return datos if isinstance(datos, list) else []


def _leer_servicio(pid, conf, http):
    clave = conf.get("token", conf.get("clave", ""))
    h = {"Authorization": "Bearer " + clave}
    urls = {
        "github": "https://api.github.com/notifications?per_page=20",
        "vercel": "https://api.vercel.com/v6/deployments?limit=10",
        "stripe": "https://api.stripe.com/v1/events?limit=20",
        "resend": "https://api.resend.com/emails?limit=20",
        "n8n": conf.get("url", "").rstrip("/") + "/api/v1/executions?status=error&limit=10",
        "notion": "https://api.notion.com/v1/search",
        "calcom": "https://api.cal.com/v2/bookings?status=upcoming&take=10",
    }
    cuerpo = None
    if pid == "github":
        h.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    if pid == "n8n":
        h = {"X-N8N-API-KEY": clave}
    if pid == "notion":
        h.update({"Notion-Version": "2022-06-28", "Content-Type": "application/json"})
        cuerpo = {"page_size": 10, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
    if pid == "calcom":
        h["cal-api-version"] = "2024-08-13"
    datos = http("POST" if cuerpo else "GET", urls[pid], h, cuerpo)
    campo = {"github": None, "vercel": "deployments", "notion": "results"}.get(pid, "data")
    salida = []
    for x in _lista(datos, campo):
        try:
            if pid == "github":
                repo = x["repository"]["full_name"]
                e = _evento(str(x["id"]) + x["updated_at"], repo, x["subject"]["title"], "https://github.com/" + repo, _ts(x["updated_at"]))
            elif pid == "vercel":
                estado = x.get("state", x.get("readyState"))
                if estado not in ("READY", "ERROR"):
                    continue
                e = _evento(str(x["uid"]) + estado, x["name"], "Despliegue listo" if estado == "READY" else "Despliegue con error", "https://" + x["url"] if x.get("url") else "", float(x["createdAt"]) / 1000)
            elif pid == "stripe":
                textos = {"charge.succeeded": "Pago recibido", "charge.failed": "Pago fallido", "charge.refunded": "Reembolso", "charge.dispute.created": "Disputa", "invoice.payment_failed": "Factura sin pagar"}
                if x.get("type") not in textos:
                    continue
                texto = textos[x["type"]]
                obj = x.get("data", {}).get("object", {})
                importe = obj.get("amount_due" if x["type"] == "invoice.payment_failed" else "amount")
                if importe is not None and obj.get("currency"):
                    texto += f" · {float(importe) / 100:g} {obj['currency'].upper()}"
                e = _evento(x["id"], "Stripe", texto, "", x["created"])
            elif pid == "resend":
                textos = {"bounced": "Rebotó", "complained": "Marcado como spam", "failed": "Falló"}
                if x.get("last_event") not in textos:
                    continue
                e = _evento(str(x["id"]) + x["last_event"], "Resend", textos[x["last_event"]] + ": " + x["subject"], "", _ts(x["created_at"]))
            elif pid == "n8n":
                e = _evento(x["id"], "n8n", "Flujo con error: " + str(x["workflowId"]), "", _ts(x["startedAt"]))
            elif pid == "notion":
                titulo = "Página editada"
                for p in x.get("properties", {}).values():
                    if isinstance(p, dict) and p.get("type") == "title" and p.get("title"):
                        titulo = p["title"][0].get("plain_text") or titulo
                        break
                e = _evento(x["id"] + x["last_edited_time"], "Notion", titulo, x["url"], _ts(x["last_edited_time"]))
            else:
                e = _evento(x["uid"], "Cal.com", "Reserva nueva: " + x["title"], "", _ts(x["start"]))
            # Un servicio tampoco debe reflejar la credencial en un aviso.
            for k in ("id", "titulo", "texto", "url"):
                if clave:
                    e[k] = e[k].replace(clave, "[oculto]")
            salida.append(e)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError):
            continue
    return salida


def leer_github(conf, http=pedir):
    return _leer_servicio("github", conf, http)


def leer_vercel(conf, http=pedir):
    return _leer_servicio("vercel", conf, http)


def leer_stripe(conf, http=pedir):
    return _leer_servicio("stripe", conf, http)


def leer_resend(conf, http=pedir):
    return _leer_servicio("resend", conf, http)


def leer_n8n(conf, http=pedir):
    return _leer_servicio("n8n", conf, http)


def leer_notion(conf, http=pedir):
    return _leer_servicio("notion", conf, http)


def leer_calcom(conf, http=pedir):
    return _leer_servicio("calcom", conf, http)


def nuevos(pid, eventos, vistos):
    nuevo = {k: list(v) for k, v in vistos.items()}
    ids = list(nuevo.get(pid, []))
    conocidos, salida = set(ids), []
    for e in sorted(eventos, key=lambda e: e["ts"]):
        if e["id"] not in conocidos:
            if pid in vistos:
                salida.append(dict(e))
            ids.append(e["id"])
            conocidos.add(e["id"])
    nuevo[pid] = ids[-300:]
    return salida, nuevo


def agregar_eventos(lista, ruta=None):
    ruta = ruta or EVENTOS
    _guardar(ruta, (list(reversed(lista)) + _leer(ruta, []))[:200])


def ultimos(n=30, ruta=None):
    return _leer(ruta or EVENTOS, [])[:max(0, n)]


def _url_segura(u):
    return u if isinstance(u, str) and u.startswith(("http://", "https://")) else ""


def recibir_webhook(pid, datos, ruta=None):
    if not isinstance(datos, dict):
        return None
    mensaje = datos.get("message")
    mensaje = mensaje if isinstance(mensaje, dict) else {}
    texto = datos.get("texto") or mensaje.get("text") or mensaje.get("body") or datos.get("body")
    if not isinstance(texto, str) or not texto.strip():
        return None
    titulo = datos.get("titulo") or datos.get("pushname") or datos.get("sender") or datos.get("from") or "WhatsApp"
    huella = hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    e = _evento(huella, str(titulo)[:80], texto[:300], _url_segura(datos.get("url")), time.time())
    e["proveedor"] = pid
    agregar_eventos([e], ruta)
    return e


def _error(pid, e):
    return f"integracion {pid}: {type(e).__name__}" + (f" {e.codigo}" if isinstance(e, ErrorHttp) else "")


def revisar_una_vez(avisar, ahora=None, conf_ruta=None, vistos_ruta=None, eventos_ruta=None, http=None, ultimo=None):
    ahora = time.time() if ahora is None else ahora
    ultimo = ULTIMO if ultimo is None else ultimo
    conf = leer_conf(conf_ruta)
    for p in vista_publica(conf_ruta):
        pid = p["id"]
        if not p["activo"] or not p["configurado"]:
            continue
        if pid in ultimo and ahora - ultimo[pid] < PROVEEDORES[pid]["cada"]:
            continue
        ultimo[pid] = ahora
        try:
            eventos = globals()["leer_" + pid](conf[pid], http or pedir)
            salen, vistos = nuevos(pid, eventos, _leer(vistos_ruta or VISTOS, {}))
            _guardar(vistos_ruta or VISTOS, vistos)
            for e in salen:
                e["proveedor"] = pid
            agregar_eventos(salen, eventos_ruta)
            for e in salen[:5]:
                avisar(e)
            ERRORES.pop(pid, None)
        except Exception as e:
            ERRORES[pid] = _error(pid, e)
            log(ERRORES[pid])


def vigilar(avisar):
    import kodama_extras   # (18-nov) apagado en kodama_extras = no consulta (no hace falta reiniciar)
    time.sleep(45)
    while True:
        if not kodama_extras.activo("integraciones"):
            time.sleep(30)
            continue
        try:
            revisar_una_vez(avisar)
        except Exception as e:
            log(f"integraciones: {type(e).__name__}")
        time.sleep(30)


def probar(pid, ruta=None, http=None):
    if pid not in PROVEEDORES:
        return {"ok": False, "error": "Proveedor desconocido"}
    if not next(p for p in vista_publica(ruta) if p["id"] == pid)["configurado"]:
        return {"ok": False, "error": "Faltan campos"}
    try:
        return {"ok": True, "n": len(globals()["leer_" + pid](leer_conf(ruta)[pid], http or pedir))}
    except Exception as e:
        return {"ok": False, "error": _error(pid, e)}
