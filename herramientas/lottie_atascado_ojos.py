# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Muestras de ojos para el estado "atascado" (NO se aplican: solo para elegir).
Parte de web/lottie/estado_atascado.json y cambia SOLO los ojos durante toda la animacion; escribe en web/lottie/muestras/:
  estado_atascado_ojos_a.json  ojos apretados "> <"
  estado_atascado_ojos_b.json  ojos en espiral (mareado), la espiral gira
  estado_atascado_ojos_c.json  ojos preocupados: el ojo de siempre, parpado mas inclinado hacia el centro (borde interno ARRIBA, como "/ \\") y pupila chica (se ve con "gatoPro")
Los ojos nuevos son capas hijas de la capa OJOS (que cuelga de CUERPO), asi siguen el temblor del cuerpo igual que hoy.
  estado_atascado_ojos_c2.json ojos preocupados SUAVES (5.a vuelta): como la (c) pero menos tristes: parpado apenas inclinado (~la mitad de la inclinacion de la c),
                               pupila casi normal (85 %) y sin caida marcada
(5.a vuelta) El dueño eligio la (a): web/lottie/estado_atascado.json = la (a). Por eso el ORIGEN ya NO es estado_atascado.json (seria la (a)) sino
muestras/estado_atascado_original.json (copia del que habia antes). A cada muestra se le pone ademas el mate de las rayas (lottie_capas.mate_de_rayas).
Idempotente: siempre parte del original y reescribe las muestras."""
import copy, json, math, os, sys

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "lottie").replace(os.sep, "/") + "/"
SALIDA = BASE + "muestras/"
ORIGEN = SALIDA + "estado_atascado_original.json"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lottie_capas import mate_de_rayas   # noqa: E402
TRAZO = [1, 0.9569, 0.8706, 1]   # el mismo color del trazo "feliz" (el recolorador lo cambia en los colores claros)
OJOS = [("d", 152.0, 158.0), ("i", 88.0, 158.0)]   # (lado, x, y) del centro de cada ojo en el lienzo de 360
QUITAR = {"ojo-d", "ojo-i", "pupila-d", "pupila-i", "parpado-d", "parpado-i"}


def cargar():
    return json.load(open(ORIGEN, encoding="utf-8"))


def ks_quieto(cx, cy, rot=None):
    r = {"a": 0, "k": 0} if rot is None else rot
    return {"o": {"a": 0, "k": 100}, "r": r, "p": {"a": 0, "k": [cx, cy, 0]}, "a": {"a": 0, "k": [cx, cy, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}


def trazo_poli(nombre, puntos, ancho, cerrado=False):
    return {"ty": "gr", "nm": nombre, "bm": 0, "hd": False, "it": [
        {"ind": 0, "ty": "sh", "nm": "Path 1", "hd": False, "ks": {"a": 0, "k": {
            "i": [[0, 0] for _ in puntos], "o": [[0, 0] for _ in puntos], "v": [[round(x, 3), round(y, 3)] for x, y in puntos], "c": cerrado}}},
        {"ty": "st", "nm": "Stroke 1", "hd": False, "bm": 0, "c": {"a": 0, "k": TRAZO[:]}, "o": {"a": 0, "k": 100},
         "w": {"a": 0, "k": ancho}, "lc": 2, "lj": 2},
        {"ty": "tr", "nm": "Transform", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
         "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}}]}


def capa_nueva(molde, ind, nombre, ks, forma):
    l = copy.deepcopy(molde)
    l.pop("masksProperties", None); l.pop("hasMask", None); l.pop("cl", None)
    l.update({"ind": ind, "nm": nombre, "parent": 3, "ks": ks, "shapes": [forma], "ip": 0, "op": 90, "st": 0, "ddd": 0, "ao": 0, "sr": 1, "bm": 0})
    return l


def reemplazar_ojos(d, nuevas):
    """Quita las capas de ojo originales y pone `nuevas` donde estaba la capa de la pupila derecha (arriba del grupo de ojos)."""
    capas, salida, puesto = d["layers"], [], False
    for l in capas:
        if l.get("nm") == "pupila-d" and not puesto:
            salida.extend(nuevas); puesto = True
        if l.get("nm") in QUITAR:
            continue
        salida.append(l)
    assert puesto, "no encontre la capa pupila-d"
    d["layers"] = salida
    return d


def molde(d):
    return next(l for l in d["layers"] if l.get("nm") == "ojo-d")


def muestra_a():   # "> <": el ojo izquierdo (88) es ">" y el derecho (152) es "<": las puntas miran al centro de la cara
    d = cargar(); m = molde(d); nuevas = []
    for n, (lado, cx, cy) in enumerate(OJOS):
        # "<" = (cx+8,cy-10) -> (cx-8,cy) -> (cx+8,cy+10); ">" = (cx-8,cy-10) -> (cx+8,cy) -> (cx-8,cy+10)
        if lado == "d":
            pts = [(cx + 8, cy - 10), (cx - 8, cy), (cx + 8, cy + 10)]
        else:
            pts = [(cx - 8, cy - 10), (cx + 8, cy), (cx - 8, cy + 10)]
        nuevas.append(capa_nueva(m, 40 + n, "ojo-apretado-" + lado, ks_quieto(cx, cy), trazo_poli("apretado-" + lado, pts, 7.2)))
    return reemplazar_ojos(d, nuevas)


def espiral(cx, cy, r0=1.2, r1=14.5, vueltas=2.5, paso=math.pi / 16):
    t_max, pts, t = vueltas * 2 * math.pi, [], 0.0
    while t < t_max:
        r = r0 + (r1 - r0) * t / t_max
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t))); t += paso
    r = r1; pts.append((cx + r * math.cos(t_max), cy + r * math.sin(t_max)))
    return pts


def muestra_b():   # espirales que giran (2 vueltas en los 3 s del archivo; el bucle [21,fin] sigue siendo parejo: la velocidad es constante)
    d = cargar(); m = molde(d); nuevas = []
    for n, (lado, cx, cy) in enumerate(OJOS):
        giro = {"a": 1, "k": [{"t": 0, "s": [0], "i": {"x": [1], "y": [1]}, "o": {"x": [0], "y": [0]}}, {"t": 90, "s": [720]}]}
        nuevas.append(capa_nueva(m, 40 + n, "ojo-espiral-" + lado, ks_quieto(cx, cy, giro), trazo_poli("espiral-" + lado, espiral(cx, cy), 3.4)))
    return reemplazar_ojos(d, nuevas)


def forma_parpado(nombre, puntos):
    """Parpado = poligono cerrado del color del CUERPO (el recolorador lo cambia con el color del gato)."""
    return {"ty": "gr", "nm": nombre, "bm": 0, "hd": False, "it": [
        {"ind": 0, "ty": "sh", "nm": "Path 1", "hd": False, "ks": {"a": 0, "k": {
            "i": [[0, 0] for _ in puntos], "o": [[0, 0] for _ in puntos], "v": [[round(x, 3), round(y, 3)] for x, y in puntos], "c": True}}},
        {"ty": "fl", "nm": "Fill 1", "hd": False, "bm": 0, "c": {"a": 0, "k": [0.1216, 0.1098, 0.1333, 1]}, "o": {"a": 0, "k": 100}, "r": 1},
        {"ty": "tr", "nm": "Transform", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
         "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}}]}


def muestra_c(y_dentro=-17.5, y_fuera=7.0, pupila=(11.0, 159.6), brillo=(4.4, 2.4, 157.6)):
    """el ojo de siempre, parpado inclinado hacia el centro (borde de adentro ARRIBA, como "/ \") y pupila chica.
    y_dentro / y_fuera = altura (respecto del centro del ojo) del borde de abajo del parpado en la punta de ADENTRO y de AFUERA:
    la (c) usa -17.5 / 7 (cae 24,5 en 48 = ~27 grados). pupila = (diametro, y del centro); brillo = (diametro, desplazamiento x, y)."""
    d = cargar(); m = molde(d)
    # el parpado original (con mascara animada) casi no se ve despues del parpadeo del inicio: se cambia por uno propio, fijo, que si se ve
    lids = []
    for n, (lado, cx, cy) in enumerate(OJOS):
        k = 1 if lado == "d" else -1   # el ojo izquierdo es el espejo del derecho respecto de la cara (centro x = 120)
        pts = [(cx - k * 24, cy - 40), (cx + k * 24, cy - 40), (cx + k * 24, cy + y_fuera), (cx - k * 24, cy + y_dentro)]
        lids.append(capa_nueva(m, 44 + n, "parpado-preocupado-" + lado, ks_quieto(cx, cy), forma_parpado("parpado-preocupado-" + lado, pts)))
    capas, salida, puesto = d["layers"], [], False
    for l in capas:
        if l.get("nm") in ("parpado-d", "parpado-i"):
            if not puesto:
                salida.extend(lids); puesto = True
            continue
        salida.append(l)
    assert puesto, "no encontre el parpado"
    d["layers"] = salida
    for l in d["layers"]:
        if l.get("cl") == "pupila":
            lado_d = l["nm"].endswith("-d"); cx = 152.0 if lado_d else 88.0
            for g in l.get("shapes", []):
                for it in g.get("it", []):
                    if it.get("ty") != "el":
                        continue
                    if g["nm"] == "pupila":
                        it["s"]["k"] = [pupila[0], pupila[0]]; it["p"]["k"] = [cx, pupila[1]]
                    elif g["nm"] == "brillo":
                        it["s"]["k"] = [brillo[0], brillo[0]]; it["p"]["k"] = [cx + brillo[1], brillo[2]]
    return d


def muestra_c2():   # (5.a vuelta) la (c) menos triste: parpado a la mitad de inclinacion (cae 12,25 en 48 = ~14 grados), pupila al 85 %, sin caida marcada
    # el borde del parpado pasa por el mismo punto medio de la (c) menos ~3: tapa menos el ojo. pupila normal = 21,6 (arriba del ojo, centro y 159,2); brillo normal 7,6
    return muestra_c(y_dentro=-14.2, y_fuera=-1.95, pupila=(18.36, 159.2), brillo=(6.46, 3.4, 155.46))


def main():
    os.makedirs(SALIDA, exist_ok=True)
    for sufijo, f in (("a", muestra_a), ("b", muestra_b), ("c", muestra_c), ("c2", muestra_c2)):
        d = f()
        mate_de_rayas(d)   # (5.a vuelta) las rayas del naranja quedan recortadas a la silueta tambien en las muestras
        ruta = SALIDA + "estado_atascado_ojos_" + sufijo + ".json"
        json.dump(d, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
        print(os.path.basename(ruta), len(d["layers"]), "capas,", round(os.path.getsize(ruta) / 1024), "KB")


if __name__ == "__main__":
    main()
