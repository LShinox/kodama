# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov-2026) Preferencias que valen para todos los aparatos: horas de silencio y avisos del limite del plan.
Se guardan en estado\\preferencias.json. Sin dependencias de otros kodama_* salvo el nucleo, para que cualquiera lo importe."""
import json
import os
import re
import time

from kodama_nucleo import BASE

PREFS = os.path.join(BASE, "preferencias.json")
DEFECTO = {"silencio": {"activo": False, "desde": "22:00", "hasta": "07:00", "urgentes": False}, "alertas_uso": True, "telegram_avisos": True, "pausas": {"activo": True, "agua_min": 60, "levantarse_min": 50}}
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
UMBRALES = (80, 95, 100)
ULTIMA_ALERTA = {}   # la ultima alerta de uso, para que el gato reaccione: {"k", "umbral", "pct", "ts", "texto"}
ULTIMO_EVENTO = {}   # el ultimo aviso de integraciones o correo, para el gato: {"ts", "titulo", "texto"}


def leer(ruta=None):
    """Preferencias con los valores por defecto para lo que falte o este roto."""
    p = {"silencio": dict(DEFECTO["silencio"]), "alertas_uso": DEFECTO["alertas_uso"], "telegram_avisos": DEFECTO["telegram_avisos"], "pausas": dict(DEFECTO["pausas"])}
    try:
        d = json.load(open(ruta or PREFS, encoding="utf-8"))
    except (OSError, ValueError):
        return p
    if not isinstance(d, dict):
        return p
    s = d.get("silencio")
    if isinstance(s, dict):
        if isinstance(s.get("activo"), bool):
            p["silencio"]["activo"] = s["activo"]
        if isinstance(s.get("urgentes"), bool):
            p["silencio"]["urgentes"] = s["urgentes"]
        for k in ("desde", "hasta"):
            if isinstance(s.get(k), str) and _HORA.match(s[k]):
                p["silencio"][k] = s[k]
    if isinstance(d.get("alertas_uso"), bool):
        p["alertas_uso"] = d["alertas_uso"]
    if isinstance(d.get("telegram_avisos"), bool):   # (06-nov) False = los avisos no se copian al bot; la app sigue avisando
        p["telegram_avisos"] = d["telegram_avisos"]
    _mezclar_pausas(p, d.get("pausas"))
    return p


def _mezclar_pausas(p, x):
    """(06-nov) Recordatorios de agua y de levantarse: activo y minutos entre 10 y 240. Lo invalido se ignora."""
    if not isinstance(x, dict):
        return
    if isinstance(x.get("activo"), bool):
        p["pausas"]["activo"] = x["activo"]
    for k in ("agua_min", "levantarse_min"):
        if isinstance(x.get(k), int) and not isinstance(x.get(k), bool) and 10 <= x[k] <= 240:
            p["pausas"][k] = x[k]


def guardar(cambios, ruta=None):
    """Mezcla lo valido de `cambios` con lo guardado y lo escribe. Lo invalido se ignora. Devuelve el resultado."""
    ruta = ruta or PREFS
    p = leer(ruta)
    s = cambios.get("silencio") if isinstance(cambios, dict) else None
    if isinstance(s, dict):
        for k in ("activo", "urgentes"):
            if isinstance(s.get(k), bool):
                p["silencio"][k] = s[k]
        for k in ("desde", "hasta"):
            if isinstance(s.get(k), str) and _HORA.match(s[k]):
                p["silencio"][k] = s[k]
    if isinstance(cambios, dict) and isinstance(cambios.get("alertas_uso"), bool):
        p["alertas_uso"] = cambios["alertas_uso"]
    if isinstance(cambios, dict) and isinstance(cambios.get("telegram_avisos"), bool):
        p["telegram_avisos"] = cambios["telegram_avisos"]
    if isinstance(cambios, dict):
        _mezclar_pausas(p, cambios.get("pausas"))
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(tmp, ruta)
    return p


def _minutos(h):
    return int(h[:2]) * 60 + int(h[3:])


def en_silencio(sil, ahora=None):
    """True si la hora local cae en el tramo [desde, hasta). Cruza la medianoche si desde > hasta; desde == hasta = nunca."""
    if not sil.get("activo"):
        return False
    t = time.localtime(time.time() if ahora is None else ahora)
    m, a, b = t.tm_hour * 60 + t.tm_min, _minutos(sil["desde"]), _minutos(sil["hasta"])
    if a == b:
        return False
    return a <= m < b if a < b else (m >= a or m < b)


def silencio_ahora(tipo=None, ruta=None, ahora=None):
    """¿Hay que callar este aviso? Con "urgentes" pasan los permisos y las preguntas."""
    s = leer(ruta)["silencio"]
    if not en_silencio(s, ahora):
        return False
    return not (s.get("urgentes") and tipo in ("permiso", "pregunta"))


def estado_silencio(ruta=None, ahora=None):
    """Lo que necesita el gato: (en silencio ahora, dejan pasar urgentes)."""
    s = leer(ruta)["silencio"]
    return en_silencio(s, ahora), bool(s.get("urgentes"))


def alertas_nuevas(uso, previo):
    """Funcion pura. Compara el uso con lo ya avisado y devuelve (alertas, previo nuevo).
    alertas = [{"k": "5h"|"semana", "umbral", "pct", "estimado", "reinicia"}]. Por ventana sale solo el umbral mas alto recien cruzado.
    Se rearma cuando el uso baja 5 puntos o mas por debajo del umbral avisado (la ventana se reinicio)."""
    nuevo, salen = dict(previo or {}), []
    for k in ("5h", "semana"):
        x = (uso or {}).get(k)
        if not isinstance(x, dict) or not isinstance(x.get("pct"), (int, float)) or isinstance(x.get("pct"), bool):
            continue
        pct, avisado = x["pct"], (nuevo.get(k) or 0)
        alto = max([u for u in UMBRALES if pct >= u] or [0])
        if avisado and pct < avisado - 5:
            avisado = alto
        if alto > avisado:
            salen.append({"k": k, "umbral": alto, "pct": pct, "estimado": bool(x.get("estimado")), "reinicia": x.get("reinicia")})
            avisado = alto
        nuevo[k] = avisado
    return salen, nuevo
