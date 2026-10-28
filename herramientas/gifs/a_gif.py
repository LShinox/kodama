# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Cuadros PNG -> GIF liviano (paleta adaptiva comun, sin dither). Uso: a_gif.py <carpeta> <salida.gif> <ms> [cada] [escala]"""
import glob, os, sys
from PIL import Image
carpeta, salida, ms = sys.argv[1], sys.argv[2], int(sys.argv[3])
cada = int(sys.argv[4]) if len(sys.argv) > 4 else 1
escala = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
fs = sorted(glob.glob(os.path.join(carpeta, "f*.png")))[::cada]
ims = [Image.open(f).convert("RGB") for f in fs]
if escala != 1:
    ims = [im.resize((int(im.width * escala), int(im.height * escala)), Image.LANCZOS) for im in ims]
# una paleta para todos (sacada de un mosaico de varios cuadros): sin parpadeo de colores entre cuadros
muestra = Image.new("RGB", (ims[0].width, ims[0].height * min(6, len(ims))))
for i, im in enumerate(ims[:: max(1, len(ims) // 6)][:6]):
    muestra.paste(im, (0, i * ims[0].height))
pal = muestra.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in ims]
q[0].save(salida, save_all=True, append_images=q[1:], duration=ms * cada, loop=0, optimize=True, disposal=1)
print(os.path.basename(salida), len(q), "cuadros,", round(os.path.getsize(salida) / 1024), "KB")
