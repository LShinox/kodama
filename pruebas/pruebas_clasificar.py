# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Pruebas del clasificador de avisos (14-oct-2026). Corre sin red y sin tocar el hub que esta andando.

    python pruebas\\pruebas_clasificar.py            -> casos fijos (deben dar 100 %)
    python pruebas\\pruebas_clasificar.py --reales 50 -> los ultimos 50 mensajes reales: reparto por tipo y
                                                         pruebas\\reales.md para revisar a mano (no sale de la PC)
Cada vez que se toque clasificar(), correr los casos fijos; si un mensaje real salio mal, agregarlo aca.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import companero_hub as h   # noqa: E402  (solo importa funciones; no arranca el hub)

CASOS = [   # (evento, texto, tipo esperado)
    ("Stop", "Listo: subí los cambios y verifiqué con una captura.", "termino"),
    ("Stop", "Hecho:\n- Arreglé el globo\n- Reinicié el hub\n\nFalta: probar en el iPhone.", "termino"),
    ("Stop", "Terminé la tanda.\n\n¿Sigo con la siguiente o prefieres revisarla primero?", "pregunta"),
    ("Stop", "¿Lanzo el estudio de mascotas? Solo investiga, no instala nada.", "pregunta"),
    ("Stop", "Necesito tu OK para borrar la carpeta vieja. Respóndeme ok y lo hago.", "pregunta"),
    ("Stop", "Tengo dos caminos:\n1. Rive (USD 9/mes)\n2. Seguir con el panel gratis\n\n¿Cuál prefieres?", "pregunta"),
    ("Stop", "Para probarlo:\n1. Escríbeme acá\n2. Aléjate de la PC\n3. Responde desde el celular", "termino"),
    ("Stop", "Error: no se pudo conectar con el servidor de Telegram.", "error"),
    ("Stop", "API Error: 529 overloaded. Reintento en un rato.", "error"),
    ("Stop", "Falló la exportación: falta la plantilla de iOS.", "error"),
    ("Notification", "Claude needs your permission to use Bash", "permiso"),
    ("StopFailure", "rate limit reached", "error"),
    ("Stop", "Quedó publicado. Si quieres, después ajusto los colores.", "termino"),
    ("Stop", "La caja ya crece al escribir. ¿Lo pruebas y me dices si se ve bien?", "pregunta"),
    ("Stop", "Decime si arranco con la parte del celular.", "pregunta"),
    # (14-oct) pedidos AL PRINCIPIO del mensaje (revision de 50 reales)
    ("Stop", "Necesito dos OK tuyos:\n1. Respuestas retenidas\n2. Siguiente tanda\n\nLa mascota ya sale sin adornos.", "pregunta"),
    ("Stop", "Necesito una decisión tuya antes del resto. Lo apliqué en el hub y quedó andando.", "pregunta"),
    ("Stop", "Necesito cuatro decisiones tuyas para seguir.\n\nHecho: el globo nuevo ya corre.", "pregunta"),
    ("Stop", "Probé las tres caras. Mírala y me digas si va por el camino, después sigo con el resto.", "pregunta"),
    ("Stop", "Te dejé tres opciones en el lienzo; decime qué gato y en qué captura te gusta más.", "pregunta"),
    ("Stop", "Para seguir falta que elijas la cara de Teo. El resto quedó listo.", "pregunta"),
    ("Stop", "Si lo confirmas acá, armo lo de los chats favoritos completo.", "pregunta"),
    # (14-oct) ingles
    ("Stop", "Done. I need your approval to delete the old folder.", "pregunta"),
    ("Stop", "Finished the build, all tests pass.", "termino"),
    ("Stop", "Do you want me to deploy it now? It takes 2 min.", "pregunta"),
    ("Stop", "Let me know which version you prefer and I'll finish it.", "pregunta"),
]


def casos():
    mal = 0
    for ev, txt, esperado in CASOS:
        tipo, n, linea = h.clasificar(ev, txt)
        ok = tipo == esperado
        mal += not ok
        print(("OK  " if ok else "MAL ") + f"{esperado:9} -> {tipo:9} | {txt[:60]!r}")
    print(f"\n{len(CASOS) - mal}/{len(CASOS)} casos fijos bien")
    return mal == 0


def reales(n):
    lineas = h.leer_ultimas(h.COLA, 4000)
    items = []
    for l in lineas:
        try:
            it = json.loads(l)
        except Exception:
            continue
        if it.get("evento") in ("Stop", "Notification") and it.get("texto"):
            items.append(it)
    items = items[-n:]
    reparto, filas = {}, []
    for it in items:
        tipo, k, linea = h.clasificar(it["evento"], it["texto"])
        reparto[tipo] = reparto.get(tipo, 0) + 1
        fin = " ".join(it["texto"].split())[-220:]
        filas.append(f"| {tipo} | {h.redactar(linea)[:80]} | …{h.redactar(fin)} | |")
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reales.md")
    with open(salida, "w", encoding="utf-8") as f:
        f.write("# Clasificación de los últimos mensajes reales\n\nMarcar en la última columna lo que esté MAL "
                "(lo correcto). Lo que salga mal se agrega a CASOS en pruebas_clasificar.py.\n\n"
                "| tipo | línea del aviso | final del mensaje | ¿bien? |\n|---|---|---|---|\n" + "\n".join(filas) + "\n")
    print(f"{len(items)} mensajes reales: " + ", ".join(f"{k} {v}" for k, v in sorted(reparto.items())))
    print("para revisar:", salida)


if __name__ == "__main__":
    if "--reales" in sys.argv:
        reales(int(sys.argv[sys.argv.index("--reales") + 1]))
    else:
        sys.exit(0 if casos() else 1)
