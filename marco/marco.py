#!/usr/bin/env python3
# Marco: marco de fotos para iPad viejo (Safari 9). Solo biblioteca estandar.
import argparse
import datetime
import hmac
import json
import os
import secrets
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

CARPETA = os.path.dirname(os.path.abspath(__file__))
FOTOS_DEF = os.path.join(os.path.expanduser("~"), "Pictures", "Marco")
PUENTE_DEF = os.path.join(os.path.dirname(CARPETA), "estado", "puente")   # (19-nov) relativo a la carpeta de Kodama, sin ruta personal
LATIDO_DEF = os.path.join(os.path.dirname(CARPETA), "estado", "latido")
EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Marco</title>
<style>
html, body { margin: 0; padding: 0; width: 100%; height: 100%; background: #000; overflow: hidden; }
body { font-family: Helvetica, Arial, sans-serif; color: #fff; }
.capa { position: absolute; left: 0; top: 0; width: 100%; height: 100%; background-color: #000; background-repeat: no-repeat; background-position: center center; background-size: contain; opacity: 0; -webkit-transition: opacity 2s ease-in-out; transition: opacity 2s ease-in-out; }
.capa.on { opacity: 1; }
#franja { position: absolute; left: 0; top: 0; width: 100%; height: 96px; background: rgba(0, 0, 0, 0.55); z-index: 5; }
#hora { position: absolute; left: 24px; top: 8px; font-size: 64px; line-height: 80px; font-weight: bold; }
#estado { position: absolute; right: 24px; top: 34px; font-size: 26px; line-height: 30px; text-align: right; }
#vacio { position: absolute; left: 0; top: 45%; width: 100%; text-align: center; font-size: 28px; display: none; z-index: 4; }
</style>
</head>
<body>
<div id="capa1" class="capa"></div>
<div id="capa2" class="capa"></div>
<div id="vacio">Agrega fotos a Imágenes\Marco en la laptop</div>
<div id="franja"><span id="hora">--:--</span><span id="estado">Kodama</span></div>
<script>
var K = '';
var fotos = [];
var indice = -1;
var activa = 0;
var capas = [document.getElementById('capa1'), document.getElementById('capa2')];
var timerFotos = null;

(function () {
  var m = /[?&]k=([^&]*)/.exec(window.location.search);
  K = m ? decodeURIComponent(m[1]) : '';
})();

function kq() {
  return 'k=' + encodeURIComponent(K);
}

function pedir(ruta, alRecibir) {
  var x = new XMLHttpRequest();
  x.open('GET', ruta, true);
  x.onreadystatechange = function () {
    var datos = null;
    if (x.readyState === 4 && x.status === 200) {
      try { datos = JSON.parse(x.responseText); } catch (e) { datos = null; }
      if (datos) { alRecibir(datos); }
    }
  };
  x.send(null);
}

function mostrarFoto(n) {
  if (fotos.length === 0) { return; }
  indice = n % fotos.length;
  var nueva = (activa === 0) ? 1 : 0;
  capas[nueva].style.backgroundImage = 'url("/foto/' + encodeURIComponent(fotos[indice]) + '?' + kq() + '")';
  capas[nueva].className = 'capa on';
  capas[activa].className = 'capa';
  activa = nueva;
}

function pedirFotos() {
  pedir('/api/fotos?' + kq(), function (d) {
    fotos = d.fotos || [];
    if (fotos.length === 0) {
      document.getElementById('vacio').style.display = 'block';
      return;
    }
    document.getElementById('vacio').style.display = 'none';
    if (indice < 0) { mostrarFoto(0); }
    if (timerFotos === null) {
      timerFotos = setInterval(function () { mostrarFoto(indice + 1); }, 15000);
    }
  });
}

function pedirEstado() {
  pedir('/api/estado?' + kq(), function (d) {
    var txt;
    if (!d.kodama_vivo) { txt = 'Kodama: sin conexión'; }
    else if (d.esperan > 0) { txt = 'Kodama: ' + d.esperan + ' chats te esperan'; }
    else { txt = 'Kodama: nada pendiente'; }
    document.getElementById('estado').textContent = txt;
    document.getElementById('hora').textContent = d.hora;
  });
}

pedirFotos();
pedirEstado();
setInterval(pedirEstado, 30000);
setInterval(pedirFotos, 300000);
</script>
</body>
</html>
"""


def cargar_clave(carpeta):
    ruta = os.path.join(carpeta, "marco.json")
    if os.path.isfile(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)["clave"]
    clave = secrets.token_urlsafe(12)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"clave": clave}, f)
    return clave


def listar_fotos(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    nombres = []
    for n in os.listdir(carpeta):
        ruta = os.path.join(carpeta, n)
        if os.path.splitext(n)[1].lower() in EXT and os.path.isfile(ruta):
            nombres.append(n)
    return sorted(nombres)


def contar_esperando(carpeta):
    if not os.path.isdir(carpeta):
        return 0
    return sum(
        1 for n in os.listdir(carpeta)
        if n.endswith(".esperando") and os.path.isfile(os.path.join(carpeta, n))
    )


def kodama_vivo(latido):
    return os.path.isfile(latido) and (time.time() - os.path.getmtime(latido)) < 120


class Manejador(BaseHTTPRequestHandler):
    server_version = "Marco"
    sys_version = ""

    def log_message(self, fmt, *args):
        # No se registran URLs: llevan la clave.
        pass

    def _respond(self, code, body, ctype, extra=None, no_store=False):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if no_store:
            self.send_header("Cache-Control", "no-store")
        for nombre, valor in (extra or []):
            self.send_header(nombre, valor)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._respond(code, json.dumps(obj), "application/json; charset=utf-8", extra, no_store=True)

    def _cookie(self, nombre):
        for parte in self.headers.get("Cookie", "").split(";"):
            if "=" in parte:
                n, v = parte.strip().split("=", 1)
                if n == nombre:
                    return v
        return ""

    def do_GET(self):
        try:
            self._manejar()
        except Exception:
            try:
                self._respond(500, "Error", "text/plain; charset=utf-8")
            except Exception:
                pass

    def _manejar(self):
        cfg = self.server.cfg
        clave = cfg["clave"].encode("utf-8")
        url = urlparse(self.path)
        p = url.path
        k_url = parse_qs(url.query).get("k", [""])[0].encode("utf-8")
        k_cookie = self._cookie("k").encode("utf-8")
        extra = []
        if k_url and hmac.compare_digest(k_url, clave):
            extra.append(("Set-Cookie", "k=%s; Path=/; HttpOnly" % cfg["clave"]))
        elif k_cookie and hmac.compare_digest(k_cookie, clave):
            pass
        else:
            return self._respond(403, "Prohibido", "text/plain; charset=utf-8")

        if p == "/":
            return self._respond(200, HTML_PAGE, "text/html; charset=utf-8", extra)

        if p == "/api/fotos":
            return self._json(200, {"fotos": listar_fotos(cfg["fotos"])}, extra)

        if p == "/api/estado":
            obj = {
                "hora": datetime.datetime.now().strftime("%H:%M"),
                "esperan": contar_esperando(cfg["puente"]),
                "kodama_vivo": kodama_vivo(cfg["latido"]),
            }
            return self._json(200, obj, extra)

        if p.startswith("/foto/"):
            nombre = unquote(p[len("/foto/"):])
            if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
                return self._respond(403, "Prohibido", "text/plain; charset=utf-8")
            ext = os.path.splitext(nombre)[1].lower()
            ruta = os.path.join(cfg["fotos"], nombre)
            if ext not in EXT or not os.path.isfile(ruta):
                return self._respond(404, "No encontrado", "text/plain; charset=utf-8")
            with open(ruta, "rb") as f:
                datos = f.read()
            return self._respond(200, datos, EXT[ext], extra)

        return self._respond(404, "No encontrado", "text/plain; charset=utf-8")


def crear_servidor(puerto, carpeta=CARPETA, fotos=FOTOS_DEF, puente=PUENTE_DEF, latido=LATIDO_DEF):
    clave = cargar_clave(carpeta)
    srv = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    srv.cfg = {"clave": clave, "fotos": fotos, "puente": puente, "latido": latido}
    return srv


def ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8790)
    a = ap.parse_args()
    srv = crear_servidor(a.puerto)
    try:
        ip = ip_lan()
    except OSError:
        ip = "127.0.0.1"
    with open(os.path.join(CARPETA, "enlace.txt"), "w", encoding="utf-8") as f:
        f.write("http://%s:%d/?k=%s\n" % (ip, a.puerto, srv.cfg["clave"]))
    print("Marco escuchando en puerto %d. Enlace en enlace.txt." % a.puerto)
    os.makedirs(FOTOS_DEF, exist_ok=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
