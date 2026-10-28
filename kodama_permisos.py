# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Permisos y preguntas que llegan desde los hooks, reglas "siempre" y entrega de mensajes a un chat
(puente o buzon).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import re as _re
import time

import config
import kodama_plataforma as plataforma
from kodama_nucleo import PERMISOS, PUENTE, REGLAS_PERMISO, SES, api, log
from kodama_texto import redactar, tr


def leer_reglas():
    try:
        r = json.load(open(REGLAS_PERMISO, encoding="utf-8"))
    except (OSError, ValueError):
        r = {}
    return {"siempre": list(r.get("siempre") or []), "tarea": dict(r.get("tarea") or {})}


def guardar_reglas(r):
    tmp = REGLAS_PERMISO + ".tmp"
    json.dump(r, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, REGLAS_PERMISO)


def responder_permiso(pid, decision, motivo="", alcance=""):
    """Deja la decision para el hook companero_permiso.py. False si el pedido ya no existe (caduco o se decidio).
    (22-oct, mejora 6, idea de Nudge) al denegar puede ir un motivo corto: Claude lo recibe y cambia de rumbo.
    (22-oct, mejora 2) decision "pc" = que lo decida la PC; allow + alcance "siempre"/"tarea" guarda una regla con el
    comando exacto (o herramienta + archivo) para no volver a preguntarlo."""
    if not _re.fullmatch(r"[0-9a-f]{8}", pid or "") or decision not in ("allow", "deny", "pc"):
        return False
    ped = os.path.join(PERMISOS, pid + ".pedido")
    if not os.path.exists(ped):
        return False
    if decision == "allow" and alcance in ("siempre", "tarea"):
        try:
            p = json.load(open(ped, encoding="utf-8"))
            clave, ses = p.get("regla"), p.get("sesion")
            if clave:
                reg = leer_reglas()
                if alcance == "siempre" and clave not in reg["siempre"]:
                    reg["siempre"].append(clave)
                elif alcance == "tarea" and ses and clave not in reg["tarea"].setdefault(ses, []):
                    reg["tarea"][ses].append(clave)
                guardar_reglas(reg); log(f"regla nueva ({alcance}): {clave[:80]}")
        except Exception as e:
            log(f"regla: {type(e).__name__}")
    r = os.path.join(PERMISOS, pid + ".respuesta")
    motivo = " ".join(str(motivo or "").split())[:300] if decision == "deny" else ""
    open(r + ".tmp", "w", encoding="utf-8").write(json.dumps({"decision": decision, "motivo": motivo}, ensure_ascii=False))
    os.replace(r + ".tmp", r)
    log(f"permiso {pid}: {decision}")
    return True


def responder_pregunta(pid, respuestas):
    """(19-oct) Respuesta a una pregunta con opciones (AskUserQuestion): {pregunta: etiqueta}. El hook valida que cada
    etiqueta sea una de las opciones antes de dársela al chat."""
    if not _re.fullmatch(r"[0-9a-f]{8}", pid or "") or not isinstance(respuestas, dict) or not respuestas:
        return False
    ped = os.path.join(PERMISOS, pid + ".pedido")
    if not os.path.exists(ped):
        return False
    limpio = {str(k)[:500]: str(v)[:600] for k, v in list(respuestas.items())[:4]}
    r = os.path.join(PERMISOS, pid + ".respuesta")
    open(r + ".tmp", "w", encoding="utf-8").write(json.dumps({"decision": "answer", "respuestas": limpio}, ensure_ascii=False))
    os.replace(r + ".tmp", r)
    log(f"pregunta {pid}: respondida desde el celular")
    return True


PERM_TG = {}   # permiso_id -> (chat, message_id, enviado): mensajes de Telegram con Permitir/Denegar o pregunta abiertos


def vigilar_permisos_caducados():
    """(21-oct, Coucou #857: botones muertos que despues rechazan el permiso siguiente) Cada 5 s: si el pedido ya no
    existe (el hook espero 110 s y se pregunto en la PC, o se respondio en la PC) y nadie lo respondio desde el
    celular, el mensaje de Telegram pasa a "⌛ Caducó" y sus botones dejan de servir. La app y la mascota ya lo
    sacan solas (permisos_pendientes() solo lista pedidos vivos)."""
    while True:
        time.sleep(5)
        for pid, (chat, mid, t0) in list(PERM_TG.items()):
            if os.path.exists(os.path.join(PERMISOS, pid + ".pedido")) and time.time() - t0 < 180:
                continue
            PERM_TG.pop(pid, None)
            try:
                api("editMessageReplyMarkup", chat_id=chat, message_id=mid,
                    reply_markup={"inline_keyboard": [[{"text": tr("⌛ Ya caducó: se preguntó en la PC"), "callback_data": "x|x|x"}]]})
            except Exception as e:
                log(f"permisos caducados: {type(e).__name__}")


def permisos_pendientes():
    """{session_id: {id, texto, ts}} de los pedidos que esperan respuesta (para la app y el escritorio)."""
    # (22-oct, mejora 1) un mismo chat puede pedir dos permisos a la vez (subagentes en paralelo): antes se mostraba uno
    # cualquiera y el otro se perdia de vista. Ahora va primero el MAS VIEJO y "cola" dice cuantos esperan en total;
    # al contestarlo aparece el siguiente. Cada pedido sigue esperando su propia respuesta en su hook.
    todos = {}
    for f in os.listdir(PERMISOS) if os.path.isdir(PERMISOS) else []:
        if f.endswith(".pedido"):
            try:
                p = json.load(open(os.path.join(PERMISOS, f), encoding="utf-8"))
                if time.time() - p["ts"] < 115:
                    todos.setdefault(p["sesion"], []).append(p)
            except Exception:
                pass
    out = {}
    for ses, lista in todos.items():
        p = min(lista, key=lambda x: x["ts"])
        out[ses] = {"id": p["id"], "texto": redactar(p["texto"]), "ts": p["ts"], "cola": len(lista)}
        if p.get("preguntas"):   # (19-oct) pregunta con opciones: la app muestra botones por opcion
            out[ses]["preguntas"] = p["preguntas"]
            out[ses]["plan"] = bool(p.get("plan"))   # (20-oct) aprobar el plan: la app muestra el plan
    return out


def por_puente(s, texto):
    """(14-oct) Si el chat esta esperando en el hook Stop del puente (companero_puente.py), la respuesta va por
    ahi: le llega a Claude como decision del hook, sin el parrafo "This came from another Claude session…".
    Devuelve True si el hook la tomo (borra el archivo en <=1 s); si no la toma en 4 s, se usa el buzon."""
    sid = s.get("session_id") or ""
    esp, resp = os.path.join(PUENTE, sid + ".esperando"), os.path.join(PUENTE, sid + ".respuesta")
    try:
        if not sid or time.time() - os.path.getmtime(esp) > 540:
            return False
    except OSError:
        return False
    open(resp + ".tmp", "w", encoding="utf-8").write(texto); os.replace(resp + ".tmp", resp)
    for _ in range(40):
        time.sleep(0.1)
        if not os.path.exists(resp):
            try:   # Claude sigue trabajando con tu respuesta: que el estado lo diga
                p = os.path.join(SES, sid + ".json"); reg = json.load(open(p, encoding="utf-8"))
                reg.update(estado="trabajando", visto=time.time())
                open(p + ".tmp", "w", encoding="utf-8").write(json.dumps(reg, ensure_ascii=False)); os.replace(p + ".tmp", p)
            except Exception:
                pass
            log(f"respuesta por el puente -> {sid[:8]}")
            return True
    try:
        os.remove(resp)
    except OSError:
        pass
    return False


def entregar(s, texto, marca="📱 "):
    """Entrega el texto: por el puente si el chat te esta esperando; si no, en el buzon (named pipe) de la sesion."""
    if por_puente(s, texto):
        return None
    if not (s.get("socket") and s.get("token")):
        return "ese chat todavía no registró su buzón (escribile algo desde la PC una vez)"
    if not plataforma.es_ruta_buzon(s["socket"]):   # (auditoria) solo la tuberia de una sesion, nunca un archivo
        return "buzón inválido"
    # (14-oct) el buzon es una tuberia con nombre: entre una conexion y la siguiente puede no haber instancia libre
    # un instante (FileNotFoundError / ocupada). Se reintenta hasta ~4 s antes de dar error.
    for intento in range(8):
        try:
            p = plataforma.abrir_buzon(s["socket"])
            break
        except (FileNotFoundError, PermissionError, OSError) as e:
            if intento == 7:
                return f"no pude entregarlo ({type(e).__name__}); ¿el chat sigue abierto?"
            time.sleep(0.5)
    # (21-oct) por el buzon, Claude Code lo envuelve como "mensaje de OTRA sesion": un chat (Rol) contesto "no pude
    # responderle a esa sesion" sin saber que era LShinox desde el celular. La marca ahora dice quien escribe y donde
    # contestar. (Sigue sin contar como aprobacion: eso solo pasa por el puente, cuando el chat te estaba esperando.)
    quien = (f"{config.NOMBRE}, desde la mascota del escritorio" if marca.startswith("🐾")
             else f"{config.NOMBRE}, desde el celular")
    etiqueta = f"{marca.strip()} [{quien}, con Kodama; contéstale aquí en este chat] "
    try:
        with p:
            p.write((json.dumps({"type": "auth", "token": s["token"]}) + "\n").encode())
            p.write((json.dumps({"type": "user", "message": {"role": "user", "content":
                    etiqueta + texto}},   # 14-oct: marca (📱 celular/Telegram, 🐾 mascota del escritorio); 21-oct: + quien
                    ensure_ascii=False) + "\n").encode())
        return None
    except Exception as e:
        return f"no pude entregarlo ({type(e).__name__}); ¿el chat sigue abierto?"
