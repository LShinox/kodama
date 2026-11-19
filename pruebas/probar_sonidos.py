# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(04-nov) Prueba de los sonidos propios (kodama_archivos.sonido_propio / sonidos_disponibles) SIN tocar estado\\:
todo va a carpetas temporales. Uso: python pruebas/probar_sonidos.py  (sale con 1 si algo falla)"""
import os, shutil, sys, tempfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import kodama_archivos as ka  # noqa: E402

mal = []


def ver(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("OK  " if ok else "MAL ") + f"{nombre}: {obtenido!r}" + ("" if ok else f" (esperado {esperado!r})"))
    if not ok:
        mal.append(nombre)


def poner(carpeta, nombre, tam):
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, nombre), "wb") as f:
        f.write(b"x" * tam)


tmp = tempfile.mkdtemp(prefix="kodama-prueba-sonidos-")
try:
    # ---- tipo desconocido, recorrido de ruta y archivo que no existe
    base = os.path.join(tmp, "a")
    poner(base, "aviso.wav", 10)                     # "../aviso" en la carpeta hija apuntaria a este archivo
    hija = os.path.join(base, "hija")
    os.makedirs(hija)
    ver("tipo desconocido", ka.sonido_propio(base, "otro"), None)
    ver("recorrido ../aviso", ka.sonido_propio(hija, "../aviso"), None)
    ver("archivo que falta", ka.sonido_propio(os.path.join(tmp, "vacia"), "error"), None)

    # ---- archivo vacio, de 10 bytes y mp3
    poner(os.path.join(tmp, "vacio"), "aviso.wav", 0)
    ver("archivo vacio", ka.sonido_propio(os.path.join(tmp, "vacio"), "aviso"), None)
    ruta_wav = os.path.join(base, "aviso.wav")
    ver("aviso.wav de 10 bytes", ka.sonido_propio(base, "aviso"), (ruta_wav, "audio/wav"))
    poner(os.path.join(tmp, "mp3"), "aviso.mp3", 10)
    ver("aviso.mp3 solo", ka.sonido_propio(os.path.join(tmp, "mp3"), "aviso"),
        (os.path.join(tmp, "mp3", "aviso.mp3"), "audio/mpeg"))

    # ---- tope de 2 MB: uno de mas no entra, justo el tope si
    poner(os.path.join(tmp, "grande"), "aviso.wav", ka.SONIDO_MAX + 1)
    ver("SONIDO_MAX + 1 bytes", ka.sonido_propio(os.path.join(tmp, "grande"), "aviso"), None)
    poner(os.path.join(tmp, "justo"), "aviso.wav", ka.SONIDO_MAX)
    ver("exactamente SONIDO_MAX", ka.sonido_propio(os.path.join(tmp, "justo"), "aviso"),
        (os.path.join(tmp, "justo", "aviso.wav"), "audio/wav"))

    # ---- extension no permitida
    poner(os.path.join(tmp, "exe"), "aviso.exe", 10)
    ver("aviso.exe", ka.sonido_propio(os.path.join(tmp, "exe"), "aviso"), None)

    # ---- sonidos_disponibles: solo los validos
    mezcla = os.path.join(tmp, "mezcla")
    poner(mezcla, "aviso.wav", 10)
    poner(mezcla, "error.exe", 10)
    poner(mezcla, "enviado.ogg", 5)
    poner(mezcla, "error.mp3", 0)
    disp = ka.sonidos_disponibles(mezcla)
    ver("sonidos_disponibles solo validos", sorted(disp), ["aviso", "enviado"])
    ver("sonidos_disponibles carpeta inexistente", ka.sonidos_disponibles(os.path.join(tmp, "nada")), {})
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if mal:
    print(f"FALLARON {len(mal)}: " + ", ".join(mal))
    sys.exit(1)
print("Todo OK")
