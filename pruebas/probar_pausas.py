# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Recordatorios de agua y de levantarse, con reloj simulado. Correr: PYTHONUTF8=1 .venv\\Scripts\\python.exe pruebas\\probar_pausas.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodama_pausas as kp  # noqa: E402
import kodama_prefs  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK  ", nombre)
    else:
        fallos += 1
        print("FALLA", nombre)


class Sim:
    def __init__(self):
        self.p, self.t, self.u = kp.Pausas(), 1000.0, None
        self.p.paso(self.t, 0, False, False, 50, 60)

    def correr(self, minutos, sin_uso=0, mic=False, oculto=False):
        for _ in range(int(minutos * 60 // 15)):
            self.t += 15
            self.u = self.p.paso(self.t, sin_uso, mic, oculto, 50, 60)
        return self.u


s = Sim()
ver("49 min: nada", s.correr(49) is None)
a = s.correr(1)
ver("50 min: levantarse", a and a["tipo"] == "levantarse" and a["min"] == 50)
ver("mismo aviso mientras dura", s.correr(1)["ts"] == a["ts"])

s = Sim()
s.correr(30)
s.correr(6, sin_uso=400)
ver("5 min sin tocar la PC reinicia sentado", s.p.sentado == 0)
ver("pero no el agua", s.p.agua >= 30 * 60 - 15)
s.correr(45)
ver("tras la pausa no pide levantarse", s.p.sentado < 50 * 60 and (s.p.aviso or {}).get("tipo") != "levantarse")

s = Sim()
s.correr(30)
s.correr(10, sin_uso=400, mic=True)
ver("en llamada sigue contando sentado", s.p.sentado >= 40 * 60 - 15)
ver("en llamada no se muestra", s.correr(15, sin_uso=400, mic=True) is None and s.p.aviso is not None)
ver("al colgar sale", s.correr(0.25) is not None)

s = Sim()
s.correr(50)
ver("horas de silencio lo ocultan", s.correr(1, oculto=True) is None)
ver("PC sin uso 2 min lo oculta", s.correr(1, sin_uso=150) is None)

s = Sim()
a = s.correr(50)
ver("Listo reinicia", s.p.responder("levantarse", "listo", s.t) and s.p.sentado == 0 and s.p.aviso is None)
ver("Listo: no repite pronto", s.correr(40) is None)

s = Sim()
s.correr(50)
ver("Despues quita el aviso", s.p.responder("levantarse", "despues", s.t) and s.p.aviso is None)
ver("Despues: 9 min sin nada", s.correr(9.5) is None)
ver("Despues: a los 10 min repite", s.correr(1)["tipo"] == "levantarse")

s = Sim()
a = s.correr(50)
b = s.correr(10.25)
ver("ignorado: repite una vez con otro ts", b and b["ts"] != a["ts"] and s.p.aviso["intento"] == 2)
s.correr(10.25)
ver("ignorado dos veces: siguiente ciclo", s.p.sentado < 60 and (s.p.aviso or {}).get("tipo") != "levantarse")

s = Sim()
s.correr(50)
s.p.responder("levantarse", "listo", s.t)
a = s.correr(10)
ver("agua a los 60 min de uso", a and a["tipo"] == "agua")
ver("Listo del agua", s.p.responder("agua", "listo", s.t) and s.p.agua == 0)

s = Sim()
s.correr(30)
s.t += 3600
s.p.paso(s.t, 0, False, False, 50, 60)
ver("PC dormida: reinicia sentado y no suma agua", s.p.sentado == 0 and s.p.agua < 31 * 60)

s = Sim()
ver("responder invalido", not s.p.responder("x", "listo", s.t) and not s.p.responder("agua", "x", s.t))
ver("sin aviso, vista None", s.p.vista() is None)
ver("mic_en_uso responde sin error", kp.mic_en_uso() in (True, False))

ruta = os.path.join(tempfile.mkdtemp(dir=os.environ.get("KODAMA_PRUEBAS_TMP") or None), "p.json")
ver("prefs por defecto", kodama_prefs.leer(ruta)["pausas"] == {"activo": True, "agua_min": 60, "levantarse_min": 50})
g = kodama_prefs.guardar({"pausas": {"activo": False, "agua_min": 45, "levantarse_min": 5}}, ruta=ruta)
ver("prefs guarda lo valido e ignora lo invalido", g["pausas"] == {"activo": False, "agua_min": 45, "levantarse_min": 50})
ver("prefs lo vuelve a leer", kodama_prefs.leer(ruta)["pausas"]["agua_min"] == 45)
kodama_prefs.guardar({"alertas_uso": False}, ruta=ruta)
ver("otro cambio no lo pisa", kodama_prefs.leer(ruta)["pausas"]["agua_min"] == 45)

print(f"\n{ok} OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
