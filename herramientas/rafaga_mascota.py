# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Rafaga de capturas SOLO de la ventana de la mascota (lectura de pantalla; sin clics ni teclas).
Uso: python rafaga_mascota.py <carpeta_salida> [n] [ms]. Imprime cuantos cuadros distintos hubo."""
import ctypes, ctypes.wintypes as wt, hashlib, os, sys, time
from PIL import ImageGrab
ctypes.windll.user32.SetProcessDPIAware()
out, n, ms = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 24, int(sys.argv[3]) if len(sys.argv) > 3 else 250
pid = int(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "estado", "escritorio.pid")).read().strip())
hw = []
@ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
def cb(h, _):
    p = wt.DWORD(); ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    if p.value == pid and ctypes.windll.user32.IsWindowVisible(h):
        r = wt.RECT(); ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
        if r.right - r.left > 50:
            hw.append((r.left, r.top, r.right, r.bottom))
    return True
ctypes.windll.user32.EnumWindows(cb, 0)
print("ventanas:", hw)
os.makedirs(out, exist_ok=True)
caja = hw[0]
hashes = []
for i in range(n):
    im = ImageGrab.grab(bbox=caja, all_screens=True)
    im.save(os.path.join(out, f"f{i:02d}.png"))
    hashes.append(hashlib.md5(im.tobytes()).hexdigest()[:8])
    time.sleep(ms / 1000)
print("cuadros:", n, "| distintos:", len(set(hashes)))
print(" ".join(hashes))
