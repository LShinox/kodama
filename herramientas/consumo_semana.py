# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Consumo de esta PC desde el reinicio semanal (vie 17-oct 23:00 Ecuador = 18-oct 04:00 UTC), por dia local y por modelo.
Unidades ponderadas del estimador (mismo criterio que consumo_hoy.py). Incluye transcripts de subagentes."""
import datetime, glob, json, os
INICIO = datetime.datetime(2026, 10, 18, 4, 0, tzinfo=datetime.timezone.utc)
EC = datetime.timezone(datetime.timedelta(hours=-5))
PESO = lambda m: 5 if ("opus" in m or "fable" in m) else 3 if "sonnet" in m else 1 if "haiku" in m else 3
def costo(u, m):
    return PESO(m) * (u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0) + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0))
vistos, por_dia, por_modelo_hoy, por_hora_hoy, chats_hoy = set(), {}, {}, {}, {}
hoy = datetime.datetime.now(EC).date()
for ruta in glob.glob(os.path.join(os.path.expanduser("~"), ".claude", "projects", "**", "*.jsonl"), recursive=True):
    if os.path.getmtime(ruta) < INICIO.timestamp():
        continue
    with open(ruta, encoding="utf-8", errors="ignore") as f:
        for l in f:
            if '"usage"' not in l:
                continue
            try:
                x = json.loads(l)
            except ValueError:
                continue
            ts = x.get("timestamp") or ""
            try:
                t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if t < INICIO:
                continue
            m = x.get("message") or {}
            mid = m.get("id")
            if not mid or mid in vistos:
                continue
            vistos.add(mid)
            mod = m.get("model") or ""
            if mod.startswith("<"):
                continue
            c = costo(m.get("usage") or {}, mod)
            loc = t.astimezone(EC)
            por_dia[loc.date()] = por_dia.get(loc.date(), 0) + c
            if loc.date() == hoy:
                por_modelo_hoy[mod] = por_modelo_hoy.get(mod, 0) + c
                por_hora_hoy[loc.hour] = por_hora_hoy.get(loc.hour, 0) + c
                k = ruta.split(os.sep + "projects" + os.sep)[1][:60]
                chats_hoy[k] = chats_hoy.get(k, 0) + c
tot = sum(por_dia.values())
print("SEMANA (esta PC):", round(tot / 1e6, 1), "M")
for d in sorted(por_dia):
    print(" ", d, round(por_dia[d] / 1e6, 1), "M", f"{por_dia[d] / tot * 100:.0f}%")
print("HOY por modelo:", {k: round(v / 1e6, 1) for k, v in sorted(por_modelo_hoy.items(), key=lambda z: -z[1])})
print("HOY por hora:", {h: round(v / 1e6, 1) for h, v in sorted(por_hora_hoy.items())})
th = sum(chats_hoy.values())
for k, v in sorted(chats_hoy.items(), key=lambda z: -z[1])[:6]:
    print(f"  {v / th * 100:4.0f}%  {k}")
