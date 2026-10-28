// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Falso window.__TAURI__ para grabar los GIFs del lanzamiento con la pagina REAL de la mascota (escritorio-tauri\ui) en un navegador
// normal. La conf es de mentira (nada de la PC del dueño). Solo para grabar.
window.__errs = [];
window.addEventListener("error", e => window.__errs.push("error: " + e.message + " @" + String(e.filename).split("/").pop() + ":" + e.lineno), true);
window.addEventListener("unhandledrejection", e => window.__errs.push("rechazo: " + String(e.reason && (e.reason.stack || e.reason.message) || e.reason).slice(0, 300)));
(() => {
  const gen = () => new Proxy(function () {}, {
    get: (t, p) => (p === "then" || typeof p === "symbol") ? undefined : (Object.prototype.hasOwnProperty.call(t, p) && p !== "name" && p !== "length" && p !== "prototype") ? t[p] : gen(),
    apply: () => gen(), construct: () => gen(),
  });
  const manejadores = {};
  const P = new URLSearchParams(location.search);
  let conf = Object.assign({ capsula: true, capsulaColor: "blanca", animCompletas: true, visible: true, pj: "gatoPro", color: "negro", idioma: "es",
    loNuevoVisto: "0.9.0", sueno: true, suenoMin: 2, sonido: false }, window.__CONF || {});
  if (P.get("sincapsula")) conf.capsula = false;
  const inv = async (cmd, args) => {
    switch (cmd) {
      case "clave": return "clave-de-prueba";
      case "puerto": return String(window.__PUERTO || 8795);
      case "conf_leer": return JSON.stringify(conf);
      case "conf_guardar": try { conf = JSON.parse(args.json); } catch (e) {} return null;
      case "drop_info": return [1, 0, 0];
      case "leer_pedido": return null;
      case "zona": window.__zonaPrueba = args && args.r; return null;
      default: return null;
    }
  };
  const monitor = { scaleFactor: 1, position: { x: 0, y: 0 }, size: { width: 1920, height: 1080 }, workArea: { position: { x: 0, y: 0 }, size: { width: 1920, height: 1040 } } };
  const T = gen();
  T.core = { invoke: inv };
  T.event = { listen: async (n, cb) => { (manejadores[n] = manejadores[n] || []).push(cb); return () => {}; } };
  T.webview = { getCurrentWebview: () => ({ onDragDropEvent: async () => () => {} }) };
  T.window = {
    getCurrentWindow: () => ({ outerPosition: async () => ({ x: 1500, y: 480 }), outerSize: async () => ({ width: 400, height: 600 }), scaleFactor: async () => 1,
      setPosition: async () => {}, onMoved: () => {}, onScaleChanged: () => {} }),
    currentMonitor: async () => monitor, primaryMonitor: async () => monitor, availableMonitors: async () => [monitor],
  };
  window.__TAURI__ = T;
  window.__emitir = (n, payload) => (manejadores[n] || []).forEach(f => f({ payload }));
  window.chrome = window.chrome || {};
  window.chrome.webview = { postMessageWithAdditionalObjects: () => { setTimeout(() => window.__emitir("kodama-soltar", (window.__RUTAS || []).slice()), 25); } };
  try { document.documentElement.style.background = window.__FONDO || "#e9e4db"; } catch (e) {}
})();
