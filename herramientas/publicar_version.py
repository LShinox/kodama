# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(21-oct-2026) Arma una version del Companero para subir como "release" al repo publico de GitHub.

  python herramientas\\publicar_version.py --clave-nueva     -> UNA sola vez: crea la clave de firma (privada en
                                                               ~\\.credentials\\companero-firma.pem, NUNCA se sube) y
                                                               escribe clave_publica.txt (esa SI va con el programa)
  python herramientas\\publicar_version.py 0.9.1 [--notas "texto"]
                                                            -> escribe VERSION, arma dist\\kodama-0.9.1.zip y
                                                               dist\\kodama-0.9.1.json (sha256 + firma)

Despues: en GitHub crear el release `v0.9.1` y adjuntar ESOS DOS archivos (el texto del release = las notas).
Va una LISTA BLANCA de archivos: nada de estado\\, claves, respaldos, pruebas ni cosas de la PC de LShinox.
"""
import base64
import fnmatch
import hashlib
import json
import os
import sys
import zipfile

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVADA = os.path.join(os.path.expanduser("~"), ".credentials", "companero-firma.pem")
PUBLICA = os.path.join(APP, "clave_publica.txt")
DIST = os.path.join(APP, "dist")

INCLUIR = [
    "arrancar.pyw", "companero_*.py", "kodama_*.py", "config.py", "grupos_app.py", "estimador.py", "instalar.py",
    "requirements.txt", "VERSION", "LEEME.md", "LICENCIA.txt", "LICENSE.txt", "clave_publica.txt",
    "web/*.html", "web/*.js", "web/*.json", "web/*.png",
    "escritorio-tauri/src-tauri/target/release/kodama.exe",
]
EXCLUIR = ["*.bak*", "web/opciones.html", "web/maquetas*", "web/bench.html", "web/mascotas-referencia.html",
           "web/ajustes.json",   # ajustes.json es de cada persona (animaciones editadas)
           "web/lottie/muestras/*"]   # (27-oct) muestras de ojos de "atascado": no las usa la app


def clave_nueva():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if os.path.exists(PRIVADA):
        sys.exit(f"Ya existe {PRIVADA}: no la piso (perderla = nadie podria actualizar). Borrala a mano si de verdad querés otra.")
    k = Ed25519PrivateKey.generate()
    os.makedirs(os.path.dirname(PRIVADA), exist_ok=True)
    open(PRIVADA, "wb").write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    open(PUBLICA, "w", encoding="utf-8").write(base64.b64encode(pub).decode() + "\n")
    print("Clave creada. Privada:", PRIVADA, "(respaldala fuera de la PC; NO va a GitHub). Publica:", PUBLICA)


def archivos():
    out = []
    for raiz, dirs, fs in os.walk(APP):
        rel_raiz = os.path.relpath(raiz, APP).replace("\\", "/")
        dirs[:] = [d for d in dirs if d not in ("estado", "respaldos", "ts", ".venv", ".claude", "dist", "__pycache__",
                                                "node_modules", "pruebas", "herramientas", "paso0", "medidor", "animacion")]
        for f in fs:
            rel = f if rel_raiz == "." else f"{rel_raiz}/{f}"
            if any(fnmatch.fnmatch(rel, p) for p in INCLUIR) and not any(fnmatch.fnmatch(rel, p) for p in EXCLUIR):
                out.append(rel)
    return sorted(out)


def publicar(version, notas):
    from cryptography.hazmat.primitives import serialization
    if not os.path.exists(PRIVADA) or not os.path.exists(PUBLICA):
        sys.exit("Falta la clave de firma: corre primero --clave-nueva")
    open(os.path.join(APP, "VERSION"), "w", encoding="utf-8").write(version + "\n")
    lista = archivos()
    for imprescindible in ("companero_hub.py", "arrancar.pyw", "clave_publica.txt", "VERSION"):
        if imprescindible not in lista:
            sys.exit(f"Falta {imprescindible} en el paquete: no publico.")
    os.makedirs(DIST, exist_ok=True)
    ruta = os.path.join(DIST, f"kodama-{version}.zip")
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in lista:
            z.write(os.path.join(APP, rel), rel)
    h = hashlib.sha256(open(ruta, "rb").read()).hexdigest()
    k = serialization.load_pem_private_key(open(PRIVADA, "rb").read(), password=None)
    man = {"version": version, "sha256": h, "firma": base64.b64encode(k.sign(h.encode())).decode(), "notas": notas}
    json.dump(man, open(os.path.join(DIST, f"kodama-{version}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Listo: dist\\kodama-{version}.zip ({os.path.getsize(ruta) // 1024} KB, {len(lista)} archivos) y "
          f"dist\\kodama-{version}.json. Crear el release v{version} en GitHub y adjuntar los dos.")
    for rel in lista:
        print("  ", rel)


if __name__ == "__main__":
    if "--clave-nueva" in sys.argv:
        clave_nueva()
    elif len(sys.argv) > 1 and sys.argv[1][0].isdigit():
        n = sys.argv[sys.argv.index("--notas") + 1] if "--notas" in sys.argv else ""
        publicar(sys.argv[1], n)
    else:
        print(__doc__)
