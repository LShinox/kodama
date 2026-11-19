# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(06-nov-2026) Notas de llamadas: graba el microfono y el sonido de la PC en dos pistas WAV, sin librerias aparte (WASAPI por ctypes). Solo Windows.
Pistas: mono, 16 bits, unos 16 kHz, unos 2 MB por minuto cada una. Si la PC no suena, WASAPI no entrega datos: se rellena con silencio para que las dos pistas sigan alineadas."""
import array
import ctypes
import os
import sys
import threading
import time
import uuid
import wave
from ctypes import POINTER, byref, c_longlong, c_ubyte, c_uint32, c_uint64, c_ulong, c_void_p

OBJETIVO = 16000
MICROFONO, SISTEMA = 1, 0   # EDataFlow: eCapture, eRender
LOOPBACK = 0x00020000
SILENCIO = 0x2   # AUDCLNT_BUFFERFLAGS_SILENT
UN_SEGUNDO = 10_000_000   # en unidades de 100 ns
CLSID_ENUMERADOR = "BCDE0395-E52F-467C-8E3D-C4579291692E"
IID_ENUMERADOR = "A95664D2-9614-4F35-A746-DE8DB63617E6"
IID_CLIENTE = "1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"
IID_CAPTURA = "C8ADBD64-E71E-48A0-A4DE-185C395CD317"


class ErrorAudio(Exception):
    pass


def _clip(v):
    return 32767 if v >= 1.0 else -32768 if v <= -1.0 else int(v * 32767)


def a_mono(datos, canales, tipo, paso, resto):
    """Bytes del dispositivo a mono de 16 bits, promediando cada `paso` muestras. Devuelve (array 'h', lo que sobra para el siguiente bloque)."""
    a = array.array(tipo)
    a.frombytes(datos[:len(datos) - len(datos) % a.itemsize])
    lista = resto + (a[0::canales] if canales > 1 else a).tolist()
    n = len(lista) // paso * paso
    escala = 1.0 if tipo == "f" else 1 / 32768
    salida = array.array("h", (_clip(sum(lista[i:i + paso]) / paso * escala) for i in range(0, n, paso)))
    return salida, lista[n:]


def formato(wfx):
    """(canales, frecuencia, tamano de cuadro, tipo de muestra 'f' o 'h') de un WAVEFORMATEX o WAVEFORMATEXTENSIBLE, como bytes."""
    etiqueta = int.from_bytes(wfx[0:2], "little")
    canales = int.from_bytes(wfx[2:4], "little")
    hz = int.from_bytes(wfx[4:8], "little")
    cuadro = int.from_bytes(wfx[12:14], "little")
    bits = int.from_bytes(wfx[14:16], "little")
    if etiqueta == 0xFFFE:
        etiqueta = int.from_bytes(wfx[24:28], "little")
    if etiqueta == 3 and bits == 32:
        return canales, hz, cuadro, "f"
    if etiqueta == 1 and bits == 16:
        return canales, hz, cuadro, "h"
    raise ErrorAudio(f"formato de audio no soportado: {etiqueta}/{bits}")


def _guid(texto):
    return (c_ubyte * 16).from_buffer_copy(uuid.UUID(texto).bytes_le)


def _com(p, indice, *tipos):
    """Metodo numero `indice` de la vtable del objeto COM p. HRESULT negativo levanta OSError."""
    tabla = ctypes.cast(p, POINTER(POINTER(c_void_p))).contents
    return lambda *a: ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *tipos)(tabla[indice])(p, *a)


def _soltar(p):
    if p:
        tabla = ctypes.cast(p, POINTER(POINTER(c_void_p))).contents
        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(tabla[2])(p)


class Pista(threading.Thread):
    def __init__(self, flujo, ruta, t0, parar):
        super().__init__(daemon=True)
        self.flujo, self.ruta, self.t0, self.parar = flujo, ruta, t0, parar
        self.error, self.pico, self.segundos = None, 0, 0.0

    def run(self):
        try:
            self._grabar()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"

    def _grabar(self):
        ole = ctypes.OleDLL("ole32")
        ole.CoInitializeEx(None, 0)
        ole.CoTaskMemFree.restype = None
        ole.CoTaskMemFree.argtypes = [c_void_p]
        enumerador, dispositivo, cliente, captura, wfx = c_void_p(), c_void_p(), c_void_p(), c_void_p(), c_void_p()
        try:
            ole.CoCreateInstance(byref(_guid(CLSID_ENUMERADOR)), None, 23, byref(_guid(IID_ENUMERADOR)), byref(enumerador))
            _com(enumerador, 4, c_uint32, c_uint32, POINTER(c_void_p))(self.flujo, 0, byref(dispositivo))
            _com(dispositivo, 3, c_void_p, c_uint32, c_void_p, POINTER(c_void_p))(byref(_guid(IID_CLIENTE)), 23, None, byref(cliente))
            _com(cliente, 8, POINTER(c_void_p))(byref(wfx))
            canales, hz, cuadro, tipo = formato(ctypes.string_at(wfx, 40))
            banderas = LOOPBACK if self.flujo == SISTEMA else 0
            _com(cliente, 3, c_uint32, c_uint32, c_longlong, c_longlong, c_void_p, c_void_p)(0, banderas, UN_SEGUNDO, 0, wfx, None)
            _com(cliente, 14, c_void_p, POINTER(c_void_p))(byref(_guid(IID_CAPTURA)), byref(captura))
            paso = max(1, round(hz / OBJETIVO))
            salida_hz = hz // paso
            with wave.open(self.ruta, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(salida_hz)
                self._bucle(cliente, captura, w, canales, cuadro, tipo, paso, salida_hz)
        finally:
            if wfx:
                ole.CoTaskMemFree(wfx)
            for p in (captura, cliente, dispositivo, enumerador):
                _soltar(p)
            ole.CoUninitialize()

    def _bucle(self, cliente, captura, w, canales, cuadro, tipo, paso, hz):
        siguiente = _com(captura, 5, POINTER(c_uint32))
        tomar = _com(captura, 3, POINTER(c_void_p), POINTER(c_uint32), POINTER(c_uint32), POINTER(c_uint64), POINTER(c_uint64))
        soltar = _com(captura, 4, c_uint32)
        escritos, resto = 0, []
        _com(cliente, 10)()
        try:
            while not self.parar.is_set():
                time.sleep(0.05)
                tam = c_uint32()
                siguiente(byref(tam))
                while tam.value:
                    datos, cuadros, banderas = c_void_p(), c_uint32(), c_uint32()
                    tomar(byref(datos), byref(cuadros), byref(banderas), None, None)
                    bruto = bytes(cuadros.value * cuadro) if banderas.value & SILENCIO else ctypes.string_at(datos, cuadros.value * cuadro)
                    soltar(cuadros.value)
                    mono, resto = a_mono(bruto, canales, tipo, paso, resto)
                    if len(mono):
                        self.pico = max(self.pico, max(abs(max(mono)), abs(min(mono))))
                        w.writeframesraw(mono.tobytes())
                        escritos += len(mono)
                    siguiente(byref(tam))
                esperados = int((time.monotonic() - self.t0) * hz)
                if esperados - escritos > hz // 4:   # la PC no estaba sonando
                    w.writeframesraw(bytes((esperados - escritos) * 2))
                    escritos = esperados
                self.segundos = escritos / hz
        finally:
            _com(cliente, 11)()


class Grabacion:
    """Dos pistas a la vez: microfono.wav (tu) y sistema.wav (lo que suena en la PC)."""

    def __init__(self, carpeta):
        os.makedirs(carpeta, exist_ok=True)
        self.parar_ev = threading.Event()
        t0 = time.monotonic()
        self.mic = Pista(MICROFONO, os.path.join(carpeta, "microfono.wav"), t0, self.parar_ev)
        self.sis = Pista(SISTEMA, os.path.join(carpeta, "sistema.wav"), t0, self.parar_ev)

    def iniciar(self):
        self.mic.start()
        self.sis.start()

    def parar(self):
        self.parar_ev.set()
        self.mic.join(5)
        self.sis.join(5)
        return {"microfono": {"pico": self.mic.pico, "segundos": round(self.mic.segundos, 1), "error": self.mic.error},
                "sistema": {"pico": self.sis.pico, "segundos": round(self.sis.segundos, 1), "error": self.sis.error}}


if __name__ == "__main__":
    g = Grabacion(sys.argv[2])
    g.iniciar()
    time.sleep(float(sys.argv[1]))
    print(g.parar())
