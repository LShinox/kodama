# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(07-nov) Kodama para quien usa solo Codex, OpenCode o Antigravity: el indicador "_agentes" del estado (cache de 60 s)
y los textos neutrales. Sin escribir en el estado real: solo se parchea config.agentes_presentes."""
import io
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RAIZ)
import config  # noqa: E402
import kodama_historial as kh  # noqa: E402

ok = fallos = 0


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print("OK:", nombre)
    else:
        fallos += 1
        print("FALLO:", nombre)


def leer(rel):
    with io.open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


# 1) cache de agentes_cache(): una sola llamada a config.agentes_presentes dentro de 60 s
original = config.agentes_presentes
llamadas = []


def falso(*a, **k):
    llamadas.append(1)
    return {"claude": False, "codex": True, "antigravity": False, "opencode": False}


try:
    config.agentes_presentes = falso
    kh._AGENTES.update(t=0.0, v=None)
    d1 = kh.agentes_cache()
    d2 = kh.agentes_cache()
    ver("agentes_cache devuelve el dict de config", d1 == {"claude": False, "codex": True, "antigravity": False, "opencode": False})
    ver("agentes_cache: mismo dict en dos llamadas", d1 is d2)
    ver("agentes_cache: config.agentes_presentes llamada una vez en 60 s", len(llamadas) == 1)

    # al pasar 60 s se vuelve a calcular
    kh._AGENTES["t"] -= 61
    kh.agentes_cache()
    ver("agentes_cache: se recalcula pasados 60 s", len(llamadas) == 2)

    # si falla, queda {"claude": True} (la app se ve como antes)
    def roto(*a, **k):
        raise RuntimeError("prueba")
    config.agentes_presentes = roto
    kh._AGENTES.update(t=0.0, v=None)
    ver("agentes_cache: si falla devuelve {'claude': True}", kh.agentes_cache() == {"claude": True})
finally:
    config.agentes_presentes = original
    kh._AGENTES.update(t=0.0, v=None)

# 2) textos viejos fuera de los 5 archivos; nuevos presentes
ARCHIVOS = ["web/app.html", "web/i18n.js", "escritorio/index.html", "kodama_texto.py", "kodama_historial.py"]
texto = {rel: leer(rel) for rel in ARCHIVOS}
VIEJOS = [
    "chats de Claude Code terminan",
    "Conexión con Claude",
    "Avisos de Claude Code (hooks)",
    "abras en la app de Claude",
    "al abrirlo en la app de Claude",
    "ajusta la configuración de Claude,",
    "Dejar la configuración de Claude exactamente",
]
for viejo in VIEJOS:
    ver("sin texto viejo: " + viejo, not any(viejo in t for t in texto.values()))

NUEVOS = {
    "web/app.html": ["Conexión con tus IA", "Avisos de tus IA (hooks)", "Te aviso cuando tus chats de IA (Claude Code, Codex, OpenCode…)",
                     "ajusta la configuración de tus IA", "Dejar la configuración de tus IA exactamente", "vuelvas a abrir ese chat en la PC",
                     "function ocultarSinClaude"],
    "escritorio/index.html": ["Conexión con tus IA", "se entrega al abrirlo en la PC", "function ocultarSinClaude", "function otraIA"],
}
for rel, frases in NUEVOS.items():
    for fr in frases:
        ver("texto nuevo en " + rel + ": " + fr, fr in texto[rel])

# 3) i18n.js: cada texto nuevo en espanol tiene su entrada en ingles (misma linea, valor no vacio)
lineas_i18n = texto["web/i18n.js"].splitlines()
for fr in ["Conexión con tus IA", "Avisos de tus IA (hooks)", "Te aviso cuando tus chats de IA (Claude Code, Codex, OpenCode…)",
           "ajusta la configuración de tus IA (Claude Code, Codex…)", "Dejar la configuración de tus IA exactamente como antes de instalar",
           "vuelvas a abrir ese chat en la PC", "se entrega al abrirlo en la PC"]:
    con_en = [l for l in lineas_i18n if fr in l.split('": "')[0] and re.search(r'":\s*"[^"]+"\s*,?\s*$', l)]
    ver("i18n.js tiene ingles para: " + fr, len(con_en) == 1)

# 4) guarda rough de sintaxis (no se ejecuta node): llaves balanceadas en i18n.js
i18n = texto["web/i18n.js"]
ver("i18n.js: { y } balanceadas", i18n.count("{") == i18n.count("}"))

print("Resultado: %d OK, %d FALLO" % (ok, fallos))
sys.exit(1 if fallos else 0)
