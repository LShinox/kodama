// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Kodama de escritorio (Fase 1, 13-oct-2026): mascotas flotantes siempre visibles en Windows.
// Ideas tomadas de los estudios: ventana transparente que NO roba el foco (focusable:false), clic que atraviesa
// salvo sobre las mascotas, reafirmar "siempre visible" cada 1 s (Windows lo quita con pantalla completa),
// tope de 30 fps y pausa cuando no se ve (lo que mas le costo a Coucou fue el CPU en reposo).
// (14-oct) idioma del menú de la bandeja: la clave es el texto en español, el valor el inglés (conf.idioma = "es" | "en")
const MENU_EN = { "Ocultar": "Hide", "Mostrar": "Show", "Personaje": "Character", "Gato": "Cat", "Gato ojos lisos": "Cat plain eyes", "Brote": "Sprout",
  "Sonidos": "Sounds", "Quitar «No molestar»": "Turn off «Do not disturb»", "No molestar hasta mañana": "Do not disturb until tomorrow",
  "Volver a la esquina": "Back to the corner", "Salir": "Quit", "Editar animaciones": "Edit animations" };
const L = s => (conf.idioma === "en" && MENU_EN[s]) || s;
const { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage, globalShortcut, powerMonitor, shell, clipboard } = require("electron");
const path = require("path");
const fs = require("fs");

const BASE = path.join(__dirname, "..");
const ESTADO = path.join(BASE, "estado");
const CONF = path.join(ESTADO, "escritorio.json");
const HUB = "http://127.0.0.1:8787";

if (!app.requestSingleInstanceLock()) app.quit();

let win = null, tray = null;
const leer = (f, d) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e) { return d; } };
const conf = Object.assign({ pj: "gatoPro", x: null, y: null, visible: true }, leer(CONF, {}));
const guardar = () => { try { fs.writeFileSync(CONF + ".tmp", JSON.stringify(conf, null, 1)); fs.renameSync(CONF + ".tmp", CONF); } catch (e) {} };
const clave = () => { try { return fs.readFileSync(path.join(ESTADO, "local.key"), "utf8").trim(); } catch (e) { return ""; } };

async function hub(ruta, cuerpo) {
  const r = await fetch(HUB + ruta, {
    method: cuerpo ? "POST" : "GET",
    headers: Object.assign({ "X-Companero-Local": clave() }, cuerpo ? { "Content-Type": "application/json" } : {}),
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  return r.json();
}

function crearVentana() {
  const area = screen.getPrimaryDisplay().workArea;
  const W = 400, H = 600;
  win = new BrowserWindow({
    width: W, height: H,
    x: conf.x ?? area.x + area.width - W - 12, y: conf.y ?? area.y + area.height - H - 8,
    transparent: true, frame: false, resizable: false, skipTaskbar: true, hasShadow: false,
    alwaysOnTop: true, focusable: false, show: false, backgroundColor: "#00000000",
    webPreferences: { preload: path.join(__dirname, "preload.js"), backgroundThrottling: true },
  });
  win.setAlwaysOnTop(true, "screen-saver");
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile(path.join(__dirname, "index.html"));
  // el idioma elegido en la bandeja manda sobre el localStorage de la pagina (si se borro, vuelve a coincidir)
  win.webContents.on("did-finish-load", () => {
    const id = conf.idioma === "en" ? "en" : "es";
    win.webContents.executeJavaScript(`(localStorage.getItem("idioma") || "es") !== "${id}" && window.fijarIdioma && fijarIdioma("${id}")`).catch(() => {});
  });
  win.once("ready-to-show", () => { if (conf.visible) win.showInactive(); });
  win.on("moved", () => { const [x, y] = win.getPosition(); conf.x = x; conf.y = y; guardar(); });
  // Windows le quita el "siempre visible" cuando hay algo a pantalla completa: reafirmarlo cada segundo
  setInterval(() => { if (win && !win.isDestroyed() && win.isVisible()) win.setAlwaysOnTop(true, "screen-saver"); }, 2000);   // (14-oct) cada 2 s alcanza
  // se esconde solo mientras hay algo a pantalla completa (juego, video) y vuelve al salir
  let escondidoPorPantalla = false;
  setInterval(async () => {
    if (!win || win.isDestroyed() || !conf.visible) return;
    try {
      const { completa } = await hub("/api/pantalla");
      if (completa && !escondidoPorPantalla) { escondidoPorPantalla = true; win.hide(); win.webContents.send("visible", false); }
      else if (!completa && escondidoPorPantalla) { escondidoPorPantalla = false; win.showInactive(); win.webContents.send("visible", true); }
    } catch (e) {}
  }, 3000);
  // el clic-atraviesa de Windows deja de reenviar el mouse a veces (p. ej. tras recargar la pagina) y la mascota
  // queda "sorda": el proceso principal mira el cursor 10 veces por segundo y le avisa a la ventana (14-oct)
  let dentro = false;
  setInterval(() => {
    if (!win || win.isDestroyed() || !win.isVisible()) return;
    const p = screen.getCursorScreenPoint(), b = win.getBounds();
    const en = p.x >= b.x && p.x < b.x + b.width && p.y >= b.y && p.y < b.y + b.height;
    if (en) win.webContents.send("cursor", p.x - b.x, p.y - b.y);
    else if (dentro) win.webContents.send("cursor", -1, -1);
    dentro = en;
  }, 150);
  // autocaptura para revisar como se ve (si existe estado\escritorio-captura.pedido -> estado\escritorio-captura.png)
  setInterval(async () => {
    const ped = path.join(ESTADO, "escritorio-captura.pedido");
    if (!fs.existsSync(ped) || !win || win.isDestroyed()) return;
    try { fs.unlinkSync(ped);   // (14-oct, auditoria) el contenido del pedido ya no se ejecuta: solo captura + diagnostico fijo
      const img = await win.webContents.capturePage(); fs.writeFileSync(path.join(ESTADO, "escritorio-captura.png"), img.toPNG());
      const info = await win.webContents.executeJavaScript(`JSON.stringify({pj: document.getElementById("pj").innerHTML.length, svg: (()=>{const r=document.querySelector("#pj svg")?.getBoundingClientRect(); return r?[r.x,r.y,r.width,r.height]:null})(), err: window.__err || null})`);
      fs.writeFileSync(path.join(ESTADO, "escritorio-captura.txt"), info); } catch (e) { fs.writeFileSync(path.join(ESTADO, "escritorio-captura.txt"), "ERR " + e); }
  }, 2000);
}

function menuBandeja() {
  const pjs = [["gatoPro", "Gato"], ["gato", "Gato ojos lisos"], ["brote5", "Brote"]];
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: L(conf.visible ? "Ocultar" : "Mostrar"), click: () => alternar() },
    { label: L("Personaje"), submenu: pjs.map(([v, n]) => ({ label: L(n), type: "radio", checked: conf.pj === v, click: () => { conf.pj = v; guardar(); win.webContents.send("pj", v); } })) },
    { label: L("Sonidos"), type: "checkbox", checked: conf.sonido !== false, click: () => { conf.sonido = conf.sonido === false; guardar(); win.webContents.send("sonido", conf.sonido); menuBandeja(); } },
    { label: L(noMolestar() ? "Quitar «No molestar»" : "No molestar hasta mañana"), click: () => {
      if (noMolestar()) conf.noMolestarHasta = 0; else { const m = new Date(); m.setDate(m.getDate() + 1); m.setHours(8, 0, 0, 0); conf.noMolestarHasta = m.getTime(); }
      guardar(); win.webContents.send("noMolestar", conf.noMolestarHasta); menuBandeja(); } },
    { label: L("Editar animaciones"), click: () => abrirPanel() },
    { label: L("Volver a la esquina"), click: () => { conf.x = conf.y = null; guardar(); const a = screen.getPrimaryDisplay().workArea; const [w, h] = win.getSize(); win.setPosition(a.x + a.width - w - 12, a.y + a.height - h - 8); } },
    { label: "Idioma / Language", submenu: [["es", "Español"], ["en", "English"]].map(([v, n]) => ({ label: n, type: "radio", checked: (conf.idioma || "es") === v,
      click: () => { conf.idioma = v; guardar(); if (win && !win.isDestroyed()) win.webContents.executeJavaScript(`fijarIdioma('${v}')`).catch(() => {}); menuBandeja(); } })) },
    { type: "separator" },
    { label: L("Salir"), click: () => app.quit() },
  ]));
}
const noMolestar = () => (conf.noMolestarHasta || 0) > Date.now();
function alternar() {
  conf.visible = !conf.visible; guardar();
  if (conf.visible) win.showInactive(); else win.hide();
  win.webContents.send("visible", conf.visible); menuBandeja();
}

app.whenReady().then(() => {
  crearVentana();
  tray = new Tray(nativeImage.createFromPath(path.join(BASE, "web", "icono-180.png")).resize({ width: 16, height: 16 }));
  tray.setToolTip("Kodama");
  tray.on("click", alternar);
  menuBandeja();
  // atajos globales (estudio de globos §3.8): F10 abre/cierra el globo, F11 responde al asomo. Ctrl+Shift+F no cambia el idioma del teclado.
  const atajo = (k, que) => { if (!globalShortcut.register(k, () => { if (win && !win.isDestroyed() && win.isVisible()) win.webContents.send("atajo", que); })) console.log("atajo ocupado:", k); };
  atajo("Control+Shift+F10", "globo"); atajo("Control+Shift+F11", "asomo");
});
app.on("will-quit", () => globalShortcut.unregisterAll());
app.on("window-all-closed", () => {});

// ---- puente con la ventana ----
ipcMain.handle("conf", () => ({ pj: conf.pj, noMolestarHasta: conf.noMolestarHasta || 0, sonido: conf.sonido !== false }));
ipcMain.handle("ajustes", () => leer(path.join(BASE, "web", "ajustes.json"), {}));   // (14-oct) lo que guardas en "Editar animaciones"
ipcMain.handle("inactivo", () => powerMonitor.getSystemIdleTime());   // segundos sin mouse ni teclado en todo Windows
// abrir el chat en la app de Claude: solo enlaces de sesiones locales de la app, nada mas
ipcMain.on("abrir", (_e, url, texto) => {
  if (!/^claude:\/\/claude\.ai\/epitaxy\/local_[0-9a-f-]{36}$/.test(String(url))) return;
  // (14-oct) con texto: queda copiado para pegarlo en el chat (Ctrl+V). Escrito ahi cuenta como TU respuesta; por el
  // buzon entre sesiones Claude no lo acepta como aprobacion (lo marca "desde otra sesion").
  if (texto) clipboard.writeText(String(texto));
  shell.openExternal(url);
});
ipcMain.handle("grupos",() => hub("/api/grupos").catch(() => null));
ipcMain.handle("liberar", (_e, chat) => hub("/api/liberar", { chat }).catch(e => ({ ok: false, error: String(e.message || e) })));
ipcMain.handle("grupo", (_e, id) => hub("/api/grupo", { id }).catch(e => ({ ok: false, error: String(e.message || e) })));
ipcMain.handle("estado",() => hub("/api/estado?ligero=1").catch(e => ({ _error: String(e.message || e) })));
ipcMain.handle("responder", (_e, chat, texto, foto) => hub("/api/responder", foto ? { chat, texto, foto } : { chat, texto }).catch(e => ({ ok: false, error: String(e.message || e) })));
// la ventana deja pasar los clics salvo cuando el mouse esta sobre una mascota o la burbuja
// mientras se escribe, sacar el mouse de la ventana NO le quita el foco (si no, se cortaba lo que escribias)
let escribiendo = false;
// (14-oct) en Windows, setFocusable vuelve a mostrar el boton en la barra de tareas: se reafirma skipTaskbar
// cada vez (el icono aparecia y desaparecia al pasar el mouse por la mascota). Y solo se toca si cambia.
let enfocable = false;
const ponerFocusable = f => { if (f !== enfocable) { enfocable = f; win.setFocusable(f); } win.setSkipTaskbar(true); };
ipcMain.on("interactivo", (_e, si) => { if (!win) return; win.setIgnoreMouseEvents(!si, { forward: true }); ponerFocusable(!!si || escribiendo); });
ipcMain.on("escribir", (_e, si) => { if (!win) return; escribiendo = !!si; ponerFocusable(!!si); if (si) win.focus(); else win.blur(); });
ipcMain.on("arrastrar", (_e, dx, dy) => { if (!win) return; const [x, y] = win.getPosition(); win.setPosition(x + dx, y + dy); });

// (14-oct) "Editar animaciones": abre el panel web\ajustes.html (sliders que guardan web\ajustes.json) en una ventana
// normal. Lo sirve el hub, que pide la clave local: se agrega solo a los pedidos de esta ventana a 127.0.0.1:8787.
let panel = null;
function abrirPanel() {
  if (panel && !panel.isDestroyed()) { panel.show(); panel.focus(); return; }
  const { session } = require("electron");
  const ses = session.fromPartition("companero-panel");
  ses.webRequest.onBeforeSendHeaders({ urls: [HUB + "/*"] }, (d, cb) => { d.requestHeaders["X-Companero-Local"] = clave(); cb({ requestHeaders: d.requestHeaders }); });
  panel = new BrowserWindow({ width: 1100, height: 800, title: "Kodama — animaciones", autoHideMenuBar: true,
    webPreferences: { session: ses, contextIsolation: true, nodeIntegration: false } });
  panel.loadURL(HUB + "/ajustes.html");
}
