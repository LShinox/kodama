# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov-2026) Archivos con tokens y claves (integraciones.json, correo.json, ia.json) cifrados con DPAPI del usuario
de Windows (crypt32 via ctypes, sin dependencias nuevas). Fuera de Windows se guardan como JSON plano.
Un archivo viejo en texto plano se lee igual y se vuelve a guardar cifrado la primera vez que se lee.
Si el archivo cifrado no se puede leer, se devuelve el valor por defecto y el archivo NO se toca."""
import base64
import ctypes
import json
import os
import sys
import tempfile

try:
    from kodama_nucleo import log
except ImportError:
    def log(*args):
        pass

MARCA = b"KODAMA-DPAPI-1\n"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _dpapi(funcion, datos):
    """Llama CryptProtectData o CryptUnprotectData y devuelve los bytes de salida. Libera la memoria de Windows."""
    if sys.platform != "win32":
        raise OSError("DPAPI solo existe en Windows")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    entrada = ctypes.create_string_buffer(datos, len(datos))   # se queda vivo hasta que termina la llamada
    b_in = Blob(len(datos), ctypes.cast(entrada, ctypes.POINTER(ctypes.c_char)))
    b_out = Blob()
    llamada = getattr(crypt32, funcion)
    ok = llamada(ctypes.byref(b_in), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(b_out))
    if not ok:
        raise OSError(f"{funcion} fallo (codigo {ctypes.get_last_error()})")
    try:
        return ctypes.string_at(ctypes.cast(b_out.pbData, ctypes.c_void_p).value, b_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(b_out.pbData, ctypes.c_void_p))


def _proteger(datos):
    """Cifra con la clave del usuario actual de Windows."""
    return _dpapi("CryptProtectData", datos)


def _desproteger(datos):
    """Descifra lo que cifro este mismo usuario en esta misma PC."""
    return _dpapi("CryptUnprotectData", datos)


def _escribir_atomico(ruta, contenido):
    """Temporal en la misma carpeta y despues os.replace: nunca queda un archivo a medias."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
        os.replace(tmp, ruta)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def guardar(ruta, obj):
    """Guarda obj: en Windows cifrado (MARCA + base64 de DPAPI); en otros sistemas, JSON plano."""
    texto = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if sys.platform == "win32":
        contenido = MARCA + base64.b64encode(_proteger(texto))
    else:
        contenido = texto
    _escribir_atomico(os.fspath(ruta), contenido)


def leer(ruta, defecto):
    """Lee el archivo. Faltante = defecto. Cifrado = descifra. Texto plano viejo = lo lee y, en Windows, lo cifra.
    Cualquier error = defecto, sin sobrescribir el archivo."""
    ruta = os.fspath(ruta)
    nombre = os.path.basename(ruta)
    if not os.path.exists(ruta):
        return defecto
    try:
        with open(ruta, "rb") as f:
            crudo = f.read()
        if crudo.startswith(MARCA):
            return json.loads(_desproteger(base64.b64decode(crudo[len(MARCA):])).decode("utf-8"))
        datos = json.loads(crudo.decode("utf-8"))    # formato viejo: JSON plano
    except Exception as e:
        log(f"secreto: no se pudo leer {nombre}: {type(e).__name__}")
        return defecto
    if sys.platform == "win32":
        try:
            guardar(ruta, datos)
            log(f"secreto: {nombre} cifrado")
        except Exception as e:
            log(f"secreto: no se pudo cifrar {nombre}: {type(e).__name__}")
    return datos
