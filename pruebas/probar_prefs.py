# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov) Horas de silencio y avisos del plan. Sin escribir en el estado real: todo va a una carpeta temporal."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kodama_prefs as kp  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
    else:
        fallos += 1
        print("FALLA:", nombre)


def hora(h, m=0):
    t = list(time.localtime())
    t[3], t[4] = h, m
    return time.mktime(tuple(t))


with tempfile.TemporaryDirectory() as td:
    r = os.path.join(td, "preferencias.json")
    p = kp.leer(r)
    ver("defecto apagado", p["silencio"]["activo"] is False and p["alertas_uso"] is True)
    p = kp.guardar({"silencio": {"activo": True, "desde": "22:30", "hasta": "07:00"}}, r)
    ver("guarda", p["silencio"]["activo"] and p["silencio"]["desde"] == "22:30")
    p = kp.guardar({"silencio": {"desde": "25:00", "activo": "si"}, "alertas_uso": "x", "otro": 1}, r)
    ver("ignora invalido", p["silencio"]["desde"] == "22:30" and p["silencio"]["activo"] is True and p["alertas_uso"] is True and "otro" not in p)
    open(r, "w", encoding="utf-8").write("{roto")
    ver("archivo roto = defecto", kp.leer(r)["silencio"]["activo"] is False)
    open(r, "w", encoding="utf-8").write('["lista"]')
    ver("json raro = defecto", kp.leer(r)["silencio"]["activo"] is False)
    kp.guardar({"silencio": {"activo": True, "desde": "22:00", "hasta": "07:00", "urgentes": True}}, r)
    ver("permiso pasa con urgentes", kp.silencio_ahora("permiso", r, hora(23)) is False)
    ver("pregunta pasa con urgentes", kp.silencio_ahora("pregunta", r, hora(23)) is False)
    ver("termino calla", kp.silencio_ahora("termino", r, hora(23)) is True)
    ver("de dia no calla", kp.silencio_ahora("termino", r, hora(12)) is False)
    kp.guardar({"silencio": {"urgentes": False}}, r)
    ver("permiso calla sin urgentes", kp.silencio_ahora("permiso", r, hora(23)) is True)
    ver("estado", kp.estado_silencio(r, hora(23)) == (True, False))

s = {"activo": True, "desde": "22:00", "hasta": "07:00"}
ver("cruza medianoche 23", kp.en_silencio(s, hora(23)))
ver("cruza medianoche 3", kp.en_silencio(s, hora(3)))
ver("limite hasta excluido", not kp.en_silencio(s, hora(7)))
ver("limite desde incluido", kp.en_silencio(s, hora(22)))
ver("fuera", not kp.en_silencio(s, hora(12)))
ver("tramo de dia", kp.en_silencio({"activo": True, "desde": "09:00", "hasta": "17:00"}, hora(12)))
ver("tramo de dia fuera", not kp.en_silencio({"activo": True, "desde": "09:00", "hasta": "17:00"}, hora(18)))
ver("iguales = nunca", not kp.en_silencio({"activo": True, "desde": "09:00", "hasta": "09:00"}, hora(9)))
ver("apagado", not kp.en_silencio({"activo": False, "desde": "00:00", "hasta": "23:59"}, hora(12)))

sal, pre = kp.alertas_nuevas({"5h": {"pct": 50}}, {})
ver("50 no avisa", sal == [] and pre["5h"] == 0)
sal, pre = kp.alertas_nuevas({"5h": {"pct": 81}}, pre)
ver("80 avisa", len(sal) == 1 and sal[0]["umbral"] == 80)
sal, pre = kp.alertas_nuevas({"5h": {"pct": 83}}, pre)
ver("no repite", sal == [])
sal, pre = kp.alertas_nuevas({"5h": {"pct": 78}}, pre)
ver("oscila sin rearmar", sal == [] and pre["5h"] == 80)
sal, pre = kp.alertas_nuevas({"5h": {"pct": 100, "estimado": True, "reinicia": 123}}, pre)
ver("salta al mas alto, uno solo", len(sal) == 1 and sal[0]["umbral"] == 100 and sal[0]["estimado"] and sal[0]["reinicia"] == 123)
sal, pre = kp.alertas_nuevas({"5h": {"pct": 2}}, pre)
ver("reinicio rearma", sal == [] and pre["5h"] == 0)
sal, pre = kp.alertas_nuevas({"5h": {"pct": 96}, "semana": {"pct": 81}}, pre)
ver("dos ventanas", sorted(a["k"] for a in sal) == ["5h", "semana"])
ver("uso None", kp.alertas_nuevas(None, {"5h": 80}) == ([], {"5h": 80}))
ver("pct raro", kp.alertas_nuevas({"5h": {"pct": True}, "semana": "x"}, {}) == ([], {}))

# (06-nov) copia de avisos al bot de Telegram
_tg = os.path.join(tempfile.mkdtemp(), "p.json")
ver("telegram encendido por defecto", kp.leer(_tg)["telegram_avisos"] is True)
ver("telegram se apaga", kp.guardar({"telegram_avisos": False}, _tg)["telegram_avisos"] is False)
ver("telegram apagado se conserva al guardar otra cosa", kp.guardar({"alertas_uso": False}, _tg)["telegram_avisos"] is False)
ver("telegram con valor invalido no cambia", kp.guardar({"telegram_avisos": "no"}, _tg)["telegram_avisos"] is False)

print(f"{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
