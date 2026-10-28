# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Captura icono.html con Edge headless a 1024x1024 (cuadrado y redondeado) y arma los tamaños.
Reglas de la PC: perfil DENTRO del scratchpad, --disk-cache-size=1, cierre por PID del padre y TODOS los hijos
(buscados por el --user-data-dir), borrado del perfil y comprobacion de que no quede nada."""
import os, shutil, subprocess, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__))
PERFIL = os.path.join(AQUI, "perfil-edge")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HTML = "file:///" + os.path.join(AQUI, "icono.html").replace("\\", "/")


def hijos_del_perfil():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*" + PERFIL + "*' } | "
                        "Select-Object -ExpandProperty ProcessId"], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def captura(sufijo, salida):
    p = subprocess.Popen([EDGE, "--headless=new", f"--user-data-dir={PERFIL}", "--disk-cache-size=1",
                          "--allow-file-access-from-files", "--hide-scrollbars", "--force-device-scale-factor=1",
                          "--default-background-color=00000000", "--window-size=1024,1024", "--virtual-time-budget=3000",
                          f"--screenshot={salida}", HTML + sufijo])
    try:
        p.wait(timeout=60)
    finally:
        for pid in [p.pid] + hijos_del_perfil():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


try:
    captura("", os.path.join(AQUI, "cuadrado-1024.png"))
    captura("#redondo", os.path.join(AQUI, "redondo-1024.png"))
finally:
    time.sleep(1)
    for pid in hijos_del_perfil():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    shutil.rmtree(PERFIL, ignore_errors=True)
    print("procesos que quedan con el perfil:", hijos_del_perfil(), "| perfil borrado:", not os.path.exists(PERFIL))
for f in ("cuadrado-1024.png", "redondo-1024.png"):
    print(f, os.path.exists(os.path.join(AQUI, f)))
