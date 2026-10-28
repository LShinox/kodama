# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Texto de los avisos: clasificar (termino / pregunta / error / permiso), traduccion es/en y redaccion
(sin claves ni rutas del usuario).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import re as _re

import config


RESPUESTAS = {"ok": "OK, adelante.", "sigue": "Sigue con lo que ibas.",
              "para": "Para ahí y espera mis instrucciones.", "corto": "Explícame lo anterior en 3 líneas, sin jerga."}


def _limpio(txt):
    txt = _re.sub(r"```[\s\S]*?```", " ", txt)
    txt = _re.sub(r"`[^`]*`", " ", txt)
    txt = "\n".join(l for l in txt.splitlines() if not l.strip().startswith("|"))
    return _re.sub(r"[*_#>]+", "", txt)


# Peticiones directas al usuario (voseo y tuteo). Las condicionales tipo
# "si ves algo, dime" NO cuentan: son opcionales.
_PIDE = _re.compile(
    r"(lo que necesito de ti|necesito de ti|necesito tu (ok|visto bueno|aprobaci[oó]n|confirmaci[oó]n|respuesta|decisi[oó]n)"
    r"|\bnecesito:"
    r"|\b(decime|dime) si (arranco|lo hago|lo armo|sigo|sigo con|procedo|avanzo|lanzo|empiezo|quieres|querés)"
    r"|\bresp[oó]nd(e|é)me\b|\bcontestame\b"
    # (14-oct) pedidos de prueba/confirmacion que no llevan "?" ("dime si te gusta", "confirmame que la ves"): asi el
    # puente espera y tu respuesta llega sin el parrafo en ingles
    r"|\b(dime|decime|cu[eé]ntame|av[ií]same|avisame) (si|que|c[oó]mo|qu[eé])\b|\bconf[ií]rm(a|á)me\b|\bconf[ií]rmame\b"
    r"|\bpru[eé]ba(la|lo|las|los)\b y (dime|me dices|av[ií]same)|\b(me dices|me cuentas|me avisas) (si|qu[eé]|c[oó]mo)\b"
    r"|\b(quieres|querés) que\b|\bte parece\b|\bconfirm(as|ás) (si|que)\b|\bcu[aá]l (de|prefieres|preferís)\b"
    r"|\bnecesito que (me )?(digas|confirmes|elijas|digás|confirmés|elijás)\b"
    # (14-oct, revision de 50 reales: 12 "termino" que eran pedidos, casi todos con el pedido AL PRINCIPIO)
    r"|\bnecesito (un|una|dos|tres|cuatro|\d+|tus|tu) (ok|oks|decisi[oó]n|decisiones|respuesta|confirmaci[oó]n)"
    r"|\b(me )?(digas|digás) (si|qu[eé]|cu[aá]l)\b|\b(dime|decime) (qu[eé]|cu[aá]l)\b|\bque elij(as|ás)\b"
    r"|\bsi lo confirm(as|ás)\b|\b(p[aá]same|pasame|m[aá]ndame|env[ií]ame) (el|la|los|las|un|una)\b"
    # (14-oct) ingles
    r"|\bi need your (ok|approval|decision|answer|confirmation)\b|\b(let me know|tell me) (if|which|what)\b"
    r"|\bshould i (go ahead|proceed|continue|start)\b|\bdo you want me to\b|\bplease (confirm|choose|pick)\b)", _re.I)
# Verbo de acción al INICIO de una línea ("Aceptá en la PC...", "Elegí uno").
_ORDEN = _re.compile(r"(^|\n)\s*(acept[aá]|aprob[aá]|confirm[aá]|eleg[ií]|elige|resolv[eé]|autoriz[aá])\b", _re.I)
_LISTA = _re.compile(r"(^|\n)\s*(\d+[.)]|[ab]\)|[-•]\s)")


def clasificar(evento, texto):
    """(tipo, cuantas_preguntas, linea) — tipo: error > permiso > pregunta > termino.
    v2 (calibrada 2026-10-13 con 60 mensajes reales)."""
    t0 = (texto or "").strip()
    inicio = t0[:200]
    if evento == "StopFailure" or _re.match(r"^(error|falló|no pude|no se pudo|límite|rate limit)", inicio, _re.I) \
            or _re.search(r"Traceback|API Error|overloaded| 429 | 529 ", inicio):
        return "error", 0, _corta(inicio)
    if evento in ("Notification", "PermissionRequest"):
        return "permiso", 0, _corta(t0)
    limpio = _limpio(t0)
    parrafos = [p.strip() for p in _re.split(r"\n\s*\n", limpio) if p.strip()]
    ultimo = (parrafos[-1] if parrafos else "")[-400:]
    lineas = [l.strip() for l in ultimo.splitlines() if l.strip()]
    cola = limpio[-700:]
    pregunta = None
    if lineas and lineas[-1].endswith("?"):
        pregunta = lineas[-1]
    elif any(l.endswith("?") for l in lineas[-2:]):
        pregunta = next(l for l in reversed(lineas[-2:]) if l.endswith("?"))
    else:
        m = _re.search(r"¿[^?]{3,200}\?", ultimo)
        if m and len(ultimo[m.end():].strip()) <= 140:
            pregunta = m.group(0)
    if pregunta is None:
        # (A) la pregunta ABRE el mensaje ("lo que necesito de ti va primero"): "¿Lanzo un estudio…? Solo investiga…"
        m = _re.match(r"\s*¿[^?]{3,200}\?", limpio)
        if m:
            pregunta = m.group(0).strip()
    if pregunta is None:
        # (B) petición directa en la cola ("lo que necesito de ti", "respóndeme ok", "decime si arranco", "Aceptá …")
        # (14-oct) lo que va entre comillas es una cita, no un pedido («dime si…» nombrado como ejemplo)
        sin_citas = lambda x: _re.sub(r"«[^»]{0,120}»|\"[^\"\n]{0,120}\"|“[^”]{0,120}”", "",
                                      _re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", x))   # los links [texto](ruta) quedan en su texto
        cabeza, cola = sin_citas(limpio[:400]), sin_citas(cola)   # la regla de LShinox: "lo que necesitás de mí va PRIMERO"
        m = _PIDE.search(cola) or _ORDEN.search(cola)
        donde = cola
        if not m:
            m, donde = _PIDE.search(cabeza), cabeza
        if m:
            # (14-oct) la ORACION entera donde esta el pedido (antes una ventana de caracteres: "uando terminan…avis")
            ini = max(donde.rfind(x, 0, m.start()) for x in (". ", "! ", "? ", "\n", ": ")) + 1
            fin = min([i for i in (donde.find(x, m.end()) for x in (".", "!", "?", "\n")) if i >= 0] or [len(donde)])
            pregunta = " ".join(donde[ini:fin + 1].split())
    n_bloque = 0
    if pregunta is not None and pregunta.rstrip().endswith(":"):
        # (20-oct) el pedido es un TITULO ("Necesito de ti:") y las preguntas van debajo: la linea pasa a ser la primera
        # pregunta del bloque (antes el aviso y el globo decian solo "Necesito de ti:") y se cuentan las preguntas
        i = limpio.find(pregunta.rstrip(": ").split()[-1] + ":")
        bloque = _re.split(r"\n\s*\n", limpio[i:] if i >= 0 else "", maxsplit=1)[0].splitlines()[1:]
        items = [l.strip() for l in bloque if l.strip()]
        if items:
            n_bloque = sum(1 for l in items if "?" in l) or len(items)
            pregunta = next((l for l in items if "?" in l), items[0])
    if pregunta is not None:
        n = n_bloque or max(1, min(3, ultimo.count("¿")))
        frase = _re.sub(r"^[-•\d.)\s]+", "", pregunta)
        return "pregunta", n, _corta(frase)
    oraciones = [o.strip() for o in _re.split(r"(?<=[.!?])\s+|\n", limpio) if len(o.strip()) > 8]
    return "termino", 0, _corta(oraciones[0] if oraciones else " ".join(limpio.split()))


def _corta(s, n=110):
    """Recorta en una palabra entera, con "…" si sobra (nunca a mitad de palabra)."""
    s = _re.sub(r"^[-•*]\s+", "", " ".join((s or "").split()))   # sin la viñeta del principio
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:·-") + "…"


# ---- idioma de Telegram y de los avisos (14-oct): config.json "idioma": "es" (por defecto) o "en" ----
_EN = {
    "No hay imágenes, páginas ni PDF que se puedan abrir en esta carpeta.": "No images, pages or PDFs that can be opened in this folder.",
    "Entregado a {n}": "Delivered to {n}",
    "{n} se atoró": "{n} got stuck", "{e} {n} pide permiso": "{e} {n} needs permission",
    "{e} {n} te hace una pregunta": "{e} {n} has a question", "{e} {n} te hace {k} preguntas": "{e} {n} has {k} questions",
    "✅ {n} terminó": "✅ {n} is done", "pregunta": "question", "permiso": "permission", "se atoró": "stuck", "terminó": "done",
    "{k} chats te esperan": "{k} chats are waiting", "✅ Permitir": "✅ Allow", "⛔ Denegar": "⛔ Deny",
    "Caduca en ~2 min; si no respondes, se pregunta en la PC.": "Expires in ~2 min; if you don't answer, it asks on the PC.",
    "OK ✅": "OK ✅", "Sigue ▶": "Go on ▶", "Para ⏸": "Stop ⏸", "Explícame corto": "Explain briefly", "Abrir app": "Open app",
    "↪ Hay un mensaje más nuevo": "↪ There's a newer message", "⌛ Botón vencido: responde en el chat o la app": "⌛ Expired: reply in the chat or the app",
    "✓ Respondiste": "✓ You replied", "✓ Respondiste en la PC": "✓ You replied on the PC", "✅ Permitido": "✅ Allowed", "⛔ Denegado": "⛔ Denied",
    "⌛ Ya caducó: se preguntó en la PC": "⌛ Expired: it asked on the PC", "🔕 Silenciado {h} h": "🔕 Muted {h} h",
    "📱 Al celular: {n}": "📱 On your phone: {n}", "Ese grupo ya no existe; manda /grupo de nuevo.": "That group no longer exists; send /grupo again.",
    "¡Listo! Quedé emparejado solo contigo.": "Done! I'm paired only with you.",
    "Telegram: mensajes completos (Instalaciones sigue en corto).": "Telegram: full messages.",
    "Telegram: solo el aviso corto; el texto completo en la app.": "Telegram: short notice only; full text in the app.",
    "Modo: siempre (aviso todo)": "Mode: always (I notify everything)",
    "Modo: ausente (aviso solo si la PC lleva 2 min sin uso)": "Mode: away (I notify only if the PC is idle for 2 min)",
    "¿Qué chats llevo al celular?": "Which chats go to your phone?", "✗ No pude bajar la foto.": "✗ I couldn't download the photo.",
    "Escribe el mensaje después del comando: /{c} …": "Write the message after the command: /{c} …",
    "¿Para qué chat? Responde deslizando sobre su mensaje.": "Which chat? Reply by swiping on its message.",
    "✓ Enviado a {e} {n}": "✓ Sent to {e} {n}",
    "Te aviso cuando tus chats te necesitan.\nPara responder: desliza sobre el mensaje del chat y escribe (o toca sus botones).\n/estado: cómo está cada chat · /siempre o /ausente: cuándo te aviso · /grupo: qué chats van al celular · /completo o /corto: cuánto texto mando.":
        "I let you know when your chats need you.\nTo reply: swipe on the chat's message and type (or tap its buttons).\n/estado: status of each chat · /siempre or /ausente: when I notify you · /grupo: which chats go to your phone · /completo or /corto: how much text I send.",
    "🔄 Kodama volvió: estuvo caído ~{m} min (desde las {d}). Lo de los últimos 15 min te lo aviso ahora; lo anterior está en la app.":
        "🔄 Kodama is back: it was down ~{m} min (since {d}). I'll send what came in the last 15 min now; older items are in the app.",
    "OK, adelante.": "OK, go ahead.", "Sigue con lo que ibas.": "Carry on with what you were doing.",
    "Para ahí y espera mis instrucciones.": "Stop there and wait for my instructions.",
    "Explícame lo anterior en 3 líneas, sin jerga.": "Explain the above in 3 lines, no jargon.",
    "Kodama, responde aquí": "Kodama, reply here",
}


def tr(es, **kw):
    """Texto en el idioma de config.json; las llaves {x} se completan con kw."""
    txt = _EN.get(es, es) if config.IDIOMA == "en" else es
    return txt.format(**kw) if kw else txt


# (28-oct, "Etiqueta") Lo que Kodama antepone a un mensaje que entrega a un chat de Claude Code desde el celular (📱) o la mascota (🐾):
# "📱 Nombre (Kodama, responde aquí): texto" / en ingles "📱 Name (Kodama, reply here): texto". Antes era una frase larga entre corchetes
# ("📱 [Nombre, desde el celular, con Kodama; contéstale aquí en este chat] "); esa sigue reconociéndose porque quedó en transcripts.
_TAG_KODAMA = _re.compile(r"^(?:📱|🐾) .{1,60}\(Kodama, (?:responde aquí|reply here)\): ")
_TAG_KODAMA_ANTIGUO = "con Kodama; contéstale aquí"


def etiqueta_kodama(marca="📱 ", nombre=None):
    """Etiqueta (con el espacio final) para un mensaje entregado por Kodama; el idioma sigue al ajuste de Kodama."""
    emoji = "🐾" if (marca or "").strip().startswith("🐾") else "📱"
    nombre = " ".join(str(nombre if nombre else config.NOMBRE).split())[:40] or "?"
    return f"{emoji} {nombre} ({tr('Kodama, responde aquí')}): "


def es_entrega_kodama(texto):
    """True si el texto empieza con la etiqueta de Kodama (nueva en es/en, o la antigua)."""
    t = (texto or "").strip()
    return bool(_TAG_KODAMA.match(t)) or _TAG_KODAMA_ANTIGUO in t[:200]


def titulo_aviso(emo, nombre, tipo, n):
    return {"error": "⚠️ " + tr("{n} se atoró", n=nombre), "permiso": tr("{e} {n} pide permiso", e=emo, n=nombre),
            "pregunta": tr("{e} {n} te hace una pregunta", e=emo, n=nombre) if n <= 1 else tr("{e} {n} te hace {k} preguntas", e=emo, n=nombre, k=n),
            "termino": tr("✅ {n} terminó", n=nombre)}[tipo].strip()   # (16-oct) sin emoji queda un espacio adelante


def pendientes(conf):
    return len(conf.get("pendientes", {}))


# ---- privacidad (14-oct): lo que SALE de la PC (Telegram, Web Push) va sin claves y sin la ruta de tu usuario ----
_SECRETOS = _re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{30,}|\b\d{8,10}:[A-Za-z0-9_-]{30,}\b|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"
    r"|(?i:(?:password|passwd|contrase[nñ]a|token|api[_-]?key|secret)\s*[:=]\s*)\S{6,}"
    r"|\b[A-Fa-f0-9]{40,}\b|\b[A-Za-z0-9+/]{48,}={0,2}"
    r"|\b1000\.[a-f0-9]{32}\.[a-f0-9]{32}\b|\bya29\.[A-Za-z0-9_-]{20,}|\b(?=[A-Za-z0-9 ]{0,28}\d)(?=[A-Za-z0-9 ]{0,28}[A-Z])(?:[A-Za-z0-9]{4} ){5}[A-Za-z0-9]{4}\b"
    r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@))")
_RUTA_USUARIO = _re.compile(r"[\\/]+".join(_re.escape(x) for x in _re.split(r"[\\/]+", config.HOME)), _re.I)   # tu carpeta de usuario, con \ o /


def redactar(txt):
    return _RUTA_USUARIO.sub("~", _SECRETOS.sub("[clave oculta]", txt or ""))
