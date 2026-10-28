# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Capa de plataforma de Kodama: TODO lo que solo existe en Windows y que usan el hub, arrancar.pyw,
companero_actualizar.py, config.py y los hooks (banderas de creacion de procesos, abrir enlaces y archivos, rutas de
datos del usuario, la mascota, buscar y cerrar procesos por PID, inactividad, ventana al frente, energia, Papelera,
instancia unica, buzon de las sesiones y Tailscale).

HOY SOLO IMPLEMENTA WINDOWS, con el comportamiento exacto que tenia antes cada pieza. Cada funcion tiene su rama
`if sys.platform == "win32":` y al final `raise NotImplementedError("macOS: pendiente")`: el port a macOS se hace
agregando la rama de `darwin` en cada una, sin tocar a quienes las llaman.

Reglas de este modulo: solo biblioteca estandar (ctypes se usa dentro de las funciones, asi importarlo no falla en
otro sistema); nada de Kodama (ni config ni el hub) para que arrancar.pyw y los hooks lo importen como script suelto;
siempre PID, nunca cerrar procesos por nombre."""
import ctypes
import os
import subprocess
import sys

NOMBRE_APP_CLAUDE = "claude.exe"   # ejecutable de la app de Claude (el que se mira al frente)
NOMBRES_EXE_MASCOTA = ("kodama.exe", "companero.exe")   # el nombre nuevo y el viejo (PC de desarrollo sin recompilar)

# banderas de creacion de procesos de Windows (solo se usan dentro de las funciones de abajo)
_SIN_VENTANA = 0x08000000      # CREATE_NO_WINDOW
_DESPRENDIDO = 0x00000008      # DETACHED_PROCESS
_GRUPO_NUEVO = 0x00000200      # CREATE_NEW_PROCESS_GROUP
_FUERA_DEL_JOB = 0x01000000    # CREATE_BREAKAWAY_FROM_JOB


def _pendiente():
    raise NotImplementedError("macOS: pendiente")


# ---------------------------------------------------------------- procesos: como se crean
def sin_ventana():
    """kwargs para subprocess.run/Popen: que el proceso no abra una consola."""
    if sys.platform == "win32":
        return {"creationflags": _SIN_VENTANA}
    _pendiente()


def desprendido(sin_ventana=False, grupo=False):
    """kwargs para subprocess.Popen: proceso desprendido (sigue vivo aunque el que lo lanzo se cierre).
    `grupo`: en un grupo de procesos nuevo; `sin_ventana`: sin consola."""
    if sys.platform == "win32":
        return {"creationflags": _DESPRENDIDO | (_GRUPO_NUEVO if grupo else 0) | (_SIN_VENTANA if sin_ventana else 0)}
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
    _pendiente()


# ---------------------------------------------------------------- procesos: buscarlos y cerrarlos (siempre por PID)
def pids_por_linea(texto, exe):
    """PIDs de procesos `exe` cuya linea de comando contiene `texto` (solo mira, no toca nada). Filtra por nombre de
    ejecutable: si no, la propia consulta (que contiene el texto) se encuentra a si misma."""
    if sys.platform == "win32":
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-CimInstance Win32_Process -Filter \"Name='{exe}'\" | Where-Object {{ $_.CommandLine -like '*{texto}*' }}).ProcessId"],
                           capture_output=True, text=True, **sin_ventana())
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    _pendiente()


def linea_de_comando(pid, timeout=30):
    """Linea de comando del proceso `pid` ('' si no existe): sirve para confirmar que el PID anotado sigue siendo el
    nuestro antes de cerrarlo."""
    if sys.platform == "win32":
        return subprocess.run(["powershell", "-NoProfile", "-Command",
                               f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                              capture_output=True, text=True, timeout=timeout, **sin_ventana()).stdout
    _pendiente()


def terminar_pid(pid, arbol=False):
    """Cierra SOLO el proceso `pid` (y sus hijos si `arbol`). Nunca por nombre."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid)] + (["/T"] if arbol else []) + ["/F"], capture_output=True, **sin_ventana())
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
    _pendiente()


# ---------------------------------------------------------------- rutas y ejecutables
def python_del_venv(app_dir, sin_consola=False):
    """Ruta del python del entorno virtual de `app_dir` (el de 'sin consola' si se pide). No mira si existe."""
    if sys.platform == "win32":
        return os.path.join(app_dir, ".venv", "Scripts", "pythonw.exe" if sin_consola else "python.exe")
    _pendiente()


def python_para_scripts(app_dir):
    """El python con consola del venv, o el que corre ahora si el venv no esta (para correr instalar.py y capturar su salida)."""
    if sys.platform == "win32":
        py = python_del_venv(app_dir)
        return py if os.path.exists(py) else sys.executable.replace("pythonw.exe", "python.exe")
    _pendiente()


def nombre_proceso_python():
    """Nombre del proceso del python del venv sin consola (con el que corre el hub): para buscarlo con pids_por_linea."""
    if sys.platform == "win32":
        return "pythonw.exe"
    _pendiente()


def ruta_exe_mascota(app_dir):
    """El ejecutable de la mascota (Tauri): kodama.exe, o el viejo companero.exe si el nuevo aun no se compilo."""
    if sys.platform == "win32":
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
    _pendiente()


def carpeta_datos_usuario():
    """Nombre de la carpeta de datos de aplicaciones dentro de la carpeta del usuario (en Windows, 'AppData')."""
    if sys.platform == "win32":
        return "AppData"
    _pendiente()


def temp_claude_relativa():
    """Donde guarda Claude sus carpetas de trabajo (scratchpads), relativa a la carpeta del usuario y normalizada."""
    if sys.platform == "win32":
        return os.path.normcase(os.path.join("AppData", "Local", "Temp", "claude"))
    _pendiente()


# ---------------------------------------------------------------- abrir cosas
def abrir(destino):
    """Abre un enlace (claude://, https://) o un archivo con la aplicacion que corresponda."""
    if sys.platform == "win32":
        os.startfile(destino)
        return
    _pendiente()


# ---------------------------------------------------------------- el usuario y su pantalla
def segundos_sin_uso():
    """Segundos desde el ultimo movimiento de mouse o tecla."""
    if sys.platform == "win32":
        class LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LII(); lii.cbSize = ctypes.sizeof(LII)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000
    _pendiente()


def app_al_frente():
    """Nombre del ejecutable de la ventana que tienes al frente (p.ej. 'claude.exe')."""
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
    _pendiente()


# ---------------------------------------------------------------- energia, Papelera, instancia unica
def pedir_pc_despierta(continuo=False, sistema=True, pantalla=False):
    """Le pide al sistema que no se suspenda (`sistema`) y/o que no apague la pantalla (`pantalla`). Con `continuo` el
    pedido dura hasta que este mismo hilo lo cambie (sistema=False y pantalla=False lo suelta); sin `continuo` es un
    pedido de una vez que saca a la PC de la suspension. Vive solo mientras corre el hilo: no toca la configuracion de energia."""
    if sys.platform == "win32":
        estado = (0x80000000 if continuo else 0) | (0x00000002 if pantalla else 0) | (0x00000001 if sistema else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(estado)
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
    _pendiente()


_MUTEX = None   # el manejador tiene que seguir vivo mientras corra el proceso


def instancia_unica(nombre):
    """True si este proceso es el PRIMERO con ese `nombre`; False si ya hay otro. Se libera solo al morir el proceso."""
    global _MUTEX
    if sys.platform == "win32":
        _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\" + nombre)
        return ctypes.windll.kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS
    _pendiente()


def ms_desde_arranque_pc():
    """Milisegundos desde que se prendio la PC."""
    if sys.platform == "win32":
        return ctypes.windll.kernel32.GetTickCount64()
    _pendiente()


# ---------------------------------------------------------------- buzon de las sesiones y Tailscale
def es_ruta_buzon(ruta):
    """True si `ruta` es un buzon de sesion valido (en Windows, una tuberia con nombre \\\\.\\pipe\\...; nunca un archivo)."""
    if sys.platform == "win32":
        return str(ruta).lower().startswith("\\\\.\\pipe\\")
    _pendiente()


def abrir_buzon(ruta):
    """Abre el buzon de una sesion para escribirle (puede fallar un instante si no hay instancia libre)."""
    if sys.platform == "win32":
        return open(ruta, "r+b", buffering=0)
    _pendiente()


def ruta_tailscale_cli():
    """tailscale (el programa de linea de comandos)."""
    if sys.platform == "win32":
        return r"C:\Program Files\Tailscale\tailscale.exe"
    _pendiente()


def socket_tailscale():
    """Socket (en Windows, una tuberia) del tailscaled PROPIO de Kodama; el de la empresa no se toca."""
    if sys.platform == "win32":
        return r"\\.\pipe\companero-tailscaled"
    _pendiente()


def nombre_proceso_tailscaled():
    if sys.platform == "win32":
        return "tailscaled.exe"
    _pendiente()


def comando_tailscaled(ts_dir):
    """Comando para levantar el tailscaled propio de Kodama (red de usuario, sin tocar la red del sistema)."""
    if sys.platform == "win32":
        return [r"C:\Program Files\Tailscale\tailscaled.exe", "--windows-mode=dev", "--tun=userspace-networking",
                f"--statedir={ts_dir}", rf"--socket={socket_tailscale()}", "--port=41642"]
    _pendiente()
