# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(27-oct) Prueba de las 2 mejoras de "ultimos" (ideas de clawd #1062 y #1018) SIN Telegram real, sin el hub vivo y sin tocar la cola
ni las sesiones reales: todo el estado va a una carpeta temporal y `api` del hub es un mock que solo anota las llamadas.

  1) cerrar el aviso cuando respondes directo en la PC: el hook real recibe UserPromptSubmit -> cola -> procesar_cola del hub -> los botones
     de Telegram de ese chat quedan en "✓ Respondiste en la PC"; lo que Kodama mismo entrego (buzon o puente) no cierra nada dos veces.
  2) "pensando" vs "ejecutando": el hook ligero (PreToolUse) y el hook completo (PostToolUse / UserPromptSubmit / Stop) y la lectura del hub.
  3) (28-oct) la etiqueta con que Kodama entrega un mensaje al chat ("📱 Nombre (Kodama, responde aquí): ", en/es) y su deteccion, incluida la antigua.
No imprime textos de mensajes ni claves. Uso: python probar_ultimos.py"""
import io, json, os, shutil, sys, tempfile, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import config  # noqa: E402
import companero_hook as hook  # noqa: E402
import companero_hook_pre as pre  # noqa: E402
import companero_hub as h  # noqa: E402

mal = []


def ver(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))
    if not ok:
        mal.append(nombre)
        if os.environ.get("GITHUB_ACTIONS") == "true":   # (28-oct) anotacion visible sin login: la prueba falla a veces solo en CI
            print(f"::error title=probar_ultimos::{nombre}: {obtenido!r} (esperado {esperado!r})"[:400].replace("\n", " "))


tmp = tempfile.mkdtemp(prefix="kodama-prueba-")
try:
    # ---- carpeta temporal: el hook y el hub escriben/leen aqui
    cola, ses, fase, resp = (os.path.join(tmp, x) for x in ("cola.jsonl", "sesiones", "fase", "respuestas.jsonl"))
    os.makedirs(ses)
    hook.COLA, hook.SES, hook.FASE_DIR = cola, ses, fase
    pre.BASE = fase
    h.COLA, h.FASE_DIR, h.RESP = cola, fase, resp
    h.log = lambda m: None
    llamadas = []
    h.api = lambda metodo, **p: (llamadas.append((metodo, p)) or {"ok": True})
    h.guardar_conf = lambda c: None
    h.mirando_claude = lambda: False
    h.segundos_sin_uso = lambda: 9999
    SID, CMD = "prueba-ultimos-0001", "chatx"
    h.sesiones = lambda: [{"session_id": SID, "estado": "trabajando"}]
    h.info = lambda s: (CMD, "Chat X", "🐱") if s else None

    def ent(ev, **k):
        d = {"hook_event_name": ev, "session_id": SID, "cwd": AQUI, "transcript_path": f"C:/x/{config.clave_carpeta(os.path.join(os.path.expanduser('~'), 'Videos', 'Rol'))}/{SID}.jsonl"}   # (28-oct) mismo valor en Windows (C--Users-<u>-Videos-Rol); en macOS la clave empieza con "-"
        d.update(k)
        return d

    def hook_real(d):
        sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(d).encode("utf-8")), encoding="utf-8")
        hook.main()

    def cola_lineas():
        return [json.loads(l) for l in open(cola, encoding="utf-8").read().splitlines()] if os.path.exists(cola) else []

    def conf_nueva():
        return {"dueno": 1, "modo": "siempre", "pendientes": {CMD: time.time()}, "tg_abiertos": {CMD: [11, 12]}}

    # ============ 2) pensando / ejecutando ============
    print("--- pensando / ejecutando")
    ahora = 1000.0
    ver("fase_parse ejecutando reciente", h.fase_parse("ejecutando|comando|995.0", ahora), ("ejecutando", "comando"))
    ver("fase_parse ejecutando a los 60 s sigue", h.fase_parse("ejecutando|web|940.0", ahora), ("ejecutando", "web"))
    ver("fase_parse ejecutando a los 61 s vuelve a pensando", h.fase_parse("ejecutando|subagente|939.0", ahora), ("pensando", None))
    ver("fase_parse pensando", h.fase_parse("pensando||990.0", ahora), ("pensando", None))
    ver("fase_parse categoria rara -> herramienta", h.fase_parse("ejecutando|xx|999.0", ahora), ("ejecutando", "herramienta"))
    ver("fase_parse basura", h.fase_parse("hola", ahora), (None, None))
    # (28-oct) la hora del hook va redondeada a 0.01 s: leida al instante puede quedar unos ms "en el futuro" (o igual, con el reloj de
    # Windows que avanza a saltos de ~16 ms). Eso es ejecutando; una hora muy futura (reloj corrido) no.
    ver("fase_parse: 5 ms en el futuro sigue ejecutando", h.fase_parse("ejecutando|comando|1000.01", 1000.005), ("ejecutando", "comando"))
    ver("fase_parse: hora de la fase igual a ahora", h.fase_parse("ejecutando|web|1000.00", ahora), ("ejecutando", "web"))
    ver("fase_parse: 1 min en el futuro (reloj corrido) -> pensando", h.fase_parse("ejecutando|web|1060.0", ahora), ("pensando", None))
    for tool, esperado in [("Bash", "comando"), ("PowerShell", "comando"), ("WebFetch", "web"), ("WebSearch", "web"), ("Agent", "subagente"), ("Task", "subagente"),
                           ("mcp__claude-in-chrome__navigate", "web"), ("mcp__Claude_Browser__computer", "web"), ("mcp__wp-ejemplo__wp_list_posts", "herramienta"),
                           ("Read", ""), ("Edit", ""), ("Grep", "")]:
        ver(f"categoria {tool}", pre.categoria(tool), esperado)
    ver("hook ligero: lee session_id y tool_name sin json", (pre.valor('{"session_id": "abc-1", "tool_name":"Bash", "tool_input":{"session_id":"otro"}}', "session_id"),
        pre.valor('{"session_id": "abc-1", "tool_name":"Bash"}', "tool_name")), ("abc-1", "Bash"))
    # hook ligero: escribe "ejecutando" (con el proceso real, la salida tiene que quedar vacia)
    import subprocess
    r = subprocess.run([sys.executable, "-I", "-S", "-c", f"import sys; sys.path.insert(0, r'{AQUI}'); import companero_hook_pre as p; p.BASE = r'{fase}'; p.main()"],
                       input=json.dumps(ent("PreToolUse", tool_name="Bash", tool_input={"command": "x"})).encode(), capture_output=True, timeout=20)
    ver("hook ligero: codigo 0 y sin salida", (r.returncode, r.stdout, r.stderr), (0, b"", b""))
    ver("hub: ejecutando un comando", h.fase_de({"session_id": SID, "estado": "trabajando"}), ("ejecutando", "comando"))
    ver("hub: si el chat no trabaja, sin fase", h.fase_de({"session_id": SID, "estado": "termino"}), (None, None))
    hook_real(ent("PostToolUse", tool_name="Bash", tool_input={"command": "x"}, tool_response={}))
    ver("PostToolUse -> pensando", h.fase_de({"session_id": SID, "estado": "trabajando"}), ("pensando", None))
    r = json.load(open(os.path.join(ses, SID + ".json"), encoding="utf-8"))
    ver("PostToolUse sigue anotando 'haciendo'", r.get("haciendo"), "corriendo un comando")
    ver("el estado principal sigue siendo el de siempre", r.get("estado"), None)   # PostToolUse no lo cambia
    hook_real(ent("UserPromptSubmit", prompt="hola"))
    r = json.load(open(os.path.join(ses, SID + ".json"), encoding="utf-8"))
    ver("UserPromptSubmit: estado trabajando y fase pensando", (r.get("estado"), h.fase_de(r)), ("trabajando", ("pensando", None)))
    hook_real(ent("Stop", last_assistant_message="listo"))
    ver("Stop borra la fase", os.path.exists(os.path.join(fase, SID + ".txt")), False)
    # sesion con id raro: no escribe fuera de la carpeta
    hook.fase_escribir("PostToolUse", "../x")
    ver("id con ../ no escribe fuera de fase", os.path.exists(os.path.join(tmp, "x.txt")), False)

    # ============ 1) cerrar el aviso al responder en la PC ============
    print("--- cerrar el aviso al responder en la PC")
    if os.path.exists(cola):
        os.remove(cola)
    # un aviso del sistema (fin de subagente): el hook ya no lo manda a la cola
    hook_real(ent("UserPromptSubmit", prompt="<task-notification>algo</task-notification>"))
    ver("aviso del sistema no llega a la cola", len(cola_lineas()), 0)
    # (a) tu mensaje en la PC
    hook_real(ent("UserPromptSubmit", prompt="ok, sigue por favor"))
    ver("tu mensaje llega a la cola", [x["evento"] for x in cola_lineas()], ["UserPromptSubmit"])
    conf = conf_nueva()
    h.ESPERA[:] = [{"session_id": SID, "ts": time.time() - 5, "evento": "Stop", "texto": "viejo"}, {"session_id": "otra", "ts": time.time() - 5, "evento": "Stop", "texto": "otro chat"}]
    llamadas.clear()
    pos = h.procesar_cola(conf, 0)
    ver("2 botones cerrados con '✓ Respondiste en la PC'", [(m, p["message_id"], json.loads(p["reply_markup"]) if isinstance(p["reply_markup"], str) else p["reply_markup"]) for m, p in llamadas][0][:2], ("editMessageReplyMarkup", 11))
    ver("texto del boton", {(p["reply_markup"]["inline_keyboard"][0][0]["text"]) for m, p in llamadas}, {"✓ Respondiste en la PC"})
    ver("cantidad de llamadas = avisos abiertos", len(llamadas), 2)
    ver("el chat deja de contar pendiente y sin avisos abiertos", (CMD in conf["pendientes"], CMD in conf["tg_abiertos"]), (False, False))
    ver("el aviso sin enviar de ese chat se descarto (el de otro chat sigue)", [x["session_id"] for x in h.ESPERA], ["otra"])
    # (b) el mismo evento otra vez: nada que cerrar, ni error
    h.ESPERA.clear(); llamadas.clear()
    h.procesar_cola(conf, 0)
    ver("duplicado: cero llamadas", len(llamadas), 0)
    # (c) un mensaje que entrego Kodama (buzon, con su marca) no cierra
    os.remove(cola)
    hook_real(ent("UserPromptSubmit", prompt="📱 LShinox (Kodama, responde aquí): OK, adelante."))
    conf = conf_nueva(); llamadas.clear()
    h.procesar_cola(conf, 0)
    ver("buzon de Kodama (etiqueta nueva, es): no cierra (ya lo cerro Kodama al responder)", (len(llamadas), CMD in conf["tg_abiertos"]), (0, True))
    # (28-oct) las demas formas de la etiqueta: mascota, ingles y la antigua (quedo en transcripts); ninguna cierra
    for nombre_caso, prompt in [("mascota, es", "🐾 LShinox (Kodama, responde aquí): Sigue."),
                                ("celular, en", "📱 LShinox (Kodama, reply here): OK, go ahead."),
                                ("mascota, en", "🐾 LShinox (Kodama, reply here): Carry on."),
                                ("antigua, celular", "📱 [LShinox, desde el celular, con Kodama; contéstale aquí en este chat] OK, adelante."),
                                ("antigua, mascota", "🐾 [LShinox, desde la mascota del escritorio, con Kodama; contéstale aquí en este chat] Sigue.")]:
        os.remove(cola)
        hook_real(ent("UserPromptSubmit", prompt=prompt))
        conf = conf_nueva(); llamadas.clear()
        h.procesar_cola(conf, 0)
        ver(f"etiqueta {nombre_caso}: no cierra", len(llamadas), 0)
    # lo que escribes tu (aunque empiece con el emoji, o diga "Kodama") NO es una entrega de Kodama: sigue cerrando
    for nombre_caso, prompt in [("emoji suelto", "📱 hola, ya lo vi"), ("sin dos puntos", "📱 LShinox (Kodama, responde aquí) ya"),
                                ("texto parecido", "Kodama, responde aquí: ok"), ("etiqueta en medio", "ok 📱 LShinox (Kodama, reply here): x")]:
        os.remove(cola)
        hook_real(ent("UserPromptSubmit", prompt=prompt))
        conf = conf_nueva(); llamadas.clear()
        h.procesar_cola(conf, 0)
        ver(f"tuyo ({nombre_caso}): si cierra", len(llamadas), 2)
    # (d) puente: sin marca, pero Kodama lo registro en respuestas.jsonl hace segundos
    os.remove(cola)
    open(resp, "w", encoding="utf-8").write(json.dumps({"ts": time.time() - 3, "evento": "yo", "chat": CMD, "texto": "Sigue con lo que ibas.", "via": "telegram"}) + "\n")
    hook_real(ent("UserPromptSubmit", prompt="Sigue con lo que ibas."))
    conf = conf_nueva(); llamadas.clear()
    h.procesar_cola(conf, 0)
    ver("puente (igual a una respuesta de Kodama): no cierra", len(llamadas), 0)
    # (e) sesion que no es de Kodama: nada, sin error
    os.remove(cola)
    h.info = lambda s: None
    hook_real(ent("UserPromptSubmit", prompt="hola"))
    conf = conf_nueva(); llamadas.clear()
    h.procesar_cola(conf, 0)
    ver("chat que Kodama no sigue: cero llamadas, sin error", len(llamadas), 0)
    h.info = lambda s: (CMD, "Chat X", "🐱") if s else None
    # (f) sin avisos abiertos: no se toca nada
    os.remove(cola)
    hook_real(ent("UserPromptSubmit", prompt="otra cosa"))
    conf = {"dueno": 1, "modo": "siempre"}; llamadas.clear()
    h.procesar_cola(conf, 0)
    ver("sin avisos abiertos: cero llamadas", len(llamadas), 0)
    # (g) el cierre por Telegram de siempre no cambio
    conf = conf_nueva(); llamadas.clear()
    h.cerrar_avisos(conf, CMD, "ok")
    ver("cierre por Telegram: etiqueta de siempre", {p["reply_markup"]["inline_keyboard"][0][0]["text"] for m, p in llamadas}, {"✓ Respondiste: ok"})
    ver("EN: traduccion de la etiqueta nueva", h._EN.get("✓ Respondiste en la PC"), "✓ You replied on the PC")

    # ============ 3) la etiqueta que antepone entregar() ============
    print("--- etiqueta de entrega")
    import kodama_plataforma as plat

    class Buzon:
        def __init__(self): self.datos = b""
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def write(self, b): self.datos += b

    def lo_que_entrega(marca, idioma):
        """Llama a entregar() con un buzon falso y devuelve el texto que le habria llegado al chat."""
        b, guardado = Buzon(), (config.IDIOMA, config.NOMBRE, plat.es_ruta_buzon, plat.abrir_buzon, h.por_puente)
        try:
            config.IDIOMA, config.NOMBRE = idioma, "LShinox"
            plat.es_ruta_buzon, plat.abrir_buzon, h.por_puente = (lambda r: True), (lambda r: b), (lambda s, t: False)
            err = h.entregar({"socket": "x", "token": "t"}, "hola", marca)
        finally:
            config.IDIOMA, config.NOMBRE, plat.es_ruta_buzon, plat.abrir_buzon, h.por_puente = guardado
        lineas = [json.loads(l) for l in b.datos.decode("utf-8").splitlines()]
        return err, (lineas[1]["message"]["content"] if len(lineas) == 2 else None)

    for marca, idioma, esperado in [("📱 ", "es", "📱 LShinox (Kodama, responde aquí): hola"), ("🐾 ", "es", "🐾 LShinox (Kodama, responde aquí): hola"),
                                    ("📱 ", "en", "📱 LShinox (Kodama, reply here): hola"), ("🐾 ", "en", "🐾 LShinox (Kodama, reply here): hola")]:
        err, texto = lo_que_entrega(marca, idioma)
        ver(f"entregar {marca.strip()} {idioma}: etiqueta", (err, texto), (None, esperado))
        ver(f"entregar {marca.strip()} {idioma}: Kodama la reconoce como suya", h.entregado_por_kodama(texto, CMD), True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nTODO BIEN" if not mal else "\nFALLARON: " + ", ".join(mal))
sys.exit(1 if mal else 0)
