# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Uso del plan (estimado y lectura exacta del chat Kodama / Medidor).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import re as _re
import threading
import time

import config
import grupos_app
import kodama_plataforma as plataforma
from kodama_plataforma import segundos_sin_uso
from kodama_nucleo import BASE, LECTURA, MEDIDOR_DIR, SES, log
from kodama_permisos import entregar
from kodama_cola import prender_pantalla


def uso_plan():
    """(15-oct) % del plan (5 h y semana). Lo calcula el hilo estimar_uso() con estimador.py: exacto si hay un dato de
    menos de 20 min (app de Claude o chat Medidor), si no ESTIMADO con lo que gastaron los chats (sin gastar plan).
    {"5h": {"pct", "estimado"?}, "semana": {...}, "ts", "base_ts"?} o None."""
    return _EST.get("v")


_EST = {"v": None, "pedido5h": 0}


def estimar_uso():
    """Cada 60 s: lee lo nuevo de los transcripts y recalcula. Si el estimado de 5 h pasa de 80 % y no estas en la PC,
    pide UNA lectura exacta al chat Medidor (una sola vez por ventana de 5 h): es lo unico que gasta plan."""
    import estimador
    while True:
        try:
            estimador.actualizar()
            v = estimador.estimar(grupos_app.APP)
            _EST["v"] = v
            p5 = ((v or {}).get("5h") or {})
            if p5.get("estimado") and p5.get("pct", 0) >= 80 and segundos_sin_uso() >= 120 and lectura_exacta_activa() \
                    and time.time() - _EST["pedido5h"] > 5 * 3600:
                _EST["pedido5h"] = time.time()
                log(f"estimado 5 h {p5['pct']} %: pido lectura exacta al Medidor")
                pedir_medicion()
        except Exception as e:
            log(f"estimador: {type(e).__name__}: {e}")
        time.sleep(60)


# las instrucciones van EN el pedido: asi el Medidor funciona aunque se haya creado en otra carpeta (sin su CLAUDE.md)
PEDIDO_MEDIR = ('MEDIR. Llama UNA vez a la herramienta mcp__ccd_session_mgmt__get_usage y responde SOLO esta linea JSON, sin '
                'nada mas: {"medidor": 1, "5h": <percentUsed de "5-hour limit">, "semana": <percentUsed de "Weekly · all '
                'models">, "reinicia5h": "<resetsAt de "5-hour limit">"}. Si falla: {"medidor": 1, "error": "<motivo>"}.')


def regs_medidor():
    """Registros del chat Medidor: el de estado\\medidor.json ({"sid": ...}) o cualquiera abierto en la carpeta medidor."""
    try:
        sid = json.load(open(os.path.join(BASE, "medidor.json"), encoding="utf-8")).get("sid")
    except (OSError, ValueError):
        sid = None
    clave, out = config.clave_carpeta(MEDIDOR_DIR), []
    for n in os.listdir(SES) if os.path.isdir(SES) else []:   # todos los registros (sesiones() solo trae chats de la app)
        if n.endswith(".json"):
            try:
                x = json.load(open(os.path.join(SES, n), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if x.get("session_id") == sid or x.get("proyecto") == clave:
                out.append(x)
    # (22-oct) si hay chat en la carpeta de Kodama, manda ese: el de medidor.json puede ser uno viejo (el Medidor de antes)
    propios = [x for x in out if x.get("proyecto") == clave]
    return propios or out


def lectura_exacta_activa():
    """(22-oct, LShinox) la lectura exacta por el chat de Kodama es un EXTRA de Ajustes, apagado por defecto: gasta un
    poco de plan y cambia de chat unos segundos. Sin ajuste guardado: activa solo si ese chat ya existe (esta PC)."""
    try:
        return bool(json.load(open(LECTURA, encoding="utf-8")).get("activa"))
    except (OSError, ValueError):
        return bool(regs_medidor())


def activar_lectura_exacta(on):
    """Guarda el ajuste y, al activar, deja lista la carpeta del chat (CLAUDE.md + permisos) sin pisar una que exista."""
    json.dump({"activa": bool(on)}, open(LECTURA, "w", encoding="utf-8"))
    if on and not os.path.exists(os.path.join(MEDIDOR_DIR, "CLAUDE.md")):
        import shutil
        shutil.copytree(os.path.join(config.APP_DIR, "plantillas", "kodama-chat"), MEDIDOR_DIR, dirs_exist_ok=True)
        log("carpeta del chat de Kodama creada")
    return estado_lectura()


def estado_lectura():
    return {"ok": True, "activa": lectura_exacta_activa(), "carpeta": MEDIDOR_DIR, "chat_listo": bool(regs_medidor())}


def ordenar_kodama(orden):
    """(22-oct) ARCHIVAR/DESARCHIVAR <local_…> al chat de Kodama (sus herramientas oficiales de la app). Lo pediste
    vos desde la mascota, asi que se despierta el chat aunque estes en la PC (forzar). None si se mando, o el motivo."""
    if not _re.fullmatch(r"(ARCHIVAR|DESARCHIVAR) local_[0-9a-f-]{36}", orden or ""):
        return "orden inválida"
    log(f"Kodama: {orden.split()[0].lower()}")
    return pedir_medicion(forzar=True, pedido=orden)


def pedir_medicion(forzar=False, pedido=PEDIDO_MEDIR):
    """Manda el pedido de lectura exacta al chat Medidor. La app de Claude duerme ese chat enseguida (sin buzon), asi que
    casi siempre hay que despertarlo abriendo su enlace: eso cambia el chat que muestra la app de Claude por unos
    segundos. Solo se hace si no usas la PC, o si lo pediste con el boton "Actualizar" (forzar). Al terminar, la app
    vuelve al chat que tenias abierto. Devuelve None si se pidio, o el motivo si no se pudo."""
    if pedido == PEDIDO_MEDIR and not lectura_exacta_activa():
        return "la lectura exacta está apagada (Ajustes > Lectura exacta del uso)"
    regs = regs_medidor()
    if not regs:
        return "falta abrir el chat de Kodama (Ajustes > Lectura exacta del uso)"
    sid = max(regs, key=lambda x: x.get("visto", 0)).get("session_id")
    # (22-oct, probado) un chat ARCHIVADO no responde: la app muestra "Esta sesion esta archivada. Desarchivala para
    # seguir trabajando en ella". Se avisa enseguida en vez de quedarse "pidiendo el dato exacto…".
    if grupos_app.archivado(sid):
        log("el Medidor esta archivado: no se puede leer")
        return "el chat Medidor está archivado: desarchívalo en la app de Claude"
    if not entregar(max(regs, key=lambda x: x.get("visto", 0)), pedido, ""):
        log("pedido al chat de Kodama" if pedido != PEDIDO_MEDIR else "lectura exacta pedida al Medidor")
        return None
    if not forzar and segundos_sin_uso() < 120:
        return "el chat Medidor esta dormido y estas usando la PC"
    url = grupos_app.enlace(sid)
    if not url:
        return "no encuentro el chat Medidor en la app de Claude"
    previo = grupos_app.chat_enfocado()
    try:
        if forzar and prender_pantalla():   # solo si lo pediste ("Actualizar"); la lectura automatica no prende la PC
            time.sleep(3)
        plataforma.abrir(url); log("despertando al Medidor")
    except Exception as e:
        return f"no pude despertar al Medidor ({type(e).__name__})"

    def seguir():
        antes = os.path.getsize(estimador_exactos()) if os.path.exists(estimador_exactos()) else 0
        enviado = False
        for _ in range(12):
            time.sleep(4)
            if not enviado:
                r = regs_medidor()
                if r and not entregar(max(r, key=lambda x: x.get("visto", 0)), pedido, ""):
                    enviado = True; log("pedido al chat de Kodama (despues de despertarlo)")
                    if pedido != PEDIDO_MEDIR:
                        time.sleep(8); break   # archivar/desarchivar: no hay lectura que esperar
            elif os.path.exists(estimador_exactos()) and os.path.getsize(estimador_exactos()) > antes:
                break
        if previo and previo != sid:   # la app de Claude vuelve al chat que tenias abierto
            try:
                u = grupos_app.enlace(previo)
                if u:
                    plataforma.abrir(u)
            except Exception:
                pass
        if not enviado:
            log("el Medidor no desperto a tiempo")
    threading.Thread(target=seguir, daemon=True).start()
    return None


def estimador_exactos():
    return os.path.join(BASE, "uso_exacto.jsonl")
