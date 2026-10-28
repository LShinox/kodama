# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""Prueba del panel de Ajustes de la mascota: manda Ctrl+Shift+F12 (abrir), saca capturas de la zona de abajo a la
derecha durante la animacion, y otra vez Ctrl+Shift+F12 (cerrar). Solo el atajo; ningun clic."""
import ctypes, os, sys, time
from PIL import ImageGrab
u = ctypes.windll.user32; u.SetProcessDPIAware()
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
VK = {"ctrl": 0x11, "shift": 0x10, "f12": 0x7B}
def atajo():
    for k in ("ctrl", "shift", "f12"): u.keybd_event(VK[k], 0, 0, 0)
    time.sleep(.05)
    for k in ("f12", "shift", "ctrl"): u.keybd_event(VK[k], 0, 2, 0)
W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
caja = (W - 760, 0, W, H)
def rafaga(nombre, n, ms):
    for i in range(n):
        ImageGrab.grab(bbox=caja).save(os.path.join(out, f"{nombre}{i:02d}.png")); time.sleep(ms / 1000)
rafaga("antes", 1, 0)
atajo(); rafaga("abre", 12, 120)
time.sleep(.5); rafaga("abierto", 1, 0)
atajo(); rafaga("cierra", 12, 120)
time.sleep(.6); rafaga("despues", 1, 0)
print("pantalla", W, H, "listo")
