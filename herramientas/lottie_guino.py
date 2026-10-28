# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Crea web\\lottie\\gesto_guino.json (gesto "guiño") SIN After Effects, a partir de gesto_ladeo.json:

  El gato ladea la cabeza (gesto_ladeo: inclina ~10 grados a la izquierda del que mira, mantiene del cuadro 8 al 42 y vuelve) y,
  en lo alto del ladeo, GUIÑA el ojo del lado alto (ojo-d: al girar en sentido antihorario ese ojo sube). El otro ojo queda intacto.
    - cierra en 4 cuadros, queda cerrado 8 cuadros y abre en 5 (todo dentro del tramo de ladeo sostenido: cuadros 16 a 33);
    - el ojo (ojo-d + pupila-d) se aplasta en Y y se desvanece mientras la capa "feliz-d" (el arco ^ de ojo cerrado) aparece: se ve un
      arco, no un ojo aplastado; al abrir pasa lo inverso.
  El espejo (b3) lo hace personajes-lottie.js con scaleX(-1): guiña el otro ojo. Funciona igual con todos los colores y con ojos
  lisos o con pupila (la capa pupila-d, si existe, se anima junto con el ojo).

IDEMPOTENTE: siempre parte de gesto_ladeo.json y reescribe gesto_guino.json. No toca gesto_ladeo.json.
Uso:  python lottie_guino.py
"""
import copy
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
LOT = os.path.join(AQUI, "..", "web", "lottie")
ORIGEN = os.path.join(LOT, "gesto_ladeo.json")
DESTINO = os.path.join(LOT, "gesto_guino.json")

CIERRA = 16      # cuadro donde empieza a cerrar
T_CIERRA = 4     # cuadros que tarda en cerrar
T_CERRADO = 8    # cuadros cerrado
T_ABRE = 5       # cuadros que tarda en abrir
APLASTE = 12     # escala Y (%) del ojo al cerrar, antes de que desaparezca


def kf(puntos, dim=1):
    """Fotogramas clave lineales (mismo formato que los de gesto_ladeo): [(cuadro, valor)] -> propiedad animada de lottie."""
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
    for nm in ("ojo-d", "feliz-d"):
        if nm not in por:
            raise SystemExit("falta la capa " + nm + " en gesto_ladeo.json: no se hace nada")
    fin = int(d["op"]) - 1
    a = CIERRA
    b = a + T_CIERRA + T_CERRADO            # cuadro donde empieza a abrir
    c = b + T_ABRE                          # cuadro donde termina de abrir
    assert c < 42, "el guiño tiene que caber en el ladeo sostenido (cuadros 8 a 42)"

    # el ojo (y su pupila): se aplasta y se desvanece al cerrar; vuelve al abrir
    for nm in ("ojo-d", "pupila-d"):
        l = por.get(nm)
        if not l:
            continue
        l["ks"]["o"] = kf([(0, 100), (a, 100), (a + T_CIERRA, 0), (b, 0), (c, 100), (fin, 100)])
        l["ks"]["s"] = kf([(0, [100, 100, 100]), (a, [100, 100, 100]), (a + T_CIERRA, [100, APLASTE, 100]), (b, [100, APLASTE, 100]),
                           (c, [100, 100, 100]), (fin, [100, 100, 100])], dim=3)
    # el arco del ojo cerrado (feliz-d): aparece mientras el ojo se cierra y se va cuando abre
    f = por["feliz-d"]
    f["ks"]["o"] = kf([(0, 0), (a + 1, 0), (a + T_CIERRA, 100), (b, 100), (b + 3, 0), (fin, 0)])

    d["nm"] = "gesto_guino"
    with open(DESTINO, "w", encoding="utf-8", newline="") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    print("gesto_guino.json escrito (cierra %d-%d, cerrado hasta %d, abierto en %d; %d cuadros, 30 fps)" % (a, a + T_CIERRA, b, c, int(d["op"])))


if __name__ == "__main__":
    main()
