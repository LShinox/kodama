# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
$ErrorActionPreference = 'Stop'
$app = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Join-Path $env:USERPROFILE 'Apps\companero' }
$flag = Join-Path $app 'estado\no-relanzar'
New-Item $flag -ItemType File -Force | Out-Null
try {
    Set-Location (Join-Path $app 'escritorio-tauri')
    node preparar-ui.js
    $p = [int](Get-Content (Join-Path $app 'estado\escritorio.pid'))
    $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
    if ($proc -and ($proc.ProcessName -eq 'kodama' -or $proc.ProcessName -eq 'companero')) { Stop-Process -Id $p -Force; "mascota parada (PID $p)" }
    Set-Location (Join-Path $app 'escritorio-tauri')
    # (27-oct, lanzamiento) el .exe va en un release PUBLICO: sin esto lleva la ruta de tu usuario (carpeta .cargo\registry) en los mensajes de panico
    $env:RUSTFLAGS = '--remap-path-prefix=' + $env:USERPROFILE + '=C:\kodama'
    cmd /c "npx tauri build --no-bundle 2>&1" | Select-Object -Last 6
    if ($LASTEXITCODE -ne 0) { throw "build fallo ($LASTEXITCODE)" }
} finally {
    Remove-Item $flag -Force -ErrorAction SilentlyContinue
    # (21-oct) por WMI: el proceso nace fuera de la app de Claude (como lo lanza la tarea programada), asi no hereda la
    # virtualizacion de AppData del paquete MSIX (perfil de WebView2 y localStorage distintos)
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = '"' + (Join-Path $app '.venv\Scripts\pythonw.exe') + '" arrancar.pyw'; CurrentDirectory = $app } | Out-Null
    Start-Sleep 6
    "mascota: " + ((Get-Process kodama, companero -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) -join ',')
}
