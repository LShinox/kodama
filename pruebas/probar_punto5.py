# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Prueba sin tocar el hub vivo: importa companero_hub con Telegram falso y una carpeta de permisos temporal."""
import json, os, sys, tempfile, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import companero_hub as h

llamadas = []
h.api = lambda metodo, **kw: llamadas.append((metodo, kw)) or {"ok": True}
h.log = lambda m: llamadas.append(("log", m))
tmp = tempfile.mkdtemp(dir=os.environ.get("COMPANERO_TMP", None))
h.PERMISOS = tmp

# 1) caduca sin respuesta -> se edita a "Caducó"
open(os.path.join(tmp, "aaaaaaaa.pedido"), "w").write(json.dumps({"id": "aaaaaaaa", "sesion": "s1", "texto": "x", "ts": time.time()}))
h.PERM_TG["aaaaaaaa"] = (123, 456, time.time())
# 2) respondido -> no se toca
open(os.path.join(tmp, "bbbbbbbb.pedido"), "w").write(json.dumps({"id": "bbbbbbbb", "sesion": "s2", "texto": "y", "ts": time.time()}))
h.PERM_TG["bbbbbbbb"] = (123, 789, time.time())
print("dos pendientes a la vez (1/N):", sorted(h.permisos_pendientes()))
h.PERM_TG.pop("bbbbbbbb")          # lo que hace atender_boton al responder
os.remove(os.path.join(tmp, "aaaaaaaa.pedido"))   # el hook se rindio (110 s) y borro su pedido
threading.Thread(target=h.vigilar_permisos_caducados, daemon=True).start()
time.sleep(6.5)
ed = [kw for m, kw in llamadas if m == "editMessageReplyMarkup"]
print("ediciones:", [(e["message_id"], e["reply_markup"]["inline_keyboard"][0][0]["text"]) for e in ed])
print("caducado editado:", any(e["message_id"] == 456 for e in ed), "| respondido intacto:", not any(e["message_id"] == 789 for e in ed))

# 3) el servidor web se levanta de nuevo si serve_forever se cae
n = {"v": 0}
class Falso:
    daemon_threads = False
    def __init__(self, *a): pass
    def serve_forever(self):
        n["v"] += 1
        if n["v"] == 1:
            raise OSError("accept fallido (simulado)")
        time.sleep(60)
    def server_close(self): pass
h.http.server.ThreadingHTTPServer = Falso
h.servir_web()
time.sleep(3)
print("servidor levantado veces:", n["v"], "| log:", [m for t, m in llamadas if t == "log" and "web" in m][-2:])
