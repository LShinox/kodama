# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(07-nov) Prueba del instalador para quien NO usa Claude Code (config.agentes_presentes, tocar_settings(False) sin
archivo, tocar_settings(True) con Claude, y los textos nuevos de instalar.py). Todo va a una carpeta temporal y las
rutas se pasan a mano: nunca toca el ~\\.claude real. La carpeta temporal sale de KODAMA_PRUEBA_TMP si esta puesta.
Uso: python pruebas/probar_sin_claude.py  (sale con 1 si algo falla)"""
import json, os, shutil, sys, tempfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import config  # noqa: E402
import instalar  # noqa: E402

mal = []
oks = []


def ver(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))
    (oks if ok else mal).append(nombre)


def comandos(ruta):
    d = json.load(open(ruta, encoding="utf-8"))
    return [h.get("command", "") for ev in (d.get("hooks") or {}).values() for e in ev for h in e.get("hooks", [])]


def main():
    tmp = tempfile.mkdtemp(prefix="kodama-prueba-sin-claude-", dir=os.environ.get("KODAMA_PRUEBA_TMP") or None)
    try:
        # a. PC vacia: nadie
        vacio = os.path.join(tmp, "vacio")
        os.makedirs(vacio)
        a = config.agentes_presentes(home=vacio, which=lambda x: None, app_claude="")
        ver("a. PC vacia: todos False", a, {"claude": False, "codex": False, "antigravity": False, "opencode": False})

        # b. cada IA segun su carpeta o su comando
        casa_b = os.path.join(tmp, "casa-b")
        os.makedirs(os.path.join(casa_b, ".codex"))
        b1 = config.agentes_presentes(home=casa_b, which=lambda x: None, app_claude="")
        ver("b1. solo .codex: codex True, claude False", (b1["codex"], b1["claude"]), (True, False))
        casa_b2 = os.path.join(tmp, "casa-b2")
        os.makedirs(os.path.join(casa_b2, ".claude"))
        ver("b2. carpeta .claude: claude True", config.agentes_presentes(home=casa_b2, which=lambda x: None, app_claude="")["claude"], True)
        casa_b3 = os.path.join(tmp, "casa-b3")
        os.makedirs(casa_b3)
        b3 = config.agentes_presentes(home=casa_b3, which=lambda x: "C:\\x\\claude.exe", app_claude="")
        ver("b3. sin carpeta, comando claude en PATH: claude True", b3["claude"], True)

        # c. quitar sin settings.json: no crea el archivo ni su carpeta
        nada = os.path.join(tmp, "nada", ".claude", "settings.json")
        instalar.tocar_settings(False, nada)
        ver("c. quitar sin archivo: no crea settings.json", os.path.exists(nada), False)
        ver("c. quitar sin archivo: no crea la carpeta .claude", os.path.exists(os.path.dirname(nada)), False)

        # d. instalar con Claude sigue creando el archivo con nuestros hooks, y quitar deja el archivo sin ellos
        con_claude = os.path.join(tmp, "con-claude", ".claude", "settings.json")
        instalar.tocar_settings(True, con_claude)
        ver("d. instalar crea settings.json", os.path.exists(con_claude), True)
        if os.path.exists(con_claude):
            ver("d. instalar pone el hook companero_hook.py", any("companero_hook.py" in c for c in comandos(con_claude)), True)
            instalar.tocar_settings(False, con_claude)
            ver("d. quitar deja el archivo sin hooks de Kodama", any("companero_hook" in c for c in comandos(con_claude)), False)

        # e. textos nuevos del instalador (lectura estatica de instalar.py)
        with open(os.path.join(AQUI, "instalar.py"), encoding="utf-8") as f:
            txt = f.read()
        ver("e. texto del paso 4 sin Claude", "4. Claude Code: no está en esta PC, se salta. Si lo instalas después, vuelve a correr el instalador." in txt, True)
        ver("e. texto del aviso sin ninguna IA", "Ojo: no encontré ninguna IA de código en esta PC (Claude Code, Codex, OpenCode o Antigravity). Kodama queda instalado; cuando instales una, vuelve a correr el instalador para conectarla." in txt, True)
        ver("e. 'elegí un grupo' ya no esta", "elegí un grupo" in txt, False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(oks)} OK, {len(mal)} MAL")
    if mal:
        print("Fallaron: " + ", ".join(mal))
        sys.exit(1)


if __name__ == "__main__":
    main()
