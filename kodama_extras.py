# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov-2026) Modulos opcionales de Kodama: correo, integraciones, pausas e ia.
Vienen APAGADOS en instalaciones nuevas. Se prenden o apagan desde la PC (api/extras) y el estado se guarda en
estado\\extras.json. Si un modulo falta o no carga, Kodama sigue andando: modulo() devuelve None y esa parte no se usa.
Este archivo solo importa kodama_nucleo y kodama_secreto (cifrado de tokens), para que los modulos opcionales puedan importarlo sin ciclos."""
import importlib
import json
import os
import threading
import time

import kodama_secreto
from kodama_nucleo import BASE, log

# nombre del modulo opcional -> archivo kodama_*.py que lo implementa
MODULOS = {"correo": "kodama_correo", "integraciones": "kodama_integraciones", "pausas": "kodama_pausas", "ia": "kodama_ia"}
CACHE_SEG = 5
# el hub pone aqui su arrancar_extras(): al prender un modulo en la app, se arranca su vigilante sin reiniciar
al_encender = None

_LOCK = threading.Lock()
_cache = {"t": 0.0, "estado": None}
_avisados = set()


def ruta():
    return os.path.join(BASE, "extras.json")


def _log_una_vez(clave, texto):
    if clave not in _avisados:
        _avisados.add(clave)
        log(texto)


def _json_de(ruta_archivo):
    """Dict del archivo, o None si no existe. Archivo roto: kodama_secreto lo registra y devuelve {} (queda apagado)."""
    if not os.path.exists(ruta_archivo):
        return None
    d = kodama_secreto.leer(ruta_archivo, {})
    return d if isinstance(d, dict) else {}


def _tiene_cuentas(d):
    """correo.json: {"cuentas": [...]} con al menos una cuenta."""
    lista = d.get("cuentas") if d else None
    return isinstance(lista, list) and any(isinstance(c, dict) for c in lista)


def _tiene_proveedor(d):
    """integraciones.json: {"<proveedor>": {campos}} con al menos un campo de texto lleno."""
    if not d:
        return False
    return any(isinstance(c, dict) and any(isinstance(v, str) and v.strip() for k, v in c.items() if k != "activo")
               for c in d.values())


def _elegido(d):
    """ia.json: {"elegido": id} con un proveedor elegido."""
    return bool(d) and d.get("elegido") is not None


def _pausas_activas(d):
    """preferencias.json: {"pausas": {"activo": true}} explicito."""
    return bool(d) and isinstance(d.get("pausas"), dict) and d["pausas"].get("activo") is True


def _migrar():
    """Instalacion existente: prende lo que ya usa. Instalacion nueva (sin archivos) = todo apagado.
    Solo mira si existen los archivos y si tienen algo guardado; nunca muestra ni copia su contenido."""
    archivos = (("correo", "correo.json", _tiene_cuentas),
                ("integraciones", "integraciones.json", _tiene_proveedor),
                ("ia", "ia.json", _elegido),
                ("pausas", "preferencias.json", _pausas_activas))
    salida = {n: False for n in MODULOS}
    for nombre, archivo, mira in archivos:
        try:
            salida[nombre] = bool(mira(_json_de(os.path.join(BASE, archivo))))
        except Exception as e:
            _log_una_vez("migrar:" + nombre, f"extras: no pude revisar {archivo} para {nombre} ({type(e).__name__}); queda apagado")
    return salida


def _guardar(ruta_archivo, datos):
    """Escritura atomica: primero un .tmp y despues se reemplaza el archivo."""
    os.makedirs(os.path.dirname(ruta_archivo) or ".", exist_ok=True)
    tmp = ruta_archivo + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(tmp, ruta_archivo)


def cargar_estado():
    """Dict nombre -> bool. Archivo faltante: se crea con _migrar. Archivo roto: todo apagado (se avisa una vez)."""
    r = ruta()
    if not os.path.exists(r):
        estado = {n: False for n in MODULOS}
        mig = _migrar() or {}
        estado.update({n: bool(v) for n, v in mig.items() if n in MODULOS})
        try:
            _guardar(r, estado)
        except OSError as e:
            _log_una_vez("guardar", f"extras: no pude crear extras.json ({type(e).__name__})")
        return estado
    try:
        with open(r, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("no es un objeto")
    except (OSError, ValueError) as e:
        _log_una_vez("leer", f"extras: no pude leer extras.json ({type(e).__name__}); todo queda apagado")
        return {n: False for n in MODULOS}
    return {n: d.get(n) is True for n in MODULOS}


def activo(nombre):
    """Si el modulo esta encendido. Lee el archivo como mucho cada 5 s."""
    if nombre not in MODULOS:
        return False
    with _LOCK:
        if _cache["estado"] is None or time.time() - _cache["t"] >= CACHE_SEG:
            _cache["estado"] = cargar_estado()
            _cache["t"] = time.time()
        return bool(_cache["estado"].get(nombre))


def poner(nombre, valor):
    """Prende o apaga un modulo y guarda extras.json. Nombre desconocido = ValueError."""
    if nombre not in MODULOS:
        raise ValueError("modulo desconocido")
    with _LOCK:
        estado = cargar_estado()
        estado[nombre] = bool(valor)
        _guardar(ruta(), estado)
        _cache["estado"] = None
    return dict(estado)


def modulo(nombre):
    """El modulo ya importado, si esta encendido y carga. Si no, None."""
    if not activo(nombre):
        return None
    try:
        return importlib.import_module(MODULOS[nombre])
    except Exception as e:
        _log_una_vez("importar:" + nombre, f"extras: {nombre} encendido pero no carga ({type(e).__name__}); queda sin usar")
        return None


def disponible(nombre):
    """True si el archivo del modulo se puede importar, aunque este apagado."""
    if nombre not in MODULOS:
        return False
    try:
        importlib.import_module(MODULOS[nombre])
        return True
    except Exception:
        return False
