# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
$os = Get-CimInstance Win32_OperatingSystem
"Encendida desde: $($os.LastBootUpTime)"
"RAM libre: {0:N1} de {1:N1} GB | memoria comprometible libre: {2:N1} de {3:N1} GB" -f ($os.FreePhysicalMemory/1MB), ($os.TotalVisibleMemorySize/1MB), ($os.FreeVirtualMemory/1MB), ($os.TotalVirtualMemorySize/1MB)
$pf = Get-CimInstance Win32_PageFileUsage; foreach ($p in $pf) { "Paginacion $($p.Name): {0} MB asignado, {1} MB en uso, pico {2} MB" -f $p.AllocatedBaseSize, $p.CurrentUsage, $p.PeakUsage }
$d = Get-PSDrive C; "Disco C: libre {0:N1} GB" -f ($d.Free/1GB)
"--- por programa (memoria comprometida, procesos) ---"
Get-Process | Group-Object Name | ForEach-Object { [pscustomobject]@{ Nombre = $_.Name; N = $_.Count; CommitGB = [math]::Round((($_.Group | Measure-Object PagedMemorySize64 -Sum).Sum)/1GB, 2); RamGB = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum)/1GB, 2) } } | Sort-Object CommitGB -Descending | Select-Object -First 14 | Format-Table -AutoSize | Out-String -Width 120
"Procesos totales: $((Get-Process).Count) | handles: $((Get-Process | Measure-Object HandleCount -Sum).Sum)"
"--- hubs del companero ---"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" | Where-Object { $_.CommandLine -match 'companero' } | Select-Object ProcessId, ParentProcessId, CreationDate, @{n='cmd';e={($_.CommandLine -split '\\')[-1]}} | Format-Table -AutoSize | Out-String -Width 160
"--- eventos de sistema (errores) de las ultimas 6 h ---"
Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddHours(-6)} -ErrorAction SilentlyContinue | Group-Object Id, ProviderName | Sort-Object Count -Descending | Select-Object -First 8 Count, Name | Format-Table -AutoSize | Out-String -Width 160
Get-WinEvent -FilterHashtable @{LogName='System'; Id=2004; StartTime=(Get-Date).AddDays(-2)} -ErrorAction SilentlyContinue | Select-Object -First 5 TimeCreated, @{n='m';e={$_.Message.Substring(0,[Math]::Min(300,$_.Message.Length))}} | Format-List | Out-String -Width 200
"--- cuelgues de aplicaciones (Application Hang / Error) 2 dias ---"
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1002,1000; StartTime=(Get-Date).AddDays(-2)} -ErrorAction SilentlyContinue | ForEach-Object { ($_.Properties[0].Value) + " | " + $_.Id } | Group-Object | Sort-Object Count -Descending | Select-Object -First 10 Count, Name | Format-Table -AutoSize | Out-String -Width 160
