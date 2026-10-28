# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Genera los iconos de la app (180 y 512 px) con el Gato finalista: cara negra minimalista,
ojos crema con pupila, sobre fondo claro. Dibuja los mismos caminos SVG del personaje (viewBox 120)."""
import re
from PIL import Image, ImageDraw

N = (31, 28, 34)
CREMA = (255, 244, 222)
FONDO = (246, 241, 231)
CUERPO = "M60 105 C34 105 20 99 20 80 C20 67 23 59 28 53 L48 41.5 Q60 38.5 72 41.5 L92 53 C97 59 100 67 100 80 C100 99 86 105 60 105 Z"
OI = "M26 57 L30.5 33.5 Q31.5 27.5 36.5 31 L51 43 L54 68 L29 72 Z"
OD = "M94 57 L89.5 33.5 Q88.5 27.5 83.5 31 L69 43 L66 68 L91 72 Z"


def puntos(d, pasos=40):
    toks = re.findall(r"[MLCQZ]|-?\d+(?:\.\d+)?", d)
    pts, i, cur, cmd = [], 0, (0, 0), None
    while i < len(toks):
        if toks[i] in "MLCQZ":
            cmd = toks[i]; i += 1
            if cmd == "Z":
                continue
        n = {"M": 2, "L": 2, "Q": 4, "C": 6}[cmd]
        v = list(map(float, toks[i:i + n])); i += n
        if cmd in "ML":
            cur = (v[0], v[1]); pts.append(cur)
        elif cmd == "Q":
            p0, p1, p2 = cur, (v[0], v[1]), (v[2], v[3])
            for k in range(1, pasos + 1):
                t = k / pasos
                pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
            cur = p2
        else:
            p0, p1, p2, p3 = cur, (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
            for k in range(1, pasos + 1):
                t = k / pasos
                a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                pts.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
            cur = p3
    return pts


def icono(tam, ruta):
    S = 4 * tam                      # se dibuja a 4x y se achica (bordes suaves)
    im = Image.new("RGB", (S, S), FONDO)
    d = ImageDraw.Draw(im)
    # encuadre: la cara ocupa ~78 % del ancho, centrada (zona segura de iOS)
    esc = S * 0.70 / 82              # 82 = ancho util del gato (x 19..101)
    ox = S / 2 - 60 * esc
    oy = S / 2 - 67 * esc             # centro vertical del gato con orejas (y 27..106)
    T = lambda p: (ox + p[0] * esc, oy + p[1] * esc)
    for camino in (OI, OD, CUERPO):
        d.polygon([T(p) for p in puntos(camino)], fill=N)
    for cx in (44, 76):
        cy = 79
        d.ellipse([T((cx - 8.4, cy - 9.2)), T((cx + 8.4, cy + 9.2))], fill=CREMA)
        d.ellipse([T((cx - 5.6, cy + .6 - 5.6)), T((cx + 5.6, cy + .6 + 5.6))], fill=N)
        d.ellipse([T((cx + 2 - 1.9, cy - 1.6 - 1.9)), T((cx + 2 + 1.9, cy - 1.6 + 1.9))], fill=(255, 255, 255))
    im.resize((tam, tam), Image.LANCZOS).save(ruta)


for t, r in ((180, "web/icono-180.png"), (512, "web/icono-512.png"), (640, "estado/avatar-bot-640.png")):
    icono(t, r)
print("ok")
