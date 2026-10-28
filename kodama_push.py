# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
"""(28-oct-2026) Notificaciones push de la app web del celular (Web Push con VAPID).

Parte de companero_hub.py, que se dividio en modulos kodama_*.py: el hub quedo solo como el arranque."""
import json
import os
import threading
import time

import config
from kodama_nucleo import BASE, SALUD, SUSC, log


def push_a_todos(titulo, cuerpo, chat, tipo="", n=0, solo=None, intento=0, permiso=None, completo=False):
    """Web Push a la app del iPhone (si la venv tiene pywebpush y hay suscripciones).
    Si una suscripcion falla por red o 5xx, se reintenta SOLO esa a los 1 y 5 min (14-oct)."""
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return
    try:
        subs = json.load(open(SUSC, encoding="utf-8"))
    except Exception:
        return
    vivas, fallidas = [], []
    for s in subs:
        if solo is not None and s.get("endpoint") not in solo:
            vivas.append(s)
            continue
        try:
            datos = {"web_push": 8030,   # formato declarativo de iOS 18.4+ (lo muestra el sistema) + el propio
                     "notification": {"title": titulo, "body": cuerpo, "lang": "es",
                                      "navigate": f"{config.URL_PUBLICA}/#{chat}", "app_badge": str(n)},
                     "titulo": titulo, "cuerpo": cuerpo, "chat": chat, "tipo": tipo, "n": n,
                     "permiso": permiso, "completo": completo}   # (14-oct) Android: botones en el aviso (Si/No, OK/Sigue, Permitir/Denegar)
            webpush(subscription_info=s, data=json.dumps(datos, ensure_ascii=False),
                    vapid_private_key=os.path.join(BASE, "vapid_private.pem"),
                    vapid_claims={"sub": config.URL_PUBLICA or "mailto:companero@localhost"}, ttl=3600)
            vivas.append(s)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            log(f"push error {code}"); SALUD["push_error"] = f"{time.strftime('%H:%M')} {code}"
            if code not in (404, 410):
                vivas.append(s)
                if code is None or code >= 500 or code == 429:
                    fallidas.append(s.get("endpoint"))
        except Exception as e:
            log(f"push error {type(e).__name__}"); SALUD["push_error"] = f"{time.strftime('%H:%M')} {type(e).__name__}"
            vivas.append(s); fallidas.append(s.get("endpoint"))
    if len(vivas) != len(subs):   # escritura atomica (hoja de ruta #10)
        json.dump(vivas, open(SUSC + ".tmp", "w", encoding="utf-8")); os.replace(SUSC + ".tmp", SUSC)
    if fallidas and intento < 2:
        threading.Timer((60, 300)[intento], push_a_todos, args=(titulo, cuerpo, chat, tipo, n),
                        kwargs={"solo": fallidas, "intento": intento + 1, "permiso": permiso, "completo": completo}).start()
