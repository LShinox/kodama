# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Genera armar_gato.jsx: arma en After Effects el gato del Companero (gatoPro "lisos" de web\\personajes.js)
como capas de forma nativas (lo que Bodymovin exporta a Lottie sin conversiones), una composicion por estado
y una por gesto. Coordenadas del SVG (viewBox 120) x ESCALA. Correr: python generar_aep.py"""
import json, os, re

AQUI = os.path.dirname(os.path.abspath(__file__))
ESCALA = 2                     # comp de 240x240 (viewBox 120 x 2)
N = "#1f1c22"

def hexrgb(h):
    h = h.lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]

def tok(d):
    return re.findall(r"[MLHVCQZmlhvcqz]|-?\d*\.?\d+(?:e-?\d+)?", d)

def svg_a_formas(d):
    """Path SVG (M L H V C Q Z absolutos) -> lista de subtrazos {v, i, o, cerrado} con tangentes relativas."""
    t, k, subs, cur, x, y = tok(d), 0, [], None, 0.0, 0.0
    def num():
        nonlocal k
        k += 1
        return float(t[k - 1])
    cmd = None
    while k < len(t):
        if re.match(r"[A-Za-z]", t[k]):
            cmd = t[k]; k += 1
        if cmd in "Mm":
            x, y = num(), num()
            cur = {"v": [[x, y]], "i": [[0, 0]], "o": [[0, 0]], "cerrado": False}; subs.append(cur); cmd = "L"
        elif cmd == "L":
            x, y = num(), num(); cur["v"].append([x, y]); cur["i"].append([0, 0]); cur["o"].append([0, 0])
        elif cmd == "H":
            x = num(); cur["v"].append([x, y]); cur["i"].append([0, 0]); cur["o"].append([0, 0])
        elif cmd == "V":
            y = num(); cur["v"].append([x, y]); cur["i"].append([0, 0]); cur["o"].append([0, 0])
        elif cmd == "C":
            x1, y1, x2, y2, x3, y3 = (num() for _ in range(6))
            cur["o"][-1] = [x1 - x, y1 - y]
            cur["v"].append([x3, y3]); cur["i"].append([x2 - x3, y2 - y3]); cur["o"].append([0, 0]); x, y = x3, y3
        elif cmd == "Q":
            qx, qy, x3, y3 = (num() for _ in range(4))
            c1 = [x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y)]; c2 = [x3 + 2 / 3 * (qx - x3), y3 + 2 / 3 * (qy - y3)]
            cur["o"][-1] = [c1[0] - x, c1[1] - y]
            cur["v"].append([x3, y3]); cur["i"].append([c2[0] - x3, c2[1] - y3]); cur["o"].append([0, 0]); x, y = x3, y3
        elif cmd in "Zz":
            cur["cerrado"] = True
            v = cur["v"]
            if len(v) > 1 and abs(v[-1][0] - v[0][0]) < 1e-6 and abs(v[-1][1] - v[0][1]) < 1e-6:
                cur["i"][0] = cur["i"][-1]; v.pop(); cur["i"].pop(); cur["o"].pop()
            cmd = None
        else:
            raise ValueError("comando SVG no soportado: %r en %s" % (cmd, d[:40]))
    for s in subs:   # a la escala de la comp
        for key in ("v", "i", "o"):
            s[key] = [[round(a * ESCALA, 3), round(b * ESCALA, 3)] for a, b in s[key]]
    return subs

def P(x, y):
    return [x * ESCALA, y * ESCALA]

# ---- capas, de ABAJO hacia ARRIBA (mismo orden que el SVG) ----
CUERPO = "M60 105 C34 105 20 99 20 80 C20 67 23 59 28 53 L48 41.5 Q60 38.5 72 41.5 L92 53 C97 59 100 67 100 80 C100 99 86 105 60 105 Z"
OI = "M26 57 L30.5 33.5 Q31.5 27.5 36.5 31 L51 43 L54 68 L29 72 Z"
OD = "M94 57 L89.5 33.5 Q88.5 27.5 83.5 31 L69 43 L66 68 L91 72 Z"
COLA_ATRAS = "M88 100 C110 102 119 82 114 63 C111 54 101 56 105 65 C110 78 106 92 86 94"
COLA_FRENTE = "M98 91 C101 101 80 104 58 103.5 C40 103 24 101 18 94 C13 88 14 82 21 80"

def arco(cx, d):
    return "M%g 79 Q%g %g %g 79" % (cx - 8, cx, 79 + d, cx + 8)

CAPAS = [
    # nombre, tipo, datos, relleno, trazo, ancho, pivote (viewBox), opacidad inicial
    {"n": "sombra", "elipse": [60, 109, 34, 4.5], "fill": "#3A3530", "op": 18, "piv": [60, 109], "padre": None},
    {"n": "cola-atras", "path": COLA_ATRAS, "stroke": N, "sw": 8, "piv": [88, 97]},
    {"n": "oreja-i", "path": OI, "fill": N, "stroke": N, "sw": 2, "piv": [40, 62]},
    {"n": "oreja-d", "path": OD, "fill": N, "stroke": N, "sw": 2, "piv": [80, 62]},
    {"n": "silueta", "path": CUERPO, "fill": N, "stroke": N, "sw": 2, "piv": [60, 105]},
    {"n": "cola-frente (borde)", "path": COLA_FRENTE, "stroke": "#5A5364", "sw": 10, "piv": [58, 95], "op": 0},
    {"n": "cola-frente", "path": COLA_FRENTE, "stroke": N, "sw": 8, "piv": [58, 95], "op": 0},
    {"n": "mejilla-i", "elipse": [31, 91, 7.5, 4.4], "fill": "#FF7896", "piv": [31, 91], "op": 0},
    {"n": "mejilla-d", "elipse": [89, 91, 7.5, 4.4], "fill": "#FF7896", "piv": [89, 91], "op": 0},
    {"n": "ojo-i", "elipse": [44, 79, 7.4, 8.6], "fill": "#F4F1EA", "piv": [44, 79]},
    {"n": "ojo-d", "elipse": [76, 79, 7.4, 8.6], "fill": "#F4F1EA", "piv": [76, 79]},
    {"n": "feliz-i", "path": arco(44, -11), "stroke": "#FFF4DE", "sw": 3.4, "piv": [44, 79], "op": 0},
    {"n": "feliz-d", "path": arco(76, -11), "stroke": "#FFF4DE", "sw": 3.4, "piv": [76, 79], "op": 0},
    {"n": "dormido-i", "path": arco(44, 8), "stroke": "#FFF4DE", "sw": 3.4, "piv": [44, 79], "op": 0},
    {"n": "dormido-d", "path": arco(76, 8), "stroke": "#FFF4DE", "sw": 3.4, "piv": [76, 79], "op": 0},
    {"n": "parpado-i", "path": "M31 46 H57 V70.5 Q44 63.5 31 70.5 Z", "fill": N, "piv": [44, 46]},
    {"n": "parpado-d", "path": "M63 46 H89 V70.5 Q76 63.5 63 70.5 Z", "fill": N, "piv": [76, 46]},
]
for c in CAPAS:
    if "path" in c:
        c["formas"] = svg_a_formas(c.pop("path"))
    if "elipse" in c:
        cx, cy, rx, ry = c["elipse"]; c["elipse"] = [cx * ESCALA, cy * ESCALA, 2 * rx * ESCALA, 2 * ry * ESCALA]
    for key in ("fill", "stroke"):
        if key in c:
            c[key] = hexrgb(c[key])
    if "sw" in c:
        c["sw"] = c["sw"] * ESCALA
    c["piv"] = P(*c["piv"])

# estados de la mascota y gestos del gato (nombres de personajes.js), con una duracion inicial en segundos
ESTADOS = [("reposo", 4), ("trabajando", 2), ("escribio", 2), ("enviado", 1.5), ("dormido", 4), ("atascado", 2)]
GESTOS = [("parpadeoLento", 2), ("colita", 2.5), ("bostezo", 2), ("estirarse", 2), ("saltito", 1), ("mirar", 1.5),
          ("ladeo", 1.5), ("radar", 1.5), ("acecho", 3), ("sonrisa", 1.5), ("leer", 1.5), ("pensar", 2),
          ("teclear", 1), ("idea", 1.5), ("balanceo", 2)]

AEP = os.path.join(AQUI, "gato.aep").replace("\\", "/")
JSX = r"""
(function () {
var CAPAS = %(capas)s, ESTADOS = %(estados)s, GESTOS = %(gestos)s, ESCALA = %(escala)s, AEP = "%(aep)s";
var W = 120 * ESCALA, H = 120 * ESCALA, FPS = 30;
var FONDO = [0.93, 0.92, 0.95];
app.beginUndoGroup("Armar gato Companero");
if (!app.project) app.newProject();
var proj = app.project;
function buscarCarpeta(n) { for (var i = 1; i <= proj.numItems; i++) { if (proj.item(i) instanceof FolderItem && proj.item(i).name == n) return proj.item(i); } return proj.items.addFolder(n); }
var fEst = buscarCarpeta("01 estados"), fGes = buscarCarpeta("02 gestos"), fBase = buscarCarpeta("00 rig base");

function armar(comp) {
  // nulo con el pivote en el piso: escalarlo en Y aplasta al gato contra el piso; moverlo en Y lo hace saltar
  var nulo = comp.layers.addNull(); nulo.name = "CUERPO (aplastar / saltar)";
  nulo.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([50, 100]);
  nulo.property("ADBE Transform Group").property("ADBE Position").setValue([60 * ESCALA, 105 * ESCALA]);
  var capas = [];
  for (var i = 0; i < CAPAS.length; i++) {
    var c = CAPAS[i];
    var L = comp.layers.addShape(); L.name = c.n;
    var cont = L.property("ADBE Root Vectors Group");
    var grupo = cont.addProperty("ADBE Vector Group"); grupo.name = c.n;
    var v = grupo.property("ADBE Vectors Group");
    if (c.formas) {
      for (var s = 0; s < c.formas.length; s++) {
        var f = c.formas[s], sh = new Shape();
        sh.vertices = f.v; sh.inTangents = f.i; sh.outTangents = f.o; sh.closed = f.cerrado;
        v.addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(sh);
      }
    } else if (c.elipse) {
      var el = v.addProperty("ADBE Vector Shape - Ellipse");
      el.property("ADBE Vector Ellipse Position").setValue([c.elipse[0], c.elipse[1]]);
      el.property("ADBE Vector Ellipse Size").setValue([c.elipse[2], c.elipse[3]]);
    }
    if (c.stroke) {
      var st = v.addProperty("ADBE Vector Graphic - Stroke");
      st.property("ADBE Vector Stroke Color").setValue(c.stroke);
      st.property("ADBE Vector Stroke Width").setValue(c.sw);
      st.property("ADBE Vector Stroke Line Cap").setValue(2);    // redondo
      st.property("ADBE Vector Stroke Line Join").setValue(2);   // redondo
    }
    if (c.fill) {
      var fi = v.addProperty("ADBE Vector Graphic - Fill");
      fi.property("ADBE Vector Fill Color").setValue(c.fill);
    }
    var tr = L.property("ADBE Transform Group");
    tr.property("ADBE Anchor Point").setValue(c.piv);   // pivote = punto de giro/escala; la forma queda en su lugar
    tr.property("ADBE Position").setValue(c.piv);
    if (c.op !== undefined) tr.property("ADBE Opacity").setValue(c.op);
    capas.push(L);
  }
  // cada capa nueva entra arriba, asi que la primera de la lista ya quedo al fondo (como en el SVG)
  for (var j = 0; j < capas.length; j++) {
    if (CAPAS[j].padre !== null) capas[j].parent = nulo;   // todo cuelga del CUERPO salvo la sombra
  }
  nulo.moveToBeginning();
  return comp;
}

function nuevaComp(nombre, dur, carpeta) {
  for (var i = 1; i <= proj.numItems; i++) { if (proj.item(i) instanceof CompItem && proj.item(i).name == nombre) return null; }
  var comp = proj.items.addComp(nombre, W, H, 1, dur, FPS);
  comp.bgColor = FONDO; comp.parentFolder = carpeta;
  armar(comp);
  return comp;
}

var hechas = [];
if (nuevaComp("gato_rig", 1, fBase)) hechas.push("gato_rig");
for (var e = 0; e < ESTADOS.length; e++) if (nuevaComp("estado_" + ESTADOS[e][0], ESTADOS[e][1], fEst)) hechas.push("estado_" + ESTADOS[e][0]);
for (var g = 0; g < GESTOS.length; g++) if (nuevaComp("gesto_" + GESTOS[g][0], GESTOS[g][1], fGes)) hechas.push("gesto_" + GESTOS[g][0]);
app.endUndoGroup();
proj.save(new File(AEP));
return "comps nuevas: " + hechas.length + " | guardado en " + proj.file.fsName;
})();
"""
open(os.path.join(AQUI, "armar_gato.jsx"), "w", encoding="utf-8").write(JSX % {
    "capas": json.dumps(CAPAS), "estados": json.dumps(ESTADOS), "gestos": json.dumps(GESTOS),
    "escala": ESCALA, "aep": AEP})
print("ok", len(CAPAS), "capas,", len(ESTADOS) + len(GESTOS) + 1, "comps")
