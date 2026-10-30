# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(26-oct) Prueba de las 5 mejoras sin tocar el hub vivo ni el puerto 8787: usa puertos de prueba (18787...) y carpetas temporales.
Cubre: progreso de tareas (hook + hub), estadisticas de "Lo nuevo", puerto de respaldo (elegir_servidor, escribir_puerto, puerto_hub).
No imprime textos de mensajes ni claves. Uso: python probar_mejoras.py"""
import json, os, socket, subprocess, sys, tempfile, time

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import config  # noqa: E402
import companero_hook as hook  # noqa: E402
import companero_hub as h  # noqa: E402

h.log = lambda m: None   # el hub vivo es el unico que escribe hub.log
mal = []


def ver(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))
    if not ok:
        mal.append(nombre)


# ---- 1) progreso de tareas: la secuencia real de un .jsonl (4 TaskCreate, TaskUpdate pending->in_progress->completed)
reg = {}
for i, asunto in enumerate(["Armar el proyecto", "Marca y fondo", "Diez escenas", "Verificar"], 1):
    hook.tareas_actualizar(reg, {"tool_name": "TaskCreate", "tool_input": {"subject": asunto, "description": "x", "activeForm": "y"},
                                 "tool_response": {"task": {"id": str(i), "subject": asunto}}})
ver("4 creadas", (reg["tareas"]["h"], reg["tareas"]["t"]), (0, 4))
hook.tareas_actualizar(reg, {"tool_name": "TaskUpdate", "tool_input": {"taskId": "1", "status": "in_progress"}})
ver("la 1 en curso", (reg["tareas"]["h"], reg["tareas"]["a"]), (0, "Armar el proyecto"))
hook.tareas_actualizar(reg, {"tool_name": "TaskUpdate", "tool_input": {"taskId": "1", "status": "completed"}})
hook.tareas_actualizar(reg, {"tool_name": "TaskUpdate", "tool_input": {"taskId": "2", "status": "completed"}})
hook.tareas_actualizar(reg, {"tool_name": "TaskUpdate", "tool_input": {"taskId": "3", "status": "in_progress"}})
ver("2 de 4, la 3 en curso", (reg["tareas"]["h"], reg["tareas"]["t"], reg["tareas"]["a"]), (2, 4, "Diez escenas"))
hook.tareas_actualizar(reg, {"tool_name": "TaskUpdate", "tool_input": {"taskId": "4", "status": "deleted"}})
ver("borrar una la saca del total", (reg["tareas"]["h"], reg["tareas"]["t"]), (2, 3))
# la respuesta como texto ("Task #5 created successfully: ...") y sin respuesta (siguiente numero)
hook.tareas_actualizar(reg, {"tool_name": "TaskCreate", "tool_input": {"subject": "otra"}, "tool_response": "Task #5 created successfully: otra"})
hook.tareas_actualizar(reg, {"tool_name": "TaskCreate", "tool_input": {"subject": "y otra"}})
ver("ids por texto y por defecto", sorted(reg["tareas"]["items"]), ["1", "2", "3", "5", "6"])
ver("asunto de hasta 80 caracteres", len(reg["tareas"]["a"]) <= 80, True)
hook.tareas_actualizar(reg, {"tool_name": "TodoWrite", "tool_input": {"todos": [{"content": "a", "status": "completed"}, {"content": "b", "status": "in_progress"}, {"content": "c", "status": "pending"}]}})
ver("TodoWrite (version vieja)", (reg["tareas"]["h"], reg["tareas"]["t"], reg["tareas"]["a"]), (1, 3, "b"))

# de punta a punta: el hook real por stdin con una sesion de prueba en una carpeta personal; despues se borra su archivo
sid = "prueba-mejoras-" + str(int(time.time()))
arch = os.path.join(config.ESTADO, "sesiones", sid + ".json")
try:
    carp = sorted(config.PERSONALES)[0] if config.PERSONALES else config.clave_carpeta(os.path.join(os.path.expanduser("~"), "Videos", "Ingenieria-inversa"))
    ent = {"hook_event_name": "PostToolUse", "session_id": sid, "cwd": AQUI, "transcript_path": f"C:/x/{carp}/{sid}.jsonl",
           "tool_name": "TaskCreate", "tool_input": {"subject": "tarea de prueba"}, "tool_response": {"task": {"id": "1"}}}
    subprocess.run([sys.executable, os.path.join(AQUI, "companero_hook.py")], input=json.dumps(ent).encode(), timeout=20, check=False)
    ent.update(tool_name="TaskUpdate", tool_input={"taskId": "1", "status": "in_progress"})
    subprocess.run([sys.executable, os.path.join(AQUI, "companero_hook.py")], input=json.dumps(ent).encode(), timeout=20, check=False)
    r = json.load(open(arch, encoding="utf-8")) if os.path.exists(arch) else {}
    t = r.get("tareas") or {}
    ver("hook real: 0 de 1, en curso", (t.get("h"), t.get("t"), t.get("a"), r.get("haciendo")), (0, 1, "tarea de prueba", "actualizando sus tareas"))
finally:
    if os.path.exists(arch):
        os.remove(arch)
    fase = os.path.join(config.ESTADO, "fase", sid + ".txt")   # (27-oct) el hook real tambien deja estado\fase\<sesion>.txt
    if os.path.exists(fase):
        os.remove(fase)

# el hub: _historial() expone solo {h, t, a} del chat (con la lista de la sesion mas reciente de cada chat, inyectada en memoria)
real = h.sesiones()
h.sesiones = lambda: [dict(s, estado="trabajando", visto=time.time(), tareas={"h": 3, "t": 7, "a": "armando la mascota", "ts": time.time(), "items": {"1": ["h", "SECRETO"]}}) for s in real]   # (30-oct) la lista se muestra solo con el chat trabajando
h._HIST["v"] = None
salida = h._historial()
con = {c: d["tareas"] for c, d in salida.items() if isinstance(d, dict) and "tareas" in d}
ver("el hub expone tareas en al menos un chat", bool(con), True)
ver("y solo h, t, a (nunca la lista)", all(set(v) == {"h", "t", "a"} for v in con.values()), True)
ver("valores", next(iter(con.values()), None), {"h": 3, "t": 7, "a": "armando la mascota"})
h.sesiones = lambda: [dict(s, tareas={"h": 7, "t": 7, "a": "", "ts": time.time() - 3600}) for s in real]
ver("lista terminada hace >30 min: no se muestra", any("tareas" in d for d in h._historial().values() if isinstance(d, dict)), False)
h.sesiones = lambda: real

# ---- 2) lo nuevo + estadisticas (solo numeros)
ln = h.lo_nuevo()
ver("lo_nuevo: version y cambios es/en", (ln["version"] == config.VERSION, sorted((ln["cambios"] or {}).keys())), (True, ["en", "es"]))
ver("3 a 6 cambios en cada idioma", all(3 <= len(ln["cambios"][k]) <= 6 for k in ("es", "en")), True)
ver("estadisticas: 4 numeros", sorted(ln["stats"]), ["avisos", "chats", "respuestas", "respuestas_celular"])
ver("estadisticas: todos enteros", all(isinstance(v, int) for v in ln["stats"].values()), True)
print("   (numeros de la semana:", ln["stats"], ")")

# ---- 3) puerto de respaldo, con puertos de PRUEBA (nunca el 8787)
ocupado = socket.socket(); ocupado.bind(("127.0.0.1", 18787)); ocupado.listen(1)
vistos = []


def escribir(p):
    # en este momento el servidor aun NO escucha: puerto.txt se escribe antes de aceptar conexiones
    vistos.append((p, socket.socket().connect_ex(("127.0.0.1", p)) != 0))


try:
    srv, p = h.elegir_servidor(h.Web, [18787, 18788, 18789], escribir)
    ver("con el 18787 ocupado elige el 18788", p, 18788)
    ver("escribio el puerto UNA vez, ANTES de escuchar", vistos, [(18788, True)])
    ver("despues escucha de verdad", socket.socket().connect_ex(("127.0.0.1", 18788)), 0)
    srv.server_close()
    vistos.clear()

    def escribir_falla(p):
        vistos.append(p)
        if p == 18788:
            raise OSError(13, "EACCES simulado")
    srv, p = h.elegir_servidor(h.Web, [18787, 18788, 18789], escribir_falla)
    ver("si escribir falla en el 18788, sigue con el 18789", (p, vistos), (18789, [18788, 18789]))
    srv.server_close()
    try:
        h.elegir_servidor(h.Web, [18787], escribir)
        ver("sin puertos libres levanta OSError", "no levanto", "OSError")
    except OSError:
        ver("sin puertos libres levanta OSError", "OSError", "OSError")
finally:
    ocupado.close()

# escribir_puerto + re-apuntar el Tailscale propio (con un re-apuntador FALSO: aqui nunca se llama a tailscale)
tmp = tempfile.mkdtemp()
h.PUERTO_TXT = os.path.join(tmp, "puerto.txt")
llamadas = []
h.escribir_puerto(8787, llamadas.append)
ver("8787 y sin archivo previo: no re-apunta", (open(h.PUERTO_TXT).read(), llamadas), ("8787", []))
h.escribir_puerto(8788, llamadas.append)
ver("8788: escribe y re-apunta a 8788", (open(h.PUERTO_TXT).read(), llamadas, h.PUERTO_WEB), ("8788", [8788], 8788))
h.escribir_puerto(8788, llamadas.append)
ver("8788 otra vez (igual que antes): vuelve a re-apuntar por ser != 8787", llamadas, [8788, 8788])
llamadas.clear()
h.escribir_puerto(8787, llamadas.append)
ver("vuelve al 8787 tras estar en 8788: re-apunta de vuelta al 8787", (llamadas, h.PUERTO_WEB), ([8787], 8787))

# config.puerto_hub(): lo que leen la mascota (Rust hace lo mismo) y companero_conectar
config.ESTADO = tmp
for txt, esperado in (("8790", 8790), (" 8799\n", 8799), ("9000", 8787), ("abc", 8787), ("", 8787)):
    open(os.path.join(tmp, "puerto.txt"), "w").write(txt)
    ver(f"puerto_hub({txt.strip()!r})", config.puerto_hub(), esperado)
os.remove(os.path.join(tmp, "puerto.txt"))
ver("puerto_hub sin archivo", config.puerto_hub(), 8787)

print("\n" + ("TODO BIEN" if not mal else "FALLARON: " + ", ".join(mal)))
sys.exit(1 if mal else 0)
