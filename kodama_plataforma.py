# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Capa de plataforma de Kodama: TODO lo que cambia entre Windows y macOS y que usan el hub, arrancar.pyw,
companero_actualizar.py, config.py y los hooks (banderas de creacion de procesos, abrir enlaces y archivos, rutas de
datos del usuario, la mascota, buscar y cerrar procesos por PID, inactividad, ventana al frente, energia, Papelera,
instancia unica, buzon de las sesiones y Tailscale).

Windows: el comportamiento exacto que tenia antes cada pieza (rama `if sys.platform == "win32":`).
macOS (Mac-F2, 28-oct): rama `darwin` de cada funcion, solo con la biblioteca estandar y los programas que trae macOS
(ps, open, osascript, ioreg, sysctl, caffeinate). ESCRITA SIN UN MAC A MANO: la verifica CI (GitHub Actions, macos-latest)
con pruebas\\probar_plataforma_mac.py; lo que depende de permisos del sistema (la app al frente) falla suave.
Otro sistema: NotImplementedError.

Reglas de este modulo: solo biblioteca estandar (ctypes se usa dentro de las funciones, asi importarlo no falla en
otro sistema); nada de Kodama (ni config ni el hub) para que arrancar.pyw y los hooks lo importen como script suelto;
siempre PID, nunca cerrar procesos por nombre."""
import ctypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time

_WIN = sys.platform == "win32"
# nombre (en minusculas) con el que se reconoce a Claude: el ejecutable en Windows; el nombre de la app (System Events) en macOS
NOMBRE_APP_CLAUDE = "claude.exe" if _WIN else "claude"
NOMBRE_AGY = "agy.exe" if _WIN else "agy"   # el CLI de Antigravity
# la mascota: el nombre nuevo y el viejo (PC de desarrollo sin recompilar); en macOS el binario de Tauri no lleva extension
NOMBRES_EXE_MASCOTA = ("kodama.exe", "companero.exe") if _WIN else ("kodama", "companero")

# programas de macOS por ruta absoluta (nada de buscarlos en el PATH)
_PS, _OPEN, _OSASCRIPT, _IOREG = "/bin/ps", "/usr/bin/open", "/usr/bin/osascript", "/usr/sbin/ioreg"
_SYSCTL, _CAFFEINATE, _LSAPPINFO = "/usr/sbin/sysctl", "/usr/bin/caffeinate", "/usr/bin/lsappinfo"

# banderas de creacion de procesos de Windows (solo se usan dentro de las funciones de abajo)
_SIN_VENTANA = 0x08000000      # CREATE_NO_WINDOW
_DESPRENDIDO = 0x00000008      # DETACHED_PROCESS
_GRUPO_NUEVO = 0x00000200      # CREATE_NEW_PROCESS_GROUP
_FUERA_DEL_JOB = 0x01000000    # CREATE_BREAKAWAY_FROM_JOB


def _pendiente():
    raise NotImplementedError("plataforma no soportada (solo Windows y macOS)")


def _mudo(**extra):
    """kwargs de Popen para un proceso sin entrada ni salida."""
    return dict(close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra)


# ---------------------------------------------------------------- macOS: leer las salidas de ps, ioreg y sysctl
# (funciones puras, sin tocar el sistema: se prueban en cualquier sistema con texto de ejemplo)
_RE_PS = re.compile(r"^\s*(\d+)\s+(\d+)(?:\s+(.*?))?\s*$")


def _parsear_ps(texto):
    """Salida de `ps -axo pid=,ppid=,<campo>=` -> [(pid, ppid, texto)]."""
    out = []
    for linea in (texto or "").splitlines():
        m = _RE_PS.match(linea)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), m.group(3) or ""))
    return out


def _ps(campo):
    r = subprocess.run([_PS, "-axo", f"pid=,ppid=,{campo}="], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=15)
    return _parsear_ps(r.stdout)


def _coincide_exe(exe, comm, comando):
    """True si el ejecutable del proceso es `exe` (sin distinguir mayusculas; basta con que el nombre EMPIECE asi: 'python'
    coincide con 'python3.12' y con el 'Python' del framework). `comm` = ruta del ejecutable; `comando` = linea completa."""
    exe = (exe or "").lower()
    if not exe:
        return True
    primero = (comando or "").split(" ", 1)[0]
    return any(os.path.basename(x).lower().startswith(exe) for x in (comm, primero) if x)


def _parsear_inactividad(texto):
    """Salida de `ioreg -c IOHIDSystem` -> segundos desde el ultimo mouse o tecla (HIDIdleTime viene en nanosegundos), o None."""
    v = [int(x) for x in re.findall(r'"HIDIdleTime"\s*=\s*(\d+)', texto or "")]
    return min(v) / 1e9 if v else None


def _parsear_arranque(texto):
    """Salida de `sysctl -n kern.boottime` ('{ sec = 1730000000, usec = 0 } ...') -> epoch del arranque, o None."""
    m = re.search(r"sec\s*=\s*(\d+)", texto or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- procesos: como se crean
def sin_ventana():
    """kwargs para subprocess.run/Popen: que el proceso no abra una consola."""
    if sys.platform == "win32":
        return {"creationflags": _SIN_VENTANA}
    if sys.platform == "darwin":   # en macOS un proceso hijo no abre ninguna consola
        return {}
    _pendiente()


def desprendido(sin_ventana=False, grupo=False):
    """kwargs para subprocess.Popen: proceso desprendido (sigue vivo aunque el que lo lanzo se cierre).
    `grupo`: en un grupo de procesos nuevo; `sin_ventana`: sin consola."""
    if sys.platform == "win32":
        return {"creationflags": _DESPRENDIDO | (_GRUPO_NUEVO if grupo else 0) | (_SIN_VENTANA if sin_ventana else 0)}
    if sys.platform == "darwin":   # sesion propia (setsid): ya es su propio grupo y no depende de la terminal del que lo lanza
        return {"start_new_session": True}
    _pendiente()


def lanzar_desprendido(args, cwd, pidfile=None):
    """Lanza `args` sin ventana, desprendido y FUERA del job del que lo lanza (para que nada se lo lleve al cerrarse
    el lanzador). Si el job no permite salirse (breakaway), reintenta sin esa bandera. Devuelve el PID (y lo anota en
    `pidfile` si se pide)."""
    if sys.platform == "win32":
        flags = _DESPRENDIDO | _GRUPO_NUEVO | _FUERA_DEL_JOB | _SIN_VENTANA
        mudo = dict(close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            p = subprocess.Popen(args, cwd=cwd, creationflags=flags, **mudo)
        except OSError:   # si el job no permite "breakaway", sin esa bandera
            p = subprocess.Popen(args, cwd=cwd, creationflags=flags & ~_FUERA_DEL_JOB, **mudo)
        if pidfile:
            open(pidfile, "w").write(str(p.pid))
        return p.pid
    if sys.platform == "darwin":   # sesion nueva: ni el cierre del lanzador ni launchd (con AbandonProcessGroup) se lo llevan
        p = subprocess.Popen(args, cwd=cwd, start_new_session=True, **_mudo())
        if pidfile:
            with open(pidfile, "w") as f:
                f.write(str(p.pid))
        return p.pid
    _pendiente()


# ---------------------------------------------------------------- procesos: buscarlos y cerrarlos (siempre por PID)
def pids_por_linea(texto, exe):
    """PIDs de procesos `exe` cuya linea de comando contiene `texto` (solo mira, no toca nada). Filtra por nombre de
    ejecutable: si no, la propia consulta (que contiene el texto) se encuentra a si misma. `exe` None = cualquier ejecutable (macOS)."""
    if sys.platform == "win32":
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-CimInstance Win32_Process -Filter \"Name='{exe}'\" | Where-Object {{ $_.CommandLine -like '*{texto}*' }}).ProcessId"],
                           capture_output=True, text=True, **sin_ventana())
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    if sys.platform == "darwin":
        try:
            comm = {pid: c for pid, _pp, c in _ps("comm")}
            texto_min, yo = (texto or "").lower(), os.getpid()
            return [pid for pid, _pp, cmd in _ps("command")
                    if pid != yo and texto_min in cmd.lower() and _coincide_exe(exe, comm.get(pid, ""), cmd)]
        except (OSError, subprocess.SubprocessError):
            return []
    _pendiente()


def linea_de_comando(pid, timeout=30):
    """Linea de comando del proceso `pid` ('' si no existe): sirve para confirmar que el PID anotado sigue siendo el
    nuestro antes de cerrarlo."""
    if sys.platform == "win32":
        return subprocess.run(["powershell", "-NoProfile", "-Command",
                               f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                              capture_output=True, text=True, timeout=timeout, **sin_ventana()).stdout
    if sys.platform == "darwin":
        try:
            r = subprocess.run([_PS, "-p", str(int(pid)), "-o", "command="], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            return r.stdout.strip()
        except (OSError, ValueError, subprocess.SubprocessError):
            return ""
    _pendiente()


def terminar_pid(pid, arbol=False):
    """Cierra SOLO el proceso `pid` (y sus hijos si `arbol`). Nunca por nombre."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid)] + (["/T"] if arbol else []) + ["/F"], capture_output=True, **sin_ventana())
        return
    if sys.platform == "darwin":   # SIGTERM a ese PID (y, con `arbol`, antes a sus descendientes); jamas al PID 0/1 ni a si mismo
        import signal
        pid = int(pid)
        if pid <= 1 or pid == os.getpid():
            return
        objetivos = [pid]
        if arbol:
            try:
                tabla = [(p, pp) for p, pp, _c in _ps("comm")]
                hijos, nivel = [], {pid}
                while nivel:
                    nivel = {p for p, pp in tabla if pp in nivel and p != pid and p not in hijos}
                    hijos.extend(sorted(nivel))
                objetivos = hijos[::-1] + [pid]   # los de mas abajo primero
            except (OSError, subprocess.SubprocessError):
                pass
        for p in objetivos:
            try:
                os.kill(p, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        return
    _pendiente()


def proceso_vivo(pid):
    """True si el proceso `pid` sigue corriendo (mirar un PID no gasta nada)."""
    if sys.platform == "win32":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)                     # PROCESS_QUERY_LIMITED_INFORMATION
        vivo = False
        if h:
            code = ctypes.c_ulong()
            vivo = bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
            k.CloseHandle(h)
        return vivo
    if sys.platform == "darwin":
        pid = int(pid)
        if pid <= 0:   # os.kill(0, 0) miraria a todo el grupo
            return False
        try:
            os.kill(pid, 0)   # senal 0: no manda nada, solo comprueba que el PID existe
        except ProcessLookupError:
            return False
        except PermissionError:   # existe, pero es de otro usuario
            return True
        return True
    _pendiente()


def hijos_webview_y_edad(pid):
    """(cantidad de procesos WebView2 hijos de `pid`, segundos que lleva vivo). Si no se puede leer: (1, 0), o sea 'sano'."""
    if sys.platform == "win32":
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; "
                            f"$h=@(Get-CimInstance Win32_Process -Filter \"ParentProcessId={pid} AND Name='msedgewebview2.exe'\").Count; "
                            f"\"$h $([int]((Get-Date)-$p.CreationDate).TotalSeconds)\""],
                           capture_output=True, text=True, **sin_ventana())
        try:
            hijos, edad = (int(x) for x in r.stdout.split()[:2])
        except ValueError:
            hijos, edad = 1, 0
        return hijos, edad
    if sys.platform == "darwin":
        # En Windows esto detecta que el WebView2 de la mascota murio tras una suspension (ventana en blanco). En macOS el
        # WKWebView no es un proceso hijo de la mascota (lo lanza el sistema) y no se conoce ese fallo: siempre 'sano'.
        return 1, 0
    _pendiente()


def nombres_padres(niveles=8):
    """Nombres (en minusculas) de los procesos padre de este proceso, hasta `niveles` (sin PowerShell: lo usan hooks que deben ser rapidos)."""
    if sys.platform == "win32":
        import ctypes.wintypes as w

        class PE(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                        ("pcPriClassBase", ctypes.c_long), ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
        k = ctypes.windll.kernel32
        snap = k.CreateToolhelp32Snapshot(0x2, 0)
        tabla, e = {}, PE()
        e.dwSize = ctypes.sizeof(PE)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            tabla[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile.lower())
            ok = k.Process32NextW(snap, ctypes.byref(e))
        k.CloseHandle(snap)
        out, pid = [], os.getpid()
        for _ in range(niveles):
            if pid not in tabla:
                break
            pid, _n = tabla[pid]
            if pid in tabla:
                out.append(tabla[pid][1])
        return out
    if sys.platform == "darwin":
        try:
            tabla = {p: (pp, os.path.basename(c).lower()) for p, pp, c in _ps("comm")}
        except (OSError, subprocess.SubprocessError):
            return []
        out, pid = [], os.getpid()
        for _ in range(niveles):
            if pid not in tabla:
                break
            pid, _n = tabla[pid]
            if pid in tabla:
                out.append(tabla[pid][1])
        return out
    _pendiente()


# ---------------------------------------------------------------- rutas y ejecutables
def python_del_venv(app_dir, sin_consola=False):
    """Ruta del python del entorno virtual de `app_dir` (el de 'sin consola' si se pide). No mira si existe."""
    if sys.platform == "win32":
        return os.path.join(app_dir, ".venv", "Scripts", "pythonw.exe" if sin_consola else "python.exe")
    if sys.platform == "darwin":   # el venv de macOS es .venv/bin/python; no existe 'pythonw' (no hay consola que ocultar)
        return os.path.join(app_dir, ".venv", "bin", "python")
    _pendiente()


def python_para_scripts(app_dir):
    """El python con consola del venv, o el que corre ahora si el venv no esta (para correr instalar.py y capturar su salida)."""
    if sys.platform == "win32":
        py = python_del_venv(app_dir)
        return py if os.path.exists(py) else sys.executable.replace("pythonw.exe", "python.exe")
    if sys.platform == "darwin":
        py = python_del_venv(app_dir)
        return py if os.path.exists(py) else sys.executable
    _pendiente()


def nombre_proceso_python():
    """Nombre del proceso del python del venv sin consola (con el que corre el hub): para buscarlo con pids_por_linea."""
    if sys.platform == "win32":
        return "pythonw.exe"
    if sys.platform == "darwin":   # basta con que el nombre EMPIECE asi: 'python', 'python3.12' y el 'Python' del framework
        return "python"
    _pendiente()


def ruta_exe_mascota(app_dir):
    """El ejecutable de la mascota (Tauri): kodama.exe, o el viejo companero.exe si el nuevo aun no se compilo."""
    if sys.platform in ("win32", "darwin"):
        # macOS: el binario de Tauri sin extension, en el mismo target/release que arma CI (artefacto kodama-macos)
        rel = os.path.join(app_dir, "escritorio-tauri", "src-tauri", "target", "release")
        nuevo = os.path.join(rel, NOMBRES_EXE_MASCOTA[0])
        return nuevo if os.path.exists(nuevo) else os.path.join(rel, NOMBRES_EXE_MASCOTA[1])
    _pendiente()


def dir_datos_app_claude(home):
    """Carpeta de datos de la app de Claude (la que tiene claude-code-sessions): en Windows es MSIX y su
    %APPDATA%\\Claude real vive en el paquete (ver grupos_app.py)."""
    if sys.platform == "win32":
        import glob
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        # (20-oct) la app mudo sus datos a %LOCALAPPDATA%\Claude-Data\claude_<id>\ (README.txt ahi; en el paquete quedo
        # solo ".user-data-left"): sin esto no se encontraban los chats (enlaces, grupos, Medidor).
        nuevo = [d for d in glob.glob(os.path.join(local, "Claude-Data", "claude_*"))
                 if os.path.isdir(os.path.join(d, "claude-code-sessions"))]
        if nuevo:
            return max(nuevo, key=os.path.getmtime)
        real = glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude"))
        return real[0] if real else os.path.join(os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming"), "Claude")
    if sys.platform == "darwin":
        # ~/Library/Application Support/Claude es la carpeta de la app de escritorio de Claude en macOS (la de su
        # claude_desktop_config.json, segun la documentacion publica de MCP). POR VERIFICAR en un Mac: que la subcarpeta
        # claude-code-sessions exista ahi con el mismo formato que en Windows (si no, enlaces, grupos y Medidor no hallan los chats).
        return os.path.join(home, "Library", "Application Support", "Claude")
    _pendiente()


def carpeta_datos_usuario():
    """Nombre de la carpeta de datos de aplicaciones dentro de la carpeta del usuario (en Windows, 'AppData'; en macOS, 'Library')."""
    if sys.platform == "win32":
        return "AppData"
    if sys.platform == "darwin":
        return "Library"
    _pendiente()


def temp_claude_relativa():
    """Donde guarda Claude sus carpetas de trabajo (scratchpads), relativa a la carpeta del usuario y normalizada."""
    if sys.platform == "win32":
        return os.path.normcase(os.path.join("AppData", "Local", "Temp", "claude"))
    if sys.platform == "darwin":
        # POR VERIFICAR en un Mac: dondequiera que Claude Code ponga sus scratchpads (en macOS suelen estar bajo $TMPDIR,
        # fuera de la carpeta del usuario, y entonces no se abren desde el celular). Si no coincide, queda mas restrictivo.
        return os.path.normcase(os.path.join("Library", "Caches", "claude"))
    _pendiente()


def carpeta_datos_kodama():
    """Carpeta de datos propios de Kodama fuera de la instalacion, en macOS (~/Library/Application Support/Kodama). En
    Windows la instalacion lo guarda todo junto (estado\\ dentro de la carpeta del programa) y esto devuelve None."""
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Kodama")
    return None


# ---------------------------------------------------------------- abrir cosas
def abrir(destino):
    """Abre un enlace (claude://, https://) o un archivo con la aplicacion que corresponda."""
    if sys.platform == "win32":
        os.startfile(destino)
        return
    if sys.platform == "darwin":   # `open` abre claude://, https:// o un archivo con la app que corresponda
        destino = str(destino)
        if destino.startswith("-"):   # que un destino raro nunca se tome por una opcion de `open`
            destino = "./" + destino
        subprocess.Popen([_OPEN, destino], **_mudo())
        return
    _pendiente()


def mostrar_en_carpeta(ruta):
    """Abre el explorador del sistema con ese archivo seleccionado (Explorador en Windows, Finder en macOS)."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", ruta])
        return
    if sys.platform == "darwin":
        subprocess.Popen([_OPEN, "-R", str(ruta)], **_mudo())
        return
    _pendiente()


def version_app_claude():
    """Version de la app de escritorio de Claude ('?' si no se sabe)."""
    if sys.platform == "win32":
        try:   # WindowsApps no se puede listar sin permisos de administrador: se pregunta a Windows por el paquete
            return subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-AppxPackage -Name Claude).Version"],
                                  capture_output=True, text=True, timeout=20, **sin_ventana()).stdout.strip() or "?"
        except Exception:
            return "?"
    if sys.platform == "darwin":
        import plistlib
        for base in ("/Applications", os.path.join(os.path.expanduser("~"), "Applications")):
            try:
                with open(os.path.join(base, "Claude.app", "Contents", "Info.plist"), "rb") as f:
                    return str(plistlib.load(f).get("CFBundleShortVersionString") or "?")
            except (OSError, ValueError):
                continue
        return "?"
    _pendiente()


def actualizacion_automatica():
    """True si este sistema sabe actualizarse solo (hoy solo Windows: el zip de la version trae kodama.exe). En macOS la
    actualizacion es manual hasta que haya un paquete de macOS firmado y probado."""
    return sys.platform == "win32"


# ---------------------------------------------------------------- el usuario y su pantalla
def segundos_sin_uso():
    """Segundos desde el ultimo movimiento de mouse o tecla."""
    if sys.platform == "win32":
        class LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LII(); lii.cbSize = ctypes.sizeof(LII)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000
    if sys.platform == "darwin":
        try:
            r = subprocess.run([_IOREG, "-c", "IOHIDSystem"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=5)
            v = _parsear_inactividad(r.stdout)
            if v is not None:
                return v
        except (OSError, subprocess.SubprocessError):
            pass
        return 0.0   # si no se puede leer, se da por 'en uso': lo que decide con esto (despertar chats, avisos) se abstiene
    _pendiente()


_AL_FRENTE = {"hasta": 0.0}   # macOS: tras un fallo no se vuelve a preguntar hasta esta hora (epoch)


def app_al_frente():
    """Nombre (en minusculas) de la app que tienes al frente: en Windows el ejecutable de la ventana (p.ej. 'claude.exe'); en
    macOS el nombre de la app (p.ej. 'claude'), o None si no se pudo saber."""
    if sys.platform == "win32":
        try:
            u, k = ctypes.windll.user32, ctypes.windll.kernel32
            pid = ctypes.c_ulong()
            u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
            hp = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
            buf = ctypes.create_unicode_buffer(520); n = ctypes.c_ulong(520)
            k.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n)); k.CloseHandle(hp)
            return os.path.basename(buf.value).lower()
        except Exception:
            return ""
    if sys.platform == "darwin":
        # osascript -> System Events necesita el permiso de Automatizacion (y a veces el de Accesibilidad) para quien lo
        # lanza (Terminal, Python o la app de Kodama), en Ajustes del Sistema > Privacidad y seguridad. Sin el permiso, o
        # si algo falla, devuelve None (suave: nada se rompe, solo no se sabe cual app esta al frente). El plan B,
        # `lsappinfo` (no pide permisos), se prueba si osascript falla.
        if time.time() < _AL_FRENTE["hasta"]:
            return None
        nombre = None
        try:
            r = subprocess.run([_OSASCRIPT, "-e", 'tell application "System Events" to get name of first application process '
                                                  'whose frontmost is true'],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                nombre = r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        if nombre is None:
            try:
                asn = subprocess.run([_LSAPPINFO, "front"], capture_output=True, text=True, timeout=3).stdout.strip()
                if asn:
                    info = subprocess.run([_LSAPPINFO, "info", "-only", "name", asn], capture_output=True, text=True,
                                          encoding="utf-8", errors="replace", timeout=3).stdout
                    m = re.search(r'"(?:LSDisplayName|name)"\s*=\s*"([^"]+)"', info)
                    nombre = m.group(1) if m else None
            except (OSError, subprocess.SubprocessError):
                pass
        if nombre is None:
            _AL_FRENTE["hasta"] = time.time() + 60   # sin permiso: no insistir cada 2 s
            return None
        return nombre.lower()
    _pendiente()


class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


class _MINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]


def pantalla_completa():
    """True si la ventana al frente cubre todo su monitor (juego, video, presentacion). Ignora el escritorio."""
    if sys.platform == "win32":
        try:
            u = ctypes.windll.user32
            hw = u.GetForegroundWindow()
            if not hw:
                return False
            cls = ctypes.create_unicode_buffer(64); u.GetClassNameW(hw, cls, 64)
            if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
                return False
            r = _RECT(); u.GetWindowRect(hw, ctypes.byref(r))
            mi = _MINFO(); mi.cbSize = ctypes.sizeof(_MINFO)
            u.GetMonitorInfoW(u.MonitorFromWindow(hw, 2), ctypes.byref(mi))
            m = mi.rcMonitor
            return r.l <= m.l and r.t <= m.t and r.r >= m.r and r.b >= m.b
        except Exception:
            return False
    if sys.platform == "darwin":
        return False   # macOS no tiene una API publica y simple para saber si la ventana al frente cubre toda la pantalla
    _pendiente()


# ---------------------------------------------------------------- energia, Papelera, instancia unica
_CAFEINAS = {}   # macOS: id del hilo -> (caffeinate lanzado por ese hilo, sus argumentos)
_CAFEINAS_CERROJO = threading.Lock()


def _soltar_cafeina(p):
    """Cierra un caffeinate que lanzamos nosotros (el objeto Popen trae su PID; nunca por nombre)."""
    try:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=2)
    except (OSError, subprocess.SubprocessError):
        pass


def pedir_pc_despierta(continuo=False, sistema=True, pantalla=False):
    """Le pide al sistema que no se suspenda (`sistema`) y/o que no apague la pantalla (`pantalla`). Con `continuo` el
    pedido dura hasta que este mismo hilo lo cambie (sistema=False y pantalla=False lo suelta); sin `continuo` es un
    pedido de una vez que saca a la PC de la suspension. Vive solo mientras corre el hilo: no toca la configuracion de energia."""
    if sys.platform == "win32":
        estado = (0x80000000 if continuo else 0) | (0x00000002 if pantalla else 0) | (0x00000001 if sistema else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(estado)
        return
    if sys.platform == "darwin":
        # `caffeinate`: de una vez = -u (declara al usuario activo: enciende la pantalla) por 10 s; continuo = -i (no
        # suspender) y/o -d (pantalla) atado al PID de este proceso con -w, asi termina solo si el hub se cae. Un
        # caffeinate por hilo, para que el hilo que suelta su pedido no suelte el de otro (como SetThreadExecutionState).
        try:
            if not continuo:
                subprocess.Popen([_CAFFEINATE, "-u", "-t", "10"], **_mudo())
                return
            args = [_CAFFEINATE] + (["-i"] if sistema else []) + (["-d"] if pantalla else [])
            hilo = threading.get_ident()
            with _CAFEINAS_CERROJO:
                previo = _CAFEINAS.pop(hilo, None)
                if len(args) == 1:   # sin -i ni -d: soltar
                    if previo:
                        _soltar_cafeina(previo[0])
                    return
                args += ["-w", str(os.getpid())]
                if previo and previo[1] == args and previo[0].poll() is None:
                    _CAFEINAS[hilo] = previo   # igual que antes: no se relanza
                    return
                if previo:
                    _soltar_cafeina(previo[0])
                _CAFEINAS[hilo] = (subprocess.Popen(args, **_mudo()), args)
        except OSError:
            pass
        return
    _pendiente()


def a_papelera(ruta):
    """A la Papelera de reciclaje (se puede recuperar), no borrado definitivo. True si lo logro."""
    if sys.platform == "win32":
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                        ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int), ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", ctypes.c_wchar_p)]
        op = SHFILEOPSTRUCTW(None, 3, ruta + "\0", None, 0x0004 | 0x0010 | 0x0040 | 0x0400, 0, None, None)   # DELETE + ALLOWUNDO, sin dialogos
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted
    if sys.platform == "darwin":
        ruta = os.path.abspath(ruta)
        if not os.path.lexists(ruta):
            return False
        try:   # 1) el Finder (deja "Volver a poner"); necesita permiso de Automatizacion para controlarlo
            r = subprocess.run([_OSASCRIPT, "-e", "on run argv", "-e", 'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)',
                                "-e", "end run", ruta], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and not os.path.lexists(ruta):
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        try:   # 2) sin el Finder: mover a ~/.Trash (se recupera a mano; sin "Volver a poner")
            papelera = os.path.join(os.path.expanduser("~"), ".Trash")
            os.makedirs(papelera, exist_ok=True)
            nombre = os.path.basename(ruta.rstrip("/"))
            destino = os.path.join(papelera, nombre)
            if os.path.lexists(destino):
                base, ext = os.path.splitext(nombre)
                destino = os.path.join(papelera, f"{base} {time.strftime('%H.%M.%S')}{ext}")
            shutil.move(ruta, destino)
            return True
        except (OSError, shutil.Error):
            return False
    _pendiente()


_MUTEX = None   # el manejador tiene que seguir vivo mientras corra el proceso
_BLOQUEOS = {}   # macOS: nombre -> archivo abierto con el cerrojo (tiene que seguir abierto mientras corra el proceso)


def instancia_unica(nombre):
    """True si este proceso es el PRIMERO con ese `nombre`; False si ya hay otro. Se libera solo al morir el proceso."""
    global _MUTEX
    if sys.platform == "win32":
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\" + nombre)
        return ctypes.windll.kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS
    if sys.platform == "darwin":
        import fcntl
        import tempfile
        # un archivo de cerrojo por usuario (el temporal de macOS es por usuario); flock se libera solo al morir el proceso
        ruta = os.path.join(tempfile.gettempdir(), "kodama-" + re.sub(r"[^A-Za-z0-9_.-]", "_", nombre) + ".lock")
        f = open(ruta, "a+")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        _BLOQUEOS[nombre] = f
        return True
    _pendiente()


def ms_desde_arranque_pc():
    """Milisegundos desde que se prendio la PC."""
    if sys.platform == "win32":
        return ctypes.windll.kernel32.GetTickCount64()
    if sys.platform == "darwin":
        try:
            r = subprocess.run([_SYSCTL, "-n", "kern.boottime"], capture_output=True, text=True, timeout=5)
            sec = _parsear_arranque(r.stdout)
            if sec:
                return max(0, int((time.time() - sec) * 1000))
        except (OSError, subprocess.SubprocessError):
            pass
        return 10 ** 12   # si no se puede leer, se da por 'lleva mucho prendida' (no se frena ningun aviso)
    _pendiente()


# ---------------------------------------------------------------- buzon de las sesiones y Tailscale
class _BuzonUnix:
    """Envoltura de un socket Unix con write() y 'with', para entregar al buzon de una sesion igual que a una tuberia de Windows."""
    def __init__(self, s):
        self._s = s

    def write(self, datos):
        self._s.sendall(datos)
        return len(datos)

    def close(self):
        self._s.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def es_ruta_buzon(ruta):
    """True si `ruta` es un buzon de sesion valido (en Windows, una tuberia con nombre \\\\.\\pipe\\...; en macOS, un
    socket Unix; nunca un archivo comun)."""
    if sys.platform == "win32":
        return str(ruta).lower().startswith("\\\\.\\pipe\\")
    if sys.platform == "darwin":
        # POR VERIFICAR en un Mac: que CLAUDE_CODE_MESSAGING_SOCKET sea la ruta de un socket Unix. Si el socket aun no existe
        # (el chat se cerro) se acepta la ruta absoluta y abrir_buzon da FileNotFoundError, como la tuberia de Windows.
        import stat
        ruta = str(ruta)
        if not os.path.isabs(ruta):
            return False
        try:
            return stat.S_ISSOCK(os.stat(ruta).st_mode)
        except FileNotFoundError:
            return True
        except OSError:
            return False
    _pendiente()


def abrir_buzon(ruta):
    """Abre el buzon de una sesion para escribirle (puede fallar un instante si no hay instancia libre)."""
    if sys.platform == "win32":
        return open(ruta, "r+b", buffering=0)
    if sys.platform == "darwin":
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3)
        try:
            s.connect(str(ruta))
        except OSError:
            s.close()
            raise
        return _BuzonUnix(s)
    _pendiente()


def ruta_tailscale_cli():
    """tailscale (el programa de linea de comandos)."""
    if sys.platform == "win32":
        return r"C:\Program Files\Tailscale\tailscale.exe"
    if sys.platform == "darwin":   # la app de Tailscale se usa como CLI (alias oficial); si no esta, el `tailscale` del PATH (Homebrew)
        app = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
        return app if os.path.exists(app) else (shutil.which("tailscale") or app)
    _pendiente()


def tailscale_propio():
    """True si Kodama levanta SU tailscaled (con su propia identidad, aparte del Tailscale de la persona) y por eso hay que
    iniciar/relanzar ese proceso. Solo en Windows. En macOS NO: el hub usa el Tailscale del sistema (la app), que ya
    trae su servicio; `tailscale serve` publica el puerto del hub en la cuenta que la persona ya tiene iniciada ahi."""
    return sys.platform == "win32"


def socket_tailscale():
    """Socket (en Windows, una tuberia) del tailscaled PROPIO de Kodama; el de la empresa no se toca. None = el socket por defecto del sistema (macOS)."""
    if sys.platform == "win32":
        return r"\\.\pipe\companero-tailscaled"
    if sys.platform == "darwin":   # la app de Tailscale se encuentra sola: sin --socket
        return None
    _pendiente()


def args_tailscale():
    """Comienzo de cada llamada al CLI: [programa] + ['--socket=...'] si hay un socket propio."""
    s = socket_tailscale()
    return [ruta_tailscale_cli()] + ([f"--socket={s}"] if s else [])


def nombre_proceso_tailscaled():
    """Nombre del tailscaled propio (para ver si ya corre); None si Kodama no levanta uno (macOS)."""
    if sys.platform == "win32":
        return "tailscaled.exe"
    if sys.platform == "darwin":
        return None
    _pendiente()


def comando_tailscaled(ts_dir):
    """Comando para levantar el tailscaled propio de Kodama (red de usuario, sin tocar la red del sistema); None si no hace falta (macOS)."""
    if sys.platform == "win32":
        return [r"C:\Program Files\Tailscale\tailscaled.exe", "--windows-mode=dev", "--tun=userspace-networking",
                f"--statedir={ts_dir}", rf"--socket={socket_tailscale()}", "--port=41642"]
    if sys.platform == "darwin":
        return None
    _pendiente()
