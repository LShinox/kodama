# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Estimador del uso del plan (15-oct-2026, pedido de LShinox: "sin gastar tokens").

El % EXACTO de las 5 h y de la semana solo lo da la app de Claude (lo anota en plan-usage-history.json mientras la
usas, o lo lee un chat con su herramienta get_usage). Cuando ese dato esta viejo, aqui se ESTIMA sin preguntarle nada a
Claude: se suma lo que gastaron todos los chats desde el ultimo dato exacto (cada respuesta queda anotada con sus tokens
en ~\\.claude\\projects\\*\\*.jsonl) y se pasa a % con un factor que se calibra solo comparando los datos exactos
de la app con lo gastado entre ellos. Todo local: no gasta plan.

Costo de una respuesta (unidades propias, solo importan las proporciones): peso del modelo (Opus/Fable 5, Sonnet 3,
Haiku 1, como sus precios) x (entrada + 1,25 x escritura de cache + 0,1 x lectura de cache + 5 x salida).
"""
import datetime
import glob
import json
import os
import re
import time

import config

PROY = os.path.join(config.HOME, ".claude", "projects")
GUARDADO = os.path.join(config.ESTADO, "estimador.json")      # factores calibrados (para no empezar de cero)
EXACTOS = os.path.join(config.ESTADO, "uso_exacto.jsonl")     # lecturas exactas por get_usage (las escribe el medidor)
HORAS = 30

_RE_TS = re.compile(rb'"timestamp"\s*:\s*"([0-9T:\-\.]+)Z?"')
_RE_ID = re.compile(rb'"id"\s*:\s*"(msg_[A-Za-z0-9_]+)"')
_RE_MOD = re.compile(rb'"model"\s*:\s*"([^"]+)"')
_RE_U = re.compile(rb'"(input_tokens|cache_creation_input_tokens|cache_read_input_tokens|output_tokens)"\s*:\s*(\d+)')
_OFF = {}    # archivo -> bytes ya leidos
_EV = {}     # id de mensaje -> (ts, costo)  (Claude Code repite la misma respuesta en varias lineas: se cuenta una vez)


def _ts(b):
    try:
        return datetime.datetime.fromisoformat(b.decode().rstrip("Z") + "+00:00").timestamp()
    except ValueError:
        return None


def _peso(modelo):
    m = modelo.lower()
    return 5 if ("opus" in m or "fable" in m) else 1 if "haiku" in m else 3


def actualizar():
    """Lee lo NUEVO de los transcripts modificados en las ultimas 30 h (la primera vez lee todo eso)."""
    desde = time.time() - HORAS * 3600
    for f in glob.glob(os.path.join(PROY, "**", "*.jsonl"), recursive=True):
        try:
            st = os.stat(f)
        except OSError:
            continue
        if st.st_mtime < desde:
            continue
        off = _OFF.get(f, 0)
        if st.st_size < off:
            off = 0
        if st.st_size == off:
            continue
        try:
            with open(f, "rb") as h:
                h.seek(off)
                datos = h.read()
        except OSError:
            continue
        corte = datos.rfind(b"\n") + 1        # solo lineas completas
        _OFF[f] = off + corte
        for linea in datos[:corte].split(b"\n"):
            i = linea.find(b'"usage"')
            if i < 0 or b'"assistant"' not in linea:
                continue
            mid, ts = _RE_ID.search(linea), _RE_TS.search(linea)
            if not mid or not ts or mid.group(1) in _EV:
                continue
            t = _ts(ts.group(1))
            if not t or t < desde:
                continue
            u = {k.decode(): int(v) for k, v in _RE_U.findall(linea[i:i + 900])}
            mod = _RE_MOD.search(linea)
            costo = _peso(mod.group(1).decode() if mod else "") * (
                u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0)
                + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0))
            _EV[mid.group(1)] = (t, costo)
    for k in [k for k, (t, _) in _EV.items() if t < desde]:
        del _EV[k]


def gasto(t1, t2):
    return sum(c for t, c in _EV.values() if t1 < t <= t2)


def muestras(app_dir):
    """[(ts, pct5h, pctsemana)] exactas de las ultimas 30 h: las de la app + las del medidor, ordenadas."""
    out, desde = [], time.time() - HORAS * 3600
    try:
        txt = open(os.path.join(app_dir, "plan-usage-history.json"), encoding="utf-8").read()
        for m in re.finditer(r'"t"\s*:\s*(\d+)[^}]*?"u"\s*:\s*\{\s*"fh"\s*:\s*([\d.]+)\s*,\s*"sd"\s*:\s*([\d.]+)', txt):
            t = int(m.group(1)) / 1000
            if t >= desde:
                out.append((t, float(m.group(2)), float(m.group(3))))
    except OSError:
        pass
    try:
        for l in open(EXACTOS, encoding="utf-8"):
            d = json.loads(l)
            if d.get("ts", 0) >= desde and d.get("5h") is not None:
                out.append((d["ts"], float(d["5h"]), float(d.get("semana") or 0), d.get("reinicia5h")))
    except (OSError, ValueError):
        pass
    return sorted(out, key=lambda x: x[0])


def calibrar(ms):
    """Factor % por unidad de costo, de pares de muestras seguidas (<= 40 min) donde el % subio sin reiniciarse."""
    try:
        g = json.load(open(GUARDADO, encoding="utf-8"))
    except (OSError, ValueError):
        g = {}
    d5 = dw = c = 0.0
    for a, b in zip(ms, ms[1:]):
        if 0 < b[0] - a[0] <= 2400 and b[1] >= a[1] and b[2] >= a[2]:
            gc = gasto(a[0], b[0])
            if gc > 0:
                d5 += b[1] - a[1]; dw += b[2] - a[2]; c += gc
    nuevo = dict(g)
    if c > 0 and d5 >= 3:   # con poco movimiento el factor no es confiable: se queda el guardado
        nuevo.update(k5=d5 / c, kw=dw / c if dw > 0 else g.get("kw"))
    # (15-oct) mejor: cada lectura exacta del medidor trae cuando se reinicia la ventana de 5 h, o sea cuando EMPEZO
    # (reinicio - 5 h). Entonces % = k x gasto desde el inicio de la ventana: calibracion directa, sin pares.
    # Primera prueba: con pares daba 0,4 % y el real era 4 %; asi da el valor real.
    directos = [(m[1] / gasto(m[3] - 5 * 3600, m[0]), m[0]) for m in ms
                if len(m) > 3 and m[3] and m[1] >= 2 and gasto(m[3] - 5 * 3600, m[0]) > 0]
    if directos:
        nuevo["k5"] = directos[-1][0] if len(directos) == 1 else sum(k for k, _ in directos[-3:]) / len(directos[-3:])
    if nuevo != g:
        nuevo["t"] = time.time()
        tmp = GUARDADO + ".tmp"
        json.dump(nuevo, open(tmp, "w", encoding="utf-8")); os.replace(tmp, GUARDADO)
    return nuevo.get("k5"), nuevo.get("kw")


def estimar(app_dir):
    """{"5h": {"pct", "estimado"}, "semana": {...}, "ts", "base_ts"} o None si no hay con que."""
    ms = muestras(app_dir)
    if not ms:
        return None
    k5, kw = calibrar(ms)
    base = ms[-1]
    ahora = time.time()
    viejo = ahora - base[0]
    if viejo < 1200 or not k5:   # dato exacto fresco (<20 min) o sin factor: lo exacto tal cual
        r = {"ts": base[0], "semana": {"pct": base[2]}}
        if viejo < 5 * 3600:
            r["5h"] = {"pct": base[1]}
        return r
    reinicia = base[3] if len(base) > 3 and base[3] else None
    if reinicia and ahora <= reinicia:   # misma ventana del dato exacto: todo lo gastado desde que empezo
        p5 = k5 * gasto(reinicia - 5 * 3600, ahora)
    elif reinicia and ahora > reinicia:
        p5 = k5 * gasto(reinicia, ahora)
    elif viejo > 5 * 3600:
        p5 = k5 * gasto(ahora - 5 * 3600, ahora)          # la ventana de 5 h ya se reinicio: lo de las ultimas 5 h
    else:
        p5 = base[1] + k5 * gasto(base[0], ahora)
    pw = base[2] + (kw or 0) * gasto(base[0], ahora)
    return {"ts": ahora, "base_ts": base[0], "5h": {"pct": round(min(100, p5), 1), "estimado": True},
            "semana": {"pct": round(min(100, pw), 1), "estimado": True}}
