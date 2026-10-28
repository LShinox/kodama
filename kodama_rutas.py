# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Servidor HTTP del hub (127.0.0.1): la app web del celular, la mascota del escritorio y sus endpoints.

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import hmac
import html as _html
import http.server
import json
import os
import random
import re as _re
import secrets
import subprocess
import threading
import time
import urllib.parse

import config
import grupos_app
import kodama_plataforma as plataforma
import kodama_conexion
import kodama_nucleo
from kodama_plataforma import pantalla_completa, segundos_sin_uso
from kodama_nucleo import (
    ACTUALIZACION, ARRANQUE, AUTO_ACT, BASE, BLOQUEO, BOT, COLA, CONSERVAR_JSON, FOTOS, PUENTE, RESP, SALUD, SUSC,
    WEB, _leer_json, cargar_conf, log, poner_token
)
from kodama_texto import redactar, tr
from kodama_push import push_a_todos
from kodama_chats import (
    cambiar_seleccion, candidatos, cwd_de, grupos_propios, marcar_celular, ocultar_chat, poner_color, poner_grupo,
    seleccion, sesion_por_cmd, sesiones, silenciar, sincronizar_grupos
)
from kodama_permisos import entregar, guardar_reglas, leer_reglas, responder_permiso, responder_pregunta
from kodama_conexion import alarma, aparato_ok, bloqueado, permitido, poner_bloqueo
from kodama_cola import poner_pendiente
from kodama_medidor import (
    activar_lectura_exacta, estado_lectura, ordenar_kodama, pedir_medicion, regs_medidor, uso_plan
)
from kodama_archivos import (
    HOME_N, VER_TIPOS, VIDEO_MAX, VIDEO_TIPOS, _SALTAR, borrar_limpieza, carpeta_medios, conservar,
    escanear_limpieza, guardar_foto, listar_archivos, raices_archivos, texto_con_foto, texto_con_video,
    ver_permitido
)
from kodama_historial import contexto_chat, firma_estado, historial, lo_nuevo, mensajes_anteriores, pasos_chat
from kodama_notificaciones import REINTENTAR
from kodama_vigilantes import actualizar_ahora, actualizar_sola, chequear_salud


# (27-oct, lanzamiento) en el lanzamiento solo se elige el gato. El código de Brote sigue: poner True lo vuelve a mostrar.
MOSTRAR_BROTE = False


def _pj_visible(p):
    """Al LEER personaje.json: un Brote guardado se entrega como gato (el resto del archivo no cambia, ni se reescribe)."""
    if not MOSTRAR_BROTE and str(p.get("pj", "")).startswith("brote"):
        p = dict(p, pj="gatoPro", florCactus=True)
    return p


HOSTS_VISTOS = set()
POSTS = []   # horas de los ultimos POST (tope de frecuencia)
CERRAR = []   # respuestas hechas por la web/escritorio: el bucle principal cierra sus avisos de Telegram
_KEY = os.path.join(BASE, "local.key")
if not os.path.exists(_KEY):
    open(_KEY, "w").write(secrets.token_hex(24))
CLAVE_LOCAL = open(_KEY).read().strip()
TICKETS = {}   # ticket de un solo uso -> vence (abrir el panel de animaciones sin poner la clave en la URL)
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/manifest+json",
         ".png": "image/png", ".css": "text/css"}


class Web(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _abrir(self):
        """/abrir?chat=<id>&r=<ruta>: un link a un archivo dentro de un mensaje (C:\\..., ~\\... o relativo a la
        carpeta del chat). Si se puede ver, redirige a /ver/h/<ruta desde HOME>; si no, una pagina corta que lo dice."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        r, cmd = (q.get("r") or [""])[0].strip(), (q.get("chat") or [""])[0]
        r = r.split("#")[0]
        if r.startswith("~"):
            r = HOME_N + r[1:]
        elif not os.path.isabs(r):
            base = cwd_de(cmd)
            r = os.path.join(base, r) if base else ""
        if r and os.path.isdir(r):
            return self._galeria(r)
        rel = ver_permitido(r) if r else None
        if not rel:
            b = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                 "<body style='font:17px system-ui;padding:24px;background:#1e1c1a;color:#f1ece4'>"
                 + _html.escape(tr("Ese archivo no se puede abrir desde el celular (no existe, o no es una página, imagen o PDF)."))
                 + "</body>").encode()
            self.send_response(404); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        self.send_response(302)
        self.send_header("Location", "/ver/h/" + urllib.parse.quote(rel.replace(os.sep, "/")))
        self.send_header("Content-Length", "0"); self.end_headers()

    def _galeria(self, carpeta):
        """(15-oct) Un link a una CARPETA (p. ej. "las imagenes estan en Cuentos\\flow"): pagina con miniaturas de lo
        que se puede ver adentro (imagenes, paginas, PDF; sin subcarpetas), lo mas nuevo primero. Mismas reglas que un
        archivo suelto (ver_permitido)."""
        items = []
        try:
            for n in os.listdir(carpeta):
                p = os.path.join(carpeta, n)
                rel = ver_permitido(p) if os.path.isfile(p) else None
                if rel:
                    items.append((os.path.getmtime(p), n, rel))
        except OSError:
            pass
        items.sort(reverse=True)
        imgs = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
        celdas = []
        for _t, n, rel in items[:120]:
            url = "/ver/h/" + urllib.parse.quote(rel.replace(os.sep, "/"))
            if n.lower().endswith(imgs):
                celdas.append(f"<a href='{url}' target='_blank'><img src='{url}' loading='lazy' alt=''><span>{_html.escape(n)}</span></a>")
            else:
                celdas.append(f"<a href='{url}' target='_blank' class='doc'><b>{_html.escape(os.path.splitext(n)[1][1:].upper())}</b><span>{_html.escape(n)}</span></a>")
        vacio = "" if celdas else "<p>" + _html.escape(tr("No hay imágenes, páginas ni PDF que se puedan abrir en esta carpeta.")) + "</p>"
        b = ("<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             "<title>" + _html.escape(os.path.basename(carpeta.rstrip("\\/"))) + "</title><style>"
             "body{margin:0;padding:14px;background:#1e1c1a;color:#f1ece4;font:15px system-ui}h1{font-size:17px;margin:0 0 12px}"
             ".g{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.g a{color:inherit;text-decoration:none;background:#2a2724;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}"
             ".g img{width:100%;aspect-ratio:1;object-fit:cover;display:block}.g span{font-size:12px;padding:6px 8px;color:#b3a99d;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
             ".g .doc b{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:20px;color:#8fcf5f}</style>"
             "<h1>" + _html.escape(os.path.basename(carpeta.rstrip("\\/"))) + f" · {len(items)}</h1>{vacio}<div class=g>" + "".join(celdas) + "</div></html>").encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _ver(self, resto):
        """/ver/<id>/<ruta>: un archivo de la carpeta de un chat (solo tipos de pagina web), en sandbox."""
        rid, _, rel = resto.partition("/")
        if rid == "h":   # (14-oct) links de los mensajes: cualquier archivo que pase ver_permitido()
            archivo = os.path.normpath(os.path.join(HOME_N, rel))
            if not rel or not ver_permitido(archivo):
                return self._json(404, {"ok": False})
            archivo = os.path.realpath(archivo)
            ext = os.path.splitext(archivo)[1].lower()
        else:
            base = (raices_archivos().get(rid) or (None,))[0]
            if not base or not rel:
                return self._json(404, {"ok": False})
            base = os.path.realpath(base)
            archivo = os.path.realpath(os.path.normpath(os.path.join(base, rel)))
            ext = os.path.splitext(archivo)[1].lower()
            if not archivo.lower().startswith(base.lower().rstrip("\\/") + os.sep) or ext not in VER_TIPOS or not os.path.isfile(archivo):
                return self._json(404, {"ok": False})
            if any(p in _SALTAR or p.startswith(".") for p in os.path.relpath(archivo, base).split(os.sep)[:-1]):
                return self._json(404, {"ok": False})
        self.send_response(200)
        self.send_header("Content-Type", VER_TIPOS[ext])
        self.send_header("Content-Length", str(os.path.getsize(archivo)))
        self.send_header("Cache-Control", "no-cache"); self.send_header("X-Content-Type-Options", "nosniff")
        if ext in (".html", ".htm", ".svg"):   # lo que puede correr codigo va aislado (el PDF no: el visor del iPhone no lo abre en sandbox)
            self.send_header("Content-Security-Policy", "sandbox allow-scripts allow-popups allow-forms allow-modals")
        self.end_headers()
        with open(archivo, "rb") as f:
            while True:
                b = f.read(65536)
                if not b:
                    break
                self.wfile.write(b)

    # (14-oct) la mascota en Tauri es una pagina con origen propio que le pide al hub con fetch: CORS SOLO para ese origen
    ORIGENES_TAURI = ("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost")

    def end_headers(self):
        o = self.headers.get("Origin", "") if hasattr(self, "headers") and self.headers else ""
        if o in self.ORIGENES_TAURI:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Headers", "X-Companero-Local, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Vary", "Origin")
        # (14-oct, auditoria) otra pagina no puede enmarcar la app ni cargar sus .js/.json; /ver queda afuera porque sus
        # paginas corren en sandbox (origen "null") y cargan sus imagenes/css de aca mismo
        if not getattr(self, "path", "").lstrip("/").startswith("ver/"):
            # (22-oct) SAMEORIGIN (antes DENY): el visor de archivos de la app (iframe) abre /abrir; otro sitio sigue sin poder
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            if o not in self.ORIGENES_TAURI:
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def do_OPTIONS(self):   # pedido previo del navegador (CORS); solo se contesta al origen de la mascota
        if self.headers.get("Origin", "") not in self.ORIGENES_TAURI:
            return self._json(403, {"ok": False})
        self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()

    def _largo(self):   # (14-oct, auditoria) un Content-Length negativo o basura colgaba el hilo
        try:
            return max(0, int(self.headers.get("Content-Length", 0)))
        except (TypeError, ValueError):
            return 0

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _autorizado(self):
        # app de escritorio (misma PC): clave local en estado\local.key (solo la lee tu usuario)
        loc = self.headers.get("X-Companero-Local", "")
        if loc and CLAVE_LOCAL and hmac.compare_digest(loc, CLAVE_LOCAL):
            return True
        # (14-oct) panel de animaciones abierto en el navegador de la PC: ?k=<clave> una vez -> cookie de la sesion
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("k", [""])[0]
        # (15-oct, contra #14) ?t=<ticket de un solo uso, 60 s> en vez de ?k=<clave>: la clave ya no queda en el historial
        tk = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t", [""])[0]
        if tk and self.client_address[0] == "127.0.0.1" and TICKETS.pop(tk, 0) > time.time():
            self._poner_cookie = True
            return True
        ck = dict(x.strip().split("=", 1) for x in self.headers.get("Cookie", "").split(";") if "=" in x).get("companero_k", "")
        if CLAVE_LOCAL and self.client_address[0] == "127.0.0.1" and \
                ((q and hmac.compare_digest(q, CLAVE_LOCAL)) or (ck and hmac.compare_digest(ck, CLAVE_LOCAL))):
            self._poner_cookie = bool(q)
            return True
        if permitido(self.headers.get("Tailscale-User-Login", "")):
            host = (self.headers.get("Host", "") + " | " + self.headers.get("X-Forwarded-Host", "")).strip()
            if host not in HOSTS_VISTOS:
                HOSTS_VISTOS.add(host); log(f"host visto: {host}")
            self._via_celular = True
            marcar_celular()
            # (14-oct, auditoria) solo por la direccion publica configurada (lo que pone `tailscale serve`)
            esperado = urllib.parse.urlparse(config.URL_PUBLICA).hostname if config.URL_PUBLICA else None
            if esperado and self.headers.get("Host", "").split(":")[0].lower() != esperado.lower():
                log(f"rechazado host {self.headers.get('Host', '')[:60]}")
                self._json(403, {"ok": False, "error": "no autorizado"})
                return False
            ok, motivo = aparato_ok(self.headers.get("X-Forwarded-For", "").split(",")[0].strip())
            if not ok:
                log(f"rechazado: {motivo}")
                self._json(403, {"ok": False, "error": "no autorizado"})
                return False
            if bloqueado() and self.path.split("?")[0] not in ("/", "/app.html", "/api/bloqueo") and \
                    not self.path.split("?")[0].endswith((".js", ".css", ".png", ".json")):
                self._json(423, {"ok": False, "error": "bloqueado", "bloqueado": True})
                return False
            return True
        if self.headers.get("Tailscale-User-Login"):   # cuenta de Tailscale ajena
            alarma(tr("Una cuenta que no es la tuya intentó entrar a Kodama. No la dejé pasar."), "cta:" + self.headers.get("Tailscale-User-Login", "")[:60])
        self._json(403, {"ok": False, "error": "no autorizado"})
        return False

    def do_GET(self):
        if not self._autorizado():
            return
        ruta = self.path.split("?")[0].lstrip("/") or "app.html"
        # (14-oct, auditoria) pedidos que el navegador marca como de otro sitio: fuera (menos /ver y la mascota Tauri)
        # Abrir la app tocando un link desde otro sitio (navegacion de pagina entera) SI vale: no lee nada ajeno y la
        # app no se puede enmarcar (X-Frame-Options)
        navega = self.headers.get("Sec-Fetch-Mode", "") == "navigate" and self.headers.get("Sec-Fetch-Dest", "") in ("document", "")
        if self.headers.get("Sec-Fetch-Site", "") in ("cross-site", "same-site") and not ruta.startswith("ver/") \
                and not navega and self.headers.get("Origin", "") not in self.ORIGENES_TAURI:
            log(f"GET cruzado rechazado: {ruta[:40]}")
            return self._json(403, {"ok": False, "error": "no autorizado"})
        if ruta == "api/bloqueo":
            return self._json(200, {"bloqueado": bloqueado(), **{k: v for k, v in _leer_json(BLOQUEO, {}).items() if k in ("desde", "hora")}})
        if ruta == "api/estado":
            return self._json(200, self._recortar(historial()))
        if ruta == "api/eventos":   # (14-oct) SSE: la app recibe cada cambio al instante en vez de preguntar cada 4 s
            return self._eventos()
        if ruta == "api/grupos":   # que se puede llevar al celular (grupos de la app de Claude) y que esta elegido
            ops = grupos_app.opciones()
            return self._json(200, {"actual": seleccion(), "opciones": ops, "error": grupos_app.ERROR[:1] or None,
                                    "sesiones": len(grupos_app.catalogo()["sesiones"])})
        if ruta == "api/conectar":   # (21-oct) asistente "Conectar celular" (solo desde la PC)
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            conf = cargar_conf()
            enlace = f"https://t.me/{BOT['u']}?start={conf.get('codigo')}" if BOT.get("u") and conf.get("codigo") else ""
            return self._json(200, {"telegram": {"token": bool(kodama_nucleo.TOKEN), "bot": BOT.get("u", ""), "emparejado": bool(conf.get("dueno")),
                                                 "enlace": enlace},
                                    "tailscale": cc.estado_tailscale()})
        if ruta == "api/qr":   # (21-oct) QR en SVG, solo para los enlaces del asistente
            if not self._en_pc():
                return self._json(403, {"ok": False})
            t = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t", [""])[0]
            if not (t.startswith("https://t.me/") or t in ("https://tailscale.com/download",) or (config.URL_PUBLICA and t == config.URL_PUBLICA)):
                return self._json(400, {"ok": False})
            import companero_conectar as cc
            b = cc.qr_svg(t)
            self.send_response(200); self.send_header("Content-Type", "image/svg+xml"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        if ruta == "api/lo-nuevo":   # (26-oct) novedades de la version instalada + estadisticas de la ultima semana (solo numeros)
            return self._json(200, lo_nuevo())
        if ruta == "api/actualizacion":   # (21-oct) version nueva disponible (la escribe vigilar_actualizaciones)
            try:
                return self._json(200, dict(json.load(open(ACTUALIZACION, encoding="utf-8")), actual=config.VERSION))
            except (OSError, ValueError):
                return self._json(200, {"actual": config.VERSION})
        if ruta == "api/salud":   # para revisar de un vistazo si el hub esta sano (14-oct)
            tam = os.path.getsize(COLA) if os.path.exists(COLA) else 0
            return self._json(200, {"pid": os.getpid(), "arranque": ARRANQUE, "ahora": time.time(),
                                    "telegram_ok": SALUD["telegram_ok"], "push_error": SALUD["push_error"],
                                    "reintentos_pendientes": len(REINTENTAR), "cola_sin_procesar": max(0, tam - SALUD.get("pos", 0))})
        if ruta == "api/anteriores":   # (14-oct) "cargar anteriores" en el celular: ?chat=<id>&antes=<ts>&n=30
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                cmd, antes, n = q["chat"][0], float(q.get("antes", ["9e12"])[0]), min(int(q.get("n", ["30"])[0]), 100)
            except (KeyError, ValueError):
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            return self._json(200, {"ok": True, "mensajes": mensajes_anteriores(cmd, antes, n)})
        if ruta == "api/inactivo":   # (14-oct) segundos sin mouse/teclado en Windows (la mascota en Tauri lo pide aca)
            return self._json(200, {"segundos": segundos_sin_uso()})
        if ruta == "api/pantalla":
            return self._json(200, {"completa": pantalla_completa()})
        if ruta == "api/vapid":
            return self._json(200, {"clave": open(os.path.join(BASE, "vapid_public.txt")).read().strip()})
        if ruta == "api/info":   # (15-oct) info del chat en el celular: contexto usado y uso del plan (5 h / semana)
            cmd = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("chat") or [""])[0]
            return self._json(200, {"ok": True, "contexto": contexto_chat(cmd), "uso": uso_plan()})
        if ruta == "api/pasos":   # (19-oct) Ajustes > "Mostrar lo que hizo el chat": pasos por turno del chat abierto
            cmd = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("chat") or [""])[0]
            return self._json(200, {"ok": True, "turnos": pasos_chat(cmd)})
        if ruta == "api/candidatos":   # (14-oct) Ajustes > Chats que se ven
            return self._json(200, {"ok": True, "chats": candidatos()})
        if ruta == "api/limpieza":   # (16-oct) Ajustes > Espacio: lo que guardo el Companero, el mas pesado primero
            if "solo=ajuste" in self.path:
                return self._json(200, {"ok": True, "conservar": conservar()})
            return self._json(200, {"ok": True, **escanear_limpieza()})
        if ruta == "api/archivos":   # (14-oct) pestaña Archivos del celular
            return self._json(200, {"ok": True, "archivos": listar_archivos()})
        if ruta.startswith("ver/"):
            return self._ver(urllib.parse.unquote(ruta[4:]))
        if ruta == "abrir":   # (14-oct) link a un archivo dentro de un mensaje
            return self._abrir()
        archivo = os.path.normpath(os.path.join(WEB, ruta))
        if not archivo.startswith(os.path.normpath(WEB) + os.sep) or not os.path.isfile(archivo):
            return self._json(404, {"ok": False})
        b = open(archivo, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(os.path.splitext(archivo)[1], "application/octet-stream"))
        self.send_header("Cache-Control", "no-cache")   # que el iPhone tome siempre la versión nueva
        if getattr(self, "_poner_cookie", False):   # panel abierto con ?k=: la cookie autoriza sus pedidos siguientes
            self.send_header("Set-Cookie", f"companero_k={CLAVE_LOCAL}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _recortar(self, h):
        """?ligero=1: solo los ultimos 3 mensajes de cada chat (la mascota cada 4 s, el celular en cada cambio), salvo el
        chat que el celular tiene abierto (?abierto=<id>), que va completo. (14-oct, rendimiento) el estado entero pesa
        ~100 KB y el celular lo recibia cada 3 s mientras algun chat trabajaba; asi baja a ~25 KB."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if (q.get("ligero") or [""])[0] != "1":
            return h
        ab = (q.get("abierto") or [""])[0]
        return {k: (dict(v, mensajes=v.get("mensajes", [])[-3:]) if isinstance(v, dict) and "mensajes" in v and k != ab else v)
                for k, v in h.items()}

    def _eventos(self):
        """Mantiene la conexion abierta: mira cada 1 s si cambio algo (fechas de archivos, sin leerlos) y entonces
        manda el estado entero. Latido cada 25 s para que el proxy de Tailscale no la corte. Max 30 min por conexion
        (el navegador reconecta solo)."""
        firma = firma_estado
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        ultima, latido, inicio = None, 0, time.time()
        try:
            while time.time() - inicio < 1800:
                f = firma()
                if f != ultima and time.time() - latido >= 3:   # max. 1 envio cada 3 s (el "que esta haciendo" cambia seguido)
                    ultima = f
                    self.wfile.write(b"data: " + json.dumps(self._recortar(historial()), ensure_ascii=False).encode() + b"\n\n"); self.wfile.flush()
                    latido = time.time()
                elif time.time() - latido > 20:
                    self.wfile.write(b"event: latido\ndata: 1\n\n"); self.wfile.flush(); latido = time.time()   # evento (no comentario): la app lo ve y sabe que el flujo esta vivo
                    if getattr(self, "_via_celular", False):
                        marcar_celular()   # se pudo escribir: la app del celular sigue abierta
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def _en_pc(self):
        """(21-oct) Pedido hecho en ESTA PC (navegador o mascota), no desde el celular por `tailscale serve` (que tambien
        llega desde 127.0.0.1, pero trae Tailscale-User-Login)."""
        return self.client_address[0] == "127.0.0.1" and not self.headers.get("Tailscale-User-Login")

    def _cuerpo(self):
        try:
            d = json.loads(self.rfile.read(min(self._largo(), 20000)).decode() or "{}")
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def do_POST(self):
        if not self._autorizado():
            return
        # (14-oct) contra pedidos cruzados: una pagina de otro sitio abierta en el celular (o un HTML de la pestaña
        # Archivos, que corre en sandbox con origen "null") podria mandar un POST simple con tu identidad de Tailscale.
        # Solo se aceptan POST sin Origin (scripts locales) o desde la propia app, la PC o la mascota.
        o = self.headers.get("Origin", "")
        publico = config.URL_PUBLICA.rstrip("/").lower() if config.URL_PUBLICA else ""
        if o and o.lower() not in (publico, *self.ORIGENES_TAURI) and \
                not _re.match(r"^http://(127\.0\.0\.1|localhost):%d$" % kodama_conexion.PUERTO_WEB, o, _re.I):
            log(f"POST rechazado por origen {o[:60]}")
            return self._json(403, {"ok": False, "error": "origen no permitido"})
        # (14-oct, auditoria) tope de frecuencia: 60 pedidos por minuto en total (un toque humano no llega ni cerca)
        ahora = time.time()
        POSTS[:] = [t for t in POSTS if ahora - t < 60]
        if len(POSTS) >= 60:
            return self._json(429, {"ok": False, "error": "demasiados pedidos seguidos; espera un minuto"})
        POSTS.append(ahora)
        if self.path == "/api/bloqueo":   # (26-oct) bloqueo de emergencia: se pone desde el celular o la PC; se quita SOLO en la PC
            si, en_pc = bool(self._cuerpo().get("activo")), self._en_pc()
            if not si and not en_pc:
                return self._json(403, {"ok": False, "error": "se desbloquea desde la PC"})
            poner_bloqueo(si, "pc" if en_pc else "celular")
            return self._json(200, {"ok": True, "bloqueado": si})
        if self.path in ("/api/ticket", "/api/reporte", "/api/actualizar", "/api/probar", "/api/medir"):
            self._cuerpo()   # (21-oct) no usan el cuerpo, pero si queda sin leer, Windows corta la conexion (RST) y el pedido falla a veces
        if self.path == "/api/ajustes":   # panel web/ajustes.html: guarda los valores de animacion
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 20000)).decode())
                assert isinstance(d, dict)
                limpio = {sec: {k: float(v) for k, v in vals.items() if isinstance(v, (int, float))}
                          for sec, vals in d.items() if isinstance(vals, dict) and len(sec) < 30}
            except Exception:
                return self._json(400, {"ok": False, "error": "ajustes inválidos"})
            tmp = os.path.join(WEB, "ajustes.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(limpio, f, ensure_ascii=False, indent=1)
            os.replace(tmp, os.path.join(WEB, "ajustes.json"))
            log("ajustes de animacion guardados")
            return self._json(200, {"ok": True})
        if self.path == "/api/liberar":   # {"chat": cmd}: ✕ en la mascota/celular -> el chat deja de esperarte
            try:
                cmd = str(json.loads(self.rfile.read(min(self._largo(), 2000)).decode())["chat"])
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            s = sesion_por_cmd(cmd)
            if s and os.path.exists(os.path.join(PUENTE, s["session_id"] + ".esperando")):
                open(os.path.join(PUENTE, s["session_id"] + ".liberar"), "w").close()
                return self._json(200, {"ok": True})
            return self._json(200, {"ok": False, "error": "ese chat no te estaba esperando"})
        if self.path == "/api/permiso":   # {"id": "ab12cd34", "decision": "allow" | "deny"}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ok = responder_permiso(str(d.get("id")), str(d.get("decision")), str(d.get("motivo") or ""),
                                   str(d.get("alcance") or ""))
            return self._json(200, {"ok": ok} if ok else {"ok": False, "error": "ya caducó: se preguntó en la PC"})
        if self.path == "/api/reglas":   # (22-oct, mejora 2) {} = listar; {"borrar": clave, "sesion": sid|""} = quitar una
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 4000)).decode() or "{}")
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            reg = leer_reglas()
            if d.get("borrar"):
                if d.get("sesion"):
                    reg["tarea"][d["sesion"]] = [c for c in reg["tarea"].get(d["sesion"], []) if c != d["borrar"]]
                    if not reg["tarea"][d["sesion"]]:
                        reg["tarea"].pop(d["sesion"])
                else:
                    reg["siempre"] = [c for c in reg["siempre"] if c != d["borrar"]]
                guardar_reglas(reg); log("regla quitada")
            nombres = {s.get("session_id"): s.get("titulo") or "" for s in sesiones()} if reg["tarea"] else {}
            return self._json(200, {"ok": True, "siempre": reg["siempre"],
                                    "tarea": [{"sesion": k, "chat": nombres.get(k, k[:8]), "claves": v} for k, v in reg["tarea"].items()]})
        if self.path == "/api/pregunta":   # (19-oct) {"id": "ab12cd34", "respuestas": {"pregunta": "etiqueta"}}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 8000)).decode())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ok = responder_pregunta(str(d.get("id")), d.get("respuestas"))
            return self._json(200, {"ok": ok} if ok else {"ok": False, "error": "ya caducó: se preguntó en la PC"})
        if self.path == "/api/probar":   # (14-oct) boton de diagnostico.html: aviso de prueba a todos los celulares
            try:
                n = len(json.load(open(SUSC, encoding="utf-8")))
            except Exception:
                n = 0
            if not n:
                return self._json(200, {"ok": False, "error": "no hay celulares registrados (activa los avisos en la app)"})
            threading.Thread(target=push_a_todos, args=("Kodama", "Aviso de prueba ✅ — si lo ves, los avisos andan.", ""), daemon=True).start()
            return self._json(200, {"ok": True, "celulares": n})
        if self.path == "/api/ticket":   # (15-oct) solo la mascota (con su clave): ticket de 60 s para abrir el panel
            if not hmac.compare_digest(self.headers.get("X-Companero-Local", ""), CLAVE_LOCAL or "-"):
                return self._json(403, {"ok": False})
            for k in [k for k, v in TICKETS.items() if v < time.time()]:
                del TICKETS[k]
            t = secrets.token_urlsafe(18); TICKETS[t] = time.time() + 60
            return self._json(200, {"ok": True, "ticket": t})
        if self.path in ("/api/hooks", "/api/desinstalar"):   # (22-oct, mejora 5) revisar / arreglar / desinstalar
            d = self._cuerpo()
            py = plataforma.python_para_scripts(config.APP_DIR)
            ins = os.path.join(config.APP_DIR, "instalar.py")
            if self.path == "/api/desinstalar":
                if not self._en_pc():   # desinstalar NUNCA desde el celular
                    return self._json(403, {"ok": False, "error": "Desinstalar se hace desde la PC."})
                args = [py, ins, "--quitar"] + (["--restaurar"] if d.get("restaurar") else [])
                r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                                   **plataforma.sin_ventana())
                log(f"desinstalado desde Ajustes (restaurar={bool(d.get('restaurar'))}): {r.returncode}")
                return self._json(200, {"ok": r.returncode == 0, "detalle": [x.strip() for x in r.stdout.splitlines() if x.strip()][-8:]})
            if d.get("arreglar"):
                r = subprocess.run([py, ins, "--arreglar-hooks"], capture_output=True, timeout=60, **plataforma.sin_ventana())
                log(f"hooks arreglados desde Ajustes: {r.returncode}")
            r = subprocess.run([py, ins, "--revisar"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=30, **plataforma.sin_ventana())
            try:
                return self._json(200, json.loads(r.stdout.strip().splitlines()[-1]))
            except Exception:
                return self._json(200, {"ok": False, "error": "no pude revisar"})
        if self.path == "/api/conectar/telegram":   # (21-oct) el token se pega en la PC, nunca en un chat
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            tok = str(self._cuerpo().get("token") or "").strip()
            bot = cc.probar_token(tok)
            if not bot:
                return self._json(200, {"ok": False, "error": "Telegram no reconoce ese token: cópialo de nuevo del mensaje de @BotFather."})
            cc.guardar_token(tok); poner_token(tok, bot)
            log(f"telegram configurado (bot @{bot})")
            return self._json(200, {"ok": True, "bot": bot})
        if self.path == "/api/conectar/tailscale":   # {"accion": "login" | "publicar"}
            if not self._en_pc():
                return self._json(403, {"ok": False})
            import companero_conectar as cc
            acc = self._cuerpo().get("accion")
            if acc == "login":
                return self._json(200, {"ok": True, "tailscale": cc.iniciar_sesion_tailscale()})
            if acc == "publicar":
                r = cc.publicar(BASE)
                if r.get("ok"):
                    log(f"app del celular publicada en {r['url']}")
                return self._json(200, r)
            return self._json(400, {"ok": False})
        if self.path == "/api/reporte":   # (21-oct) "Reportar un problema": zip en el Escritorio + formulario del issue
            try:
                import companero_reporte
                ruta = companero_reporte.reportar(chequear_salud(), redactar)
                log(f"reporte armado: {os.path.basename(ruta)}")
                return self._json(200, {"ok": True, "archivo": os.path.basename(ruta)})
            except Exception as e:
                log(f"reporte: {type(e).__name__}: {e}")
                return self._json(200, {"ok": False, "error": f"{type(e).__name__}"})
        if self.path == "/api/actualizar":   # (21-oct) bajar, verificar firma y sha256, e instalar
            # (22-oct) tambien desde Ajustes del celular (el dueno, ya autorizado arriba por Tailscale), no solo la mascota
            r = actualizar_ahora()
            return self._json(200, r)
        if self.path == "/api/actualizar-auto":   # (22-oct) {} = estado; {"activar": bool} = "Actualizar sola" (apagado por defecto)
            d = self._cuerpo()
            if "activar" in d:
                json.dump({"activa": bool(d["activar"])}, open(AUTO_ACT, "w", encoding="utf-8")); log(f"actualizar sola: {bool(d['activar'])}")
            try:
                nueva = json.load(open(ACTUALIZACION, encoding="utf-8"))
            except (OSError, ValueError):
                nueva = None
            return self._json(200, {"ok": True, "activa": actualizar_sola(), "actual": config.VERSION, "nueva": nueva})
        if self.path == "/api/medir":   # (15-oct) boton "Actualizar" del celular: lectura exacta del uso del plan
            err = pedir_medicion(forzar=True)
            return self._json(200, {"ok": not err, "error": err})
        if self.path == "/api/grupo-chat":   # (15-oct) {"chat": id, "grupo": "Nombre" o "" (sin grupo)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, g = str(d["chat"]), " ".join(str(d.get("grupo") or "").split())[:30]
                assert any(c["chat"] == cmd for c in candidatos())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            a = grupos_propios()
            if g:
                a[cmd] = g
            else:
                a.pop(cmd, None)
            poner_grupo(a)
            return self._json(200, {"ok": True})
        if self.path == "/api/sincronizar-grupos":
            return self._json(200, {"ok": True, "chats": sincronizar_grupos()})
        if self.path == "/api/color":   # (14-oct) {"chat": <id de chat>, "color": "#rrggbb" o "" (el de siempre)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, color = str(d["chat"]), str(d.get("color") or "")
                assert color == "" or _re.fullmatch(r"#[0-9a-fA-F]{6}", color)
                assert any(c["chat"] == cmd for c in candidatos())
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            poner_color(cmd, color)
            return self._json(200, {"ok": True})
        if self.path == "/api/ocultar":   # (14-oct) {"id": <session id de candidatos()>, "oculto": true|false}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cli, oculto = str(d["id"]), bool(d.get("oculto"))
                assert any(c["id"] == cli for c in candidatos())   # solo chats de la lista, nada inventado
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            ocultar_chat(cli, oculto)
            return self._json(200, {"ok": True})
        if self.path == "/api/silenciar":   # {"chat": cmd, "horas": 1 | 8 | 0 (quitar)}
            try:
                d = json.loads(self.rfile.read(min(self._largo(), 2000)).decode())
                cmd, horas = str(d["chat"]), max(0.0, min(float(d.get("horas", 1)), 72.0))
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            silenciar(cmd, horas)
            return self._json(200, {"ok": True})
        if self.path == "/api/personaje":   # (22-oct) la MISMA mascota en la PC y el celular: {} = leer; {pj, color, florCactus} = guardar
            d, ruta = self._cuerpo(), os.path.join(BASE, "personaje.json")
            if d.get("pj"):
                # (27-oct, lanzamiento) la cápsula se elige SOLO en la PC: si quien guarda (el celular) no manda capsulaColor,
                # se conserva el que ya estaba en el archivo (antes se pisaba con "blanca")
                try: antes = json.load(open(ruta, encoding="utf-8"))
                except (OSError, ValueError): antes = {}
                cap = d.get("capsulaColor")
                if cap not in ("blanca", "negra"): cap = "negra" if antes.get("capsulaColor") == "negra" else "blanca"
                nuevo = {"pj": str(d["pj"])[:40], "color": str(d.get("color") or "negro")[:20],
                         "florCactus": d.get("florCactus") is not False,
                         # (26-oct, LShinox) color de la cápsula elegido por el usuario (en la PC)
                         "capsulaColor": cap, "ts": time.time()}
                json.dump(nuevo, open(ruta, "w", encoding="utf-8")); log(f"personaje: {nuevo['pj']} {nuevo['color']}")
                return self._json(200, {"ok": True, **_pj_visible(nuevo)})
            try:
                return self._json(200, {"ok": True, **_pj_visible(json.load(open(ruta, encoding="utf-8")))})
            except (OSError, ValueError):
                return self._json(200, {"ok": True})
        if self.path == "/api/lectura-exacta":   # (22-oct) {} = estado; {"activar": true|false}
            d = self._cuerpo()
            return self._json(200, activar_lectura_exacta(d["activar"]) if "activar" in d else estado_lectura())
        if self.path in ("/api/archivar", "/api/archivados"):   # (22-oct) archivar/desarchivar por el chat de Kodama
            d = self._cuerpo()
            if self.path == "/api/archivar":   # {"chat": cmd}
                s = sesion_por_cmd(str(d.get("chat") or ""))
                local = grupos_app.local_de(s.get("session_id")) if s else None
                if not local:
                    return self._json(200, {"ok": False, "error": "no encuentro ese chat en la app de Claude"})
                if local == grupos_app.local_de((max(regs_medidor(), key=lambda x: x.get("visto", 0)) if regs_medidor() else {}).get("session_id")):
                    return self._json(200, {"ok": False, "error": "el chat de Kodama no se archiva"})
                err = ordenar_kodama("ARCHIVAR " + local)
                return self._json(200, {"ok": not err, "error": err})
            if d.get("desarchivar"):   # {"desarchivar": "local_…"}
                err = ordenar_kodama("DESARCHIVAR " + str(d["desarchivar"]))
                return self._json(200, {"ok": not err, "error": err})
            return self._json(200, {"ok": True, "chats": grupos_app.archivados()})
        if self.path == "/api/grupo":
            try:
                sel = json.loads(self.rfile.read(min(self._largo(), 2000)).decode()).get("id")
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            nombre = cambiar_seleccion(sel)
            return self._json(200, {"ok": True, "nombre": nombre} if nombre else {"ok": False, "error": "ese grupo no existe"})
        if self.path == "/api/bench":   # resultados de web/bench.html (prueba de rendimiento en el iPhone)
            datos = self.rfile.read(min(self._largo(), 20000)).decode(errors="replace")
            with open(os.path.join(BASE, "bench.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "datos": datos}, ensure_ascii=False) + "\n")
            log("bench recibido")
            return self._json(200, {"ok": True})
        if self.path == "/api/suscribir":
            try:
                sub = json.loads(self.rfile.read(min(self._largo(), 20000)).decode())
                host = urllib.parse.urlparse(sub.get("endpoint", "")).hostname or ""
                assert sub["endpoint"].startswith("https://") and "keys" in sub and \
                    _re.search(r"(^|\.)(push\.apple\.com|fcm\.googleapis\.com|push\.services\.mozilla\.com|notify\.windows\.com)$", host)
            except Exception:
                return self._json(400, {"ok": False, "error": "suscripción inválida"})
            try:
                subs = json.load(open(SUSC, encoding="utf-8"))
            except Exception:
                subs = []
            subs = [s for s in subs if s.get("endpoint") != sub["endpoint"]] + [sub]
            json.dump(subs, open(SUSC, "w", encoding="utf-8"))
            log("suscripción push guardada")
            threading.Thread(target=push_a_todos, args=("Kodama", "¡Listo! Ya te puedo avisar desde acá.", ""), daemon=True).start()
            return self._json(200, {"ok": True})
        if self.path == "/api/conservar":   # (16-oct) {"conservar": true|false}
            try:
                v = bool(json.loads(self.rfile.read(min(self._largo(), 2000)).decode()).get("conservar"))
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            tmp = CONSERVAR_JSON + ".tmp"
            json.dump({"conservar": v}, open(tmp, "w", encoding="utf-8")); os.replace(tmp, CONSERVAR_JSON)
            log(f"conservar siempre los archivos: {'SI' if v else 'no'}")
            return self._json(200, {"ok": True, "conservar": v})
        if self.path == "/api/limpieza":   # (16-oct) {"ids": [...]} de la ultima revision -> a la Papelera de reciclaje
            try:
                ids = json.loads(self.rfile.read(min(self._largo(), 200000)).decode()).get("ids") or []
                assert isinstance(ids, list)
            except Exception:
                return self._json(400, {"ok": False, "error": "pedido inválido"})
            return self._json(200, {"ok": True, **borrar_limpieza([str(i) for i in ids][:2000])})
        if self.path == "/api/subir":   # (16-oct) videos del celular: el archivo crudo (no base64), directo a disco por partes
            ext = VIDEO_TIPOS.get((self.headers.get("Content-Type") or "").split(";")[0].strip().lower())
            largo = self._largo()
            if not ext:
                return self._json(415, {"ok": False, "error": "solo videos (mp4, mov, webm, 3gp)"})
            if not largo or largo > VIDEO_MAX:
                return self._json(413, {"ok": False, "error": "video demasiado grande (máx. 5 GB)"})
            import shutil
            if shutil.disk_usage(BASE).free < largo + 8 * 1024 ** 3:   # nunca dejar el disco con menos de 8 GB libres
                return self._json(507, {"ok": False, "error": "no hay espacio en la PC para ese video"})
            os.makedirs(FOTOS, exist_ok=True)
            nombre = time.strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}{ext}"
            ruta, falta = os.path.join(FOTOS, nombre), largo
            try:
                with open(ruta + ".parcial", "wb") as f:
                    while falta > 0:
                        b = self.rfile.read(min(1 << 20, falta))
                        if not b:
                            raise ConnectionError("corte")
                        f.write(b); falta -= len(b)
                os.replace(ruta + ".parcial", ruta)
            except Exception as e:
                try:
                    os.remove(ruta + ".parcial")
                except OSError:
                    pass
                return self._json(400, {"ok": False, "error": f"no llegó entero ({type(e).__name__})"})
            log(f"video del celular guardado: {nombre} ({largo // (1024 * 1024)} MB)")
            return self._json(200, {"ok": True, "archivo": nombre})
        if self.path != "/api/responder":
            return self._json(404, {"ok": False})
        try:
            largo = self._largo()
            if largo > 8 * 1024 * 1024:   # tope: una foto del celular ya comprimida entra holgada
                return self._json(413, {"ok": False, "error": "demasiado grande (máx. 8 MB)"})
            d = json.loads(self.rfile.read(largo).decode())
            cmd, texto = d.get("chat"), (d.get("texto") or "").strip()[:4000]
        except Exception:
            return self._json(400, {"ok": False, "error": "pedido inválido"})
        s = sesion_por_cmd(cmd) if cmd else None
        foto = d.get("foto") or ""
        if foto.startswith("data:image/"):
            try:
                import base64
                ruta = guardar_foto(base64.b64decode(foto.split(",", 1)[1]), carpeta=carpeta_medios(cmd))
                texto = texto_con_foto(ruta, texto)
            except Exception as e:
                return self._json(400, {"ok": False, "error": f"foto inválida ({type(e).__name__})"})
        video = str(d.get("video") or "")   # (16-oct) nombre que devolvio /api/subir (solo el nombre, nunca una ruta)
        if video:
            ruta = os.path.join(FOTOS, os.path.basename(video))
            if os.path.basename(video) != video or not os.path.isfile(ruta) or os.path.splitext(video)[1] not in VIDEO_TIPOS.values():
                return self._json(400, {"ok": False, "error": "video inválido"})
            destino = carpeta_medios(cmd)   # se subio a estado\fotos (sin saber el chat): ahora va a la carpeta del chat
            if destino != FOTOS:
                try:
                    os.makedirs(destino, exist_ok=True)
                    import shutil
                    ruta = shutil.move(ruta, os.path.join(destino, video))
                except OSError as e:
                    log(f"video: no lo pude mover a {destino} ({type(e).__name__}); queda en estado\\fotos")
            texto = texto_con_video(os.path.normpath(ruta), texto)
        if s and s.get("agente") == "codex":   # (20-oct) Codex etapa 1: avisos y permisos, todavia sin responder
            return self._json(400, {"ok": False, "error": "a los chats de Codex todavía no se les puede escribir desde aquí; los permisos sí se aprueban"})
        if s and s.get("agente") == "antigravity":   # (20-oct) Antigravity etapa 1: solo avisos
            return self._json(400, {"ok": False, "error": "a los chats de Antigravity todavía no se les puede escribir desde aquí"})
        if not s or not texto:
            log(f"respuesta NO entregada a {cmd}: {'sin sesion registrada' if not s else 'texto vacio'}")   # (15-oct) diagnostico
            return self._json(400, {"ok": False, "error": "chat o texto vacío"})
        marca = "📱 " if getattr(self, "_via_celular", False) else "🐾 "
        err = entregar(s, texto, marca)
        if err and ("FileNotFoundError" in err or "no registró su buzón" in err):
            # (15-oct) el chat esta DORMIDO (la app de Claude apago su proceso por inactividad): no hay buzon. El
            # mensaje queda en cola y se entrega solo apenas el chat despierte (al abrirlo en la PC)
            poner_pendiente(cmd, texto, marca, s.get("socket"))
            with open(RESP, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "evento": "yo", "chat": cmd, "texto": texto,
                                    "via": "celular" if getattr(self, "_via_celular", False) else "pc"}, ensure_ascii=False) + "\n")
            log(f"respuesta EN COLA para {cmd} (chat dormido)")
            return self._json(200, {"ok": True, "pendiente": True, "despertando": segundos_sin_uso() >= 120})
        if err:
            log(f"respuesta NO entregada a {cmd}: {err}")
            return self._json(200, {"ok": False, "error": err})
        with open(RESP, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "evento": "yo", "chat": cmd, "texto": texto,
                                "via": "celular" if getattr(self, "_via_celular", False) else "pc"}, ensure_ascii=False) + "\n")
        log(f"respuesta web -> {cmd}")
        CERRAR.append((cmd, texto))
        return self._json(200, {"ok": True})
