# Publicar la version de macOS (Mac-F3)

El binario de la mascota para macOS se compila en GitHub Actions (no hay un Mac para compilarlo aqui). La FIRMA del paquete se hace
siempre en la PC de LShinox con la clave local (`~\.credentials\companero-firma.pem`): esa clave no sale de la PC y CI no la tiene.

## Pasos (cada release)

1. **Compilar el binario universal.** En github.com/LShinox/kodama > pestana **Actions** > workflow **Release macOS (universal binary)** >
   **Run workflow** (rama `main`). Tarda unos 10-20 minutos. No firma ni publica nada.
2. **Bajar el artefacto.** Abre la corrida terminada, baja a **Artifacts** y descarga **`kodama-macos-universal`** (hay que tener la
   sesion de GitHub iniciada). Es un `.zip` con un solo archivo, `kodama`: descomprimelo.
3. **Armar los paquetes en la PC** (usa el python del `.venv`; ejemplo para la version 1.1.0):
   ```
   cd <carpeta del programa>
   $env:PYTHONUTF8 = 1
   .venv\Scripts\python.exe herramientas\publicar_version.py 1.1.0 --notas "texto"
   .venv\Scripts\python.exe herramientas\publicar_version.py 1.1.0 --mac C:\ruta\a\kodama --notas "texto"
   ```
   La primera linea arma el paquete de Windows (`dist\kodama-1.1.0.zip` + `.json`, como siempre). La segunda arma el de macOS:
   `dist\kodama-1.1.0-macos.zip` + `dist\kodama-1.1.0-macos.json`, firmados con la MISMA clave y el mismo formato
   (`{version, sha256, firma, notas}`). Lleva los mismos archivos de Python y web, mas `arrancar_mac.py` y el binario `kodama`
   (en `escritorio-tauri/src-tauri/target/release/kodama`, con permiso de ejecucion), y NO lleva `kodama.exe`. El script rechaza un
   binario que no sea universal (x86_64 + arm64).
4. **Crear el release `v1.1.0` en GitHub** y adjuntar los CUATRO archivos (los dos de Windows y los dos de macOS) en el MISMO release.
   Los dos instaladores leen `releases/latest`: si un release trae solo un par, el instalador del otro sistema dice que la version no
   trae sus archivos. Las notas del release = las notas.
5. Despues de publicar, probar `instalar.sh` en un Mac (abajo) antes de anunciar nada.

## Probar el paquete en un Mac ANTES de publicarlo

Copia a una carpeta del Mac `kodama-1.1.0-macos.zip`, `kodama-1.1.0-macos.json` y `clave_publica.txt` (la del repo), y corre:

```
KODAMA_ORIGEN_PRUEBA=/ruta/a/la/carpeta bash instalar.sh -Acepto -Si
```

`KODAMA_ORIGEN_PRUEBA` es SOLO para pruebas (CI la usa): salta la descarga de GitHub, pero la firma se verifica igual.

## Lo que ya prueba CI

`pruebas/probar_instalador_mac.py` (job "macOS installer" de `ci.yml`, en `macos-latest`, con un HOME falso y `--sin-launchctl`) arma
un paquete de prueba con una clave desechable y comprueba: sha256 y firma malos rechazados, instalacion completa (`~/Kodama`, venv,
hooks, statusLine encadenada, Codex/Antigravity, plist), reinstalar sin duplicar, y `--quitar`. NO prueba: `launchctl` de verdad, el
binario de la mascota corriendo, Gatekeeper ni nada que necesite una pantalla.

## Pendiente de un Mac real

La mascota (ventana transparente, clic que atraviesa, bandeja, arrastrar archivos), `launchctl bootstrap` del LaunchAgent, el permiso de
Automatizacion, el binario sin firmar/notarizar (Gatekeeper), la ruta de las sesiones de la app de Claude y la actualizacion (en macOS es
manual: volver a correr `instalar.sh`).

## Modo isla (muesca)

En macOS la mascota puede vivir en la muesca del MacBook, como una Dynamic Island. `estado/escritorio.json` -> `"isla": "auto" | "si" | "no"`
(por defecto `auto`: isla solo si la pantalla tiene muesca; `si`: siempre, y sin muesca es una pastilla justo debajo de la barra de menus; `no`:
la mascota de siempre). Tambien en Ajustes > "Modo isla (muesca)". Cerrada es una pastilla negra pegada a la muesca (gato a un lado, punto de
estado o numero de chats al otro); cuando un chat te necesita crece hacia abajo con el aviso / el globo / Ajustes y vuelve a cerrarse sola.
Rust (`isla.rs`): muesca = `safeAreaInsets.top > 0` + `auxiliaryTopLeftArea/RightArea`, ventana por encima de la barra de menus
(mainMenu + 3) y en todos los Spaces. Pruebas: `KODAMA_ISLA_MUESCA_PRUEBA=190x32` simula una muesca (solo CI).
El workflow `capturas-mac.yml` saca capturas (`screencapture -x`) con un hub falso y las sube como el artefacto `capturas-mac` (7 dias); si el
runner no deja capturar ventanas de apps (TCC), el resumen del job lo dice. Windows no cambia nada de esto.
