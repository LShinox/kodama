# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Hub FALSO solo para grabar los GIFs del lanzamiento (nunca habla con el hub real ni con datos reales).
Uso: python hub_falso.py <puerto>
  GET  /api/estado        -> chats FICTICIOS ("Mi proyecto", "Tesis", "Web") segun el escenario actual
  POST /_set {"esc": ...} -> cambia el escenario: reposo | pensando | ejecutando | pregunta | dos
  el resto de /api/...    -> respuestas minimas para que el panel de Ajustes se vea completo
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ESC = {"esc": "reposo"}
TS = {}   # marca de tiempo FIJA de cada chat mientras esta activo (si cambiara en cada consulta, la mascota diria "llego otro mensaje")


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
    t_tesis = marca("tesis", e in ("pensando", "ejecutando"), 40)
    t_proy = marca("proyecto", e in ("pregunta", "dos"), 2)
    t_web = marca("web", e == "dos", 1)
    if t_tesis:
        out["tesis"].update(estado="trabajando", fase=e, haciendo="editando capitulo2.md", ultimo_ts=t_tesis, mensajes=[{"ts": t_tesis, "texto": "Voy a revisar el capítulo 2 y ordenar la bibliografía.", "yo": False}], tareas={"h": 3, "t": 7, "a": "Revisar el capítulo 2"})
        if e == "ejecutando":
            out["tesis"]["fase_tipo"] = "comando"
    if t_proy:
        q = "¿Publico la versión de hoy o la dejo para mañana?"
        out["proyecto"].update(estado="termino", tipo="pregunta", n=1, linea=q, ultimo_ts=t_proy,
                               mensajes=[{"ts": t_proy, "texto": "Revisé todo y está listo. " + q, "yo": False, "evento": "Stop"}])
    if t_web:
        out["web"].update(estado="termino", tipo="termino", n=1, linea="Listo: el sitio quedó actualizado.", ultimo_ts=t_web,
                          mensajes=[{"ts": t_web, "texto": "Listo: el sitio quedó actualizado.", "yo": False, "evento": "Stop"}])
    out["_seleccion"] = "personales"
    return out


def lo_nuevo():
    try:
        c = json.load(open(os.path.join(APP, "web", "lo-nuevo.json"), encoding="utf-8")).get("1.0.0")
    except Exception:
        c = None
    return {"version": "1.0.0", "cambios": c, "stats": {"avisos": 42, "respuestas": 17, "chats": 5, "respuestas_celular": 6}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

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
        if p == "/api/lo-nuevo":
            return self._json(lo_nuevo())
        if p == "/api/actualizacion":
            return self._json({"actual": "1.0.0"})
        if p == "/ajustes.json":
            return self._json({})
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
        if p == "/api/lo-nuevo":
            return self._json(lo_nuevo())
        if p == "/api/reglas":
            return self._json({"siempre": ["Bash: npm test", "Leer archivos del proyecto"], "tarea": []})
        if p == "/api/hooks":
            return self._json({"ok": True, "items": [{"que": "Aviso al terminar", "ok": True}, {"que": "Preguntas y permisos", "ok": True}, {"que": "Progreso de tareas", "ok": True}]})
        if p == "/api/actualizar-auto":
            return self._json({"actual": "1.0.0", "nueva": None, "activa": False})
        if p == "/api/lectura-exacta":
            return self._json({"activa": False})
        return self._json({"ok": True})


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
