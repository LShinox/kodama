# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov-2026) Chat con proveedores de IA con la clave del propio usuario o con un servidor local.
La clave nunca sale en lo que se devuelve ni en el log: la vista publica solo dice si existe."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from kodama_nucleo import BASE, log
import kodama_secreto

CONF = os.path.join(BASE, "ia.json")
OLLAMA = "http://127.0.0.1:11434"
APAGAR_OLLAMA_SEG = 600
SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0
PROVEEDORES = {
    "openrouter": {"nombre": "OpenRouter", "base": "https://openrouter.ai/api/v1", "tipo": "openai", "clave": True, "nube": True},
    "openai": {"nombre": "OpenAI", "base": "https://api.openai.com/v1", "tipo": "openai", "clave": True, "nube": True},
    "gemini": {"nombre": "Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "tipo": "openai", "clave": True, "nube": True},
    "deepseek": {"nombre": "DeepSeek", "base": "https://api.deepseek.com/v1", "tipo": "openai", "clave": True, "nube": True},
    "groq": {"nombre": "Groq", "base": "https://api.groq.com/openai/v1", "tipo": "openai", "clave": True, "nube": True},
    "anthropic": {"nombre": "Anthropic", "base": "https://api.anthropic.com/v1", "tipo": "anthropic", "clave": True, "nube": True},
    "ollama": {"nombre": "Ollama (local)", "base": "http://127.0.0.1:11434/v1", "tipo": "openai", "clave": False, "nube": False},
    "lmstudio": {"nombre": "LM Studio (local)", "base": "http://127.0.0.1:1234/v1", "tipo": "openai", "clave": False, "nube": False},
}
MAX_MENSAJES = 30
MAX_CARACTERES = 60000
MAX_TXT = 300


class ErrorIA(Exception):
    """Texto seguro para mostrar: solo codigo HTTP o nombre de la excepcion, nunca URL, cabeceras ni clave."""


def _leer_json(ruta, defecto):
    """ia.json (con claves): se lee y se guarda con kodama_secreto (cifrado en Windows)."""
    d = kodama_secreto.leer(ruta, defecto)
    return d if isinstance(d, dict) else defecto


def _guardar_json(ruta, d):
    kodama_secreto.guardar(ruta, d)


def leer_conf(ruta=None):
    """{"elegido": pid o None, "config": {pid: {"clave", "modelo"}}} con solo los proveedores conocidos."""
    d = _leer_json(ruta or CONF, {})
    cfg = d.get("config") if isinstance(d.get("config"), dict) else {}
    salida = {}
    for pid in PROVEEDORES:
        x = cfg.get(pid) if isinstance(cfg.get(pid), dict) else {}
        salida[pid] = {
            "clave": x.get("clave") if isinstance(x.get("clave"), str) else "",
            "modelo": x.get("modelo") if isinstance(x.get("modelo"), str) else "",
        }
    elegido = d.get("elegido")
    return {"elegido": elegido if elegido in PROVEEDORES else None, "config": salida}


def guardar(pid, clave=None, modelo=None, ruta=None):
    """Guarda clave y modelo de un proveedor conocido. Clave vacia = se queda la vieja; la clave solo se guarda si el proveedor la usa."""
    if pid not in PROVEEDORES:
        raise ValueError("proveedor desconocido")
    c = leer_conf(ruta)
    cfg = c["config"][pid]
    if clave is not None and PROVEEDORES[pid]["clave"] and str(clave).strip():
        cfg["clave"] = str(clave).strip()[:MAX_TXT]
    if modelo is not None:
        cfg["modelo"] = str(modelo).strip()[:MAX_TXT]
    _guardar_json(ruta or CONF, c)
    return vista_publica(ruta)


def elegir(pid, ruta=None):
    """Proveedor por defecto. None lo quita."""
    if pid is not None and pid not in PROVEEDORES:
        raise ValueError("proveedor desconocido")
    c = leer_conf(ruta)
    c["elegido"] = pid
    _guardar_json(ruta or CONF, c)
    return vista_publica(ruta)


def vista_publica(ruta=None):
    """Lista de proveedores y cual esta elegido. Nunca incluye la clave."""
    c = leer_conf(ruta)
    lista = []
    for pid, p in PROVEEDORES.items():
        cfg = c["config"][pid]
        lista.append({
            "id": pid,
            "nombre": p["nombre"],
            "nube": p["nube"],
            "necesita_clave": p["clave"],
            "configurado": (not p["clave"]) or bool(cfg["clave"]),
            "modelo": cfg["modelo"],
        })
    return {"proveedores": lista, "elegido": c["elegido"]}


def pedir_json(metodo, url, cabeceras, cuerpo=None, timeout=120):
    """Peticion HTTP con verificacion SSL normal. Los errores salen como ErrorIA sin URL ni cabeceras."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    cab = {"User-Agent": "kodama", "Accept": "application/json"}
    cab.update(cabeceras or {})
    if datos is not None:
        cab.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErrorIA(f"HTTP {e.code}") from None
    except Exception as e:
        raise ErrorIA(type(e).__name__) from None


def arrancar_ollama():
    """(06-nov) Ollama no arranca con la PC, para no gastar memoria. Devuelve el proceso si lo arranco aqui; None si ya corria."""
    try:
        urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3).read()
        return None
    except OSError:
        pass
    exe = shutil.which("ollama") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    if not os.path.exists(exe):
        raise ErrorIA("Ollama no está instalado")
    p = subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=SIN_VENTANA)
    for _ in range(30):
        time.sleep(1)
        try:
            urllib.request.urlopen(OLLAMA + "/api/tags", timeout=2).read()
            return p
        except OSError:
            pass
    cerrar_ollama(p)
    raise ErrorIA("Ollama no arrancó")


def cerrar_ollama(p):
    """Solo el proceso que arrancamos nosotros, por PID, con sus hijos."""
    if p:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=SIN_VENTANA)


_ollama = {"proc": None, "reloj": None}
_ollama_lock = threading.Lock()


def _apagar_ollama_propio():
    with _ollama_lock:
        p, _ollama["proc"], _ollama["reloj"] = _ollama["proc"], None, None
    cerrar_ollama(p)


def _ollama_a_demanda():
    """Para el chat: lo enciende si hace falta y lo apaga tras 10 min sin usarlo. Si ya corria por otro lado, no lo toca."""
    with _ollama_lock:
        if _ollama["reloj"]:
            _ollama["reloj"].cancel()
            _ollama["reloj"] = None
        if not _ollama["proc"]:
            _ollama["proc"] = arrancar_ollama()
        if _ollama["proc"]:
            _ollama["reloj"] = threading.Timer(APAGAR_OLLAMA_SEG, _apagar_ollama_propio)
            _ollama["reloj"].daemon = True
            _ollama["reloj"].start()


def _cabeceras(p, clave):
    """Cabeceras de autenticacion. Solo los proveedores de clave llevan Authorization o x-api-key."""
    if not p["clave"] or not clave:
        return {}
    if p["tipo"] == "anthropic":
        return {"x-api-key": clave, "anthropic-version": "2023-06-01"}
    return {"Authorization": "Bearer " + clave}


def modelos(pid, ruta=None, http=None):
    """Ids de modelo del proveedor, ordenados, maximo 200."""
    if pid not in PROVEEDORES:
        raise ValueError("proveedor desconocido")
    p = PROVEEDORES[pid]
    clave = leer_conf(ruta)["config"][pid]["clave"]
    if p["clave"] and not clave:
        raise ErrorIA("falta la clave")
    if pid == "ollama" and http is None:
        _ollama_a_demanda()
    data = (http or pedir_json)("GET", p["base"] + "/models", _cabeceras(p, clave))
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ErrorIA("respuesta rara")
    ids = {x["id"] for x in items if isinstance(x, dict) and isinstance(x.get("id"), str)}
    return sorted(ids)[:200]


def _filtrar(mensajes):
    """Solo user/assistant con texto; los ultimos 30; sin pasar de 60000 caracteres (se descartan los mas viejos)."""
    limpios = [m for m in (mensajes or []) if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    limpios = limpios[-MAX_MENSAJES:]
    salida, total = [], 0
    for m in reversed(limpios):
        if total + len(m["content"]) > MAX_CARACTERES:
            break
        total += len(m["content"])
        salida.append({"role": m["role"], "content": m["content"]})
    salida.reverse()
    return salida


def preguntar(mensajes, pid=None, modelo=None, ruta=None, http=None):
    """Envia la conversacion al proveedor y devuelve la respuesta de texto."""
    c = leer_conf(ruta)
    pid = pid or c["elegido"]
    if pid not in PROVEEDORES:
        return {"ok": False, "error": "falta elegir proveedor"}
    p = PROVEEDORES[pid]
    cfg = c["config"][pid]
    modelo = modelo or cfg["modelo"]
    if not modelo:
        return {"ok": False, "error": "falta elegir modelo"}
    if p["clave"] and not cfg["clave"]:
        return {"ok": False, "error": "falta la clave"}
    msgs = _filtrar(mensajes)
    if not msgs:
        return {"ok": False, "error": "sin mensajes"}
    cab = _cabeceras(p, cfg["clave"])
    try:
        if p["tipo"] == "anthropic":
            data = (http or pedir_json)("POST", p["base"] + "/messages", cab,
                                        {"model": modelo, "max_tokens": 2048, "messages": msgs})
            bloques = data["content"]
            texto = "".join(b["text"] for b in bloques if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
            if not isinstance(bloques, list) or not texto:
                raise KeyError("texto")
        else:
            cuerpo = {"model": modelo, "messages": msgs, "stream": False}
            if pid == "ollama":
                cuerpo["reasoning_effort"] = "none"   # (06-nov) con razonamiento, qwen3.5:2b pasaba de 120 s y daba TimeoutError; sin el, unos segundos
                if http is None:
                    _ollama_a_demanda()
            data = (http or pedir_json)("POST", p["base"] + "/chat/completions", cab, cuerpo)
            texto = data["choices"][0]["message"]["content"]
            if not isinstance(texto, str):
                raise TypeError("texto")
    except ErrorIA as e:
        log(f"ia {pid}: {e}")
        return {"ok": False, "error": str(e)}
    except (KeyError, IndexError, TypeError, AttributeError):
        return {"ok": False, "error": "respuesta rara"}
    return {"ok": True, "texto": texto, "modelo": modelo}
