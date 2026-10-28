# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(Mac-F2, 28-oct) Prueba la rama de macOS de kodama_plataforma.py y el LaunchAgent de arrancar_mac.py.

- Parte A (cualquier sistema): las funciones PURAS (leer ps / ioreg / sysctl, comparar nombres de ejecutable) y la
  estructura del plist. No toca el sistema.
- Parte B (SOLO en macOS; en otro sistema dice "SALTADA"): cada funcion devuelve tipos razonables, sin efectos: no abre
  apps, no cierra procesos ajenos. Lo unico que se cierra es el proceso de ayuda que la propia prueba lanza (por su PID).
  Se escribio SIN un Mac: la corre CI (macos-latest)."""
import os
import plistlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import kodama_plataforma as p  # noqa: E402
import arrancar_mac as am  # noqa: E402

fallos = []


def ok(nombre, cond, detalle=""):
    print(("OK    " if cond else "FALLA ") + nombre + (f" -> {detalle}" if (detalle and not cond) else ""))
    if not cond:
        fallos.append(nombre)


# ---------------------------------------------------------------- Parte A: puro
ejemplo_ps = """    1     0 /sbin/launchd
  123     1 /Applications/Tailscale.app/Contents/MacOS/Tailscale
  456   123 /Users/x/Apps/kodama/.venv/bin/python /Users/x/Apps/kodama/companero_hub.py
  789     1 /Users/x/Library/Application Support/Kodama/escritorio-tauri/src-tauri/target/release/kodama
   12    11
garbage line
"""
filas = p._parsear_ps(ejemplo_ps)
ok("ps: filas leidas", [f[0] for f in filas] == [1, 123, 456, 789, 12], filas)
ok("ps: pid, ppid y comando", filas[2] == (456, 123, "/Users/x/Apps/kodama/.venv/bin/python /Users/x/Apps/kodama/companero_hub.py"), filas[2])
ok("ps: comando con espacios en la ruta", filas[3][2].endswith("release/kodama") and "Application Support" in filas[3][2])
ok("ps: texto vacio o None", p._parsear_ps("") == [] and p._parsear_ps(None) == [])
ok("exe: python coincide con python y con Python del framework",
   p._coincide_exe("python", "/x/.venv/bin/python3.12", "") and p._coincide_exe("python", "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python", ""))
ok("exe: kodama coincide por comm o por el primer token del comando",
   p._coincide_exe("kodama", "/a/b/kodama", "") and p._coincide_exe("kodama", "", "/a/b/kodama --x"))
ok("exe: otro programa no coincide", not p._coincide_exe("kodama", "/usr/bin/vim", "/usr/bin/vim kodama.txt"))
ok("exe: sin filtro coincide con todo", p._coincide_exe(None, "/usr/bin/vim", "vim"))
ioreg = '    | |   "HIDIdleTime" = 4294967296\n    | |   "HIDIdleTime" = 2000000000\n'
ok("ioreg: HIDIdleTime en nanosegundos, el menor", p._parsear_inactividad(ioreg) == 2.0, p._parsear_inactividad(ioreg))
ok("ioreg: sin dato", p._parsear_inactividad("nada") is None and p._parsear_inactividad("") is None)
ok("sysctl: kern.boottime", p._parsear_arranque("{ sec = 1730000000, usec = 123456 } Tue Oct 29 10:00:00 2024") == 1730000000)
ok("sysctl: sin dato", p._parsear_arranque("") is None)

d = am.armar_plist("/Users/x/Apps/kodama", "/Users/x/Apps/kodama/.venv/bin/python")
ok("plist: etiqueta y arranque", d["Label"] == "app.kodama" and d["RunAtLoad"] is True and d["StartInterval"] == 600)
ok("plist: sin que launchd se lleve al hub", d["AbandonProcessGroup"] is True)
ok("plist: comando = python + arrancar.pyw", d["ProgramArguments"] == ["/Users/x/Apps/kodama/.venv/bin/python", "/Users/x/Apps/kodama/arrancar.pyw"] or
   (d["ProgramArguments"][0].endswith("python") and d["ProgramArguments"][1].replace("\\", "/").endswith("kodama/arrancar.pyw")), d["ProgramArguments"])
ok("plist: es XML valido de plistlib", plistlib.loads(am.plist_bytes("/Users/x/Apps/kodama", "/Users/x/Apps/kodama/.venv/bin/python"))["Label"] == "app.kodama")
ok("plist: la ruta del archivo", am.ruta_plist().replace("\\", "/").endswith("Library/LaunchAgents/app.kodama.plist"))
ok("plist: no escribe en otro sistema", sys.platform == "darwin" or am.instalar()["ok"] is False)
ok("actualizacion_automatica: solo Windows", p.actualizacion_automatica() == (sys.platform == "win32"))

# ---------------------------------------------------------------- Parte A2: la logica de la rama darwin con ps y senales FALSOS (cualquier sistema)
from unittest import mock  # noqa: E402

TABLA = [(1, 0, "/sbin/launchd"), (100, 1, "/x/.venv/bin/python /x/companero_hub.py"), (101, 100, "/usr/bin/a"),
         (102, 100, "/usr/bin/b"), (103, 101, "/usr/bin/c"), (200, 1, "/x/release/kodama"), (300, 1, "/usr/bin/vim kodama")]
COMM = {pid: cmd.split(" ")[0] for pid, _pp, cmd in TABLA}
with mock.patch.object(p.sys, "platform", "darwin"):
    def ps_falso(campo):
        return [(pid, pp, COMM[pid] if campo == "comm" else cmd) for pid, pp, cmd in TABLA]
    with mock.patch.object(p, "_ps", ps_falso), mock.patch.object(p.os, "getpid", return_value=999):
        ok("darwin/falso: pids_por_linea por texto y exe", p.pids_por_linea("companero_hub.py", "python") == [100], p.pids_por_linea("companero_hub.py", "python"))
        ok("darwin/falso: pids_por_linea no confunde un editor con la mascota", p.pids_por_linea("kodama", "kodama") == [200], p.pids_por_linea("kodama", "kodama"))
        ok("darwin/falso: pids_por_linea sin filtro de exe", sorted(p.pids_por_linea("kodama", None)) == [200, 300])
        matadas = []
        with mock.patch.object(p.os, "kill", lambda pid, sig: matadas.append((pid, sig))):
            p.terminar_pid(100, arbol=True)
            ok("darwin/falso: terminar_pid(arbol) manda SIGTERM a los hijos primero y al final al PID", [m[0] for m in matadas] == [103, 102, 101, 100], matadas)
            matadas.clear(); p.terminar_pid(100)
            ok("darwin/falso: terminar_pid sin arbol = solo ese PID", [m[0] for m in matadas] == [100], matadas)
            matadas.clear(); p.terminar_pid(0); p.terminar_pid(1); p.terminar_pid(-4); p.terminar_pid(999)
            ok("darwin/falso: terminar_pid nunca toca PID 0, 1, negativo ni a si mismo", matadas == [], matadas)
        ok("darwin/falso: nombres_padres sube por ppid", p.nombres_padres() == [], p.nombres_padres())   # 999 no esta en la tabla
    with mock.patch.object(p, "_ps", ps_falso), mock.patch.object(p.os, "getpid", return_value=103):
        ok("darwin/falso: nombres_padres de un nieto", p.nombres_padres() == ["a", "python", "launchd"] or p.nombres_padres() == ["a", "python"], p.nombres_padres())

    def kill_vivo(pid, sig): return None
    def kill_muerto(pid, sig): raise ProcessLookupError()
    def kill_ajeno(pid, sig): raise PermissionError()
    with mock.patch.object(p.os, "kill", kill_vivo):
        ok("darwin/falso: proceso_vivo vivo", p.proceso_vivo(50) is True)
    with mock.patch.object(p.os, "kill", kill_muerto):
        ok("darwin/falso: proceso_vivo muerto", p.proceso_vivo(50) is False)
    with mock.patch.object(p.os, "kill", kill_ajeno):
        ok("darwin/falso: proceso_vivo de otro usuario existe", p.proceso_vivo(50) is True)
    ok("darwin/falso: proceso_vivo(0) no mira el grupo", p.proceso_vivo(0) is False)
    ok("darwin/falso: constantes sin extension y sin tailscaled propio",
       p.sin_ventana() == {} and p.desprendido() == {"start_new_session": True} and p.python_del_venv("/a").replace("\\", "/") == "/a/.venv/bin/python"
       and p.hijos_webview_y_edad(1) == (1, 0) and p.pantalla_completa() is False and p.socket_tailscale() is None
       and p.nombre_proceso_tailscaled() is None and p.comando_tailscaled("/t") is None and p.tailscale_propio() is False)
    ok("darwin/falso: ruta_exe_mascota cae al companero viejo si no hay kodama", p.ruta_exe_mascota("/no/existe").replace("\\", "/").endswith("target/release/" + p.NOMBRES_EXE_MASCOTA[1]))
    ok("darwin/falso: dir_datos_app_claude", p.dir_datos_app_claude("/Users/x").replace("\\", "/") == "/Users/x/Library/Application Support/Claude")
    ok("darwin/falso: es_ruta_buzon relativa no, absoluta inexistente si", p.es_ruta_buzon("b.sock") is False and p.es_ruta_buzon("/tmp/no-existe-xyz.sock") is True)

# ---------------------------------------------------------------- Parte B: solo macOS
if sys.platform != "darwin":
    print("SALTADA: la parte B (rama darwin en vivo) solo corre en macOS")
else:
    tmp = tempfile.mkdtemp(prefix="kodama-pm-")
    ayuda = None
    try:
        ok("nombres: claude, agy, mascota", p.NOMBRE_APP_CLAUDE == "claude" and p.NOMBRE_AGY == "agy" and p.NOMBRES_EXE_MASCOTA == ("kodama", "companero"))
        # procesos: como se crean
        ok("sin_ventana vacio", p.sin_ventana() == {})
        ok("desprendido = sesion nueva", p.desprendido() == {"start_new_session": True} and p.desprendido(sin_ventana=True, grupo=True) == {"start_new_session": True})
        pidf = os.path.join(tmp, "x.pid")
        pid_l = p.lanzar_desprendido([sys.executable, "-c", "pass"], tmp, pidf)
        ok("lanzar_desprendido: PID y pidfile", isinstance(pid_l, int) and pid_l > 1 and open(pidf).read() == str(pid_l))
        # procesos: buscarlos
        marca = "kodama-prueba-" + uuid.uuid4().hex[:10]
        ayuda = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", marca], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        ok("proceso_vivo: el de ayuda", p.proceso_vivo(ayuda.pid) is True)
        ok("proceso_vivo: PID inexistente / 0 / negativo", p.proceso_vivo(99999999) is False and p.proceso_vivo(0) is False and p.proceso_vivo(-3) is False)
        ok("pids_por_linea: halla al de ayuda por texto y 'python'", ayuda.pid in p.pids_por_linea(marca, p.nombre_proceso_python()), p.pids_por_linea(marca, "python"))
        ok("pids_por_linea: otro nombre de ejecutable no coincide", ayuda.pid not in p.pids_por_linea(marca, "vim"))
        ok("pids_por_linea: texto que nadie tiene", p.pids_por_linea("no-existe-" + uuid.uuid4().hex, "python") == [])
        lc = p.linea_de_comando(ayuda.pid)
        ok("linea_de_comando: trae la marca", isinstance(lc, str) and marca in lc, lc)
        ok("linea_de_comando: PID inexistente", p.linea_de_comando(99999999) == "")
        ok("hijos_webview_y_edad: sano", p.hijos_webview_y_edad(os.getpid()) == (1, 0))
        pad = p.nombres_padres()
        ok("nombres_padres: lista de textos", isinstance(pad, list) and all(isinstance(x, str) for x in pad), pad)
        # terminar_pid: guardas (no hace nada) y el proceso de ayuda (el unico que la prueba cierra, por su PID)
        p.terminar_pid(0); p.terminar_pid(1); p.terminar_pid(os.getpid())
        ok("terminar_pid: no toca PID 0, 1 ni a si mismo", True)
        p.terminar_pid(ayuda.pid, arbol=True)
        try:
            ayuda.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        ok("terminar_pid: cerro SOLO al de ayuda", ayuda.poll() is not None and p.proceso_vivo(ayuda.pid) is False)
        # rutas
        ok("python_del_venv", p.python_del_venv("/a/b") == "/a/b/.venv/bin/python" and p.python_del_venv("/a/b", sin_consola=True) == "/a/b/.venv/bin/python")
        ok("python_para_scripts: sin venv usa el actual", p.python_para_scripts(tmp) == sys.executable)
        ok("nombre_proceso_python", p.nombre_proceso_python() == "python")
        rm = p.ruta_exe_mascota("/a/b")
        ok("ruta_exe_mascota: target/release/kodama", rm == "/a/b/escritorio-tauri/src-tauri/target/release/companero" or rm.endswith("target/release/kodama"), rm)
        ok("dir_datos_app_claude", p.dir_datos_app_claude("/Users/x") == "/Users/x/Library/Application Support/Claude")
        ok("carpeta_datos_usuario / temp_claude_relativa / carpeta_datos_kodama",
           p.carpeta_datos_usuario() == "Library" and isinstance(p.temp_claude_relativa(), str)
           and p.carpeta_datos_kodama().endswith("Library/Application Support/Kodama"))
        # usuario y pantalla
        s = p.segundos_sin_uso()
        ok("segundos_sin_uso: numero >= 0", isinstance(s, float) and s >= 0, s)
        a = p.app_al_frente()
        ok("app_al_frente: None o texto en minusculas", a is None or (isinstance(a, str) and a == a.lower()), a)
        ok("pantalla_completa: False", p.pantalla_completa() is False)
        ok("version_app_claude: texto", isinstance(p.version_app_claude(), str))
        # energia
        p.pedir_pc_despierta(continuo=True, sistema=True)
        activo = p.threading.get_ident() in p._CAFEINAS and p._CAFEINAS[p.threading.get_ident()][0].poll() is None
        ok("pedir_pc_despierta: continuo lanza caffeinate", activo or not os.path.exists(p._CAFFEINATE))
        p.pedir_pc_despierta(continuo=True, sistema=False)
        ok("pedir_pc_despierta: soltar", p.threading.get_ident() not in p._CAFEINAS)
        p.pedir_pc_despierta()
        ok("pedir_pc_despierta: de una vez no falla", True)
        # Papelera
        victima = os.path.join(tmp, "para-la-papelera-" + uuid.uuid4().hex[:8] + ".txt")
        open(victima, "w").write("x")
        ok("a_papelera: archivo", p.a_papelera(victima) is True and not os.path.exists(victima))
        ok("a_papelera: no existe", p.a_papelera(os.path.join(tmp, "no-esta.txt")) is False)
        # instancia unica
        nom = "kodama_prueba_" + uuid.uuid4().hex[:8]
        ok("instancia_unica: la primera si, la segunda no", p.instancia_unica(nom) is True and p.instancia_unica(nom) is False)
        ms = p.ms_desde_arranque_pc()
        ok("ms_desde_arranque_pc: entero positivo", isinstance(ms, int) and ms > 0, ms)
        # buzon
        ok("es_ruta_buzon: relativa no", p.es_ruta_buzon("buzon.sock") is False)
        arch = os.path.join(tmp, "comun.txt"); open(arch, "w").write("x")
        ok("es_ruta_buzon: archivo comun no", p.es_ruta_buzon(arch) is False)
        corto = tempfile.mkdtemp(prefix="kb", dir="/tmp")   # las rutas de socket Unix son cortas
        sock = os.path.join(corto, "b.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(sock); srv.listen(1)
        ok("es_ruta_buzon: socket Unix si", p.es_ruta_buzon(sock) is True)
        ok("es_ruta_buzon: ruta absoluta que no existe (chat cerrado)", p.es_ruta_buzon(os.path.join(corto, "nada.sock")) is True)
        srv.settimeout(5)
        b = p.abrir_buzon(sock)
        conn, _ = srv.accept()
        with b:
            b.write(b"hola\n")
        conn.settimeout(5)
        ok("abrir_buzon: escribe al socket", conn.recv(100) == b"hola\n")
        conn.close(); srv.close()
        shutil.rmtree(corto, ignore_errors=True)
        try:
            p.abrir_buzon(os.path.join(tmp, "nada.sock"))
            ok("abrir_buzon: sin socket da error", False)
        except OSError:
            ok("abrir_buzon: sin socket da error", True)
        # Tailscale: se usa el del sistema
        ok("tailscale: ruta, socket por defecto y sin tailscaled propio",
           isinstance(p.ruta_tailscale_cli(), str) and p.socket_tailscale() is None and p.nombre_proceso_tailscaled() is None
           and p.comando_tailscaled(tmp) is None and p.tailscale_propio() is False and p.args_tailscale() == [p.ruta_tailscale_cli()])
        # LaunchAgent: estado sin escribir nada
        e = am.estado()
        ok("arrancar_mac.estado: dos booleanos", isinstance(e.get("escrito"), bool) and isinstance(e.get("cargado"), bool), e)
    finally:
        if ayuda is not None and ayuda.poll() is None:
            ayuda.terminate()
        shutil.rmtree(tmp, ignore_errors=True)

print("\nTODO BIEN" if not fallos else f"\nFALLARON {len(fallos)}: {fallos}")
sys.exit(1 if fallos else 0)
