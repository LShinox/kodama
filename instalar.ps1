# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
#  2026 LShinox. Instalador de una sola linea de Kodama (Windows).
#
#   Una persona, en PowerShell:   irm https://raw.githubusercontent.com/LShinox/kodama/main/instalar.ps1 | iex
#   El Claude de la persona:      lo baja y lo corre con  -Acepto -Si  (despues de mostrarle la licencia en el chat)
#
# Que hace: revisa Windows, la app de Claude y Python (si falta Python, lo instala con winget, preguntando);
# baja la ultima version firmada de GitHub, comprueba su sha256, la descomprime en %USERPROFILE%\Kodama
# (nunca en AppData: la app de Claude virtualiza esa carpeta) y corre instalar.py, que verifica la FIRMA antes de
# tocar nada. Actualizar despues: menu del gato -> "Actualizar a ...".
param([switch]$Acepto, [switch]$Si, [switch]$SoloClaude, [string]$Destino = (Join-Path $HOME 'Kodama'), [string]$Repo = 'LShinox/kodama')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Language: English by default; Spanish if the Windows language starts with "es".
$Es = ((Get-UICulture).Name -match '^es') -or ((Get-Culture).Name -match '^es')
$L = if ($Es) { 'es' } else { 'en' }
$Tx = @{
    titulo     = @{ es = 'Kodama - instalacion'; en = 'Kodama - installation' }
    soloWin    = @{ es = 'Kodama es para Windows.'; en = 'Kodama is for Windows only.' }
    sinClaude  = @{ es = 'No encuentro la app de escritorio de Claude. Kodama funciona con ella (pestana Code): instalala primero.'; en = 'Could not find the Claude desktop app. Kodama works with it (Code tab): install it first.' }
    pidePython = @{ es = 'Falta Python 3.10 o mas nuevo. Lo instalo con winget (Python 3.12, ~30 MB)?'; en = 'Python 3.10 or newer is missing. Install it with winget (Python 3.12, ~30 MB)?' }
    sinPython  = @{ es = 'Sin Python no se puede instalar.'; en = 'Cannot install without Python.' }
    buscando   = @{ es = 'Buscando la ultima version en github.com/{0}'; en = 'Looking for the latest version at github.com/{0}' }
    faltanArch = @{ es = 'La version {0} no trae sus archivos (kodama-{0}.zip y .json).'; en = 'Version {0} does not include its files (kodama-{0}.zip and .json).' }
    huella     = @{ es = 'El archivo bajado no coincide con su huella (sha256): no se instala nada.'; en = 'The downloaded file does not match its checksum (sha256): nothing was installed.' }
    bajada     = @{ es = 'Version {0} bajada y comprobada'; en = 'Version {0} downloaded and verified' }
    copiado    = @{ es = 'Copiado en {0}'; en = 'Copied to {0}' }
    siAuto     = @{ es = '(si)'; en = '(yes)' }
    sn         = @{ es = '[s/N]'; en = '[y/N]' }
}
function Tr($k, $a) { $s = $Tx[$k][$L]; if ($null -ne $a) { $s -f $a } else { $s } }
function Paso($t) { Write-Host "-> $t" -ForegroundColor Cyan }
function Pregunta($t) { if ($Si) { Write-Host "$t $(Tr 'siAuto')"; return $true }; (Read-Host "$t $(Tr 'sn')") -match '^(s|si|y)$' }

Write-Host (Tr 'titulo') -ForegroundColor Green
if (-not [Environment]::OSVersion.Platform.ToString().StartsWith('Win')) { throw (Tr 'soloWin') }
if (-not (Get-AppxPackage -Name Claude -ErrorAction SilentlyContinue)) {
    Write-Warning (Tr 'sinClaude')
}

# 1. Python 3.10+
$py = $null
foreach ($c in 'py', 'python') {
    try { $v = & $c -c "import sys;print(sys.version_info>=(3,10))" 2>$null; if ($v -eq 'True') { $py = $c; break } } catch {}
}
if (-not $py) {
    if (-not (Pregunta (Tr 'pidePython'))) { throw (Tr 'sinPython') }
    winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $py = 'python'
}
Paso "Python: $(& $py --version)"

# 2. Ultima version firmada
Paso (Tr 'buscando' $Repo)
$rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'Kodama-instalador' }
$ver = $rel.tag_name.TrimStart('v', 'V')
$zipA = $rel.assets | Where-Object name -eq "kodama-$ver.zip"
$jsonA = $rel.assets | Where-Object name -eq "kodama-$ver.json"
if (-not $zipA -or -not $jsonA) { throw (Tr 'faltanArch' $ver) }
$tmp = Join-Path $env:TEMP "kodama-$ver"
New-Item -ItemType Directory -Force $tmp | Out-Null
Invoke-WebRequest $zipA.browser_download_url -OutFile "$tmp\kodama-$ver.zip" -UseBasicParsing
Invoke-WebRequest $jsonA.browser_download_url -OutFile "$tmp\kodama-$ver.json" -UseBasicParsing
$man = Get-Content "$tmp\kodama-$ver.json" -Raw | ConvertFrom-Json
$sha = (Get-FileHash "$tmp\kodama-$ver.zip" -Algorithm SHA256).Hash.ToLower()
if ($sha -ne $man.sha256) { throw (Tr 'huella') }
Paso (Tr 'bajada' $ver)

# 3. Descomprimir (sin pisar estado\, config.json ni el .venv si ya estaba instalado)
New-Item -ItemType Directory -Force $Destino | Out-Null
Expand-Archive "$tmp\kodama-$ver.zip" -DestinationPath $Destino -Force
$inst = Join-Path $Destino 'estado\instalacion'
New-Item -ItemType Directory -Force $inst | Out-Null
Copy-Item "$tmp\kodama-$ver.zip", "$tmp\kodama-$ver.json" $inst -Force
Remove-Item $tmp -Recurse -Force
Paso (Tr 'copiado' $Destino)

# 4. instalar.py: verifica la firma, pone los hooks, la tarea de arranque y lanza la mascota
$args2 = @("$Destino\instalar.py")
if ($Acepto) { $args2 += '--acepto' }
if ($Si) { $args2 += '--si' }
if ($SoloClaude) { $args2 += '--solo-claude' }
Push-Location $Destino
try { & $py @args2 } finally { Pop-Location }
