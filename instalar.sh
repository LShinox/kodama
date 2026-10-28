#!/usr/bin/env bash
# (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENCIA.txt.
#
# Kodama one-line installer for macOS (beta). Mirror of instalar.ps1 (Windows).
#
#   A person, in Terminal:       curl -fsSL https://raw.githubusercontent.com/LShinox/kodama/main/instalar.sh | bash
#   Their Claude runs it with:   curl -fsSL .../instalar.sh | bash -s -- -Acepto -Si     (after showing them the license in the chat)
#
# Flags (same names as instalar.ps1):  -Acepto  license accepted in the chat      -Si  answer "yes" to the questions
#                                      -SoloClaude  do not touch Codex/Antigravity
#                                      -Destino <dir> (default ~/Kodama)   -Repo <owner/name> (default LShinox/kodama)
#                                      --sin-launchctl  TEST ONLY: write the LaunchAgent plist but do not load it or launch anything
#
# What it does: checks macOS and the CPU, finds Python 3.10+ (if missing: with Homebrew it ASKS before `brew install python@3.12`;
# without Homebrew it tells you how to get it from python.org and stops), downloads the latest signed macOS package from GitHub
# (kodama-<ver>-macos.zip + .json), checks its sha256, unzips it into ~/Kodama, creates the venv, installs requirements.txt and
# runs instalar.py, which VERIFIES THE SIGNATURE (Ed25519, clave_publica.txt) before it touches ~/.claude/settings.json.
# A package whose sha256 or signature does not match is never installed.
#
# Gatekeeper: files downloaded with curl carry no com.apple.quarantine attribute, so macOS does not block Kodama's binary
# (it is not notarized yet). If the attribute is present anyway (e.g. the zip came from a browser), this script removes it from
# Kodama's own binary only (xattr -d), never from anything else.
#
# TEST ONLY (used by CI, never set it yourself): KODAMA_ORIGEN_PRUEBA=<dir> makes the script take kodama-<ver>-macos.zip,
# kodama-<ver>-macos.json and clave_publica.txt from that LOCAL directory instead of GitHub. The signature is still verified.
#
# Written for bash 3.2 (the one macOS ships): no associative arrays, no ${var,,}. Everything runs inside main(), called on the
# last line, so a truncated download never executes half a script.
set -eu
set -o pipefail

# ---------------------------------------------------------------- language: English by default, Spanish if macOS is in Spanish
L=en
detectar_idioma() {
  local l="${KODAMA_IDIOMA:-}"   # es | en: forces the language (CI uses it)
  if [ -z "$l" ] && command -v defaults >/dev/null 2>&1; then
    l=$(defaults read -g AppleLanguages 2>/dev/null | sed -n 2p | tr -d ' ",' || true)
  fi
  [ -n "$l" ] || l="${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}"
  case "$l" in es*|ES*) L=es ;; esac
}

_m() { printf '%b' "$1"; }   # the text as is: %s stays for tf(); backslash-n becomes a newline
t() {
  case "$1:$L" in
    titulo:es) _m 'Kodama - instalacion (macOS, beta)' ;;
    titulo:en) _m 'Kodama - installation (macOS, beta)' ;;
    soloMac:es) _m 'Este instalador es para macOS. En Windows usa instalar.ps1.' ;;
    soloMac:en) _m 'This installer is for macOS. On Windows use instalar.ps1.' ;;
    arqRara:es) _m 'Arquitectura no soportada: %s (hace falta arm64 o x86_64).' ;;
    arqRara:en) _m 'Unsupported architecture: %s (arm64 or x86_64 required).' ;;
    sinClaude:es) _m 'No encuentro la app de escritorio de Claude. Kodama funciona con ella (pestana Code): instalala primero.' ;;
    sinClaude:en) _m 'Could not find the Claude desktop app. Kodama works with it (Code tab): install it first.' ;;
    pidePython:es) _m 'Falta Python 3.10 o mas nuevo. Lo instalo con Homebrew (brew install python@3.12, ~30 MB)?' ;;
    pidePython:en) _m 'Python 3.10 or newer is missing. Install it with Homebrew (brew install python@3.12, ~30 MB)?' ;;
    pyOrg:es) _m 'Falta Python 3.10 o mas nuevo y no encuentro Homebrew.\n  1. Instala Python 3.12 desde https://www.python.org/downloads/macos/\n  2. Abre una Terminal nueva y vuelve a correr este comando.' ;;
    pyOrg:en) _m 'Python 3.10 or newer is missing and Homebrew was not found.\n  1. Install Python 3.12 from https://www.python.org/downloads/macos/\n  2. Open a NEW Terminal window and run this command again.' ;;
    sinPython:es) _m 'Sin Python no se puede instalar.' ;;
    sinPython:en) _m 'Cannot install without Python.' ;;
    pyFallo:es) _m 'Homebrew termino pero no encuentro Python 3.10+. Abre una Terminal nueva y vuelve a correr este comando.' ;;
    pyFallo:en) _m 'Homebrew finished but Python 3.10+ was not found. Open a new Terminal window and run this command again.' ;;
    buscando:es) _m 'Buscando la ultima version en github.com/%s' ;;
    buscando:en) _m 'Looking for the latest version at github.com/%s' ;;
    faltanArch:es) _m 'La version %s no trae sus archivos de macOS (kodama-%s-macos.zip y .json).' ;;
    faltanArch:en) _m 'Version %s does not include its macOS files (kodama-%s-macos.zip and .json).' ;;
    huella:es) _m 'El archivo bajado no coincide con su huella (sha256): no se instala nada.' ;;
    huella:en) _m 'The downloaded file does not match its checksum (sha256): nothing was installed.' ;;
    claveDist:es) _m 'La clave publica del paquete no coincide con la del repositorio: no se instala nada.' ;;
    claveDist:en) _m 'The package public key does not match the repository key: nothing was installed.' ;;
    bajada:es) _m 'Version %s bajada y comprobada' ;;
    bajada:en) _m 'Version %s downloaded and verified' ;;
    copiado:es) _m 'Copiado en %s' ;;
    copiado:en) _m 'Copied to %s' ;;
    sinTty:es) _m 'No hay terminal para pedirte la licencia. Corre: curl -fsSL URL | bash -s -- -Acepto -Si   (despues de leer la licencia).' ;;
    sinTty:en) _m 'No terminal to ask for the license. Run: curl -fsSL URL | bash -s -- -Acepto -Si   (after reading the license).' ;;
    modoPrueba:es) _m 'MODO PRUEBA (KODAMA_ORIGEN_PRUEBA): el paquete sale de una carpeta local, no de GitHub.' ;;
    modoPrueba:en) _m 'TEST MODE (KODAMA_ORIGEN_PRUEBA): the package comes from a local folder, not from GitHub.' ;;
    cuarentena:es) _m 'Atributo de cuarentena quitado del binario de Kodama (solo de ese archivo).' ;;
    cuarentena:en) _m "Quarantine attribute removed from Kodama's binary (that file only)." ;;
    siAuto:es) _m '(si)' ;;
    siAuto:en) _m '(yes)' ;;
    sn:es) _m '[s/N]' ;;
    sn:en) _m '[y/N]' ;;
    *) printf '%s' "$1" ;;
  esac
}
tf() { local k="$1"; shift; local f; f=$(t "$k"); printf "$f" "$@"; }   # t() whose text takes printf arguments

paso() { printf '\033[36m-> %s\033[0m\n' "$1"; }
aviso() { printf '\033[33mWARNING: %s\033[0m\n' "$1" >&2; }
die() { printf '\033[31m%s\033[0m\n' "$1" >&2; exit 1; }

SI=0
tiene_tty() { { : </dev/tty; } 2>/dev/null; }
pregunta() {   # $1 = text. With -Si: yes. Otherwise it asks on the terminal (stdin is the script itself under `curl | bash`).
  if [ "$SI" = 1 ]; then printf '%s %s\n' "$1" "$(t siAuto)"; return 0; fi
  if tiene_tty; then
    printf '%s %s ' "$1" "$(t sn)" >/dev/tty
    local r=""
    read -r r </dev/tty || r=""
    case "$r" in s|S|si|SI|Si|y|Y|yes|YES|Yes) return 0 ;; esac
  fi
  return 1
}

# Python >= 3.10 that can build a venv
py_ok() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 \
    && "$1" -c 'import venv, ensurepip' >/dev/null 2>&1
}
PY=""
buscar_python() {
  local c p
  for c in python3.13 python3.12 python3.11 python3.10 python3 python \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    # /usr/bin/python3 is Apple's stub: without the Command Line Tools, running it pops up an installer dialog. Do not run it then.
    if [ "$p" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
    if py_ok "$p"; then PY="$p"; return 0; fi
  done
  return 1
}

leer_json() {   # $1 = json file, $2 = key -> prints the value of a top-level string key (empty if missing)
  "$PY" -c 'import json,sys; v=json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2], ""); print(v if isinstance(v, str) else "")' "$1" "$2"
}

TMP=""
limpiar() { if [ -n "$TMP" ] && [ -d "$TMP" ]; then rm -rf "$TMP"; fi; }

main() {
  local REPO="LShinox/kodama"
  local DESTINO="$HOME/Kodama"
  local ACEPTO=0 SOLO_CLAUDE=0 SIN_LAUNCHCTL=0
  while [ $# -gt 0 ]; do
    case "$1" in
      -Acepto|--acepto|-acepto) ACEPTO=1 ;;
      -Si|--si|-si|-Yes|--yes|-yes) SI=1 ;;
      -SoloClaude|--solo-claude|-soloclaude) SOLO_CLAUDE=1 ;;
      --sin-launchctl) SIN_LAUNCHCTL=1 ;;
      -Destino|--destino|-destino) [ $# -ge 2 ] || die "$1 needs a value"; DESTINO="$2"; shift ;;
      -Repo|--repo|-repo) [ $# -ge 2 ] || die "$1 needs a value"; REPO="$2"; shift ;;
      -h|--help) sed -n '2,28p' "$0" 2>/dev/null || true; exit 0 ;;
      *) die "Unknown option: $1" ;;
    esac
    shift
  done
  trap limpiar EXIT
  detectar_idioma
  printf '\033[32m%s\033[0m\n' "$(t titulo)"

  # ------------------------------------------------------------ 0. macOS and architecture
  [ "$(uname -s)" = "Darwin" ] || die "$(t soloMac)"
  local ARQ
  ARQ=$(uname -m)
  case "$ARQ" in arm64|x86_64) ;; *) die "$(tf arqRara "$ARQ")" ;; esac
  paso "macOS $(sw_vers -productVersion 2>/dev/null || echo '?') ($ARQ)"
  if [ ! -d "/Applications/Claude.app" ] && [ ! -d "$HOME/Applications/Claude.app" ]; then
    aviso "$(t sinClaude)"
  fi

  # ------------------------------------------------------------ 1. Python 3.10+
  if ! buscar_python; then
    local BREW="" b _pref
    for b in "$(command -v brew 2>/dev/null || true)" /opt/homebrew/bin/brew /usr/local/bin/brew; do
      if [ -n "$b" ] && [ -x "$b" ]; then BREW="$b"; break; fi
    done
    if [ -z "$BREW" ]; then die "$(t pyOrg)"; fi
    pregunta "$(t pidePython)" || die "$(t sinPython)"
    "$BREW" install python@3.12 </dev/null
    _pref=$("$BREW" --prefix python@3.12 2>/dev/null || true)
    if [ -n "$_pref" ] && [ -x "$_pref/bin/python3.12" ] && py_ok "$_pref/bin/python3.12"; then
      PY="$_pref/bin/python3.12"
    elif ! buscar_python; then
      die "$(t pyFallo)"
    fi
  fi
  paso "Python: $("$PY" --version 2>&1)"

  # ------------------------------------------------------------ 2. Latest signed package
  TMP=$(mktemp -d "${TMPDIR:-/tmp}/kodama-XXXXXX")
  local VER ORIGEN="${KODAMA_ORIGEN_PRUEBA:-}"
  if [ -n "$ORIGEN" ]; then
    aviso "$(t modoPrueba)"
    [ -d "$ORIGEN" ] || die "KODAMA_ORIGEN_PRUEBA: $ORIGEN is not a directory"
    local n=0 f jf=""
    for f in "$ORIGEN"/kodama-*-macos.json; do
      [ -f "$f" ] || continue
      n=$((n + 1)); jf="$f"
    done
    [ "$n" = 1 ] || die "KODAMA_ORIGEN_PRUEBA: expected exactly one kodama-<ver>-macos.json in $ORIGEN"
    VER=$(basename "$jf" .json); VER=${VER#kodama-}; VER=${VER%-macos}
    cp "$ORIGEN/kodama-$VER-macos.zip" "$TMP/kodama-$VER-macos.zip"
    cp "$jf" "$TMP/kodama-$VER-macos.json"
    cp "$ORIGEN/clave_publica.txt" "$TMP/clave_publica_repo.txt"
  else
    paso "$(tf buscando "$REPO")"
    curl -fsSL --retry 3 -H 'User-Agent: Kodama-instalador' -o "$TMP/release.json" "https://api.github.com/repos/$REPO/releases/latest" \
      || die "Could not reach api.github.com"
    local info TAG URL_ZIP URL_JSON
    info=$("$PY" -c '
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
tag = r.get("tag_name") or ""
ver = tag.lstrip("vV")
a = {x.get("name"): x.get("browser_download_url") for x in r.get("assets") or []}
print(tag); print(ver); print(a.get("kodama-%s-macos.zip" % ver) or ""); print(a.get("kodama-%s-macos.json" % ver) or "")
' "$TMP/release.json")
    TAG=$(printf '%s\n' "$info" | sed -n 1p)
    VER=$(printf '%s\n' "$info" | sed -n 2p)
    URL_ZIP=$(printf '%s\n' "$info" | sed -n 3p)
    URL_JSON=$(printf '%s\n' "$info" | sed -n 4p)
    case "$VER" in ""|*[!0-9A-Za-z._-]*) die "Unexpected release version: $VER" ;; esac
    case "$TAG" in *[!0-9A-Za-z._-]*) die "Unexpected release tag: $TAG" ;; esac
    if [ -z "$URL_ZIP" ] || [ -z "$URL_JSON" ]; then die "$(tf faltanArch "$VER" "$VER")"; fi
    case "$URL_ZIP" in https://github.com/*) ;; *) die "Unexpected download URL" ;; esac
    case "$URL_JSON" in https://github.com/*) ;; *) die "Unexpected download URL" ;; esac
    curl -fsSL --retry 3 -o "$TMP/kodama-$VER-macos.zip" "$URL_ZIP"
    curl -fsSL --retry 3 -o "$TMP/kodama-$VER-macos.json" "$URL_JSON"
    # The public key as published in the repository at that tag (compared with the one inside the package below)
    curl -fsSL --retry 3 -o "$TMP/clave_publica_repo.txt" "https://raw.githubusercontent.com/$REPO/$TAG/clave_publica.txt" \
      || die "Could not download clave_publica.txt from the repository"
  fi
  local ZIP="$TMP/kodama-$VER-macos.zip" JSON="$TMP/kodama-$VER-macos.json" SHA SHA_ESPERADA
  SHA=$(shasum -a 256 "$ZIP" | awk '{print $1}')
  SHA_ESPERADA=$(leer_json "$JSON" sha256)
  { [ -n "$SHA_ESPERADA" ] && [ "$SHA" = "$SHA_ESPERADA" ]; } || die "$(t huella)"
  [ "$(leer_json "$JSON" version)" = "$VER" ] || die "$(t huella)"
  # The key inside the package must be the one the repository publishes (instalar.py then checks the Ed25519 signature with it).
  "$PY" -c '
import sys, zipfile
dentro = zipfile.ZipFile(sys.argv[1]).read("clave_publica.txt").decode("utf-8").strip()
fuera = open(sys.argv[2], encoding="utf-8").read().strip()
sys.exit(0 if dentro and dentro == fuera else 1)
' "$ZIP" "$TMP/clave_publica_repo.txt" || die "$(t claveDist)"
  paso "$(tf bajada "$VER")"

  # ------------------------------------------------------------ 3. Unzip (does not touch estado/, config.json or .venv if already installed)
  mkdir -p "$DESTINO"
  /usr/bin/unzip -o -q "$ZIP" -d "$DESTINO"
  mkdir -p "$DESTINO/estado/instalacion"
  rm -f "$DESTINO"/estado/instalacion/kodama-*.zip "$DESTINO"/estado/instalacion/kodama-*.json   # only the package being installed stays, so instalar.py checks THAT one
  cp "$ZIP" "$JSON" "$DESTINO/estado/instalacion/"
  local BIN="$DESTINO/escritorio-tauri/src-tauri/target/release/kodama"
  if [ -f "$BIN" ]; then
    chmod 755 "$BIN"
    if /usr/bin/xattr -p com.apple.quarantine "$BIN" >/dev/null 2>&1; then
      /usr/bin/xattr -d com.apple.quarantine "$BIN" >/dev/null 2>&1 || true
      paso "$(t cuarentena)"
    fi
  fi
  paso "$(tf copiado "$DESTINO")"

  # ------------------------------------------------------------ 4. venv + requirements, then instalar.py (it verifies the signature)
  local VPY="$DESTINO/.venv/bin/python"
  if [ ! -x "$VPY" ]; then "$PY" -m venv "$DESTINO/.venv" </dev/null; fi
  "$VPY" -m pip install --disable-pip-version-check -q -r "$DESTINO/requirements.txt" </dev/null

  local ARGS="" ENTRADA=/dev/null
  if [ "$ACEPTO" = 1 ]; then ARGS="$ARGS --acepto"; fi
  if [ "$SI" = 1 ]; then ARGS="$ARGS --si"; fi
  if [ "$SOLO_CLAUDE" = 1 ]; then ARGS="$ARGS --solo-claude"; fi
  if [ "$SIN_LAUNCHCTL" = 1 ]; then ARGS="$ARGS --sin-launchctl"; fi
  if tiene_tty; then
    ENTRADA=/dev/tty   # instalar.py may ask (license, y/N): the keyboard, not the pipe that carries this script
  elif [ "$ACEPTO" != 1 ]; then
    die "$(t sinTty)"
  fi
  export PYTHONUTF8=1
  cd "$DESTINO"
  # shellcheck disable=SC2086
  "$VPY" "$DESTINO/instalar.py" $ARGS <"$ENTRADA"
}

main "$@"
