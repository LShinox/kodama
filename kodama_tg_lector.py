# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(18-nov) Lee Telegram en su propio hilo: si Telegram no responde, el bucle de avisos no espera."""
import queue
import threading
import time

ESPERA_MIN = 5
ESPERA_MAX = 300


class Lector:
    """Pide las novedades de Telegram en un hilo aparte y las deja en una cola para el bucle del hub."""

    def __init__(self, api, offset, log, dormir=time.sleep, timeout=25):
        self.api = api
        self.offset = offset
        self.log = log
        self.dormir = dormir
        self.timeout = timeout
        self.cola = queue.Queue()
        self.fallos = 0

    def una_vuelta(self):
        """Una consulta a Telegram. Devuelve los segundos a esperar antes de la siguiente."""
        r = self.api("getUpdates", _silencio=True, offset=self.offset, timeout=self.timeout)
        if r.get("ok"):
            if self.fallos > 0:
                self.log(f"Telegram volvio tras {self.fallos} fallos")
                self.fallos = 0
            for u in r.get("result", []):
                self.offset = u["update_id"] + 1
                self.cola.put(u)
            return 0
        self.fallos += 1
        if self.fallos == 1:
            self.log("Telegram no responde: reintento con espera creciente (5 s a 5 min)")
        return min(ESPERA_MAX, ESPERA_MIN * 2 ** (self.fallos - 1))

    def correr(self):
        while True:
            try:
                s = self.una_vuelta()
            except Exception as e:
                self.log(f"lector telegram: {type(e).__name__}")
                s = ESPERA_MIN
            if s:
                self.dormir(s)

    def iniciar(self):
        threading.Thread(target=self.correr, daemon=True).start()

    def tomar(self, espera):
        """Espera hasta `espera` s la primera novedad y devuelve todas las que haya, en orden."""
        try:
            nuevos = [self.cola.get(timeout=espera)]
        except queue.Empty:
            return []
        while True:
            try:
                nuevos.append(self.cola.get_nowait())
            except queue.Empty:
                return nuevos
