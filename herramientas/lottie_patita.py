# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov-2026) Crea web\\lottie\\gesto_patita.json (el gato levanta una pata y saluda) SIN After Effects, desde gesto_agarrar.json.

Sale cuando un chat te necesita. Solo se mueve pata-i; pata-d queda invisible. El cuerpo, los ojos y las orejas siguen como en
gesto_agarrar. IDEMPOTENTE: siempre parte de gesto_agarrar.json y reescribe gesto_patita.json.
Uso:  python lottie_patita.py
"""
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
LOT = os.path.join(AQUI, "..", "web", "lottie")
ORIGEN = os.path.join(LOT, "gesto_agarrar.json")
DESTINO = os.path.join(LOT, "gesto_patita.json")


def kf(puntos, dim=1):
    r = []
    for n, (t, v) in enumerate(puntos):
        e = {"t": t, "s": list(v) if isinstance(v, (list, tuple)) else [v]}
        if n < len(puntos) - 1:
            e["i"] = {"x": [0.833] * dim, "y": [0.833] * dim}
            e["o"] = {"x": [0.167] * dim, "y": [0.167] * dim}
        r.append(e)
    return {"a": 1, "k": r}


def main():
    d = json.load(open(ORIGEN, encoding="utf-8"))
    por = {l.get("nm"): l for l in d["layers"]}
    for nm in ("pata-d", "pata-i"):
        if nm not in por:
            raise SystemExit("falta la capa " + nm + ": no se hace nada")
    fin = int(d["op"])
    # pata-i: del otro lado esta la cola, y la pata negra se confunde con ella
    p = por["pata-i"]["ks"]
    p["o"] = kf([(0, 0), (5, 0), (8, 100), (47, 100), (51, 0), (fin, 0)])
    # la pata flota junto a la cabeza (igual que en gesto_agarrar): sube y saluda de lado a lado, fuera de la silueta para que se vea en el gato negro
    p["p"] = kf([(0, [94, 205, 0]), (5, [94, 205, 0]), (14, [34, 160, 0]), (20, [24, 112, 0]), (25, [12, 102, 0]), (30, [28, 112, 0]), (35, [12, 102, 0]), (40, [26, 112, 0]), (47, [40, 170, 0]), (51, [94, 205, 0]), (fin, [94, 205, 0])], dim=3)
    p["r"] = kf([(0, 0), (5, 0), (14, -12), (20, 6), (25, -14), (30, 12), (35, -14), (40, 6), (47, 0), (fin, 0)])
    p["s"] = kf([(0, [44, 44, 100]), (5, [44, 44, 100]), (14, [82, 82, 100]), (20, [100, 100, 100]), (40, [100, 100, 100]), (47, [66, 66, 100]), (51, [44, 44, 100]), (fin, [44, 44, 100])], dim=3)
    por["pata-d"]["ks"]["o"] = {"a": 0, "k": 0}
    d["nm"] = "gesto_patita"
    with open(DESTINO, "w", encoding="utf-8", newline="") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    print("gesto_patita.json escrito: %d cuadros" % fin)


if __name__ == "__main__":
    main()
