# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct) Prepara una copia LIMPIA del repo para correr las pruebas en CI (GitHub Actions, Windows y macOS): crea estado/, un
config.json de prueba (un chat personal en ~/Videos/Ingenieria-inversa) y una sesion de prueba que deja el hook real.
Solo corre con CI=true (GitHub lo pone solo) y NUNCA pisa un config.json que ya exista: no es para tu instalacion."""
import json, os, subprocess, sys

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("CI") != "true":
    sys.exit("preparar_ci.py solo corre en CI (CI=true): no toca instalaciones reales.")
HOME = os.path.expanduser("~")
CARPETA = os.path.join(HOME, "Videos", "Ingenieria-inversa")
os.makedirs(os.path.join(AQUI, "estado"), exist_ok=True)
cfg = os.path.join(AQUI, "config.json")
if os.path.exists(cfg):
    print("config.json ya existe: no se toca")
else:
    json.dump({"raices_personales": [os.path.join(HOME, "Videos")],
               "chats": [{"id": "ci", "nombre": "CI", "carpeta": CARPETA}]}, open(cfg, "w", encoding="utf-8"))
sys.path.insert(0, AQUI)
import config  # noqa: E402  (despues de escribir config.json)
clave = config.clave_carpeta(CARPETA)
ev = {"hook_event_name": "SessionStart", "source": "resume", "session_id": "ci-semilla-0000", "cwd": CARPETA,
      "transcript_path": f"{HOME}/.claude/projects/{clave}/ci-semilla-0000.jsonl"}
subprocess.run([sys.executable, os.path.join(AQUI, "companero_hook.py")], input=json.dumps(ev).encode(), timeout=30, check=True)
print("listo: estado/, config.json de prueba y una sesion de prueba")
