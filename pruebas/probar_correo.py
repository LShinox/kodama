# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(05-nov) Correo de solo lectura. IMAP falso; todo va a una carpeta temporal y el log se captura."""
import imaplib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kodama_correo as kc  # noqa: E402

ok = fallos = 0
CFG = {}          # servidor -> comportamiento del IMAP falso
INSTANCIAS = []
LOGS = []
kc.log = LOGS.append


def ver(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
    else:
        fallos += 1
        print("FALLA:", nombre)


class FakeIMAP:
    """Registra cada llamada. No habla con ningun servidor."""

    def __init__(self, servidor, puerto, timeout=None):
        self.cfg = CFG[servidor]
        self.timeout = timeout
        self.llamadas = []
        INSTANCIAS.append(self)

    def _rec(self, nombre, *args, **kw):
        self.llamadas.append((nombre, args, kw))

    def login(self, usuario, clave):
        self._rec("login", usuario)
        if self.cfg.get("falla_login"):
            raise imaplib.IMAP4.error("AUTH rechazada para " + clave)

    def select(self, buzon, readonly=False):
        self._rec("select", buzon, readonly=readonly)
        return ("OK", [b"1"])

    def search(self, charset, criterio):
        self._rec("search", charset, criterio)
        if self.cfg.get("falla_search"):
            raise imaplib.IMAP4.error("fallo de busqueda")
        return ("OK", [" ".join(str(n) for n in self.cfg["unseen"]).encode()])

    def fetch(self, seq, partes):
        self._rec("fetch", seq, partes)
        raw = self.cfg["cab"].get(str(seq), b"")
        cab = f"{seq} (BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] {{{len(raw)}}})".encode()
        return ("OK", [(cab, raw), b")"])

    def store(self, *args):
        self._rec("store", *args)
        return ("OK", [])

    def logout(self):
        self._rec("logout")
        return ("BYE", [])


def fab(servidor, puerto, timeout=None):
    return FakeIMAP(servidor, puerto, timeout=timeout)


def cab(mid, asunto, de="Ana <ana@ejemplo.com>", fecha="Mon, 2 Nov 2026 10:00:00 +0000"):
    return f"From: {de}\r\nSubject: {asunto}\r\nDate: {fecha}\r\nMessage-ID: <{mid}>\r\n\r\n".encode()


with tempfile.TemporaryDirectory() as td:
    conf = os.path.join(td, "correo.json")
    vistos_f = os.path.join(td, "vistos.json")
    conf2 = os.path.join(td, "correo2.json")
    vistos2 = os.path.join(td, "vistos2.json")

    # Lectura: solo cabeceras, PEEK, select de solo lectura, sin store, logout, timeout 20.
    CFG["imap.a.test"] = {"unseen": [1, 2], "cab": {"1": cab("m1", "Hola"), "2": cab("m2", "=?utf-8?q?Canci=C3=B3n?=")}}
    r = kc.revisar_cuenta({"servidor": "imap.a.test", "puerto": 993, "usuario": "u", "clave": "k"}, conectar=fab)
    ins = INSTANCIAS[-1]
    partes = [a[1] for n, a, k in ins.llamadas if n == "fetch"]
    ver("select solo lectura", ("select", ("INBOX",), {"readonly": True}) in ins.llamadas)
    ver("PEEK sin cuerpo", len(partes) == 2 and all("BODY.PEEK" in p and "RFC822" not in p and "BODY[]" not in p for p in partes))
    ver("nunca store", not any(n == "store" for n, _, _ in ins.llamadas))
    ver("logout normal", any(n == "logout" for n, _, _ in ins.llamadas))
    ver("timeout 20", ins.timeout == 20)
    ver("no leidos 2", r["no_leidos"] == 2 and len(r["mensajes"]) == 2)
    ver("mas nuevo primero", r["mensajes"][0]["id"] == "<m2>" and r["mensajes"][1]["asunto"] == "Hola")
    ver("MIME decodifica", r["mensajes"][0]["asunto"] == "Canción")
    ver("de y fecha", r["mensajes"][0]["de"] == "Ana <ana@ejemplo.com>" and "2 Nov 2026" in r["mensajes"][0]["fecha"])

    # Error: logout igual, y el tipo de error sale a quien llama.
    CFG["imap.b.test"] = {"unseen": [], "cab": {}, "falla_search": True}
    try:
        kc.revisar_cuenta({"servidor": "imap.b.test", "puerto": 993, "usuario": "u", "clave": "k"}, conectar=fab)
        ver("error propaga", False)
    except imaplib.IMAP4.error:
        ver("error propaga", True)
    ver("logout con error", any(n == "logout" for n, _, _ in INSTANCIAS[-1].llamadas))

    # Cuentas: vista sin clave, clave vacia conserva, presets, id automatico.
    kc.guardar_cuenta({"id": "c1", "nombre": "Gmail mio", "preset": "gmail", "usuario": "yo@gmail.com",
                       "clave": "CLAVE_SECRETA", "activo": True}, conf)
    v = kc.vista_publica(conf)
    ver("vista sin clave", "CLAVE_SECRETA" not in json.dumps(v) and all("clave" not in x for x in v) and v[0]["configurada"] is True)
    ver("preset gmail", kc.leer_conf(conf)["cuentas"][0]["servidor"] == "imap.gmail.com" and kc.leer_conf(conf)["cuentas"][0]["puerto"] == 993)
    kc.guardar_cuenta({"id": "c1", "clave": "", "nombre": "Gmail nuevo"}, conf)
    cta = kc.leer_conf(conf)["cuentas"][0]
    ver("clave vacia conserva", cta["clave"] == "CLAVE_SECRETA" and cta["nombre"] == "Gmail nuevo" and cta["usuario"] == "yo@gmail.com")
    for pid, (srv, pt) in kc.PRESETS.items():
        kc.guardar_cuenta({"id": "p-" + pid, "preset": pid, "usuario": "x", "clave": "y"}, conf)
        ver("preset " + pid, any(c["id"] == "p-" + pid and c["servidor"] == srv and c["puerto"] == pt for c in kc.leer_conf(conf)["cuentas"]))
    nueva = kc.guardar_cuenta({"servidor": "imap.propio.test", "puerto": 1143, "usuario": "z", "clave": "w"}, conf)
    ver("id automatico y puerto propio", any(x.get("servidor") == "imap.propio.test" and x["puerto"] == 1143 and x["id"] for x in nueva))
    try:
        kc.guardar_cuenta({"id": "malo", "usuario": "x", "clave": "y"}, conf)
        ver("sin servidor falla", False)
    except ValueError:
        ver("sin servidor falla", True)
    try:
        kc.guardar_cuenta({"id": "malo2", "servidor": "imap.x.test", "puerto": 70000}, conf)
        ver("puerto fuera de rango falla", False)
    except ValueError:
        ver("puerto fuera de rango falla", True)
    kc.quitar_cuenta("c1", conf)
    ver("quitar", not any(c["id"] == "c1" for c in kc.leer_conf(conf)["cuentas"]))

    # Decodificar nunca lanza.
    ver("decodificar nulo", kc.decodificar(None) == "")
    ver("decodificar sin saltos", kc.decodificar("a\r\nb") == "a b")

    # nuevos (funcion pura): primera vez silenciosa, despues avisa, tope de 300.
    sal, v = kc.nuevos("c1", [{"id": "a"}, {"id": "b"}], {})
    ver("primera vez silencio", sal == [] and v["c1"] == ["a", "b"])
    sal, v = kc.nuevos("c1", [{"id": "c"}, {"id": "a"}, {"id": "b"}], v)
    ver("mensaje nuevo dispara", [m["id"] for m in sal] == ["c"])
    sal, v = kc.nuevos("c2", [{"id": f"x{i}"} for i in range(400)], {})
    ver("tope 300 en primera vez", sal == [] and len(v["c2"]) == 300)
    sal, v = kc.nuevos("c2", [{"id": f"y{i}"} for i in range(350)], v)
    ver("tope 300 despues", len(sal) == 350 and len(v["c2"]) == 300)

    # revisar_todas: primera ronda silenciosa, la siguiente avisa una vez.
    kc.guardar_cuenta({"id": "cA", "nombre": "Cuenta A", "servidor": "imap.c.test", "usuario": "u", "clave": "k", "activo": True}, conf2)
    CFG["imap.c.test"] = {"unseen": [], "cab": {}}
    avisos = []
    kc.revisar_todas(lambda n, m: avisos.append((n, m)), conf_ruta=conf2, vistos_ruta=vistos2, conectar=fab)
    ver("primera ronda silencio", avisos == [] and os.path.exists(vistos2))
    CFG["imap.c.test"] = {"unseen": [1], "cab": {"1": cab("n1", "Nuevo correo")}}
    kc.revisar_todas(lambda n, m: avisos.append((n, m)), conf_ruta=conf2, vistos_ruta=vistos2, conectar=fab)
    ver("nuevo avisa una vez", len(avisos) == 1 and avisos[0][0] == "Cuenta A" and avisos[0][1]["asunto"] == "Nuevo correo")
    kc.revisar_todas(lambda n, m: avisos.append((n, m)), conf_ruta=conf2, vistos_ruta=vistos2, conectar=fab)
    ver("no repite", len(avisos) == 1)

    # Una cuenta falla y no frena a la otra; el error no lleva clave ni usuario.
    conf3 = os.path.join(td, "correo3.json")
    vistos3 = os.path.join(td, "vistos3.json")
    kc.guardar_cuenta({"id": "malA", "nombre": "Mala", "servidor": "imap.bad.test", "usuario": "usuarioSECRETO",
                       "clave": "PASSWORD_SECRETO", "activo": True}, conf3)
    kc.guardar_cuenta({"id": "okB", "nombre": "Buena", "servidor": "imap.ok.test", "usuario": "u",
                       "clave": "k", "activo": True}, conf3)
    CFG["imap.bad.test"] = {"unseen": [], "cab": {}, "falla_login": True}
    CFG["imap.ok.test"] = {"unseen": [], "cab": {}}
    LOGS.clear()
    avisos3 = []
    kc.revisar_todas(lambda n, m: avisos3.append((n, m)), conf_ruta=conf3, vistos_ruta=vistos3, conectar=fab)
    CFG["imap.ok.test"] = {"unseen": [1], "cab": {"1": cab("o1", "Para la buena")}}
    kc.revisar_todas(lambda n, m: avisos3.append((n, m)), conf_ruta=conf3, vistos_ruta=vistos3, conectar=fab)
    ver("falla no frena la otra", len(avisos3) == 1 and avisos3[0][0] == "Buena")
    ver("error solo tipo", kc.RESUMEN["malA"]["error"] == "error" and kc.RESUMEN["okB"]["error"] is None)
    texto = json.dumps(kc.RESUMEN) + " ".join(LOGS)
    ver("sin clave ni usuario en errores", "PASSWORD_SECRETO" not in texto and "usuarioSECRETO" not in texto)
    ver("log del fallo", any("correo: error" == l for l in LOGS))

    # Maximo 5 avisos por cuenta y ronda.
    conf4 = os.path.join(td, "correo4.json")
    vistos4 = os.path.join(td, "vistos4.json")
    kc.guardar_cuenta({"id": "cD", "nombre": "Cuenta D", "servidor": "imap.d.test", "usuario": "u", "clave": "k", "activo": True}, conf4)
    CFG["imap.d.test"] = {"unseen": [], "cab": {}}
    kc.revisar_todas(lambda n, m: None, conf_ruta=conf4, vistos_ruta=vistos4, conectar=fab)
    CFG["imap.d.test"] = {"unseen": list(range(1, 9)), "cab": {str(i): cab(f"d{i}", f"Correo {i}") for i in range(1, 9)}}
    avisos4 = []
    kc.revisar_todas(lambda n, m: avisos4.append(m), conf_ruta=conf4, vistos_ruta=vistos4, conectar=fab)
    ver("maximo 5 por ronda", len(avisos4) == 5)

    # Archivo de cuentas roto o faltante = sin cuentas.
    roto = os.path.join(td, "roto.json")
    open(roto, "w", encoding="utf-8").write("{roto")
    ver("conf rota = vacia", kc.leer_conf(roto) == {"cuentas": []})
    ver("conf faltante = vacia", kc.leer_conf(os.path.join(td, "no.json")) == {"cuentas": []})

    # Ninguna prueba toca el estado real ni hizo store.
    ver("ningun store en todo", not any(n == "store" for i in INSTANCIAS for n, _, _ in i.llamadas))

print(f"{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
