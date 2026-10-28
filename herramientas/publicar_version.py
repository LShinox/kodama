# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(21-oct-2026) Arma una version del Companero para subir como "release" al repo publico de GitHub.

  python herramientas\\publicar_version.py --clave-nueva     -> UNA sola vez: crea la clave de firma (privada en
                                                               ~\\.credentials\\companero-firma.pem, NUNCA se sube) y
                                                               escribe clave_publica.txt (esa SI va con el programa)
  python herramientas\\publicar_version.py 0.9.1 [--notas "texto"]
                                                            -> escribe VERSION, arma dist\\kodama-0.9.1.zip y
                                                               dist\\kodama-0.9.1.json (sha256 + firma)
  python herramientas\\publicar_version.py 0.9.1 --mac <ruta\\al\\binario\\kodama> [--notas "texto"]
                                                            -> (Mac-F3, 28-oct) el paquete de macOS: dist\\kodama-0.9.1-macos.zip y
                                                               dist\\kodama-0.9.1-macos.json, firmados con la MISMA clave local y
                                                               el mismo formato. Lleva los mismos archivos de Python y web, mas
                                                               arrancar_mac.py y el binario universal de la mascota (el que arma
                                                               CI, artefacto `kodama-macos-universal`) en el lugar que espera el
                                                               programa, SIN kodama.exe. Se sube al MISMO release que el de
                                                               Windows. Ver herramientas\\LEEME-mac.md.

Despues: en GitHub crear el release `v0.9.1` y adjuntar ESOS DOS archivos (el texto del release = las notas).
Va una LISTA BLANCA de archivos: nada de estado\\, claves, respaldos, pruebas ni cosas de la PC de LShinox.
"""
import base64
import fnmatch
import hashlib
import json
import os
import struct
import sys
import time
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
# (Mac-F3) el paquete de macOS: sin kodama.exe, con el lanzador de macOS y el binario universal de la mascota
MAC_BINARIO = "escritorio-tauri/src-tauri/target/release/kodama"
MAC_EXTRA = ["arrancar_mac.py"]
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


def archivos(mac=False):
    incluir = [p for p in INCLUIR if not (mac and p.endswith(".exe"))] + (MAC_EXTRA if mac else [])
    out = []
    for raiz, dirs, fs in os.walk(APP):
        rel_raiz = os.path.relpath(raiz, APP).replace("\\", "/")
        dirs[:] = [d for d in dirs if d not in ("estado", "respaldos", "ts", ".venv", ".claude", "dist", "__pycache__",
                                                "node_modules", "pruebas", "herramientas", "paso0", "medidor", "animacion")]
        for f in fs:
            rel = f if rel_raiz == "." else f"{rel_raiz}/{f}"
            if any(fnmatch.fnmatch(rel, p) for p in incluir) and not any(fnmatch.fnmatch(rel, p) for p in EXCLUIR):
                out.append(rel)
    return sorted(out)


def validar_binario_mac(ruta):
    """(Mac-F3) El binario de la mascota para macOS debe ser un ejecutable Mach-O UNIVERSAL (x86_64 + arm64). Devuelve un
    texto de error, o None si esta bien."""
    if not os.path.isfile(ruta) or os.path.getsize(ruta) < 1024:
        return f"{ruta} no existe o es demasiado chico para ser el binario de la mascota."
    with open(ruta, "rb") as f:
        cab = f.read(8)
        if cab[:4] != b"\xca\xfe\xba\xbe":
            return ("El binario no es universal (Mach-O 'fat'). Baja el artefacto `kodama-macos-universal` del workflow "
                    "Release macOS de GitHub Actions (ver herramientas\\LEEME-mac.md).")
        n = struct.unpack(">I", cab[4:8])[0]
        if not 1 <= n <= 8:
            return "Cabecera 'fat' invalida: no parece un binario de macOS."
        tipos = {struct.unpack(">I", f.read(20)[:4])[0] for _ in range(n)}
    if not {0x01000007, 0x0100000C} <= tipos:   # x86_64 y arm64
        return "El binario universal no trae las dos arquitecturas (x86_64 y arm64)."
    return None


def publicar(version, notas, mac=None, privada=PRIVADA, publica=PUBLICA, dist=DIST, reemplazos=None, escribir_version=True,
             validar=True):
    """Arma dist/kodama-<version>.zip + .json (o, con `mac` = ruta del binario, dist/kodama-<version>-macos.zip + .json).
    Los demas parametros son para las pruebas de CI (clave de prueba, carpeta de salida, contenido sustituido de
    clave_publica.txt/VERSION); la clave REAL nunca se usa fuera de la PC de LShinox."""
    from cryptography.hazmat.primitives import serialization
    if not os.path.exists(privada) or not os.path.exists(publica):
        sys.exit("Falta la clave de firma: corre primero --clave-nueva")
    if mac and validar:
        error = validar_binario_mac(mac)
        if error:
            sys.exit(error)
    if escribir_version:
        open(os.path.join(APP, "VERSION"), "w", encoding="utf-8").write(version + "\n")
    lista = archivos(mac=bool(mac))
    for imprescindible in ("companero_hub.py", "arrancar.pyw", "clave_publica.txt", "VERSION") + (("arrancar_mac.py",) if mac else ()):
        if imprescindible not in lista:
            sys.exit(f"Falta {imprescindible} en el paquete: no publico.")
    reemplazos = reemplazos or {}
    os.makedirs(dist, exist_ok=True)
    sufijo = "-macos" if mac else ""
    ruta = os.path.join(dist, f"kodama-{version}{sufijo}.zip")
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in lista:
            if rel in reemplazos:
                z.writestr(rel, reemplazos[rel])
            else:
                z.write(os.path.join(APP, rel), rel)
        if mac:   # el zip guarda el permiso de ejecucion del binario (el instalador ademas se lo pone)
            zi = zipfile.ZipInfo(MAC_BINARIO, date_time=time.localtime()[:6])
            zi.create_system = 3
            zi.external_attr = 0o100755 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(mac, "rb").read())
            lista = lista + [MAC_BINARIO]
    h = hashlib.sha256(open(ruta, "rb").read()).hexdigest()
    k = serialization.load_pem_private_key(open(privada, "rb").read(), password=None)
    man = {"version": version, "sha256": h, "firma": base64.b64encode(k.sign(h.encode())).decode(), "notas": notas}
    json.dump(man, open(os.path.join(dist, f"kodama-{version}{sufijo}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Listo: dist\\kodama-{version}{sufijo}.zip ({os.path.getsize(ruta) // 1024} KB, {len(lista)} archivos) y "
          f"dist\\kodama-{version}{sufijo}.json. Crear el release v{version} en GitHub y adjuntar los dos"
          + (" (junto con los de Windows, en el MISMO release)." if mac else "."))
    for rel in lista:
        print("  ", rel)
    return ruta


if __name__ == "__main__":
    if "--clave-nueva" in sys.argv:
        clave_nueva()
    elif len(sys.argv) > 1 and sys.argv[1][0].isdigit():
        n = sys.argv[sys.argv.index("--notas") + 1] if "--notas" in sys.argv else ""
        if "--mac" in sys.argv:
            if sys.argv.index("--mac") + 1 >= len(sys.argv):
                sys.exit("--mac necesita la ruta del binario kodama (ver herramientas\\LEEME-mac.md)")
            publicar(sys.argv[1], n, mac=sys.argv[sys.argv.index("--mac") + 1])
        else:
            publicar(sys.argv[1], n)
    else:
        print(__doc__)
