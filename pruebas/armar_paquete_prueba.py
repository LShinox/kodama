# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(Mac-F3, 28-oct) SOLO PRUEBAS / CI: arma un paquete de macOS DE PRUEBA para probar instalar.sh de punta a punta.

    python pruebas/armar_paquete_prueba.py <carpeta_de_salida> [version]

Genera una clave Ed25519 DESECHABLE (en una carpeta temporal que se borra al terminar: la clave privada de prueba no queda
en ningun lado), arma con herramientas/publicar_version.py el mismo zip que armaria el release de macOS (con un "binario"
falso en vez del de la mascota) pero con la clave PUBLICA de prueba dentro, lo firma con la clave de prueba y deja en la
carpeta de salida:  kodama-<version>-macos.zip, kodama-<version>-macos.json y clave_publica.txt (la de prueba).
instalar.sh lo toma de ahi con KODAMA_ORIGEN_PRUEBA=<carpeta>. La clave REAL de firma no se usa ni se lee. Solo corre con
CI=true (GitHub lo pone solo) o con --aunque-no-sea-ci."""
import base64
import os
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("CI") != "true" and "--aunque-no-sea-ci" not in sys.argv:
    sys.exit("armar_paquete_prueba.py solo corre en CI (CI=true) o con --aunque-no-sea-ci: es para pruebas, no para publicar.")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit(__doc__)
salida = os.path.abspath(args[0])
version = args[1] if len(args) > 1 else "0.0.1"

sys.path.insert(0, os.path.join(AQUI, "herramientas"))
import publicar_version as pv  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

tmp = tempfile.mkdtemp(prefix="kodama-clave-prueba-")
try:
    k = Ed25519PrivateKey.generate()
    privada = os.path.join(tmp, "prueba.pem")
    with open(privada, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode() + "\n"
    falso = os.path.join(tmp, "kodama")   # "binario" de la mascota: un script de shell relleno hasta pasar de 1 KB
    with open(falso, "wb") as f:
        f.write(b"#!/bin/sh\n# binario de prueba de Kodama (CI)\n" + b"#" * 2000 + b"\nexit 0\n")
    os.makedirs(salida, exist_ok=True)
    pv.publicar(version, "paquete de prueba (CI)", mac=falso, privada=privada, dist=salida,
                reemplazos={"clave_publica.txt": pub.encode(), "VERSION": (version + "\n").encode()},
                escribir_version=False, validar=False)
    with open(os.path.join(salida, "clave_publica.txt"), "w", encoding="utf-8") as f:
        f.write(pub)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("paquete de prueba en", salida)
