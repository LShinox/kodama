# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
# Receptor local para la grabacion: la pagina del navegador interno hace POST de los JSON / PNG aqui.
# Solo escribe dentro de animacion/grabaciones y animacion/verificacion. Se apaga con GET /fin o por inactividad.
import http.server, os, sys, threading, time, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
PERMITIDAS = ("grabaciones", "verificacion")
ultimo = [time.time()]
PUERTO = 8770


class H(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        ultimo[0] = time.time()
        self.send_response(200); self._cors(); self.end_headers()
        self.wfile.write(b"ok")
        if self.path.startswith("/fin"):
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def do_POST(self):
        ultimo[0] = time.time()
        q = urllib.parse.urlparse(self.path)
        rel = urllib.parse.parse_qs(q.query).get("f", [""])[0].replace("\\", "/")
        n = int(self.headers.get("Content-Length", "0"))
        datos = self.rfile.read(n)
        destino = os.path.normpath(os.path.join(BASE, rel))
        ok = rel.split("/")[0] in PERMITIDAS and destino.startswith(BASE + os.sep) and ".." not in rel
        if not ok:
            self.send_response(403); self._cors(); self.end_headers(); self.wfile.write(b"no"); return
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(datos)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(str(len(datos)).encode())

    def log_message(self, *a):
        pass


def vigilar(srv):
    while True:
        time.sleep(30)
        if time.time() - ultimo[0] > 3600:
            srv.shutdown(); return


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), H)
    threading.Thread(target=vigilar, args=(srv,), daemon=True).start()
    print("PID", os.getpid(), flush=True)
    srv.serve_forever()
