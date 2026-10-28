# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Prueba mejoras 1 y 6 sin tocar chats reales: dos pedidos falsos del mismo chat + responder con motivo."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import companero_hub as h
os.makedirs(h.PERMISOS, exist_ok=True)
ids = ["aaaa0001", "aaaa0002"]
try:
    for i, pid in enumerate(ids):
        json.dump({"id": pid, "sesion": "prueba-cola", "texto": f"pedido {i+1}", "ts": time.time() - 10 + i},
                  open(os.path.join(h.PERMISOS, pid + ".pedido"), "w", encoding="utf-8"))
    p = h.permisos_pendientes()["prueba-cola"]
    print("primero:", p["id"], "| cola:", p["cola"])
    print("responder con motivo:", h.responder_permiso("aaaa0001", "deny", "  No toques   esa carpeta "))
    print("respuesta escrita:", open(os.path.join(h.PERMISOS, "aaaa0001.respuesta"), encoding="utf-8").read())
    os.remove(os.path.join(h.PERMISOS, "aaaa0001.pedido"))
    p = h.permisos_pendientes()["prueba-cola"]
    print("despues:", p["id"], "| cola:", p["cola"])
finally:
    for pid in ids:
        for ext in (".pedido", ".respuesta"):
            try:
                os.remove(os.path.join(h.PERMISOS, pid + ext))
            except OSError:
                pass
    print("limpio:", "prueba-cola" not in h.permisos_pendientes())
