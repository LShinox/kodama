// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Graba una pagina local a cuadros PNG con Edge headless por DevTools (Page.captureScreenshot cada N ms).
// Reglas de la PC: perfil DENTRO del scratchpad, --disk-cache-size=1, y en el finally se cierra por PID el padre y
// TODOS los hijos (buscados por el --user-data-dir), se borra el perfil y se comprueba que no quede nada.
// Uso: node grabar.js <url> <carpeta_salida> <ancho> <alto> <segundos> <ms_por_cuadro> [js_al_empezar]
const { spawn, execFileSync } = require("child_process"); const fs = require("fs"), path = require("path"), http = require("http");
const [url, salida, W, H, seg, ms, alEmpezar] = process.argv.slice(2);
const PERFIL = path.join(__dirname, "perfil-edge-gif"), PUERTO = 9333;
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const espera = t => new Promise(r => setTimeout(r, t));
function hijos() {
  try { return execFileSync("powershell", ["-NoProfile", "-Command", `Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object { $_.CommandLine -like '*perfil-edge-gif*' } | Select-Object -ExpandProperty ProcessId`]).toString().split(/\s+/).filter(Boolean).map(Number); } catch (e) { return []; }
}
function json(u) { return new Promise((ok, mal) => http.get(u, r => { let d = ""; r.on("data", c => d += c); r.on("end", () => { try { ok(JSON.parse(d)); } catch (e) { mal(e); } }); }).on("error", mal)); }
(async () => {
  fs.mkdirSync(salida, { recursive: true });
  const p = spawn(EDGE, ["--headless=new", `--user-data-dir=${PERFIL}`, "--disk-cache-size=1", `--remote-debugging-port=${PUERTO}`,
    "--allow-file-access-from-files", "--hide-scrollbars", "--force-device-scale-factor=1", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
  try {
    let pag = null;
    for (let i = 0; i < 40 && !pag; i++) { await espera(250); try { pag = (await json(`http://127.0.0.1:${PUERTO}/json`)).find(x => x.type === "page"); } catch (e) {} }
    if (!pag) throw new Error("Edge no abrio DevTools");
    const ws = new WebSocket(pag.webSocketDebuggerUrl); let id = 0; const pend = {};
    await new Promise(r => ws.onopen = r);
    ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } };
    const cdp = (method, params = {}) => new Promise(r => { const n = ++id; pend[n] = r; ws.send(JSON.stringify({ id: n, method, params })); });
    await cdp("Emulation.setDeviceMetricsOverride", { width: +W, height: +H, deviceScaleFactor: 1, mobile: false });
    await cdp("Page.navigate", { url }); await espera(1500);
    if (alEmpezar) {   // "@archivo.js": el codigo se lee de un archivo (las comillas no sobreviven a la linea de comandos)
      const r = await cdp("Runtime.evaluate", { expression: alEmpezar.startsWith("@") ? fs.readFileSync(alEmpezar.slice(1), "utf8") : alEmpezar });
      if (r && r.exceptionDetails) console.log("error en el script:", JSON.stringify(r.exceptionDetails).slice(0, 300));
    }
    const n = Math.round(seg * 1000 / ms), t0 = Date.now();
    for (let i = 0; i < n; i++) {
      const r = await cdp("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(salida, `f${String(i).padStart(3, "0")}.png`), Buffer.from(r.data, "base64"));
      const falta = t0 + (i + 1) * ms - Date.now(); if (falta > 0) await espera(falta);
    }
    ws.close(); console.log("cuadros:", n);
  } finally {
    for (const pid of [p.pid, ...hijos()]) { try { execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" }); } catch (e) {} }
    await espera(800);
    for (const pid of hijos()) { try { execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" }); } catch (e) {} }
    fs.rmSync(PERFIL, { recursive: true, force: true });
    console.log("quedan con el perfil:", hijos().length, "| perfil borrado:", !fs.existsSync(PERFIL));
  }
})().catch(e => { console.error("ERROR", e.message); process.exitCode = 1; });
