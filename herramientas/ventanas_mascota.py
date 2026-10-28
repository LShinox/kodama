# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
import ctypes, ctypes.wintypes as wt, sys
u = ctypes.windll.user32
PID = int(sys.argv[1])
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
def f(h, l):
    p = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
    if p.value == PID:
        r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        b = ctypes.create_unicode_buffer(200); u.GetWindowTextW(h, b, 200)
        c = ctypes.create_unicode_buffer(200); u.GetClassNameW(h, c, 200)
        ex = u.GetWindowLongW(h, -20)
        print(h, "vis", bool(u.IsWindowVisible(h)), "min", bool(u.IsIconic(h)), "rect", (r.left, r.top, r.right, r.bottom), repr(b.value), c.value, hex(ex & 0xFFFFFFFF))
    return True
u.EnumWindows(CB(f), 0)
