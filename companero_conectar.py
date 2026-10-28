# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(21-oct-2026) Asistente "Conectar celular" (pagina web\\conectar.html, se abre desde el menu del gato).

Dos caminos, se pueden usar los dos:
  - Telegram: sin instalar nada mas. La persona crea su bot con @BotFather, pega el token EN SU PC (nunca en un chat)
    y escanea un QR que abre su bot con /start <codigo>: queda emparejado solo con ella.
  - App del celular: por el Tailscale propio del Companero (userspace, socket companero-tailscaled). Iniciar sesion
    una vez en el navegador, publicar el puerto 8787 con `tailscale serve`, y en el celular: Tailscale con la misma
    cuenta + QR de la app.
Ningun token ni clave sale en logs ni en respuestas: solo "hay token" si/no y el nombre del bot.
"""
import io
import json
import os
import re
import subprocess
import time
import urllib.request

import config
import kodama_plataforma as plataforma

# (Mac-F2) Rutas y banderas por plataforma. Windows: el tailscale.exe y la tuberia del tailscaled propio de Kodama.
# macOS: la app de Tailscale del sistema, sin --socket (usa su socket por defecto).
TS_EXE = plataforma.ruta_tailscale_cli()
SOCKET = plataforma.socket_tailscale()


def _ts_base():
    return [TS_EXE] + ([f"--socket={SOCKET}"] if SOCKET else [])


def _ts(*args, timeout=20):
    return subprocess.run(_ts_base() + [*args], capture_output=True, text=True, timeout=timeout, **plataforma.sin_ventana())


def estado_tailscale():
    if not os.path.exists(TS_EXE):
        return {"instalado": False}
    try:
        s = json.loads(_ts("status", "--json").stdout or "{}")
    except Exception:
        return {"instalado": True, "estado": "sin respuesta"}
    usuario = ""
    try:
        uid = str((s.get("Self") or {}).get("UserID"))
        usuario = (s.get("User") or {}).get(uid, {}).get("LoginName", "")
    except Exception:
        pass
    dns = ((s.get("Self") or {}).get("DNSName") or "").rstrip(".")
    try:
        serve = str(config.puerto_hub()) in _ts("serve", "status").stdout   # (26-oct) el puerto real del hub (8787 salvo que no se pudiera abrir)
    except Exception:
        serve = False
    return {"instalado": True, "estado": s.get("BackendState", "?"), "auth_url": s.get("AuthURL") or "",
            "dns": dns, "usuario": usuario, "publicado": serve, "url_publica": config.URL_PUBLICA}


def iniciar_sesion_tailscale():
    """Lanza `up` sin esperar (se queda esperando el login) y devuelve la URL de inicio de sesion en cuanto aparece.
    (Mac-F2) En macOS no se toca el Tailscale de la persona (`up` cambiaria su nombre y sus ajustes): ella inicia sesion
    en la app de Tailscale y aqui solo se lee el estado."""
    if not plataforma.tailscale_propio():
        return estado_tailscale()
    subprocess.Popen(_ts_base() + ["up", "--hostname=kodama", "--unattended"],
                     close_fds=True, **plataforma.sin_ventana())
    for _ in range(20):
        time.sleep(1)
        e = estado_tailscale()
        if e.get("auth_url") or e.get("estado") == "Running":
            return e
    return estado_tailscale()


def publicar(base_estado):
    """`tailscale serve` del 8787 y guarda la direccion y la cuenta duena en config.json y estado\\web.json."""
    e = estado_tailscale()
    if e.get("estado") != "Running" or not e.get("dns"):
        return {"ok": False, "error": "Tailscale todavía no tiene la sesión iniciada"}
    r = _ts("serve", "--bg", str(config.puerto_hub()), timeout=40)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout).strip()[:300]}
    url = "https://" + e["dns"]
    ruta = os.path.join(config.APP_DIR, "config.json")
    try:
        c = json.load(open(ruta, encoding="utf-8-sig"))
    except (OSError, ValueError):
        c = {}
    c["url_publica"] = url
    json.dump(c, open(ruta, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    config.URL_PUBLICA = url
    if e.get("usuario"):
        w = os.path.join(base_estado, "web.json")
        try:
            wj = json.load(open(w, encoding="utf-8"))
        except (OSError, ValueError):
            wj = {}
        wj["dueno_web"] = e["usuario"]
        json.dump(wj, open(w, "w", encoding="utf-8"), indent=1)
    return {"ok": True, "url": url}


def probar_token(token):
    """getMe con ese token. Devuelve el usuario del bot o None (sin loguear nada: la URL lleva el token)."""
    if not re.fullmatch(r"\d{5,12}:[A-Za-z0-9_-]{30,50}", token or ""):
        return None
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=15) as r:
            d = json.load(r)
        return d.get("result", {}).get("username") if d.get("ok") else None
    except Exception:
        return None


def guardar_token(token):
    os.makedirs(os.path.dirname(config.TOKEN_TELEGRAM), exist_ok=True)
    tmp = config.TOKEN_TELEGRAM + ".tmp"
    open(tmp, "w", encoding="utf-8").write(token.strip() + "\n")
    os.replace(tmp, config.TOKEN_TELEGRAM)


def qr_svg(texto):
    import segno
    b = io.BytesIO()
    segno.make(texto, error="m").save(b, kind="svg", scale=6, border=2, dark="#1d1b20", light="#ffffff")
    return b.getvalue()
