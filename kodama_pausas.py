# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(06-nov-2026) Recordatorios de agua y de levantarse, solo en la PC. Se mide el uso de la PC (mouse y teclado), no los chats:
- Sentado: suma mientras usas la PC. Con 5 min seguidos sin tocarla vuelve a cero, salvo con el microfono en uso (llamada), que sigue contando.
- Agua: suma lo mismo, pero una pausa no la reinicia; solo "Listo".
- "Despues" repite a los 10 min. Sin respuesta repite una vez a los 10 min y espera al siguiente ciclo.
- No se muestra en llamada, en horas de silencio ni con la PC sin uso; lo de chats pendientes lo mira el gato."""
import threading
import time

import kodama_prefs
from kodama_nucleo import log

PASO = 15
AUSENTE = 300     # sin tocar la PC: te levantaste
SIN_USO_OCULTA = 120
REPETIR = 600


class Pausas:
    """Sin reloj ni sistema: todo entra por argumentos, para poder probarla."""

    def __init__(self):
        self.sentado = self.agua = 0.0
        self.antes = None
        self.aviso = None          # {"tipo", "ts", "intento"}; ts 0 = todavia sin mostrar
        self.espera = {"levantarse": 0.0, "agua": 0.0}   # "Despues": hasta cuando no vuelve a salir

    def _reiniciar(self, tipo):
        if tipo == "levantarse":
            self.sentado = 0.0
        else:
            self.agua = 0.0
        if self.aviso and self.aviso["tipo"] == tipo:
            self.aviso = None

    def paso(self, ahora, sin_uso, mic, oculto, min_levantarse, min_agua):
        """Una vuelta. `oculto` = horas de silencio."""
        dt = 0.0 if self.antes is None else max(0.0, ahora - self.antes)
        self.antes = ahora
        if dt > 120:   # la PC estuvo dormida o el hub parado: no estabas aqui
            self._reiniciar("levantarse")
            dt = 0.0
        if sin_uso >= AUSENTE and not mic:
            self._reiniciar("levantarse")
        elif sin_uso < AUSENTE or mic:
            self.sentado += dt
            self.agua += dt
        if not self.aviso:
            for tipo, cuenta, tope in (("levantarse", self.sentado, min_levantarse), ("agua", self.agua, min_agua)):
                if cuenta >= tope * 60 and ahora >= self.espera[tipo]:
                    self.aviso = {"tipo": tipo, "ts": 0.0, "intento": 1}
                    break
        a = self.aviso
        if not a:
            return None
        if mic or oculto or sin_uso >= SIN_USO_OCULTA:
            a["ts"] = 0.0   # al volver se muestra otra vez, sin gastar el intento
            return None
        if not a["ts"]:
            a["ts"] = ahora
        elif ahora - a["ts"] >= REPETIR:
            if a["intento"] >= 2:
                self._reiniciar(a["tipo"])   # ignorado dos veces: al siguiente ciclo
                return None
            a["intento"] += 1
            a["ts"] = ahora
        return self.vista()

    def vista(self):
        a = self.aviso
        if not a or not a["ts"]:
            return None
        return {"tipo": a["tipo"], "ts": a["ts"], "min": int(self.sentado // 60)}   # el texto lo arma el gato, para poder traducirlo

    def responder(self, tipo, accion, ahora):
        if tipo not in self.espera:
            return False
        if accion == "listo":
            self._reiniciar(tipo)
            self.espera[tipo] = 0.0
            return True
        if accion == "despues":
            if self.aviso and self.aviso["tipo"] == tipo:
                self.aviso = None
            self.espera[tipo] = ahora + REPETIR
            return True
        return False


ESTADO = Pausas()
_LOCK = threading.Lock()
VISTA = {"aviso": None}


def mic_en_uso():
    """Windows anota que app usa el microfono: LastUsedTimeStop = 0 mientras lo tiene abierto. Sin texto ni audio. Si no se puede leer, False."""
    try:
        import winreg
    except ImportError:
        return False
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"

    def abierto(clave):
        try:
            inicio = winreg.QueryValueEx(clave, "LastUsedTimeStart")[0]
            return bool(inicio) and winreg.QueryValueEx(clave, "LastUsedTimeStop")[0] == 0
        except OSError:
            return False

    def recorrer(ruta):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta) as k:
                i = 0
                while True:
                    try:
                        nombre = winreg.EnumKey(k, i)
                    except OSError:
                        return False
                    i += 1
                    with winreg.OpenKey(k, nombre) as h:
                        if abierto(h):
                            return True
                    if nombre == "NonPackaged" and recorrer(ruta + "\\NonPackaged"):
                        return True
        except OSError:
            return False

    return recorrer(base)


def responder(tipo, accion):
    with _LOCK:
        ok = ESTADO.responder(tipo, accion, time.time())
        VISTA["aviso"] = ESTADO.vista()
    return ok


def vigilar():
    from kodama_plataforma import segundos_sin_uso
    import kodama_extras   # (18-nov) apagado en kodama_extras = no mide (no hace falta reiniciar)
    while True:
        if not kodama_extras.activo("pausas"):
            time.sleep(30)
            continue
        time.sleep(PASO)
        try:
            p = kodama_prefs.leer()["pausas"]
            if not p["activo"]:
                VISTA["aviso"] = None
                continue
            sin_uso, mic = float(segundos_sin_uso()), mic_en_uso()
            with _LOCK:
                VISTA["aviso"] = ESTADO.paso(time.time(), sin_uso, mic, kodama_prefs.silencio_ahora(), p["levantarse_min"], p["agua_min"])
        except Exception as e:
            log(f"pausas: {type(e).__name__}: {e}")
