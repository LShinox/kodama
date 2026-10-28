# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Agrega capas a los JSON de web\\lottie\\ SIN After Effects (After no se abre):

  pupila-d / pupila-i  (cl "pupila")   pupila + brillo del gatoPro, hermanas de ojo-d / ojo-i (mismo padre y misma
                                       transformacion, asi siguen el parpadeo y la mirada); ENCIMA del ojo, DEBAJO de los parpados
  esmoquin             (cl "esmoquin") pecho y dos patitas blancas, padre CUERPO, encima de la silueta y debajo de mejillas/ojos
  rayas                (cl "rayas")    las rayas del naranja, padre CUERPO, ENCIMA de todo (como el SVG original)
  tapa-oreja-d/i (+ "-mate") (cl "tapa-oreja") (7.a vuelta) contorno de la silueta pintado del color del cuerpo, recortado por la propia oreja (mate); quita_mate_parpados deja los parpados como antes de la 6.a vuelta
                                       (8.a vuelta) la tapa cubre solo dentro de un rectangulo del cuerpo (CORTE): queda la muesca del primer cuadro original (pedacito que entra y se corta), no la linea entera ni nada
  rayas-mate           (cl "rayas")    (5.a vuelta) copia de 'silueta' justo ENCIMA de las rayas como mate (td=1; las rayas con tt=3, luminancia):
                                       las rayas no salen de la silueta ni pisan su contorno cuando el cuerpo se aplasta o se inclina
  capa_colita.json y capa_colita_enviado.json quedan EXCLUIDAS (solo la cola y sus nulos).

Cada capa lleva su "cl": lottie-web lo exporta como class del <g> del SVG, y personajes-lottie.js las muestra u oculta por CSS
segun el tipo (gatoPro / gato) y el color. Las medidas salen de personajes.js (funcion gatoPro): el lienzo del JSON es el
viewBox 120x120 del SVG x2.

IDEMPOTENTE: si la capa ya existe (por nombre) no se duplica. Se puede correr las veces que haga falta.
Uso:  python lottie_capas.py [--seco]      (--seco = solo contar, no escribe)
Los respaldos (respaldos\\*.bak-lottie2-20261026) los hace quien lo corre antes de la primera vez; aqui no se escribe nada fuera de web\\lottie.
"""
import copy
import glob
import json
import math
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
LOT = os.path.join(AQUI, "..", "web", "lottie")
K = 2.0   # viewBox del SVG -> lienzo del JSON

CUERPO_RGB = [0.1216, 0.1098, 0.1333, 1]   # #1f1c22: la pupila del negro/gris/esmoquin (personajes.js: pup = N); personajes-lottie.js la recolorea
BLANCO = [1, 1, 1, 1]
CREMA = [1, 0.9569, 0.8706, 1]              # #FFF4DE: ojo de los gatos oscuros (en los claros lo recolorea personajes-lottie.js)
PECHO = [0.9804, 0.9686, 0.949, 1]          # #FAF7F2
RAYA = [0.8157, 0.4784, 0.1804, 1]          # #D07A2E


def tr():
    return {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
            "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}, "nm": "Transform"}


def fl(c, o=100):
    return {"ty": "fl", "c": {"a": 0, "k": list(c)}, "o": {"a": 0, "k": o}, "r": 1, "bm": 0, "nm": "Fill 1", "hd": False}


def elipse(cx, cy, w, h):
    return {"d": 1, "ty": "el", "s": {"a": 0, "k": [w, h]}, "p": {"a": 0, "k": [cx, cy]}, "nm": "Ellipse Path 1", "hd": False}


def grupo(nombre, items):
    return {"ty": "gr", "it": items + [tr()], "nm": nombre, "bm": 0, "hd": False}


def camino(v, i, o, cerrado=True):
    return {"i": i, "o": o, "v": v, "c": cerrado}


def trazo_sh(forma):
    return {"ind": 0, "ty": "sh", "ks": {"a": 0, "k": forma}, "nm": "Path 1", "hd": False}


def capa(ind, nm, cl, parent, ks, shapes, ip, op, st=0, mascaras=None):
    d = {"ddd": 0, "ind": ind, "ty": 4, "nm": nm, "cl": cl, "parent": parent, "sr": 1, "ks": copy.deepcopy(ks), "ao": 0}
    if mascaras:
        d["hasMask"] = True
        d["masksProperties"] = mascaras
    d.update({"shapes": shapes, "ip": ip, "op": op, "st": st, "ct": 1, "bm": 0})
    return d


def cuna(x1, y1, x2, y2, w):
    """Cuna de pelo de personajes.js (base ancha en x1,y1; punta en x2,y2), en coordenadas del SVG; devuelve la forma del lienzo (x2)."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L * w / 2, dx / L * w / 2
    A = (x1 + px, y1 + py)
    B = (x1 - px, y1 - py)
    Q1 = (x1 + dx * .55 + px * .6, y1 + dy * .55 + py * .6)
    Q2 = (x1 + dx * .55 - px * .6, y1 + dy * .55 - py * .6)
    T = (x2, y2)
    c = 2.0 / 3.0
    def rel(a, b):
        return [round((b[0] - a[0]) * K, 3), round((b[1] - a[1]) * K, 3)]
    # Q -> cubica: control = punta + 2/3 (Q - punta)
    v = [A, T, B]
    o = [rel(A, (A[0] + c * (Q1[0] - A[0]), A[1] + c * (Q1[1] - A[1]))),
         rel(T, (T[0] + c * (Q2[0] - T[0]), T[1] + c * (Q2[1] - T[1]))),
         [0, 0]]
    i = [[0, 0],
         rel(T, (T[0] + c * (Q1[0] - T[0]), T[1] + c * (Q1[1] - T[1]))),
         rel(B, (B[0] + c * (Q2[0] - B[0]), B[1] + c * (Q2[1] - B[1])))]
    return camino([[round(p[0] * K, 3), round(p[1] * K, 3)] for p in v], i, o)


RAYAS = [(60, 40, 60, 55, 4.2), (51, 42, 53.5, 53, 3.4), (69, 42, 66.5, 53, 3.4),
         (20, 75, 31, 77.5, 3.6), (20, 83, 30, 83.5, 3.4), (100, 75, 89, 77.5, 3.6), (100, 83, 90, 83.5, 3.4),
         (41, 104, 44, 97, 3.4), (79, 104, 76, 97, 3.4)]


def forma_pecho():
    # M50 106 C50 100 54 96 60 96 C66 96 70 100 70 106 Z  (x2)
    v = [[100, 212], [120, 192], [140, 212]]
    o = [[0, -12], [12, 0], [0, 0]]
    i = [[0, 0], [-12, 0], [0, -12]]
    return camino(v, i, o)


def mascaras_de(silueta_capa, forma_silueta):
    """Mascara = silueta (suma) + las del piso que ya trae la silueta (interseccion): lo que sobra del cuerpo o baja del piso se corta."""
    m = [{"inv": False, "mode": "a", "pt": {"a": 0, "k": copy.deepcopy(forma_silueta)}, "o": {"a": 0, "k": 100}, "x": {"a": 0, "k": 0}, "nm": "Silueta"}]
    for p in silueta_capa.get("masksProperties", []):
        q = copy.deepcopy(p)
        q["mode"] = "i"
        m.append(q)
    return m


# (5.a vuelta) Archivos que NUNCA se tocan aunque algun dia traigan "silueta": capa_colita.json es SOLO la cola (y sus nulos) y se mezcla DETRAS de
# un gesto quieto; si recibiera rayas, esmoquin o pupila, se veria un segundo cuerpo/orejas debajo del gesto.
# (27-oct) sello que llevan TODOS los JSON de web\lottie\ dentro de "meta" (los reproductores Lottie lo ignoran)
SELLO_META = {"sello": "peltre-9k4x-2f81", "pulso": 0.80317249}
EXCLUIR = {"capa_colita.json", "capa_colita_enviado.json"}   # (27-oct) capa_colita_enviado: la cola nueva de estado_enviado, tambien SOLO cola y nulos
RAYA_MATE = "rayas-mate"
GROSOR_BORDE = 4.0       # grosor del contorno de la silueta (lienzo de 360); el mate lo "come" por dentro para que las rayas no pisen la linea
GROSOR_MATE = 5.0        # (8.a vuelta) 1 mas que el contorno (4): las rayas quedan 0,5 unidades ANTES del borde interior de la linea y nunca la pisan (con 4 rozaban el borde con el antialias; con menos pisaban ~0,2 px)


def copia_mate(sil, ind, nm, cl):
    """Copia de la capa 'silueta' como MATE DE LUMINANCIA (td=1): relleno BLANCO y contorno NEGRO de GROSOR_MATE centrado en el trazo = solo el interior de la linea."""
    m = copy.deepcopy(sil)
    m.update({"ind": ind, "nm": nm, "cl": cl, "td": 1})
    m.pop("tt", None)
    for g in m["shapes"]:
        for it in g.get("it", []):
            if it.get("ty") == "fl":
                it["c"] = {"a": 0, "k": [1, 1, 1, 1]}
                it["o"] = {"a": 0, "k": 100}
            elif it.get("ty") == "st":
                it["c"] = {"a": 0, "k": [0, 0, 0, 1]}
                it["o"] = {"a": 0, "k": 100}
                it["w"] = {"a": 0, "k": GROSOR_MATE}
    return m


def mate_de_rayas(d):
    """(5.a vuelta) Recorta las rayas a la silueta con un MATE de Lottie (en vez de la mascara estatica de forma_sil, que no seguia al cuerpo
    cuando se aplasta o se inclina y dejaba las cuñas pisando la linea del contorno, sobre todo abajo).
    Una copia de la capa 'silueta' (mismo padre, ks, mascara del piso y fotogramas) va justo ENCIMA de 'rayas' como mate (td=1) y las rayas
    quedan con tt=3 (mate de LUMINANCIA): la copia pinta el relleno en BLANCO y el contorno en NEGRO (centrado en el trazo), asi las rayas llegan
    solo hasta el borde INTERIOR de la linea. Las rayas pierden su mascara propia (la del piso ya viene en el mate).
    Idempotente: se reconstruye desde 'silueta' cada vez; si ya estaba igual no cambia nada. Devuelve lo que hizo (lista de textos)."""
    capas = d["layers"]
    por = {l.get("nm"): l for l in capas}
    if "rayas" not in por or "silueta" not in por:
        return []
    rayas, sil = por["rayas"], por["silueta"]
    hecho = []
    previo = por.get(RAYA_MATE)
    ind = previo["ind"] if previo else max(l["ind"] for l in capas) + 1
    m = copia_mate(sil, ind, RAYA_MATE, "rayas")    # (en la silueta el trazo va antes que el relleno en la lista = encima: el contorno NEGRO queda sobre el relleno BLANCO, como se necesita)
    if previo is None or json.dumps(previo, sort_keys=True) != json.dumps(m, sort_keys=True):
        if previo is not None:
            capas.remove(previo)
        capas.insert(next(n for n, l in enumerate(capas) if l is rayas), m)
        hecho.append(RAYA_MATE)
    if rayas.get("tt") != 3 or rayas.get("hasMask") or rayas.get("masksProperties"):
        rayas["tt"] = 3
        rayas.pop("hasMask", None); rayas.pop("masksProperties", None)
        hecho.append("rayas tt=3")
    return hecho


# (7.a vuelta) Se QUITA el mate de los parpados de la 6.a vuelta (el dueño no quiere la linea continua bajo las orejas): vuelven los parpados como estaban
# (rectangulos opacos encima de la silueta). Esta funcion deja los JSON limpios y es idempotente (si no hay nada que quitar, no hace nada).
def quitar_mate_parpados(d):
    capas = d["layers"]
    hecho = []
    for l in [l for l in capas if str(l.get("nm", "")).startswith("parpado-") and str(l.get("nm", "")).endswith("-mate")]:
        capas.remove(l)
        hecho.append("quitado " + l["nm"])
    for l in capas:
        if re.match(r"^parpado-[di]$", str(l.get("nm", ""))) and "tt" in l:
            del l["tt"]
            hecho.append(l["nm"] + " sin tt")
    return hecho


# (7.a vuelta) OREJA Y CABEZA, UNA SOLA PIEZA. La silueta (cuerpo + cabeza) va ENCIMA de las orejas y su contorno cruza la base de cada oreja
# (la cuesta de la cabeza). Lo que el dueño quiere es el look "cortado": sin linea en la base de la oreja. Tecnica (probada en TODOS los cuadros):
#   tapa-oreja-d / tapa-oreja-i (cl "tapa-oreja")  copia SOLO DEL CONTORNO de la silueta pintado del color del CUERPO (el recoloreo lo trata como cuerpo),
#       justo encima de la silueta, con un MATE DE LUMINANCIA (tt=3) = la propia oreja (copia de oreja-d/i con su padre, transformacion
#       animada y mascara, asi sigue la oreja en cada cuadro: rota, se aplana, se inclina). Solo se tapa el contorno donde cruza la oreja.
#   tapa-oreja-d/i-mate (td=1) relleno BLANCO + contorno NEGRO de 2*INSET_OREJA: el mate vale solo el interior de la oreja a INSET_OREJA px del borde,
#       asi el contorno de la propia oreja (por fuera de la cabeza) y el del cuerpo no se tocan.
# (8.a vuelta) Estas capas valen para TODOS los colores: en negro y esmoquin personajes-lottie.js recolorea el contorno (silueta, orejas y los trazos) a #433D4B, un poco mas claro que el cuerpo (#1F1C22).
TAPA = "tapa-oreja-"
INSET_OREJA = 2.5        # px (lienzo 360) que el mate se aleja del borde de la oreja (el trazo de la oreja mide 4 = 2 por lado)
GROSOR_TAPA = 6.0        # un poco mas que el contorno (4) para cubrirlo entero con su antialias


# (8.a vuelta) LOOK "CORTADO" del primer cuadro de las animaciones originales: la base de cada oreja se ve "partida" con DOS trazos cortos de la linea de la cabeza que entran
# y se afinan en punta (ni la linea entera, que forma triangulos, ni ninguna linea). Eleccion del dueño con capturas 60-64:
#   ARRIBA (trazo-arriba-d/i): sale del arco de la cabeza sin quiebre (sigue el arco con el mismo grosor, hasta ARCO_X0, y ahi se curva suave de la tangente del arco a la
#       direccion de la linea y se afina hasta una punta a ~16 unidades), es una FORMA RELLENA con el color del borde (el recoloreo la pinta como el contorno).
#   ABAJO (silueta-abajo-d/i): copia del contorno de la silueta recortada por una mascara con la CUÑA del borde exterior: parte del borde de la oreja con el grosor completo
#       (sin escalon) y afina hacia adentro hasta una punta (~15 unidades) siguiendo la linea de la cabeza.
# Las tapas (tapa-oreja-d/i, del color del cuerpo) cubren la linea ENTERA dentro de la oreja; estos trazos van ENCIMA de todo (rayas y parpados incluidos, en el espacio del
# cuerpo: el parpado opaco del cuadro 0 cortaba el de abajo en vertical, que era la "ticita"), asi que el contorno nunca queda debajo de una raya y el corte se ve igual en
# todos los cuadros (la oreja gira sobre su base, fija en el cuerpo). Se descarto un rectangulo en el espacio de la oreja (con orejas planas giraba y la linea volvia a verse entera).
# La linea de la cabeza dentro de la oreja es el segmento recto (144,83)-(184,106) de la silueta; el arco de la cabeza llega a (144,83) con tangente (16,4). Izquierda = espejo en x=120.
LINEA_O = (144.0, 83.0)
LINEA_F = (184.0, 106.0)
ARCO = ((96.0, 83.0), (112.0, 79.0), (128.0, 79.0), (144.0, 83.0))   # bezier del arco de la silueta que termina en LINEA_O
ARCO_X0 = 128.0          # el trazo de arriba empieza a seguir el arco desde esta x (antes de la oreja, que empieza en x ~138)
TIP_ARRIBA = (158.0, 89.2)   # punta del trazo de arriba
LARGO_ABAJO = 15.0       # largo visible de la cuña de abajo (de la punta al grosor completo)
NOMBRES_TRAZOS = ("trazo-arriba-d", "trazo-arriba-i", "silueta-abajo-d", "silueta-abajo-i")
BORDE_ORIG = [0.3529, 0.3255, 0.3922, 1]   # ORIG.borde de personajes-lottie.js: el recoloreo lo cambia por el borde de cada color


def _bez(p, t):
    mt = 1 - t
    return (mt ** 3 * p[0][0] + 3 * mt * mt * t * p[1][0] + 3 * mt * t * t * p[2][0] + t ** 3 * p[3][0],
            mt ** 3 * p[0][1] + 3 * mt * mt * t * p[1][1] + 3 * mt * t * t * p[2][1] + t ** 3 * p[3][1])


def forma_arriba(lado):
    """Poligono (muestreado) del trazo de arriba. Centro: el arco desde x=ARCO_X0 hasta (144,83) y una curva suave de ahi a la punta; semiancho 2 en el arco y 2 -> 0 en la curva."""
    cen, hw = [], []
    t0 = next(i / 400.0 for i in range(401) if _bez(ARCO, i / 400.0)[0] >= ARCO_X0)
    for k in range(9):
        cen.append(_bez(ARCO, t0 + (1 - t0) * k / 8.0)); hw.append(2.0)
    ox, oy = LINEA_O
    dx, dy = LINEA_F[0] - ox, LINEA_F[1] - oy
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    tgx, tgy = ARCO[3][0] - ARCO[2][0], ARCO[3][1] - ARCO[2][1]
    g = math.hypot(tgx, tgy); tgx, tgy = tgx / g, tgy / g
    tx, ty = TIP_ARRIBA
    c1 = (ox + 6.0 * tgx, oy + 6.0 * tgy)
    c2 = (tx - 6.0 * ux, ty - 6.0 * uy)
    cur = ((ox, oy), c1, c2, (tx, ty))
    N = 14
    for k in range(1, N + 1):
        s = k / float(N)
        cen.append(_bez(cur, s)); hw.append(2.0 * (1 - s))
    izq, der = [], []
    for i, (x, y) in enumerate(cen):
        a, b = cen[max(0, i - 1)], cen[min(len(cen) - 1, i + 1)]
        vx, vy = b[0] - a[0], b[1] - a[1]
        m = math.hypot(vx, vy) or 1.0
        nx, ny = -vy / m, vx / m
        izq.append((x + nx * hw[i], y + ny * hw[i])); der.append((x - nx * hw[i], y - ny * hw[i]))
    pts = izq + der[::-1][1:]
    return [[round(240 - x if lado == "i" else x, 3), round(y, 3)] for x, y in pts]


def forma_abajo(lado):
    """Zona (espacio del cuerpo) donde el trazo de abajo SI se ve: del extremo de afuera hacia adentro, n <= b(u) (cuña que afina a punta), y de ahi en adelante todo el trazo."""
    ox, oy = LINEA_O
    dx, dy = LINEA_F[0] - ox, LINEA_F[1] - oy
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    tan = 4.0 / LARGO_ABAJO
    tip2 = L - 0.5 - LARGO_ABAJO                      # el grosor llega a 4 en u = L - 0.5 (donde empieza el mate de la oreja)
    uf, u1 = L - 0.5, L + 8.0
    pts_un = [(tip2, -2.0), (uf, -2 + (uf - tip2) * tan), (uf, 12.0), (u1, 12.0), (u1, -7.0), (tip2, -7.0)]
    pts = []
    for u, n in pts_un:
        x, y = ox + u * ux + n * nx, oy + u * uy + n * ny
        pts.append([round(240 - x if lado == "i" else x, 3), round(y, 3)])
    return pts


def zona_cabeza(lado):
    """Rectangulo (espacio del cuerpo) a lo largo del arranque de la linea (u de 0,2 a 19, n de -2 a 3,5): ahi la tapa cubre SIEMPRE, con o sin la oreja encima (la oreja gira y deja ver
    una astilla de la linea justo debajo del trazo de arriba); es la base de la oreja, que nunca es contorno de la cabeza contra el fondo."""
    ox, oy = LINEA_O
    dx, dy = LINEA_F[0] - ox, LINEA_F[1] - oy
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    pts = []
    for u, n in ((0.2, -2.0), (19.0, -2.0), (19.0, 3.5), (0.2, 3.5)):
        x, y = ox + u * ux + n * nx, oy + u * uy + n * ny
        pts.append([round(240 - x if lado == "i" else x, 3), round(y, 3)])
    return pts


def capa_tapa_cabeza(sil, ind, nm, lado):
    t = capa_tapa(sil, ind, nm)
    t.pop("tt", None)           # sin mate de oreja: solo la zona fija
    pts = zona_cabeza(lado)
    t["hasMask"] = True
    t.setdefault("masksProperties", []).append({"inv": False, "mode": "i", "pt": {"a": 0, "k": camino(pts, [[0, 0]] * 4, [[0, 0]] * 4)},
                                               "o": {"a": 0, "k": 100}, "x": {"a": 0, "k": 0}, "nm": "Arranque"})
    return t


def capa_trazo_arriba(sil, ind, nm, lado):
    t = copy.deepcopy(sil)
    t.update({"ind": ind, "nm": nm, "cl": "tapa-oreja"})
    t.pop("tt", None); t.pop("td", None)
    pts = forma_arriba(lado)
    t["shapes"] = [grupo(nm, [trazo_sh(camino(pts, [[0, 0]] * len(pts), [[0, 0]] * len(pts))), fl(BORDE_ORIG)])]
    return t


def capa_trazo_abajo(sil, ind, nm, lado):
    t = copy.deepcopy(sil)      # nombre "silueta-abajo-*": el recoloreo lo trata como contorno (borde)
    t.update({"ind": ind, "nm": nm, "cl": "tapa-oreja"})
    t.pop("tt", None); t.pop("td", None)
    for g in t["shapes"]:
        g["it"] = [it for it in g.get("it", []) if it.get("ty") != "fl"]
    pts = forma_abajo(lado)
    t["hasMask"] = True
    t.setdefault("masksProperties", []).append({"inv": False, "mode": "i", "pt": {"a": 0, "k": camino(pts, [[0, 0]] * len(pts), [[0, 0]] * len(pts))},
                                               "o": {"a": 0, "k": 100}, "x": {"a": 0, "k": 0}, "nm": "Cuña abajo"})
    return t


def capa_tapa(sil, ind, nm, region=None):
    """region: camino (v/i/o/c) de la zona donde la oreja se ve cuando la propia oreja ya trae un mate de recorte (estado_atascado: oreja-d-mate); mismo espacio del cuerpo que la silueta."""
    t = copy.deepcopy(sil)
    t.update({"ind": ind, "nm": nm, "cl": "tapa-oreja", "tt": 3})
    t.pop("td", None)
    for g in t["shapes"]:
        g["it"] = [it for it in g.get("it", []) if it.get("ty") != "fl"]
        for it in g["it"]:
            if it.get("ty") == "st":
                it["c"] = {"a": 0, "k": list(CUERPO_RGB)}
                it["o"] = {"a": 0, "k": 100}
                it["w"] = {"a": 0, "k": GROSOR_TAPA}
    if region is not None:
        t["hasMask"] = True
        t.setdefault("masksProperties", []).append({"inv": False, "mode": "i", "pt": {"a": 0, "k": copy.deepcopy(region)}, "o": {"a": 0, "k": 100}, "x": {"a": 0, "k": 0}, "nm": "Region oreja"})
    return t


def mate_oreja(ore, ind, nm):
    m = copy.deepcopy(ore)
    m.update({"ind": ind, "nm": nm, "cl": "tapa-oreja", "td": 1})
    m.pop("tt", None)
    for g in m["shapes"]:
        for it in g.get("it", []):
            if it.get("ty") == "fl":
                it["c"] = {"a": 0, "k": [1, 1, 1, 1]}
                it["o"] = {"a": 0, "k": 100}
            elif it.get("ty") == "st":
                it["c"] = {"a": 0, "k": [0, 0, 0, 1]}
                it["o"] = {"a": 0, "k": 100}
                it["w"] = {"a": 0, "k": 2 * INSET_OREJA}
    return m


def region_de(por, ore, sil):
    """Si la oreja esta recortada por un mate propio (tt=1, capa "<oreja>-mate" con un rectangulo estatico en el mismo espacio de la silueta), devuelve su camino; si no, None."""
    if ore.get("tt") != 1:
        return None
    mt = por.get(ore["nm"] + "-mate")
    if mt is None or mt.get("ks") != sil["ks"] or mt.get("parent") != sil.get("parent"):
        raise ValueError("la oreja " + ore["nm"] + " tiene un mate que no se sabe copiar")
    sh = [i for g in mt["shapes"] for i in g.get("it", []) if i.get("ty") == "sh"]
    if len(sh) != 1 or sh[0]["ks"].get("a") != 0:
        raise ValueError("el mate de " + ore["nm"] + " no es un camino estatico")
    return sh[0]["ks"]["k"]


def tapa_orejas(d):
    """Agrega (o reconstruye, idempotente): justo encima de la silueta, de arriba abajo, tapa-oreja-d-mate, tapa-oreja-d, tapa-oreja-i-mate, tapa-oreja-i; y al tope de la lista los
    4 trazos (trazo-arriba-d/i y silueta-abajo-d/i), por encima de rayas y parpados."""
    capas = d["layers"]
    por = {l.get("nm"): l for l in capas}
    if "silueta" not in por or "oreja-d" not in por or "oreja-i" not in por:
        return []
    sil = por["silueta"]
    sig = [max(l["ind"] for l in capas) + 1]

    def ind_de(nm):
        if nm in por:
            return por[nm]["ind"]
        sig[0] += 1
        return sig[0] - 1

    deseadas, trazos = [], []
    for lado in ("d", "i"):
        nm = TAPA + lado
        ind_m = ind_de(nm + "-mate")
        ind_t = ind_de(nm)
        deseadas.append(capa_tapa_cabeza(sil, ind_de(nm + "-cabeza"), nm + "-cabeza", lado))
        deseadas.append(mate_oreja(por["oreja-" + lado], ind_m, nm + "-mate"))
        deseadas.append(capa_tapa(sil, ind_t, nm, region_de(por, por["oreja-" + lado], sil)))
    for lado in ("d", "i"):
        trazos.append(capa_trazo_arriba(sil, ind_de("trazo-arriba-" + lado), "trazo-arriba-" + lado, lado))
    for lado in ("d", "i"):
        trazos.append(capa_trazo_abajo(sil, ind_de("silueta-abajo-" + lado), "silueta-abajo-" + lado, lado))
    resto = [l for l in capas if not str(l.get("nm", "")).startswith(TAPA) and l.get("nm") not in NOMBRES_TRAZOS]
    pos = next(n for n, l in enumerate(resto) if l.get("nm") == "silueta")
    final = trazos + resto[:pos] + deseadas + resto[pos:]
    if json.dumps(final, sort_keys=True) == json.dumps(capas, sort_keys=True):
        return []
    capas[:] = final
    return [TAPA + "d", TAPA + "i"] + list(NOMBRES_TRAZOS)


def sellar(d):
    """Pone SELLO_META dentro de d["meta"] (lo crea si falta). Idempotente: devuelve ["meta"] solo si cambio algo."""
    m = d.get("meta")
    if not isinstance(m, dict):
        m = d["meta"] = {}
    if all(m.get(k) == v for k, v in SELLO_META.items()):
        return []
    m.update(SELLO_META)
    return ["meta"]


def procesar(ruta, seco=False):
    d = json.load(open(ruta, encoding="utf-8"))
    hecho = None if os.path.basename(ruta) in EXCLUIR else agregar_capas(d)
    marca = sellar(d)
    if hecho is None and not marca:
        return None
    hecho = (hecho or []) + marca
    if hecho and not seco:
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return hecho


def agregar_capas(d):
    if d.get("w") != 360:
        return None
    capas = d["layers"]
    por = {l.get("nm"): l for l in capas}
    if "silueta" not in por:
        return None
    cuerpo = por["CUERPO (aplastar / saltar)"]["ind"]
    sil = por["silueta"]
    forma_sil = [i for i in sil["shapes"][0]["it"] if i["ty"] == "sh"][0]["ks"]["k"]
    nuevo_ind = max(l["ind"] for l in capas) + 1
    hecho = []

    def idx(nm):
        return next(n for n, l in enumerate(capas) if l.get("nm") == nm)

    # ---- pupilas (encima del ojo, debajo de los parpados) ---- (solo si la animacion tiene los ojos de siempre: "atascado" con ojos nuevos no)
    for lado, cx in (("d", 152), ("i", 88)) if "ojo-d" in por else ():
        nm = "pupila-" + lado
        # el ojo "pro" del SVG es un poco mas grande que el liso de la animacion (rx 8.4 ry 9.2 contra 7.4 y 8.6) y mas crema:
        # va debajo de la pupila, dentro de la misma capa, asi solo se ve en gatoPro
        pro = grupo("ojo-pro", [elipse(cx, 158, 8.4 * 2 * K, 9.2 * 2 * K), fl(CREMA)])
        if nm in por:   # ya estaba: solo se completa (corridas anteriores no traian el ojo grande)
            g = por[nm]["shapes"]
            if not any(x.get("nm") == "ojo-pro" for x in g):
                g.append(pro)
                hecho.append(nm + "+ojo-pro")
            continue
        ojo = por["ojo-" + lado]
        sh = [grupo("brillo", [elipse(cx + 2 * K, 158 - 1.6 * K, 1.9 * 2 * K, 1.9 * 2 * K), fl(BLANCO)]),
              grupo("pupila", [elipse(cx, 158 + 0.6 * K, 5.4 * 2 * K, 5.4 * 2 * K), fl(CUERPO_RGB)]),
              pro]
        c = capa(nuevo_ind, nm, "pupila", ojo["parent"], ojo["ks"], sh, ojo["ip"], ojo["op"], ojo.get("st", 0), copy.deepcopy(ojo.get("masksProperties")))
        nuevo_ind += 1
        capas.insert(idx("ojo-" + lado), c)
        hecho.append(nm)

    # ---- esmoquin (encima de la silueta, debajo de cola/mejillas/ojos) ----
    if "esmoquin" not in por:
        sh = [grupo("patita-i", [elipse(45 * K, 104 * K, 6.5 * 2 * K, 3.6 * 2 * K), fl(PECHO)]),
              grupo("patita-d", [elipse(75 * K, 104 * K, 6.5 * 2 * K, 3.6 * 2 * K), fl(PECHO)]),
              grupo("pecho", [trazo_sh(forma_pecho()), fl(PECHO)])]
        c = capa(nuevo_ind, "esmoquin", "esmoquin", cuerpo, sil["ks"], sh, sil["ip"], sil["op"], sil.get("st", 0), mascaras_de(sil, forma_sil))
        nuevo_ind += 1
        capas.insert(idx("silueta"), c)
        hecho.append("esmoquin")

    # ---- rayas (encima de todo, como en el SVG: tambien tapan los parpados) ----
    if "rayas" not in por and "parpado-d" in por and "parpado-i" in por:
        sh = [grupo("raya-%d" % n, [trazo_sh(cuna(*r)), fl(RAYA)]) for n, r in enumerate(RAYAS)]
        c = capa(nuevo_ind, "rayas", "rayas", cuerpo, sil["ks"], sh, sil["ip"], sil["op"], sil.get("st", 0))   # sin mascara propia: el mate de abajo las recorta
        c["ks"]["o"] = {"a": 0, "k": 85}   # el SVG las dibuja con opacity .85
        nuevo_ind += 1
        pos = min(idx("parpado-d"), idx("parpado-i"))
        capas.insert(pos, c)
        hecho.append("rayas")

    # ---- mate de las rayas (5.a vuelta): recorta las rayas a la silueta, sin pisar el contorno ----
    hecho.extend(mate_de_rayas(d))
    hecho.extend(quitar_mate_parpados(d))   # (7.a vuelta) los parpados vuelven a como estaban antes del mate de la 6.a vuelta
    hecho.extend(tapa_orejas(d))
    return hecho


if __name__ == "__main__":
    seco = "--seco" in sys.argv
    total = 0
    for ruta in sorted(glob.glob(os.path.join(LOT, "*.json"))):
        r = procesar(ruta, seco)
        if r is None:
            print("  (sin tocar) " + os.path.basename(ruta))
        else:
            total += len(r)
            print(("  agregadas " + ", ".join(r)) if r else "  ya estaba", "->", os.path.basename(ruta))
    print(("SECO: " if seco else "") + "capas nuevas: %d" % total)

