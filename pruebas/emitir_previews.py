# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
"""Prints the preview crops of capturas_mac.py (previews.json) as GitHub annotations, in pieces of 3900 characters, because one annotation holds at most
~4 KB and the artifact itself cannot be downloaded without logging in (the annotations of a public run can be read through the API).
Usage: python emitir_previews.py <previews.json> <lote> [por_lote]   (a step can show at most 10 annotations of each kind: one step per lote)
Title of each piece: pv<image>.<piece>/<pieces> <name>. The message is the base64 piece. Test aid only: the workflow runs it just when the commit message has [previews]."""
import json
import sys

TROZO = 3900


def main():
    ruta, lote = sys.argv[1], int(sys.argv[2])
    por = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    try:
        with open(ruta) as f:
            prev = json.load(f)
    except Exception as e:
        print("no previews:", e)
        return 0
    piezas = []
    for i, p in enumerate(prev):
        b = p["jpg_b64"]
        n = (len(b) + TROZO - 1) // TROZO
        for k in range(n):
            piezas.append(("pv%02d.%d/%d %s" % (i + 1, k + 1, n, p["nombre"]), b[k * TROZO:(k + 1) * TROZO]))
    for t, m in piezas[lote * por:(lote + 1) * por]:
        print("::notice title=%s::%s" % (t, m), flush=True)
    if lote == 0:
        print("total pieces:", len(piezas), "images:", len(prev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
