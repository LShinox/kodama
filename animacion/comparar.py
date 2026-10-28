# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
# Compara verificacion/<comp>_fNNN_ae.png contra _nav.png: metricas + montaje (nav | ae | diferencia).
import glob, os, sys, json
import numpy as np
from PIL import Image

V = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verificacion").replace(os.sep, "/") + "/"

def comparar(ae, nav):
    a = np.asarray(Image.open(ae).convert("RGB")).astype(int)
    n = np.asarray(Image.open(nav).convert("RGB")).astype(int)
    d = np.abs(a - n).max(axis=2)
    cat = d[: 206 * 1, :]          # sin la franja de la sombra (y>=206 en px de 240)
    return dict(medio=round(float(d.mean()), 2), pct24=round(float((d > 24).mean() * 100), 2),
                pct24_sinsombra=round(float((cat > 24).mean() * 100), 2)), a, n, d

def montaje(ae, nav, d, destino):
    m = np.concatenate([n_img(nav), n_img(ae), np.stack([np.clip(d * 3, 0, 255)] * 3, axis=2)], axis=1).astype("uint8")
    Image.fromarray(m).save(destino)

def n_img(x):
    return x

def main(filtro=None):
    res = {}
    for ae in sorted(glob.glob(V + "*_ae.png")):
        nav = ae.replace("_ae.png", "_nav.png")
        base = os.path.basename(ae)[:-7]
        if filtro and not any(base.startswith(f) for f in filtro):
            continue
        if not os.path.exists(nav):
            continue
        m, a, n, d = comparar(ae, nav)
        res[base] = m
        montaje(a, n, d, V + "montaje_" + base + ".png")
    json.dump(res, open(V + "metricas.json", "w"), indent=1)
    for k, v in res.items():
        print(k, v)

if __name__ == "__main__":
    main(sys.argv[1:] or None)
