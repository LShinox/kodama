# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct) Prueba del uso EXACTO del plan que Claude Code le pasa a la statusLine (rate_limits.five_hour / seven_day).
Todo en carpetas temporales: NO toca estado\\, hub.log, ~\\.claude\\settings.json ni config.json reales, y no necesita el hub.
Cubre:
  1) uso.json fresco -> valores exactos (con la hora de reinicio) y el pedido al Medidor NO sale;
  2) uso.json viejo, ausente, roto o con la ventana ya reiniciada -> el estimador, como siempre (y el Medidor sale si toca);
  3) companero_uso.py encadena la statusLine anterior (mismo stdin, su salida tal cual) y sin anterior imprime lo de siempre;
  4) instalar.py: sin statusLine pone la de Kodama; con una propia la guarda en config.json, la encadena y al quitar la devuelve.
No imprime claves ni textos de mensajes. Uso: python probar_limites.py"""
import json, os, shutil, sys, tempfile, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import estimador  # noqa: E402
import kodama_medidor as km  # noqa: E402
import companero_uso as uso  # noqa: E402

fallos = []


def ok(nombre, cond, extra=""):
    print(("OK   " if cond else "FALLA"), nombre, ("" if cond else extra))
    if not cond:
        fallos.append(nombre)


TMP = tempfile.mkdtemp(prefix="kodama-limites-")
try:
    ahora = time.time()
    f_uso = os.path.join(TMP, "uso.json")

    def escribir(d):
        json.dump(d, open(f_uso, "w", encoding="utf-8"))

    rei5, rei7 = int(ahora + 3 * 3600), int(ahora + 4 * 86400)

    # ---------- 1) fresco: exacto ----------
    escribir({"ts": ahora - 30, "5h": {"pct": 23.4, "reinicia": rei5}, "semana": {"pct": 61, "reinicia": rei7}})
    u = km.uso_statusline(f_uso, ahora)
    ok("fresco: 5 h exacto con su reinicio", bool(u) and u["5h"] == {"pct": 23.4, "reinicia": rei5}, str(u))
    ok("fresco: semana exacta con su reinicio", bool(u) and u["semana"] == {"pct": 61, "reinicia": rei7}, str(u))
    escribir({"ts": ahora - 30, "5h": {"pct": 150, "reinicia": "%s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ahora + 7200))}})
    u = km.uso_statusline(f_uso, ahora)
    ok("fresco: reinicio en texto ISO y % recortado a 100", bool(u) and u["5h"]["pct"] == 100 and abs(u["5h"]["reinicia"] - (ahora + 7200)) < 2 and "semana" not in u, str(u))

    # ---------- 2) viejo / ausente / roto / ventana reiniciada ----------
    escribir({"ts": ahora - 3600, "5h": {"pct": 23, "reinicia": rei5}, "semana": {"pct": 61, "reinicia": rei7}})
    ok("viejo (1 h): None", km.uso_statusline(f_uso, ahora) is None)
    escribir({"ts": ahora - 10, "5h": {"pct": 23, "reinicia": int(ahora - 5)}, "semana": {"pct": 61, "reinicia": rei7}})
    u = km.uso_statusline(f_uso, ahora)
    ok("5 h ya reiniciada: se descarta solo esa ventana", bool(u) and "5h" not in u and u["semana"]["pct"] == 61, str(u))
    escribir({"ts": ahora - 10, "5h": {"pct": 23, "reinicia": int(ahora - 5)}})
    ok("todas reiniciadas: None", km.uso_statusline(f_uso, ahora) is None)
    os.remove(f_uso)
    ok("ausente: None", km.uso_statusline(f_uso, ahora) is None)
    open(f_uso, "w").write("{no es json")
    ok("roto: None", km.uso_statusline(f_uso, ahora) is None)
    escribir({"ts": ahora - 5, "5h": {"pct": "mucho", "reinicia": rei5}, "semana": {"pct": 10}})
    ok("campos mal formados: None", km.uso_statusline(f_uso, ahora) is None)

    # ---------- combinar ----------
    est = {"ts": ahora, "base_ts": ahora - 9999, "5h": {"pct": 90, "estimado": True}, "semana": {"pct": 50, "estimado": True}}
    c = km.combinar_uso({"ts": ahora - 5, "5h": {"pct": 20, "reinicia": rei5}, "semana": {"pct": 61, "reinicia": rei7}}, est)
    ok("combinar: exacto manda y la marca dice exacto", c["exacto"] is True and c["5h"]["pct"] == 20 and "estimado" not in c["5h"]
       and c["fuente"] == "statusline" and "base_ts" not in c, str(c))
    c = km.combinar_uso({"ts": ahora - 5, "5h": {"pct": 20, "reinicia": rei5}}, est)
    ok("combinar: una ventana exacta y otra estimada -> exacto False", c["exacto"] is False and c["semana"]["estimado"] and c["5h"]["pct"] == 20, str(c))
    c = km.combinar_uso(None, est)
    ok("combinar: sin exacto = el estimador, marcado estimado", c["exacto"] is False and c["5h"]["pct"] == 90 and "fuente" not in c, str(c))
    ok("combinar: nada de nada = None", km.combinar_uso(None, None) is None)

    # ---------- hilo: el Medidor solo sale sin dato fresco ----------
    pedidos, avisos = [], []
    resp = {"5h": {"pct": 90, "estimado": True}, "semana": {"pct": 50, "estimado": True}, "ts": ahora, "base_ts": ahora - 9999}
    orig = {n: getattr(km, n) for n in ("pedir_medicion", "segundos_sin_uso", "lectura_exacta_activa", "log", "USO_JSON")}
    o_act, o_est = estimador.actualizar, estimador.estimar
    try:
        km.pedir_medicion = lambda *a, **k: pedidos.append(1)
        km.segundos_sin_uso = lambda: 9999
        km.lectura_exacta_activa = lambda: True
        km.log = lambda m: avisos.append(m)
        km.USO_JSON = f_uso
        estimador.actualizar = lambda: None
        estimador.estimar = lambda app: dict(resp)

        km._EST.update(v=None, pedido5h=0)
        escribir({"ts": time.time() - 20, "5h": {"pct": 31, "reinicia": rei5}, "semana": {"pct": 62, "reinicia": rei7}})
        km._ciclo_estimar()
        v = km.uso_plan()
        ok("hilo, dato fresco: uso_plan es el exacto (5 h, semana, reinicio, exacto)", v["5h"]["pct"] == 31 and v["semana"]["pct"] == 62
           and v["5h"]["reinicia"] == rei5 and v["exacto"] is True, str(v))
        ok("hilo, dato fresco: NO se pide lectura al Medidor (aunque el estimado pase de 80 %)", pedidos == [], str(pedidos))

        km._EST.update(v=None, pedido5h=0)
        escribir({"ts": time.time() - 7200, "5h": {"pct": 31, "reinicia": rei5}, "semana": {"pct": 62, "reinicia": rei7}})
        km._ciclo_estimar()
        v = km.uso_plan()
        ok("hilo, dato viejo: vuelve al estimador (estimado, exacto False)", v["5h"]["pct"] == 90 and v["5h"]["estimado"] and v["exacto"] is False, str(v))
        ok("hilo, dato viejo: el Medidor se pide como antes", pedidos == [1], str(pedidos))

        km._EST.update(v=None, pedido5h=0)
        pedidos.clear(); os.remove(f_uso)
        km._ciclo_estimar()
        ok("hilo, sin uso.json: igual que antes (estimador + Medidor)", km.uso_plan()["5h"]["estimado"] and pedidos == [1])
    finally:
        for n, f in orig.items():
            setattr(km, n, f)
        estimador.actualizar, estimador.estimar = o_act, o_est
        km._EST.update(v=None, pedido5h=0)

    # ---------- 3) companero_uso.py: encadenado ----------
    sesion = {"model": {"display_name": "Prueba"}, "rate_limits": {"five_hour": {"used_percentage": 23.4, "resets_at": rei5},
                                                                      "seven_day": {"used_percentage": 61, "resets_at": rei7}}}
    raw = json.dumps(sesion).encode("utf-8")
    f2 = os.path.join(TMP, "uso2.json")
    PY = sys.executable.replace("\\", "/")

    out = uso.main(raw, {}, f2)
    ok("sin statusLine previa: imprime la linea de siempre", out == "5h 23% · semana 61%".encode("utf-8"), repr(out))
    g = json.load(open(f2, encoding="utf-8"))
    ok("sin previa: escribe uso.json con la forma de siempre", g["5h"] == {"pct": 23.4, "reinicia": rei5} and g["semana"]["pct"] == 61 and "ts" in g, str(g))
    ok("sin previa y sin rate_limits: no imprime nada y no escribe", uso.main(b'{"model": {}}', {}, os.path.join(TMP, "nada.json")) == b""
       and not os.path.exists(os.path.join(TMP, "nada.json")))
    ok("sin previa y stdin roto: no imprime nada", uso.main(b"no json", {}, os.path.join(TMP, "nada.json")) == b"")

    os.remove(f2)
    previa = {"type": "command", "padding": 2,
              "command": f'"{PY}" -c "import json,sys; d=json.load(sys.stdin); print(\'PREV[\' + d[\'model\'][\'display_name\'] + \']\')"'}
    out = uso.main(raw, previa, f2)
    ok("con previa: imprime la salida del comando anterior, con el mismo stdin", out.decode("utf-8").strip() == "PREV[Prueba]", repr(out))
    ok("con previa: igual anota el uso", os.path.exists(f2) and json.load(open(f2, encoding="utf-8"))["5h"]["pct"] == 23.4)
    out = uso.main(raw, {"type": "command", "command": f'"{PY}" -c "import sys; sys.exit(3)"'}, f2)
    ok("con previa que falla: no rompe (salida vacia)", out == b"", repr(out))
    out = uso.main(raw, {"type": "command", "command": "python " + os.path.join(AQUI, "companero_uso.py")}, f2)
    ok("previa que es Kodama misma: no se llama a si misma", out == b"", repr(out))

    # ---------- 4) instalar.py ----------
    sys.argv = [sys.argv[0]]
    import instalar as ins  # noqa: E402
    ins_set, ins_cfg, ins_pyv, ins_aqui, ins_prueba = ins.SETTINGS, ins.CONFIG_JSON, ins.PYV, ins.AQUI, ins.PRUEBA
    D = os.path.join(TMP, "inst")
    os.makedirs(D)
    ins.SETTINGS, ins.CONFIG_JSON, ins.PRUEBA = os.path.join(D, "settings.json"), os.path.join(D, "config.json"), False
    ins.PYV, ins.AQUI = "C:/kodama/.venv/Scripts/python.exe", "C:/kodama"

    def leer(r):
        return json.load(open(r, encoding="utf-8"))

    try:
        # a) sin settings.json
        ins.tocar_settings(True)
        s = leer(ins.SETTINGS)
        ok("instalar sin statusLine: pone la de Kodama", s["statusLine"]["command"] == '"C:/kodama/.venv/Scripts/python.exe" "C:/kodama/companero_uso.py"', str(s.get("statusLine")))
        ok("instalar sin statusLine: no guarda ninguna previa", not os.path.exists(ins.CONFIG_JSON) or "statusline_previa" not in leer(ins.CONFIG_JSON))
        ins.tocar_settings(False)
        ok("quitar: saca la statusLine y los hooks de Kodama", "statusLine" not in leer(ins.SETTINGS) and "hooks" not in leer(ins.SETTINGS))

        # b) con statusLine propia (y otras cosas del usuario que no se tocan)
        suya = {"type": "command", "command": 'bash ~/.claude/mi-barra.sh', "padding": 1}
        json.dump({"theme": "dark", "statusLine": suya, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mi-hook"}]}]}},
                  open(ins.SETTINGS, "w", encoding="utf-8"))
        json.dump({"url_publica": "x", "chats": []}, open(ins.CONFIG_JSON, "w", encoding="utf-8"))
        ins.tocar_settings(True)
        s, c = leer(ins.SETTINGS), leer(ins.CONFIG_JSON)
        ok("instalar con statusLine propia: queda la de Kodama (conserva padding)", "companero_uso.py" in s["statusLine"]["command"] and s["statusLine"]["padding"] == 1, str(s["statusLine"]))
        ok("instalar con statusLine propia: la suya se guarda en config.json, sin perder el resto", c.get("statusline_previa") == suya and c["url_publica"] == "x", str(c))
        ok("instalar: lo demas de settings.json sigue (theme y el hook ajeno)", s["theme"] == "dark" and any("mi-hook" in json.dumps(e) for e in s["hooks"]["Stop"]))
        ok("instalar: respaldo de settings.json hecho", any(n.startswith("settings.json.bak-companero-") for n in os.listdir(D)))
        ins.tocar_settings(True)   # repetir no la pisa
        c = leer(ins.CONFIG_JSON)
        ok("reinstalar: la statusLine guardada sigue siendo la del usuario (no la de Kodama)", c.get("statusline_previa") == suya, str(c))
        ins.tocar_settings(False)
        s, c = leer(ins.SETTINGS), leer(ins.CONFIG_JSON)
        ok("quitar: vuelve la statusLine del usuario, tal cual", s["statusLine"] == suya, str(s.get("statusLine")))
        ok("quitar: se borra la previa de config.json y el hook ajeno queda", "statusline_previa" not in c and s["hooks"]["Stop"][0]["hooks"][0]["command"] == "mi-hook")

        # c) en --prueba no se toca nada
        antes = (open(ins.SETTINGS, "rb").read(), open(ins.CONFIG_JSON, "rb").read())
        ins.PRUEBA = True
        ins.tocar_settings(True)
        ok("--prueba: no cambia settings.json ni config.json", antes == (open(ins.SETTINGS, "rb").read(), open(ins.CONFIG_JSON, "rb").read()))
        ins.PRUEBA = False
    finally:
        ins.SETTINGS, ins.CONFIG_JSON, ins.PYV, ins.AQUI, ins.PRUEBA = ins_set, ins_cfg, ins_pyv, ins_aqui, ins_prueba
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("TODO BIEN" if not fallos else "FALLARON: " + ", ".join(fallos))
sys.exit(1 if fallos else 0)
