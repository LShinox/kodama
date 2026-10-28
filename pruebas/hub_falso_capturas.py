# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
"""FAKE hub for the macOS screenshot job (capturas-mac.yml). It never talks to the real hub or to any real data.
Adapted from herramientas/gifs/lanzamiento/hub_falso.py (same fictional chats), with scenarios for the states we photograph and explicit CORS headers
(the pet runs from the tauri:// origin and sends the X-Companero-Local header, so the preflight must allow it).

Usage: python hub_falso_capturas.py <port>
  GET  /api/estado     -> fictional chats for the current scenario
  POST /_set {"esc": ...} -> change scenario: reposo | trabajando | pregunta | permiso
  everything else      -> minimal answers so the pet and its Settings panel have something to show
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ESC = {"esc": "reposo"}
TS = {}   # fixed timestamp of each active chat (if it changed on every poll the pet would say "another message arrived")


def marca(c, activo, antes=2):
    if not activo:
        TS.pop(c, None)
        return 0
    return TS.setdefault(c, time.time() - antes)


COLORES = {"proyecto": "#2F7FC1", "tesis": "#8e5bd0", "web": "#2e9d6a"}


def chat(nombre, color, **kw):
    a = time.time()
    d = {"nombre": nombre, "color": color, "estado": "reposo", "tipo": "", "visto": a - 5, "ultimo_ts": a - 3600, "mensajes": [], "n": 0, "linea": ""}
    d.update(kw)
    return d


def estado():
    e = ESC["esc"]
    out = {"proyecto": chat("Mi proyecto", COLORES["proyecto"]), "tesis": chat("Tesis", COLORES["tesis"]), "web": chat("Web", COLORES["web"])}
    t_tesis = marca("tesis", e == "trabajando", 40)
    t_preg = marca("proyecto", e == "pregunta", 2)
    t_perm = marca("web", e == "permiso", 2)
    if t_tesis:
        out["tesis"].update(estado="trabajando", fase="ejecutando", fase_tipo="comando", haciendo="editando capitulo2.md", ultimo_ts=t_tesis,
                            mensajes=[{"ts": t_tesis, "texto": "Voy a revisar el capitulo 2 y ordenar la bibliografia.", "yo": False}])
    if t_preg:
        q = "Publico la version de hoy o la dejo para manana?"
        out["proyecto"].update(estado="termino", tipo="pregunta", n=1, linea=q, ultimo_ts=t_preg,
                               mensajes=[{"ts": t_preg, "texto": "Revise todo y esta listo. " + q, "yo": False, "evento": "Stop"}])
    if t_perm:
        q = "Necesito tu OK para ejecutar: npm install --force"
        out["web"].update(estado="termino", tipo="permiso", n=1, linea=q, ultimo_ts=t_perm, permiso={"id": "p-ci-1"},
                          mensajes=[{"ts": t_perm, "texto": q + "\nQuieres que lo ejecute?\n1. Permitir una vez\n2. Permitir siempre esto\n3. Denegar", "yo": False, "evento": "PermissionRequest"}])
    out["_seleccion"] = "personales"
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Companero-Local, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, o):
        b = json.dumps(o).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/estado":
            return self._json(estado())
        if p == "/api/inactivo":
            return self._json({"segundos": 0})
        if p == "/api/pantalla":
            return self._json({"completa": False})
        if p == "/api/actualizacion":
            return self._json({"actual": "1.0.0"})
        if p == "/api/bloqueo":
            return self._json({"bloqueado": False})
        return self._json({})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            cuerpo = json.loads(self.rfile.read(n).decode("utf8", "replace") or "{}")
        except Exception:
            cuerpo = {}
        p = self.path.split("?")[0]
        if p == "/_set":
            ESC["esc"] = cuerpo.get("esc", "reposo")
            return self._json({"ok": True})
        if p == "/api/reglas":
            return self._json({"siempre": ["Bash: npm test", "Leer archivos del proyecto"], "tarea": []})
        if p == "/api/hooks":
            return self._json({"ok": True, "items": [{"que": "Aviso al terminar", "ok": True}, {"que": "Preguntas y permisos", "ok": True}]})
        if p == "/api/actualizar-auto":
            return self._json({"actual": "1.0.0", "nueva": None, "activa": False})
        if p == "/api/lectura-exacta":
            return self._json({"activa": False})
        if p == "/api/lo-nuevo":
            return self._json({"version": "1.0.0", "cambios": None, "stats": {"avisos": 0, "respuestas": 0, "chats": 3}})
        return self._json({"ok": True})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
