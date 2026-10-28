# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Configuracion del Companero (14-oct-2026, paso 1 hacia el uso masivo): nada atado a una PC en el codigo.

Todo sale de la carpeta donde esta este archivo y de config.json (al lado). Si config.json no existe, valores
por defecto: sin chats fijos (se eligen desde los grupos de la app de Claude) y sin URL publica.

config.json:
{
  "url_publica": "https://kodama.<tu-tailnet>.ts.net",   # direccion de la app del celular (Tailscale)
  "token_telegram": "C:/ruta/al/token.txt",                  # opcional; vacio = sin Telegram
  "chats": [                                                  # chats fijos ("Personales"), por carpeta
    {"carpeta": "~/Proyectos/juego", "id": "juegos", "nombre": "Juegos", "emoji": "🎮", "color": "#2E8B57"}
  ],
  "colores": {"instalaciones": "#2F7FC1"}                     # color de chats agregados por sesion (opcional)
}
"""
import glob
import json
import os
import re

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(APP_DIR, "estado")
WEB = os.path.join(APP_DIR, "web")
TS_DIR = os.path.join(APP_DIR, "ts")
RESPALDOS = os.path.join(APP_DIR, "respaldos")
HOME = os.path.expanduser("~")
# (22-oct) carpeta del chat de Kodama (antes "Medidor", en APP_DIR\medidor): fuera de la carpeta del programa, asi ese
# chat no ve el codigo, y la app de Claude lo muestra como "Kodama"
CHAT_DIR = os.path.join(HOME, "Kodama")

try:
    _C = json.load(open(os.path.join(APP_DIR, "config.json"), encoding="utf-8-sig"))
except (OSError, ValueError):
    _C = {}

URL_PUBLICA = (_C.get("url_publica") or "").rstrip("/")
# (21-oct) soporte y actualizaciones por GitHub. (27-oct) El repo publico tambien aloja el codigo fuente, bajo PolyForm Noncommercial 1.0.0 (ver LICENCIA.txt); lo que se instala sigue siendo la release firmada
REPO = _C.get("repo") or "LShinox/kodama"
try:
    VERSION = open(os.path.join(APP_DIR, "VERSION"), encoding="utf-8").read().strip()
except OSError:
    VERSION = "0.0.0"
TOKEN_TELEGRAM = _C.get("token_telegram") or os.path.join(HOME, ".credentials", "telegram-bot.txt")

PUERTO_BASE = 8787                       # (26-oct) puerto de siempre del hub; si no se puede abrir se prueba 8788..8799
PUERTOS_HUB = [PUERTO_BASE] + list(range(8788, 8800))


def puerto_hub():
    """(26-oct) Puerto REAL del hub: lo escribe el hub en estado\\puerto.txt antes de quedar escuchando. Sin archivo, o con
    algo que no sea un puerto de la lista, 8787. Lo leen la mascota (por el comando `puerto` de Rust) y companero_conectar."""
    try:
        p = int(open(os.path.join(ESTADO, "puerto.txt"), encoding="utf-8").read().strip())
        return p if p in PUERTOS_HUB else PUERTO_BASE
    except (OSError, ValueError):
        return PUERTO_BASE


def clave_carpeta(ruta):
    """Como nombra Claude Code la carpeta del proyecto en ~/.claude/projects: todo lo que no es letra, numero o
    guion pasa a "-" (la carpeta Videos\\Musica del usuario "yo" -> C--Users-yo-Videos-Musica)."""
    return re.sub(r"[^A-Za-z0-9-]", "-", os.path.normpath(ruta))


CHATS = {}     # clave de carpeta -> (id, nombre, emoji)
COLORES = dict(_C.get("colores") or {})
for c in _C.get("chats") or []:
    if c.get("carpeta") and c.get("id"):
        CHATS[clave_carpeta(c["carpeta"])] = (c["id"], c.get("nombre") or c["id"], c.get("emoji") or "💬")
        if c.get("color"):
            COLORES[c["id"]] = c["color"]
PERSONALES = set(CHATS)
CARPETAS_PERSONALES = [c["carpeta"] for c in _C.get("chats") or [] if c.get("carpeta")]


# (14-oct) chats PERSONALES por regla de carpeta: toda sesion en una carpeta dentro de "raices_personales" que no
# este en "excluir_carpetas" (LShinox: "todo Videos\<X> con X distinto de Claude"). Cada sesion es su propio chat;
# los nuevos aparecen solos. "nombres" (por sesion) y "emoji_carpeta" solo cambian como se muestran.
RAICES = list(_C.get("raices_personales") or [])
EXCLUIR = list(_C.get("excluir_carpetas") or [])
EMOJI_CARPETA = dict(_C.get("emoji_carpeta") or {})
NOMBRES = {k: tuple(v) for k, v in (_C.get("nombres") or {}).items()}
OCULTOS_JSON = os.path.join(ESTADO, "ocultos.json")   # (14-oct) los que ocultas desde la app (Ajustes > Chats que se ven)
VISIBLES_JSON = os.path.join(ESTADO, "visibles.json")   # (16-oct) los de config.json "ocultar" que PRENDISTE desde la app
_OC = {"m": None, "v": set()}


def _leer_set(ruta, m):
    try:
        return set(json.load(open(ruta, encoding="utf-8"))) if m else set()
    except (OSError, ValueError, TypeError):
        return set()


def ocultos():
    """Sesiones que no van a la app: las de config.json "ocultar" (menos las que prendiste desde la app) + las que
    ocultaste desde la app. (16-oct) Antes el interruptor no podia prender uno de config.json: se volvia a apagar solo."""
    m = tuple(os.path.getmtime(r) if os.path.exists(r) else 0 for r in (OCULTOS_JSON, VISIBLES_JSON))
    if m != _OC["m"]:
        extra, visibles = _leer_set(OCULTOS_JSON, m[0]), _leer_set(VISIBLES_JSON, m[1])
        _OC.update(m=m, v=(set(_C.get("ocultar") or []) - visibles) | extra)
    return _OC["v"]


class _Ocultar:   # `sid in OCULTAR` sigue funcionando en todos lados, pero ahora mira tambien lo que ocultas desde la app
    def __contains__(self, sid):
        return sid in ocultos()


OCULTAR = _Ocultar()
NOMBRE = _C.get("nombre_usuario") or "el usuario"   # como se presenta tu respuesta en el puente
IDIOMA = "en" if _C.get("idioma") == "en" else "es"   # Telegram y avisos (la interfaz tiene su propio selector)
GRUPOS_APP = _C.get("mostrar_grupos_app", True)   # LShinox 14-oct: false (no quiere chats de empresa en la app)
FIJAS = {k: tuple(v) for k, v in (_C.get("sesiones_fijas") or {}).items()}   # sesiones de otras carpetas que van igual
# (14-oct) pestaña "Archivos" del celular: ademas de la carpeta de cada chat personal, estas (p. ej. la de Instalaciones)
CARPETAS_ARCHIVOS = [x for x in (_C.get("carpetas_archivos") or []) if isinstance(x, dict) and x.get("carpeta")]
_RAICES_K = [clave_carpeta(r) for r in RAICES]
_EXCLUIR_K = [clave_carpeta(e) for e in EXCLUIR]


def es_personal(clave_proyecto):
    """Para el hook (que solo ve la carpeta del transcript, ya convertida a clave)."""
    k = clave_proyecto or ""
    dentro = lambda raiz: k == raiz or k.startswith(raiz + "-")
    return any(dentro(r) for r in _RAICES_K) and not any(dentro(e) for e in _EXCLUIR_K)


def dir_app_claude():
    """La app de Claude en Windows es MSIX: su %APPDATA%\\Claude real vive en el paquete (ver grupos_app.py)."""
    local = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local")
    # (20-oct) la app mudo sus datos a %LOCALAPPDATA%\Claude-Data\claude_<id>\ (README.txt ahi; en el paquete quedo
    # solo ".user-data-left"): sin esto no se encontraban los chats (enlaces, grupos, Medidor).
    nuevo = [d for d in glob.glob(os.path.join(local, "Claude-Data", "claude_*"))
             if os.path.isdir(os.path.join(d, "claude-code-sessions"))]
    if nuevo:
        return max(nuevo, key=os.path.getmtime)
    real = glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude"))
    return real[0] if real else os.path.join(os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming"), "Claude")
