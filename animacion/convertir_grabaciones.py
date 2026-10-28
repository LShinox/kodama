# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
# Convierte animacion/grabaciones/*.json (matrices SVG por cuadro, grabadas del codigo GSAP) en
# animacion/datos_animacion.json (fotogramas clave por capa de AE, simplificados) y animacion/rig_capas.json (rig v2).
# Rutas con barras normales (nunca "\a", "\n" dentro de strings de ruta).
import json, math, glob, os, re

BASE = os.path.dirname(os.path.abspath(__file__)).replace(os.sep, "/") + "/"
FPS = 30
TOL = {"p": 0.3, "r": 0.5, "s": 0.5, "o": 1.0, "t": 1.0}

NULO_MUEVE = "MUEVE (inclinar / saltar / gestos)"
NULO_CUERPO = "CUERPO (aplastar / saltar)"
NULO_OJOS = "OJOS (mirar)"

# --------------------------------------------------------------- rig v2
def rig_v2():
    src = open(BASE + "armar_gato.jsx", encoding="utf-8").read()
    m = re.search(r"var CAPAS = (\[.*?\]), ESTADOS =", src, re.S)
    capas = json.loads(m.group(1))
    por = {c["n"]: c for c in capas}
    # pivotes = origen que usa GSAP (svgOrigin x2) para que girar/escalar a mano gire donde gira el codigo
    por["oreja-i"]["piv"] = [76, 96]
    por["oreja-d"]["piv"] = [164, 96]
    por["parpado-i"]["piv"] = [88, 139.6]
    por["parpado-d"]["piv"] = [152, 139.6]
    por["cola-atras"]["piv"] = [176, 196]
    por["sombra"]["grad"] = True      # degradado radial aproximado con anillos
    por["sombra"]["op"] = 100
    for n in ("cola-frente (borde)", "cola-frente"):
        por[n]["trim"] = True
    ojos = {"ojo-i", "ojo-d", "feliz-i", "feliz-d", "dormido-i", "dormido-d"}
    for c in capas:
        if c["n"] == "sombra":
            c["padre"] = None
        elif c["n"] in ojos:
            c["padre"] = NULO_OJOS
        else:
            c["padre"] = NULO_CUERPO
    # linea del piso (la dibuja el codigo debajo del gato): capa nueva justo encima de la sombra
    piso = {"n": "piso", "stroke": [0.549, 0.5176, 0.5804], "sw": 3.2, "piv": [120, 211.2], "op": 0, "padre": None,
            "formas": [{"v": [[44.0, 211.2], [196.0, 211.2]], "i": [[0, 0], [0, 0]], "o": [[0, 0], [0, 0]], "cerrado": False}]}
    capas.insert(1, piso)
    nulos = [
        {"n": NULO_MUEVE, "ap": [130.22, 210], "padre": None},
        {"n": NULO_CUERPO, "ap": [130.22, 210], "padre": NULO_MUEVE},
        {"n": NULO_OJOS, "ap": [120, 158], "padre": NULO_CUERPO},
    ]
    json.dump({"capas": capas, "nulos": nulos}, open(BASE + "rig_capas.json", "w", encoding="utf-8"), ensure_ascii=False)
    return capas

# --------------------------------------------------------------- matrices
def comps_mat(M, pivAE):
    a, b, c, d, e, f = M
    px, py = pivAE[0] / 2.0, pivAE[1] / 2.0
    sx = math.hypot(a, b)
    rot = math.degrees(math.atan2(b, a)) if sx > 0.02 else None
    sy = (a * d - b * c) / sx if sx > 1e-6 else math.hypot(c, d)
    pos = (2 * (a * px + c * py + e), 2 * (b * px + d * py + f))
    return pos, rot, sx * 100.0, sy * 100.0

def desenrollar(rot):
    # rellena None con el vecino conocido y quita saltos de 360
    n = len(rot)
    conocidos = [i for i, v in enumerate(rot) if v is not None]
    if not conocidos:
        return [0.0] * n
    for i in range(n):
        if rot[i] is None:
            j = min(conocidos, key=lambda k: abs(k - i))
            rot[i] = rot[j]
    out = [rot[0]]
    for i in range(1, n):
        d = rot[i] - out[-1]
        d = (d + 180.0) % 360.0 - 180.0
        out.append(out[-1] + d)
    return out

# --------------------------------------------------------------- RDP (con tiempo, interpolacion lineal)
def simplificar(serie, tol):
    # serie: lista de tuplas (valores por componente) por cuadro. devuelve indices a conservar
    n = len(serie)
    if n <= 2:
        return list(range(n))
    nd = len(serie[0])
    keep = {0, n - 1}
    pila = [(0, n - 1)]
    while pila:
        s, e = pila.pop()
        worst, wi = 0.0, -1
        for i in range(s + 1, e):
            u = (i - s) / float(e - s)
            err = max(abs(serie[i][k] - (serie[s][k] + (serie[e][k] - serie[s][k]) * u)) / tol for k in range(nd))
            if err > worst:
                worst, wi = err, i
        if worst > 1.0:
            keep.add(wi); pila.append((s, wi)); pila.append((wi, e))
    return sorted(keep)

def propiedad(serie, tol, dec=3):
    """serie: lista de tuplas. Devuelve {'v': [...]} si es constante o {'k': [[t, v...], ...]}."""
    nd = len(serie[0])
    ref = serie[0]
    if all(max(abs(v[k] - ref[k]) for k in range(nd)) <= tol * 0.5 for v in serie):
        return {"v": [round(x, dec) for x in ref]}
    idx = simplificar(serie, tol)
    return {"k": [[round(i / float(FPS), 4)] + [round(x, dec) for x in serie[i]] for i in idx]}

# --------------------------------------------------------------- capas -> datos
PIV_SVG = {}  # se llena con el rig (en AE)

def capa_mat(frames, clave, pivAE, op_fn=None, trim_clave=None):
    pos, rot, sx, sy = [], [], [], []
    for fr in frames:
        M = fr[clave] if isinstance(clave, str) else clave(fr)
        p, r, a, b = comps_mat(M, pivAE)
        pos.append(p); rot.append(r); sx.append(a); sy.append(b)
    rot = desenrollar(rot)
    out = {"p": propiedad(pos, TOL["p"]), "r": propiedad([(x,) for x in rot], TOL["r"]),
           "s": propiedad(list(zip(sx, sy)), TOL["s"])}
    return out

def convertir(nombre, d, capas):
    fr = d["frames"][: d["N"]]          # cuadros 0..N-1 ; comp = N/30 s
    piv = {c["n"]: c["piv"] for c in capas if "piv" in c}
    ap = {NULO_MUEVE: [130.22, 210], NULO_CUERPO: [130.22, 210], NULO_OJOS: [120, 158]}
    L = {}
    # sombra
    L["sombra"] = capa_mat(fr, lambda f: f["sb"][0], piv["sombra"])
    L["sombra"]["o"] = propiedad([(min(100.0, 100.0 * f["sb"][1]),) for f in fr], TOL["o"])
    # piso
    L["piso"] = {"s": propiedad([((f["pi"][1] - f["pi"][0]) / 76.0 * 100.0, 100.0) for f in fr], TOL["s"]),
                 "o": propiedad([(f["pi"][2] * 100.0,) for f in fr], TOL["o"])}
    # nulos
    L[NULO_MUEVE] = capa_mat(fr, "mu", ap[NULO_MUEVE])
    L[NULO_CUERPO] = capa_mat(fr, "cu", ap[NULO_CUERPO])
    L[NULO_OJOS] = capa_mat(fr, "oj", ap[NULO_OJOS])
    # ojos / expresiones
    for i, lado in enumerate(("i", "d")):
        L["ojo-" + lado] = capa_mat(fr, lambda f, i=i: f["ojo"][i], piv["ojo-" + lado])
        L["ojo-" + lado]["o"] = propiedad([(f["ojo"][2] * 100.0,) for f in fr], TOL["o"])
        for nom, k in (("feliz-", "fe"), ("dormido-", "dr")):
            L[nom + lado] = capa_mat(fr, lambda f, k=k: f[k][0], piv[nom + lado])
            L[nom + lado]["o"] = propiedad([(f[k][1] * 100.0,) for f in fr], TOL["o"])
    # orejas / parpados (lids) / cola atras
    L["oreja-i"] = capa_mat(fr, "oi", piv["oreja-i"]); L["oreja-d"] = capa_mat(fr, "od", piv["oreja-d"])
    L["parpado-i"] = capa_mat(fr, "li", piv["parpado-i"]); L["parpado-d"] = capa_mat(fr, "ld", piv["parpado-d"])
    L["cola-atras"] = capa_mat(fr, "ca", piv["cola-atras"])
    # cola de frente (acurrucada): opacidad y trazo (trim)
    for nom, ti in (("cola-frente (borde)", 0), ("cola-frente", 1)):
        fin = [max(0.0, min(100.0, (1.0 - f["tz"][ti]) * 100.0)) for f in fr]
        op = [(f["cfo"] * 100.0 if fin[i] > 0.3 else 0.0,) for i, f in enumerate(fr)]
        L[nom] = {"o": propiedad(op, TOL["o"]), "t": propiedad([(x,) for x in fin], TOL["t"])}
    # mejillas
    for i, lado in enumerate(("i", "d")):
        L["mejilla-" + lado] = {"o": propiedad([(f["mj"][i] * 100.0,) for f in fr], TOL["o"])}
    nk = 0
    for c in L.values():
        for p in c.values():
            if "k" in p:
                nk += len(p["k"])
    return {"dur": round(d["N"] / float(FPS), 4), "N": d["N"], "L": L}, nk

def main():
    capas = rig_v2()
    datos, resumen = {}, {}
    for f in sorted(glob.glob(BASE + "grabaciones/*.json")):
        d = json.load(open(f, encoding="utf-8"))
        out, nk = convertir(d["nombre"], d, capas)
        datos[d["nombre"]] = out
        animadas = sum(1 for c in out["L"].values() if any("k" in p for p in c.values()))
        resumen[d["nombre"]] = (d["N"], nk, animadas)
    json.dump(datos, open(BASE + "datos_animacion.json", "w", encoding="utf-8"), separators=(",", ":"))
    for k, v in resumen.items():
        print(k, "cuadros", v[0], "claves", v[1], "capas animadas", v[2])
    print("datos KB", os.path.getsize(BASE + "datos_animacion.json") // 1024)

main()
