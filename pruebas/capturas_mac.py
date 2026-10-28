# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
"""Screenshots of the pet on a macOS runner (job `capturas-mac.yml`). It does NOT bypass anything: it only runs `screencapture -x` as a normal process.

What it does
  1. sets a LIGHT solid-gray wallpaper (a PNG generated here, set with osascript / System Events; if the runner does not allow it, a solid-gray window at the
     desktop level started by this script) so the black island shape is visible;
  2. starts the FAKE hub (pruebas/hub_falso_capturas.py) on a local port and a work folder with a throwaway `estado/` (no real keys, no real data);
  3. launches the pet binary several times: A = island with a SIMULATED notch (English), B = island without notch, C = normal pet, D = island in Spanish;
  4. for each state (collapsed, hover, working, question, permission, bubble, Settings option A and B) waits until the page itself says it is in that
     state (the pet's fixed diagnostic: estado/escritorio-captura.pedido -> .txt), then runs `screencapture -x`;
  5. records, for every shot, the page state, the pet window as macOS sees it (layer = window level, bounds, activation policy, who owns the menu bar;
     pruebas/ventanas_mac.swift) and whether the image differs from an "empty desktop" baseline. If macOS does not let the runner capture app windows
     (Screen Recording / TCC), the image comes out WITHOUT the app: this is written in the job summary.
  6. writes small JPEG crops of every shot into previews.json and prints them as annotations (base64), because the artifact cannot be downloaded without
     logging in but the annotations of a run can be read through the public API.
It stops only the processes it started, by their saved PID.
"""
import argparse
import base64
import hashlib
import http.client
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
PUERTO = 8791
ACTUAL = {"pet": None}   # the pet process in use (so the waits notice if it died)
RESUMEN = []     # one dict per screenshot
NOTAS = []
PREVIEWS = []    # (name, jpeg bytes)
PROCS = []       # helper processes we started (wallpaper window): stopped at the end by PID


def log(*a):
    print(*a, flush=True)


def anotar(nivel, titulo, texto):
    """GitHub annotation (visible on the run page and through the public API without logging in): ::notice / ::warning / ::error."""
    t = str(texto)[:60000].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::%s title=%s::%s" % (nivel, titulo, t), flush=True)


def hub_req(metodo, ruta, cuerpo=None):
    """Direct HTTP to the fake hub with http.client: it never goes through a system proxy (urllib would, if the runner defines one)."""
    c = http.client.HTTPConnection("127.0.0.1", PUERTO, timeout=5)
    try:
        c.request(metodo, ruta, body=json.dumps(cuerpo).encode() if cuerpo is not None else None, headers={"Content-Type": "application/json"})
        r = c.getresponse()
        return r.read()
    finally:
        c.close()


def hub_set(esc, lang=None):
    cuerpo = {"esc": esc}
    if lang:
        cuerpo["lang"] = lang
    hub_req("POST", "/_set", cuerpo)


def pedir(work, orden="x", espera=9.0):
    """Pet's fixed diagnostic. `orden` = x (just read state) | kodama:globo | kodama:ajustes | kodama:prueba | kodama:hover | kodama:ajustes-a | kodama:ajustes-b.
    Returns the dict, or None."""
    est = os.path.join(work, "estado")
    txt, ped = os.path.join(est, "escritorio-captura.txt"), os.path.join(est, "escritorio-captura.pedido")
    try:
        os.remove(txt)
    except OSError:
        pass
    with open(ped, "w", encoding="utf-8") as f:
        f.write(orden)
    t0 = time.time()
    while time.time() - t0 < espera:
        if os.path.exists(txt):
            try:
                with open(txt, encoding="utf-8") as f:
                    return json.loads(f.read())
            except Exception:
                pass
        time.sleep(0.3)
    return None


def esperar(work, cond, timeout=45.0, que=""):
    t0 = time.time()
    ult = None
    while time.time() - t0 < timeout:
        pa = ACTUAL.get("pet")
        if pa is not None and pa.p.poll() is not None:
            NOTAS.append("the pet process exited (rc=%s) while waiting for: %s" % (pa.p.poll(), que))
            return ult, False
        d = pedir(work)
        if d is not None:
            ult = d
            try:
                if cond(d):
                    return d, True
            except Exception:
                pass
        time.sleep(0.5)
    NOTAS.append("timeout waiting for: " + que)
    return ult, False


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def clase(d):
    return ((d or {}).get("isla") or [""])[0] or ""


# ---------------------------------------------------------------- wallpaper
def png_solido(path, rgb, w=64, h=64):
    """Solid-color PNG written with the standard library only."""
    fila = b"\x00" + bytes(rgb) * w
    datos = zlib.compress(fila * h, 9)

    def trozo(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + trozo(b"IDAT", datos) + trozo(b"IEND", b""))


def png_pixel(path, x, y):
    """RGB of one pixel of an 8-bit RGB/RGBA non-interlaced PNG (what `screencapture` writes), or None."""
    try:
        with open(path, "rb") as f:
            b = f.read()
        pos, idat, ihdr = 8, b"", None
        while pos < len(b):
            n = struct.unpack(">I", b[pos:pos + 4])[0]
            t = b[pos + 4:pos + 8]
            d = b[pos + 8:pos + 8 + n]
            if t == b"IHDR":
                ihdr = struct.unpack(">IIBBBBB", d)
            elif t == b"IDAT":
                idat += d
            pos += 12 + n
        w, h, prof, ct, _, _, inter = ihdr
        if prof != 8 or ct not in (2, 6) or inter != 0:
            return None
        bpp = 3 if ct == 2 else 4
        raw = zlib.decompress(idat)
        stride = w * bpp
        prev = bytearray(stride)
        fila = None
        pos = 0
        for yy in range(h):
            ft = raw[pos]
            cur = bytearray(raw[pos + 1:pos + 1 + stride])
            pos += 1 + stride
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                bb = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if ft == 1:
                    cur[i] = (cur[i] + a) & 255
                elif ft == 2:
                    cur[i] = (cur[i] + bb) & 255
                elif ft == 3:
                    cur[i] = (cur[i] + ((a + bb) >> 1)) & 255
                elif ft == 4:
                    p = a + bb - c
                    pa, pb, pc = abs(p - a), abs(p - bb), abs(p - c)
                    pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                    cur[i] = (cur[i] + pr) & 255
            prev = cur
            if yy == y:
                fila = cur
                break
        if fila is None or x >= w:
            return None
        return (fila[x * bpp], fila[x * bpp + 1], fila[x * bpp + 2])
    except Exception:
        return None


def fondo_claro(work, out):
    """Light wallpaper. Returns a short description of what happened (goes to the notes)."""
    png = os.path.join(work, "fondo-claro.png")
    png_solido(png, (230, 230, 232))
    resultados = []
    guiones = [
        'tell application "System Events" to tell every desktop to set picture to POSIX file "%s"' % png,
        'tell application "Finder" to set desktop picture to POSIX file "%s"' % png,
    ]
    for g in guiones:
        try:
            r = subprocess.run(["osascript", "-e", g], capture_output=True, text=True, timeout=40)
            resultados.append("osascript rc=%s %s" % (r.returncode, (r.stderr or r.stdout or "").strip()[:120]))
        except Exception as e:
            resultados.append("osascript failed: %s" % e)
        time.sleep(3)
        px = muestra_fondo(out)
        if px and sum(px) / 3 > 200:
            return "light wallpaper OK via osascript (pixel %s). %s" % (px, " | ".join(resultados))
    # fallback: our own solid window at the desktop level
    exe = os.path.join(work, "fondo_mac")
    try:
        r = subprocess.run(["swiftc", "-O", os.path.join(AQUI, "fondo_mac.swift"), "-o", exe], capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            p = subprocess.Popen([exe, "230", "230", "232"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            PROCS.append(p)
            time.sleep(3)
            px = muestra_fondo(out)
            return "osascript did not change the wallpaper (%s); fallback gray window started (pixel now %s)" % (" | ".join(resultados), px)
        return "osascript failed and the fallback did not compile: " + r.stderr[-200:]
    except Exception as e:
        return "osascript failed (%s) and the fallback failed: %s" % (" | ".join(resultados), e)


def muestra_fondo(out):
    f = os.path.join(out, "_muestra.png")
    try:
        subprocess.run(["screencapture", "-x", f], capture_output=True, timeout=40)
        px = png_pixel(f, 512, 450)
        os.remove(f)
        return px
    except Exception:
        return None


def ventanas(exe_ventanas, pid):
    if not exe_ventanas:
        return None
    try:
        r = subprocess.run([exe_ventanas, str(pid)], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.stdout.strip() else None
    except Exception as e:
        return {"error": str(e)}


def previsualizar(out, nombre, f, region, zoom):
    """Small JPEG crop (region = x, y, w, h in screen points) of a shot. Best effort; goes into PREVIEWS (written to previews.json; emitir_previews.py
    prints them as annotations: an annotation message holds at most ~4 KB, so every image is cut in chunks)."""
    try:
        g = subprocess.run(["sips", "-g", "pixelWidth", f], capture_output=True, text=True, timeout=20).stdout
        nums = [int(x) for x in g.split() if x.isdigit()]
        w = nums[0] if nums else 0
        esc = 2 if w > 1500 else 1
        x, y, rw, rh = [int(v) * esc for v in region]
        rc = os.path.join(out, "_rec.png")
        jp = os.path.join(out, "_rec.jpg")
        subprocess.run(["sips", "-c", str(rh), str(rw), "--cropOffset", str(y), str(x), f, "--out", rc], capture_output=True, timeout=20)
        if zoom != 1:
            subprocess.run(["sips", "--resampleWidth", str(int(rw * zoom)), rc], capture_output=True, timeout=20)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "38", rc, "--out", jp], capture_output=True, timeout=20)
        if os.path.exists(jp):
            with open(jp, "rb") as fh:
                PREVIEWS.append((nombre, fh.read()))
        for x in (rc, jp):
            try:
                os.remove(x)
            except OSError:
                pass
    except Exception as e:
        NOTAS.append("preview failed for %s: %s" % (nombre, e))


# crops (x, y, w, h in points) used for the previews; the island window is 440 wide, centered on a 1024-wide screen (x = 292)
R_PILL = (342, 0, 340, 56)
def R_ISLA(alto):
    return (292, 0, 440, alto)


def foto(out, nombre, modo, d, pid, exe_ventanas, base_sha, region=None, zoom=1):
    f = os.path.join(out, nombre + ".png")
    try:
        r = subprocess.run(["screencapture", "-x", f], capture_output=True, text=True, timeout=40)
        rc, err = r.returncode, (r.stderr or "").strip()[:200]
    except Exception as e:
        rc, err = -1, str(e)
    tam = os.path.getsize(f) if os.path.exists(f) else 0
    solo = [x.strip() for x in os.environ.get("KODAMA_PREVIEW_SOLO", "").split(",") if x.strip()]   # empty = all the shots that have a region
    if tam and region and (not solo or nombre.split("-")[0] in solo):
        previsualizar(out, nombre, f, region, zoom)
    wi = ventanas(exe_ventanas, pid)
    RESUMEN.append({"nombre": nombre, "modo": modo, "rc": rc, "stderr": err, "bytes": tam, "igual_al_fondo": bool(tam and sha(f) == base_sha),
                    "pagina": d, "ventanas": wi})
    log("shot", nombre, "rc", rc, "bytes", tam, "igual_al_fondo", RESUMEN[-1]["igual_al_fondo"])


class Pet:
    def __init__(self, binario, work, extra_env, etiqueta):
        env = dict(os.environ)
        env.update(extra_env)
        self.log = open(os.path.join(work, "pet-%s.log" % etiqueta), "w")
        self.p = subprocess.Popen([binario], cwd=work, env=env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        self.pid = self.p.pid
        ACTUAL["pet"] = self

    def parar(self):
        ACTUAL["pet"] = None
        # only the process we started, by its PID (Popen handle); children of the webview are system XPC services that exit with it
        try:
            self.p.terminate()
            self.p.wait(timeout=15)
        except Exception:
            try:
                self.p.kill()
                self.p.wait(timeout=10)
            except Exception:
                pass
        try:
            self.log.close()
        except Exception:
            pass


def escribir_conf(work, isla, idioma="en"):
    est = os.path.join(work, "estado")
    os.makedirs(est, exist_ok=True)
    with open(os.path.join(est, "local.key"), "w") as f:
        f.write("clave-de-prueba-ci")
    with open(os.path.join(est, "puerto.txt"), "w") as f:
        f.write(str(PUERTO))
    # sleep off: the screenshots must not catch a sleeping pet; sound off: the runner has no audio device
    with open(os.path.join(est, "escritorio.json"), "w", encoding="utf-8") as f:
        json.dump({"isla": isla, "idioma": idioma, "sonido": False, "sueno": False, "ojos": False, "visible": True}, f)
    for n in ("escritorio-captura.pedido", "escritorio-captura.txt"):
        try:
            os.remove(os.path.join(est, n))
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    a.bin = os.path.abspath(a.bin)   # the pet is started with cwd = work folder: a relative path would not be found
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="kodama-capturas-")
    log("work folder:", work)

    # swift helper compiled once (window level + bounds + screens + activation policy + menu bar owner), optional
    exe_v = os.path.join(work, "ventanas_mac")
    try:
        r = subprocess.run(["swiftc", "-O", os.path.join(AQUI, "ventanas_mac.swift"), "-o", exe_v], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            NOTAS.append("swiftc failed (window info unavailable): " + r.stderr[-300:])
            exe_v = ""
    except Exception as e:
        NOTAS.append("swiftc not available: %s" % e)
        exe_v = ""

    if not os.path.exists(a.bin):
        anotar("error", "capturas_mac", "binary not found: " + a.bin)
    hub_log = open(os.path.join(work, "hub.log"), "w")
    hub = subprocess.Popen([sys.executable, os.path.join(AQUI, "hub_falso_capturas.py"), str(PUERTO)], stdout=hub_log, stderr=subprocess.STDOUT, start_new_session=True)
    pet = None
    try:
        t0 = time.time()
        hub_ok = False
        while time.time() - t0 < 20:
            try:
                hub_req("GET", "/api/inactivo")
                hub_ok = True
                break
            except Exception:
                time.sleep(0.4)
        if not hub_ok:
            hub_log.flush()
            with open(os.path.join(work, "hub.log"), errors="replace") as hl:
                anotar("error", "fake hub unreachable", "poll=%s log=%s" % (hub.poll(), hl.read()[-600:]))
        hub_set("reposo", "en")

        # light wallpaper, then the baseline: the desktop WITHOUT the pet (to tell whether later shots really contain the app)
        try:
            NOTAS.append("wallpaper: " + fondo_claro(work, out))
        except Exception as e:
            NOTAS.append("wallpaper step failed: %s" % e)
        base = os.path.join(out, "00-light-desktop-without-app.png")
        subprocess.run(["screencapture", "-x", base], capture_output=True, timeout=40)
        base_sha = sha(base)
        log("baseline bytes", os.path.getsize(base) if os.path.exists(base) else 0)

        def lista(d):
            return d is not None and d.get("isla") is not None

        def abierta(d):
            return "abierta" in clase(d)

        def sec_A():
            nonlocal pet
            # ---------- A: island with a SIMULATED notch (conf "auto"; the runner has no real notch), English ----------
            escribir_conf(work, "auto", "en")
            hub_set("reposo", "en")
            pet = Pet(a.bin, work, {"KODAMA_ISLA_MUESCA_PRUEBA": "190x32"}, "A")
            d, ok = esperar(work, lambda d: lista(d) and d.get("estado") is not None, 60, "A: island up and state loaded")
            time.sleep(2.5)
            d = pedir(work) or d
            foto(out, "A01-island-collapsed-en", "auto + simulated notch", d, pet.pid, exe_v, base_sha, R_PILL, 2)

            pedir(work, "kodama:hover")
            d, ok = esperar(work, lambda d: "hov" in clase(d), 15, "A: hover state")
            time.sleep(1.0)
            foto(out, "A02-island-hover-en", "auto + simulated notch, mouse over (forced)", pedir(work) or d, pet.pid, exe_v, base_sha, R_PILL, 2)
            pedir(work, "kodama:hover")
            esperar(work, lambda d: "hov" not in clase(d), 15, "A: hover released")

            hub_set("trabajando", "en")
            d, ok = esperar(work, lambda d: d.get("estado") == "trabajando", 30, "A: working state")
            time.sleep(1.5)
            foto(out, "A03-island-working-en", "auto + simulated notch", d, pet.pid, exe_v, base_sha, None)

            hub_set("pregunta", "en")
            d, ok = esperar(work, lambda d: d.get("asomo") and abierta(d), 40, "A: question notice expanded")
            time.sleep(1.0)
            foto(out, "A04-island-question-expanded-en", "auto + simulated notch", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(170))
            pedir(work, "kodama:globo")
            d, ok = esperar(work, lambda d: d.get("globo"), 20, "A: bubble open (question)")
            time.sleep(1.4)
            foto(out, "A05-island-question-bubble-en", "auto + simulated notch (keyboard focus in the box)", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(235))
            pedir(work, "kodama:globo")
            esperar(work, lambda d: not d.get("globo") and not abierta(d), 20, "A: bubble closed")

            hub_set("reposo", "en")
            time.sleep(22)   # the pet shows one notice every 20 s at most
            hub_set("permiso", "en")
            d, ok = esperar(work, lambda d: d.get("asomo") and abierta(d), 40, "A: permission notice expanded")
            time.sleep(1.0)
            foto(out, "A06-island-permission-expanded-en", "auto + simulated notch", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(170))
            pedir(work, "kodama:globo")
            d, ok = esperar(work, lambda d: d.get("globo"), 20, "A: bubble open (permission)")
            time.sleep(1.4)
            foto(out, "A07-island-permission-bubble-en", "auto + simulated notch", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(280))
            pedir(work, "kodama:globo")
            esperar(work, lambda d: not d.get("globo"), 20, "A: bubble closed 2")

            hub_set("reposo", "en")
            time.sleep(1.0)
            pedir(work, "kodama:ajustes-a")
            d, ok = esperar(work, lambda d: d.get("panel"), 20, "A: Settings open (option A)")
            time.sleep(1.4)
            foto(out, "A08-settings-optionA-floating-panel-en", "auto + simulated notch: Settings as a floating panel under the pill", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(610))
            pedir(work, "kodama:ajustes-b")   # closes the panel and opens it again with option B (the island grows into a settings card)
            time.sleep(0.8)
            d, ok = esperar(work, lambda d: d.get("panel") and abierta(d), 20, "A: Settings open (option B)")
            time.sleep(1.4)
            foto(out, "A09-settings-optionB-expanded-card-en", "auto + simulated notch: the island grows into a settings card", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(600))
            pet.parar()
            pet = None

        def sec_B():
            nonlocal pet
            # ---------- B: island WITHOUT notch (conf "si": pill just below the menu bar), English ----------
            escribir_conf(work, "si", "en")
            hub_set("reposo", "en")
            pet = Pet(a.bin, work, {}, "B")
            d, ok = esperar(work, lambda d: lista(d) and d.get("estado") is not None, 60, "B: island up and state loaded")
            time.sleep(2.5)
            foto(out, "B01-island-no-notch-collapsed-en", "si, no notch", pedir(work) or d, pet.pid, exe_v, base_sha, (342, 0, 340, 60), 2)
            hub_set("pregunta", "en")
            d, ok = esperar(work, lambda d: d.get("asomo") and abierta(d), 40, "B: question notice expanded")
            time.sleep(1.0)
            foto(out, "B02-island-no-notch-question-expanded-en", "si, no notch", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(172))
            pet.parar()
            pet = None

        def sec_C():
            nonlocal pet
            # ---------- C: normal pet (conf "no"), for comparison ----------
            escribir_conf(work, "no", "en")
            hub_set("reposo", "en")
            pet = Pet(a.bin, work, {}, "C")
            d, ok = esperar(work, lambda d: d.get("estado") is not None, 60, "C: normal pet up and state loaded")
            time.sleep(3)
            foto(out, "C01-normal-mode-idle-en", "no (normal pet): bottom right corner; the menu bar must not show the app", pedir(work) or d, pet.pid, exe_v, base_sha, (780, 540, 244, 180))
            hub_set("pregunta", "en")
            d, ok = esperar(work, lambda d: d.get("asomo"), 40, "C: question notice")
            time.sleep(1.2)
            foto(out, "C02-normal-mode-question-en", "no (normal pet)", pedir(work) or d, pet.pid, exe_v, base_sha, (612, 470, 412, 230))
            pet.parar()
            pet = None

        def sec_D():
            nonlocal pet
            # ---------- D: island in SPANISH (everything must be Spanish: the badge, the buttons, the placeholder) ----------
            escribir_conf(work, "auto", "es")
            hub_set("reposo", "es")
            pet = Pet(a.bin, work, {"KODAMA_ISLA_MUESCA_PRUEBA": "190x32"}, "D")
            d, ok = esperar(work, lambda d: lista(d) and d.get("estado") is not None, 60, "D: island up and state loaded")
            time.sleep(2.5)
            foto(out, "D01-island-collapsed-es", "auto + simulated notch, Spanish", pedir(work) or d, pet.pid, exe_v, base_sha, None)
            hub_set("pregunta", "es")
            d, ok = esperar(work, lambda d: d.get("asomo") and abierta(d), 40, "D: question notice expanded")
            time.sleep(1.0)
            foto(out, "D02-island-question-expanded-es", "auto + simulated notch, Spanish", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(160))
            pedir(work, "kodama:globo")
            d, ok = esperar(work, lambda d: d.get("globo"), 20, "D: bubble open")
            time.sleep(1.4)
            foto(out, "D03-island-question-bubble-es", "auto + simulated notch, Spanish", pedir(work) or d, pet.pid, exe_v, base_sha, R_ISLA(240))
            pedir(work, "kodama:globo")
            esperar(work, lambda d: not d.get("globo") and not abierta(d), 20, "D: bubble closed")
            hub_set("reposo", "es")
            time.sleep(1.0)
            pedir(work, "kodama:ajustes-a")
            d, ok = esperar(work, lambda d: d.get("panel"), 20, "D: Settings open")
            time.sleep(1.4)
            foto(out, "D04-settings-floating-panel-es", "auto + simulated notch, Spanish", pedir(work) or d, pet.pid, exe_v, base_sha, None)
            pet.parar()
            pet = None

        for nom, fn in (("A", sec_A), ("B", sec_B), ("C", sec_C), ("D", sec_D)):
            try:
                fn()
            except Exception:
                anotar("error", "capturas_mac section " + nom, traceback.format_exc())
                NOTAS.append("section %s failed: see annotation" % nom)
            finally:
                if pet is not None:
                    pet.parar()
                    pet = None
    except Exception:
        anotar("error", "capturas_mac exception", traceback.format_exc())
        raise
    finally:
        if pet is not None:
            pet.parar()
        for p in PROCS:   # the wallpaper window, by its PID
            try:
                p.terminate()
                p.wait(timeout=10)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        try:
            hub.terminate()
            hub.wait(timeout=10)
        except Exception:
            try:
                hub.kill()
            except Exception:
                pass
        for n in os.listdir(work):
            if n.endswith(".log"):
                shutil.copy(os.path.join(work, n), os.path.join(out, n))
                try:
                    with open(os.path.join(work, n), encoding="utf-8", errors="replace") as lf:
                        cola = lf.read()[-700:].strip()
                    if cola:
                        anotar("warning", "pet log " + n, cola)
                except OSError:
                    pass
        shutil.rmtree(work, ignore_errors=True)
        resumen(out)   # also when something failed above: whatever was captured is reported
        emitir_previews(out)
    return 0 if RESUMEN else 1


def emitir_previews(out):
    """JPEG crops into previews.json (part of the artifact). pruebas/emitir_previews.py prints them as annotations in later workflow steps."""
    if not PREVIEWS:
        return
    with open(os.path.join(out, "previews.json"), "w") as f:
        json.dump([{"nombre": n, "jpg_b64": base64.b64encode(b).decode()} for n, b in PREVIEWS], f)


def resumen(out):
    fotos = [x for x in RESUMEN]
    sin_app = [x for x in fotos if x["igual_al_fondo"]]
    if not fotos:
        veredicto = "NO screenshots were taken."
    elif len(sin_app) == len(fotos):
        veredicto = "BLOCKED: every screenshot is byte-identical to the empty-desktop baseline, so macOS did not let the runner capture app windows (Screen Recording / TCC). Not bypassed."
    elif sin_app:
        veredicto = "PARTIAL: %d of %d screenshots are identical to the empty desktop (app not captured)." % (len(sin_app), len(fotos))
    else:
        veredicto = "OK: every screenshot differs from the empty-desktop baseline (the app window is in the image; check the pictures to be sure)."
    L = ["## Kodama on macOS: island screenshots", "", "**Result:** " + veredicto, ""]
    L.append("| shot | mode | page state (island class, w, h, top) | window level / bounds / policy / menu bar owner | image bytes | = empty desktop |")
    L.append("|---|---|---|---|---|---|")
    for x in fotos:
        d = x["pagina"] or {}
        w = ""
        wi = x["ventanas"] or {}
        for v in (wi.get("windows") or []):
            b = v.get("bounds") or {}
            w += "layer %s at (%s,%s) %sx%s on-screen=%s; " % (v.get("layer"), b.get("X"), b.get("Y"), b.get("Width"), b.get("Height"), v.get("onscreen"))
        w += "policy=%s menuBarOwner=%s frontmost=%s" % (wi.get("activationPolicy"), wi.get("menuBarOwner"), wi.get("frontmost"))
        L.append("| %s | %s | %s | %s | %s | %s |" % (x["nombre"], x["modo"], json.dumps(d.get("isla")) if d else "no answer", w, x["bytes"], "yes" if x["igual_al_fondo"] else "no"))
    if NOTAS:
        L += ["", "**Notes:**"] + ["- " + n for n in NOTAS]
    scr = None
    for x in fotos:
        if x["ventanas"] and x["ventanas"].get("screens"):
            scr = x["ventanas"]["screens"]
            break
    if scr:
        L += ["", "Screens seen by macOS: `" + json.dumps(scr) + "`"]
    texto = "\n".join(L) + "\n"
    with open(os.path.join(out, "resumen.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    with open(os.path.join(out, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump({"veredicto": veredicto, "fotos": fotos, "notas": NOTAS}, f, indent=1, default=str)
    # compact annotations (a GitHub annotation message is cut at ~4 KB): 1 = where each window is + the Accessory check; 2 = language labels; 3 = cat size
    comp = [veredicto]
    for x in fotos:
        d = x["pagina"] or {}
        wi = x["ventanas"] or {}
        w = ""
        for v in (wi.get("windows") or []):
            b = v.get("bounds") or {}
            if v.get("onscreen"):
                w += "L%s@(%s,%s)%sx%s " % (v.get("layer"), b.get("X"), b.get("Y"), b.get("Width"), b.get("Height"))
        isla = d.get("isla")
        comp.append("%s|%s|%s|pol=%s bar=%s front=%s|%sB%s" % (x["nombre"][:3], json.dumps(isla, separators=(",", ":")) if isla else "-", w, wi.get("activationPolicy"), wi.get("menuBarOwner"),
                                                              wi.get("frontmost"), x["bytes"] // 1000, "|=bg" if x["igual_al_fondo"] else ""))
    anotar("notice", "Kodama island screenshots", "\n".join(comp)[:3900])
    idi = []
    for x in fotos:
        d = x["pagina"] or {}
        if d and x["nombre"][:3] in ("A04", "A07", "C02", "D02", "D03"):
            rot = [r for r in (d.get("rotulos") or []) if r and not r.endswith("=")]
            idi.append("%s|lang=%s|%s|focus=%s active=%s" % (x["nombre"][:3], d.get("idioma"), "; ".join(rot), d.get("foco"), d.get("activo")))
    if idi:
        anotar("notice", "Kodama language check", "\n".join(idi)[:3900])
    gat = []
    for x in fotos:
        d = x["pagina"] or {}
        if d and x["nombre"][:3] in ("A01", "A02", "A04", "B01", "C01"):
            gat.append("%s|pie=%s|pj=%s" % (x["nombre"][:3], d.get("pieRect"), d.get("pjRect")))
    if gat:
        anotar("notice", "Kodama cat size", "\n".join(gat))
    if NOTAS:
        anotar("warning", "Kodama island notes", "\n".join(NOTAS))
    gs = os.environ.get("GITHUB_STEP_SUMMARY")
    if gs:
        with open(gs, "a", encoding="utf-8") as f:
            f.write(texto)
    log(texto)


if __name__ == "__main__":
    sys.exit(main())
