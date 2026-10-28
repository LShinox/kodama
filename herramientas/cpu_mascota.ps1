# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
param([int]$seg = 30)
# CPU de la mascota (kodama.exe + sus WebView2), por tipo de proceso, en % de UN nucleo
$ids = @()
$m = Get-Process kodama, companero -ErrorAction SilentlyContinue | Select-Object -First 1
if ($m) { $ids += [pscustomobject]@{ id = $m.Id; t = 'kodama.exe' } }
Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" | Where-Object { $_.CommandLine -match 'webview-exe-name=(kodama|companero)' } | ForEach-Object {
    $t = ([regex]'--type=(\S+)').Match($_.CommandLine).Groups[1].Value; if (-not $t) { $t = 'browser' }
    $ids += [pscustomobject]@{ id = $_.ProcessId; t = $t }
}
$a = @{}; foreach ($x in $ids) { $q = Get-Process -Id $x.id -ErrorAction SilentlyContinue; if ($q) { $a[$x.id] = $q.TotalProcessorTime.TotalSeconds } }
Start-Sleep $seg
$tot = 0
foreach ($x in $ids) { $q = Get-Process -Id $x.id -ErrorAction SilentlyContinue; if ($q -and $a.ContainsKey($x.id)) { $p = ($q.TotalProcessorTime.TotalSeconds - $a[$x.id]) / $seg * 100; $tot += $p; "{0,-14} {1,6:N1} %" -f $x.t, $p } }
"TOTAL          {0,6:N1} % de un nucleo ({1} s)" -f $tot, $seg
