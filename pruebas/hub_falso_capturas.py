# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
"""FAKE hub for the macOS screenshot job (capturas-mac.yml). It never talks to the real hub or to any real data.
Adapted from herramientas/gifs/lanzamiento/hub_falso.py (same fictional chats), with scenarios for the states we photograph and explicit CORS headers
(the pet runs from the tauri:// origin and sends the X-Companero-Local header, so the preflight must allow it).

Usage: python hub_falso_capturas.py <port>
  GET  /api/estado     -> fictional chats for the current scenario
  POST /_set {"esc": ..., "lang": "en"|"es"} -> change scenario (reposo | trabajando | pregunta | permiso) and chat content language
  everything else      -> minimal answers so the pet and its Settings panel have something to show
"""
import json
import socketserver
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ESC = {"esc": "reposo", "lang": "en"}   # lang: language of the fictional chat content (the pet UI language is set in its own config)
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


# fictional chat content in both languages (it is chat content, not pet UI: but a screenshot with Spanish chat text under an English UI looks like a mix)
TXT = {
    "en": {"proyecto": "My project", "tesis": "Thesis", "web": "Web",
           "t_msg": "I'll review chapter 2 and tidy up the bibliography.", "t_haciendo": "editing chapter2.md",
           "q": "Should I publish today's version or leave it for tomorrow?", "q_msg": "I reviewed everything and it is ready. ",
           "p": "I need your OK to run: npm install --force", "p_msg": "\nDo you want me to run it?\n1. Allow once\n2. Always allow this\n3. Deny"},
    "es": {"proyecto": "Mi proyecto", "tesis": "Tesis", "web": "Web",
           "t_msg": "Voy a revisar el capitulo 2 y ordenar la bibliografia.", "t_haciendo": "editando capitulo2.md",
           "q": "Publico la version de hoy o la dejo para manana?", "q_msg": "Revise todo y esta listo. ",
           "p": "Necesito tu OK para ejecutar: npm install --force", "p_msg": "\nQuieres que lo ejecute?\n1. Permitir una vez\n2. Permitir siempre esto\n3. Denegar"},
}


def estado():
    e = ESC["esc"]
    T = TXT.get(ESC.get("lang"), TXT["en"])
    out = {"proyecto": chat(T["proyecto"], COLORES["proyecto"]), "tesis": chat(T["tesis"], COLORES["tesis"]), "web": chat(T["web"], COLORES["web"])}
    t_tesis = marca("tesis", e == "trabajando", 40)
    t_preg = marca("proyecto", e == "pregunta", 2)
    t_perm = marca("web", e == "permiso", 2)
    if t_tesis:
        out["tesis"].update(estado="trabajando", fase="ejecutando", fase_tipo="comando", haciendo=T["t_haciendo"], ultimo_ts=t_tesis,
                            mensajes=[{"ts": t_tesis, "texto": T["t_msg"], "yo": False}])
    if t_preg:
        q = T["q"]
        out["proyecto"].update(estado="termino", tipo="pregunta", n=1, linea=q, ultimo_ts=t_preg,
                               mensajes=[{"ts": t_preg, "texto": T["q_msg"] + q, "yo": False, "evento": "Stop"}])
    if t_perm:
        q = T["p"]
        out["web"].update(estado="termino", tipo="permiso", n=1, linea=q, ultimo_ts=t_perm, permiso={"id": "p-ci-1"},
                          mensajes=[{"ts": t_perm, "texto": q + T["p_msg"], "yo": False, "evento": "PermissionRequest"}])
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
            if cuerpo.get("lang") in TXT:
                ESC["lang"] = cuerpo["lang"]
                TS.clear()   # the notices are rebuilt in the new language
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


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        # HTTPServer.server_bind calls socket.getfqdn(), which can block for many seconds on a macOS runner (reverse DNS) BEFORE the socket listens
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


if __name__ == "__main__":
    Servidor(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
