# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
"""Screenshots of the pet on a macOS runner (job `capturas-mac.yml`). It does NOT bypass anything: it only runs `screencapture -x` as a normal process.

What it does
  1. starts the FAKE hub (pruebas/hub_falso_capturas.py) on a local port and a work folder with a throwaway `estado/` (no real keys, no real data);
  2. launches the pet binary three times (island with a SIMULATED notch = "auto" path, island without notch = "si" path, normal pet = "no" path);
  3. for each state (idle, working, needs-you with a question, permission request, bubble open, Settings) waits until the page itself says it is in that
     state (the pet's fixed diagnostic: estado/escritorio-captura.pedido -> .txt), then runs `screencapture -x`;
  4. records, for every shot, the page state, the pet window as macOS sees it (layer = window level, bounds; pruebas/ventanas_mac.swift) and whether the
     image differs from an "empty desktop" baseline. If macOS does not let the runner capture app windows (Screen Recording / TCC), the image comes out
     WITHOUT the app: this is written in the job summary. The window info and the page state still prove where the island is.
It stops only the processes it started, by their saved PID.
"""
import argparse
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PUERTO = 8791
RESUMEN = []     # one dict per screenshot
NOTAS = []


def log(*a):
    print(*a, flush=True)


def anotar(nivel, titulo, texto):
    """GitHub annotation (visible on the run page and through the public API without logging in): ::notice / ::warning / ::error."""
    t = str(texto)[:3800].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
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


def hub_set(esc):
    hub_req("POST", "/_set", {"esc": esc})


def pedir(work, orden="x", espera=9.0):
    """Pet's fixed diagnostic. `orden` = x (just read state) | kodama:globo | kodama:ajustes | kodama:prueba. Returns the dict, or None."""
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


def ventanas(exe_ventanas, pid):
    if not exe_ventanas:
        return None
    try:
        r = subprocess.run([exe_ventanas, str(pid)], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.stdout.strip() else None
    except Exception as e:
        return {"error": str(e)}


def foto(out, nombre, modo, d, pid, exe_ventanas, base_sha):
    f = os.path.join(out, nombre + ".png")
    try:
        r = subprocess.run(["screencapture", "-x", f], capture_output=True, text=True, timeout=40)
        rc, err = r.returncode, (r.stderr or "").strip()[:200]
    except Exception as e:
        rc, err = -1, str(e)
    tam = os.path.getsize(f) if os.path.exists(f) else 0
    # crop of the top-center area (where the island is), with sips; best effort
    recorte = ""
    if tam:
        try:
            g = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", f], capture_output=True, text=True, timeout=20).stdout
            w = int([x for x in g.split() if x.isdigit()][0]) if g else 0
            if w > 1200:
                rc2 = os.path.join(out, nombre + "-recorte.png")
                subprocess.run(["sips", "-c", "760", "1200", "--cropOffset", "0", str((w - 1200) // 2), f, "--out", rc2], capture_output=True, timeout=20)
                recorte = os.path.basename(rc2) if os.path.exists(rc2) else ""
        except Exception:
            pass
    wi = ventanas(exe_ventanas, pid)
    RESUMEN.append({"nombre": nombre, "modo": modo, "rc": rc, "stderr": err, "bytes": tam, "igual_al_fondo": bool(tam and sha(f) == base_sha),
                    "recorte": recorte, "pagina": d, "ventanas": wi})
    log("shot", nombre, "rc", rc, "bytes", tam, "igual_al_fondo", RESUMEN[-1]["igual_al_fondo"])


class Pet:
    def __init__(self, binario, work, extra_env, etiqueta):
        env = dict(os.environ)
        env.update(extra_env)
        self.log = open(os.path.join(work, "pet-%s.log" % etiqueta), "w")
        self.p = subprocess.Popen([binario], cwd=work, env=env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        self.pid = self.p.pid

    def parar(self):
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


def escribir_conf(work, isla):
    est = os.path.join(work, "estado")
    os.makedirs(est, exist_ok=True)
    with open(os.path.join(est, "local.key"), "w") as f:
        f.write("clave-de-prueba-ci")
    with open(os.path.join(est, "puerto.txt"), "w") as f:
        f.write(str(PUERTO))
    # sleep off: the screenshots must not catch a sleeping pet; sound off: the runner has no audio device
    with open(os.path.join(est, "escritorio.json"), "w", encoding="utf-8") as f:
        json.dump({"isla": isla, "idioma": "en", "sonido": False, "sueno": False, "ojos": False, "visible": True}, f)
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

    # swift helper compiled once (window level + bounds + screens), optional
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
        hub_set("reposo")

        # baseline: the desktop WITHOUT the pet (to tell whether later shots really contain the app)
        base = os.path.join(out, "00-fondo-sin-app.png")
        subprocess.run(["screencapture", "-x", base], capture_output=True, timeout=40)
        base_sha = sha(base)
        log("baseline bytes", os.path.getsize(base) if os.path.exists(base) else 0)

        def lista(d):
            return d is not None and d.get("isla") is not None

        # ---------- A: island with a SIMULATED notch (conf "auto"; the runner has no real notch) ----------
        escribir_conf(work, "auto")
        pet = Pet(a.bin, work, {"KODAMA_ISLA_MUESCA_PRUEBA": "190x32"}, "A")
        d, ok = esperar(work, lambda d: lista(d) and d.get("estado") is not None, 60, "A: island up and state loaded")
        time.sleep(2)
        d = pedir(work) or d
        foto(out, "A1-isla-muesca-reposo", "auto + muesca simulada", d, pet.pid, exe_v, base_sha)

        hub_set("trabajando")
        d, ok = esperar(work, lambda d: d.get("estado") == "trabajando", 30, "A: working state")
        time.sleep(1.5)
        foto(out, "A2-isla-muesca-trabajando", "auto + muesca simulada", d, pet.pid, exe_v, base_sha)

        hub_set("pregunta")
        d, ok = esperar(work, lambda d: d.get("asomo") and "abierta" in (d.get("isla") or [""])[0], 40, "A: question notice expanded")
        time.sleep(0.9)
        foto(out, "A3-isla-muesca-aviso-pregunta", "auto + muesca simulada", pedir(work) or d, pet.pid, exe_v, base_sha)
        pedir(work, "kodama:globo")
        d, ok = esperar(work, lambda d: d.get("globo"), 20, "A: bubble open (question)")
        time.sleep(1.2)
        foto(out, "A4-isla-muesca-globo-pregunta", "auto + muesca simulada", pedir(work) or d, pet.pid, exe_v, base_sha)
        pedir(work, "kodama:globo")
        esperar(work, lambda d: not d.get("globo") and "abierta" not in (d.get("isla") or [""])[0], 20, "A: bubble closed")

        hub_set("reposo")
        time.sleep(22)   # the pet shows one notice every 20 s at most
        hub_set("permiso")
        d, ok = esperar(work, lambda d: d.get("asomo") and "abierta" in (d.get("isla") or [""])[0], 40, "A: permission notice expanded")
        time.sleep(0.9)
        foto(out, "A5-isla-muesca-aviso-permiso", "auto + muesca simulada", pedir(work) or d, pet.pid, exe_v, base_sha)
        pedir(work, "kodama:globo")
        d, ok = esperar(work, lambda d: d.get("globo"), 20, "A: bubble open (permission)")
        time.sleep(1.2)
        foto(out, "A6-isla-muesca-globo-permiso", "auto + muesca simulada", pedir(work) or d, pet.pid, exe_v, base_sha)
        pedir(work, "kodama:globo")
        esperar(work, lambda d: not d.get("globo"), 20, "A: bubble closed 2")

        hub_set("reposo")
        pedir(work, "kodama:ajustes")
        d, ok = esperar(work, lambda d: d.get("panel"), 20, "A: Settings open")
        time.sleep(1.2)
        foto(out, "A7-isla-muesca-ajustes", "auto + muesca simulada", pedir(work) or d, pet.pid, exe_v, base_sha)
        pet.parar()
        pet = None

        # ---------- B: island WITHOUT notch (conf "si": pill just below the menu bar) ----------
        escribir_conf(work, "si")
        hub_set("reposo")
        pet = Pet(a.bin, work, {}, "B")
        d, ok = esperar(work, lambda d: lista(d) and d.get("estado") is not None, 60, "B: island up and state loaded")
        time.sleep(2)
        foto(out, "B1-isla-sin-muesca-reposo", "si, sin muesca", pedir(work) or d, pet.pid, exe_v, base_sha)
        hub_set("pregunta")
        d, ok = esperar(work, lambda d: d.get("asomo") and "abierta" in (d.get("isla") or [""])[0], 40, "B: question notice expanded")
        time.sleep(0.9)
        foto(out, "B2-isla-sin-muesca-aviso-pregunta", "si, sin muesca", pedir(work) or d, pet.pid, exe_v, base_sha)
        pet.parar()
        pet = None

        # ---------- C: normal pet (conf "no"), for comparison ----------
        escribir_conf(work, "no")
        hub_set("reposo")
        pet = Pet(a.bin, work, {}, "C")
        d, ok = esperar(work, lambda d: d.get("estado") is not None, 60, "C: normal pet up and state loaded")
        time.sleep(3)
        foto(out, "C1-normal-reposo", "no (mascota normal)", pedir(work) or d, pet.pid, exe_v, base_sha)
        hub_set("pregunta")
        d, ok = esperar(work, lambda d: d.get("asomo"), 40, "C: question notice")
        time.sleep(1.2)
        foto(out, "C2-normal-aviso-pregunta", "no (mascota normal)", pedir(work) or d, pet.pid, exe_v, base_sha)
    except Exception:
        anotar("error", "capturas_mac exception", traceback.format_exc())
        raise
    finally:
        if pet is not None:
            pet.parar()
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


def resumen(out):
    fotos = [x for x in RESUMEN]
    sin_app = [x for x in fotos if x["igual_al_fondo"]]
    con_dom = [x for x in fotos if x["pagina"] and x["pagina"].get("isla") is not None]
    if not fotos:
        veredicto = "NO screenshots were taken."
    elif len(sin_app) == len(fotos):
        veredicto = "BLOCKED: every screenshot is byte-identical to the empty-desktop baseline, so macOS did not let the runner capture app windows (Screen Recording / TCC). Not bypassed."
    elif sin_app:
        veredicto = "PARTIAL: %d of %d screenshots are identical to the empty desktop (app not captured)." % (len(sin_app), len(fotos))
    else:
        veredicto = "OK: every screenshot differs from the empty-desktop baseline (the app window is in the image; check the pictures to be sure)."
    L = ["## Kodama on macOS: island screenshots", "", "**Result:** " + veredicto, ""]
    L.append("| shot | mode | page state (island class, w, h, top) | window level / bounds | image bytes | = empty desktop |")
    L.append("|---|---|---|---|---|---|")
    for x in fotos:
        d = x["pagina"] or {}
        w = ""
        for v in ((x["ventanas"] or {}).get("windows") or []):
            b = v.get("bounds") or {}
            w += "layer %s at (%s,%s) %sx%s on-screen=%s; " % (v.get("layer"), b.get("X"), b.get("Y"), b.get("Width"), b.get("Height"), v.get("onscreen"))
        L.append("| %s | %s | %s | %s | %s | %s |" % (x["nombre"], x["modo"], json.dumps(d.get("isla")) if d else "no answer", w or "n/a", x["bytes"], "yes" if x["igual_al_fondo"] else "no"))
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
    comp = [veredicto]
    for x in fotos:
        d = x["pagina"] or {}
        w = ""
        for v in ((x["ventanas"] or {}).get("windows") or []):
            b = v.get("bounds") or {}
            w += "L%s@(%s,%s)%sx%s on=%s " % (v.get("layer"), b.get("X"), b.get("Y"), b.get("Width"), b.get("Height"), v.get("onscreen"))
        comp.append("%s | isla=%s | %s| %sB | =fondo:%s | rc=%s" % (x["nombre"], json.dumps(d.get("isla")) if d else "sin respuesta", w, x["bytes"], x["igual_al_fondo"], x["rc"]))
    if scr:
        comp.append("screens: " + json.dumps(scr))
    anotar("notice", "Kodama island screenshots", "\n".join(comp))
    if NOTAS:
        anotar("warning", "Kodama island notes", "\n".join(NOTAS))
    gs = os.environ.get("GITHUB_STEP_SUMMARY")
    if gs:
        with open(gs, "a", encoding="utf-8") as f:
            f.write(texto)
    log(texto)


if __name__ == "__main__":
    main()
