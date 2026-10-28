// © 2026 LShinox. Todos los derechos reservados. Ver LICENCIA.txt
// Puente de la mascota en Tauri (14-oct-2026): define window.companero con la MISMA forma que el preload.js de
// Electron, asi escritorio\index.html no cambia. Lo propio de la ventana (clic que atraviesa, foco, mover, mostrar,
// cursor) lo hace Rust (src-tauri\src\main.rs); lo demas va directo al hub con fetch (CORS solo para este origen).
// (27-oct, 4.a vuelta) lo que la CSP bloquee queda anotado (maximo 20) para el diagnostico fijo de estado\escritorio-captura.pedido
window.__csp = []; document.addEventListener("securitypolicyviolation", e => { if (window.__csp.length < 20) window.__csp.push(String(e.effectiveDirective) + " " + String(e.blockedURI).slice(0, 40)); }, true);
(() => {
  const T = window.__TAURI__, inv = T.core.invoke;
  let HUB = "http://127.0.0.1:8787";   // (26-oct) el puerto real sale de estado\puerto.txt (comando `puerto` de Rust); 8787 si no existe
  let KEY = "", conf = {};
  const oyentes = { pj: [], visible: [], atajo: [], noMolestar: [], sonido: [], cursor: [], ojos: [], modo: [], ajustes: [], sueno: [], capsula: [], capsulaColor: [], animCompletas: [] };
  const avisar = (k, ...a) => oyentes[k].forEach(f => { try { f(...a); } catch (e) {} });
  const clave = async () => KEY || (KEY = await inv("clave"));
  const leerPuerto = async () => { try { const p = parseInt(await inv("puerto"), 10); if (p >= 8787 && p <= 8799) HUB = "http://127.0.0.1:" + p; } catch (e) {} return HUB; };
  let puertoListo = leerPuerto();
  async function hub(ruta, cuerpo) {
    await puertoListo;
    const pedir = async () => fetch(HUB + ruta, { method: cuerpo ? "POST" : "GET", body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      headers: Object.assign({ "X-Companero-Local": await clave() }, cuerpo ? { "Content-Type": "application/json" } : {}) });
    let r;
    // (26-oct, idea de clawd #1261) si el pedido falla, el hub pudo reiniciarse en otro puerto: se relee puerto.txt y se reintenta UNA vez
    try { r = await pedir(); } catch (e) { const antes = HUB; await leerPuerto(); if (HUB === antes) throw e; r = await pedir(); }
    return r.json();
  }
  const guardar = () => inv("conf_guardar", { json: JSON.stringify(conf) });
  // (27-oct, 4.a vuelta) capsulaColor ("blanca" | "negra") viaja junto al personaje; el hub de hoy solo guarda pj/color/florCactus y descarta el resto (ver ejecutor-log)
  // (27-oct, lanzamiento) SOLO EL GATO: Brote queda oculto de todos los menus. true = vuelve a mostrarse (el codigo de Brote sigue entero).
  const MOSTRAR_BROTE = false;
  // al LEER: un Brote guardado se muestra como gato (con los ojos que el gato tenia); conf.json no se reescribe por esto
  const pjVis = p => { p = p || "gatoPro"; return !MOSTRAR_BROTE && p.startsWith("brote") ? (conf.ojosGato === "gato" ? "gato" : "gatoPro") : p; };
  const capCol = () => conf.capsulaColor === "negra" ? "negra" : "blanca";
  const compartirPj = () => hub("/api/personaje", { pj: pjVis(conf.pj), color: conf.color || "negro", florCactus: conf.florCactus !== false, capsulaColor: capCol() }).catch(() => {});
  // (21-oct) color del gato: va pegado al tipo ("gatoPro-naranja"); los brotes no tienen color aparte
  const pjEfectivo = () => {
    const b = pjVis(conf.pj);
    if (b.startsWith("broteCactus")) return conf.florCactus === false ? b + "-sinflor" : b;   // (21-oct) cactus con o sin flor
    return b.startsWith("gato") && conf.color && conf.color !== "negro" && conf.color !== "calico" ? b + "-" + conf.color : b;
  };
  const noMolestar = () => (conf.noMolestarHasta || 0) > Date.now();
  // (26-oct) sueño profundo: encendido por defecto; minutos sin cambios de 1 a 60 (por defecto 2, lo que ya hacia la mascota desde el 21-oct)
  const sueno = () => ({ on: conf.sueno !== false, min: conf.suenoMin >= 1 && conf.suenoMin <= 60 ? Math.round(conf.suenoMin) : 2 });
  // (27-oct, 5.a vuelta) "Animaciones completas": encendido por defecto; ignora prefers-reduced-motion. Es de ESTA PC: nunca se manda al hub.
  const animCompletas = () => conf.animCompletas !== false;
  const aplicarAnimCompletas = () => { window.KODAMA_ANIM_COMPLETAS = animCompletas(); avisar("animCompletas", animCompletas()); };

  // (27-oct) Rust quita la region de la ventana cuando esta cambia de tamaño (limites): se le pide a la pagina que mande la zona nueva
  const zonaYa = () => { try { window.zonaYa && window.zonaYa(true); } catch (e) {} };
  window.companero = {
    conf: async () => { try { conf = JSON.parse(await inv("conf_leer")); } catch (e) { conf = {}; }
      return { pj: pjEfectivo(), noMolestarHasta: conf.noMolestarHasta || 0, sonido: conf.sonido !== false }; },
    estado: () => hub("/api/estado?ligero=1").catch(e => ({ _error: String(e.message || e) })),
    responder: (chat, texto, foto) => hub("/api/responder", foto ? { chat, texto, foto } : { chat, texto }).catch(e => ({ ok: false, error: String(e.message || e) })),
    interactivo: si => inv("interactivo", { si }),
    // (27-oct) ZONA TACTIL FIJA: la pagina manda los rectangulos [x, y, ancho, alto] (px CSS) de lo que se ve y se toca; Rust arma con ellos la
    // region de la ventana (SetWindowRgn) con la escala del monitor donde esta. Fuera de la region los clics pasan a lo de abajo, sin sondeo.
    zona: r => { window.__zona = r; return inv("zona", { r }); },
    escribir: si => inv("escribir", { si }),
    arrastrar: (dx, dy) => inv("mover", { dx, dy }),
    inactivo: () => hub("/api/inactivo").then(j => j.segundos).catch(() => 0),
    ajustes: async () => { try { await puertoListo; return await (await fetch(HUB + "/ajustes.json", { headers: { "X-Companero-Local": await clave() } })).json(); } catch (e) { return {}; } },
    grupos: () => hub("/api/grupos").catch(() => null),
    grupo: id => hub("/api/grupo", { id }).catch(e => ({ ok: false, error: String(e) })),
    liberar: chat => hub("/api/liberar", { chat }).catch(e => ({ ok: false, error: String(e) })),
    // (22-oct) archivar / ver archivados / desarchivar (lo hace el chat de Kodama con las herramientas de la app)
    archivar: chat => hub("/api/archivar", { chat }).catch(e => ({ ok: false, error: String(e) })),
    archivados: () => hub("/api/archivados", {}).catch(() => ({ ok: false, chats: [] })),
    desarchivar: local => hub("/api/archivados", { desarchivar: local }).catch(e => ({ ok: false, error: String(e) })),
    abrir: (url, texto) => { if (texto) navigator.clipboard.writeText(texto).catch(() => {}); inv("abrir_url", { url }); },
    alCambiarPj: f => oyentes.pj.push(f), alVisible: f => oyentes.visible.push(f), alAtajo: f => oyentes.atajo.push(f),
    alNoMolestar: f => oyentes.noMolestar.push(f), alSonido: f => oyentes.sonido.push(f), alCursor: f => oyentes.cursor.push(f),
    alOjos: f => { oyentes.ojos.push(f); setTimeout(() => f(!!(conf && conf.ojos)), 0); },   // (15-oct) seguir el mouse siempre
    // (21-oct) modo "Aparecer solo cuando me necesitan": la pagina muestra/esconde la ventana sin tocar conf.visible
    alAjustes: f => oyentes.ajustes.push(f),   // (22-oct) "Ajustes…" del menu de la bandeja abre el panel
    alModo: f => { oyentes.modo.push(f); setTimeout(() => f(conf && conf.modo === "aviso" ? "aviso" : "siempre"), 0); },
    // (26-oct) "Sueño profundo": {on, min}. Se llama una vez al registrarse y cada vez que cambia en Ajustes
    alSueno: f => { oyentes.sueno.push(f); setTimeout(() => f(sueno()), 0); },
    // (27-oct) "Con cápsula": la mascota descansa dentro de un circulo del color de la ventana (variante del prototipo kodama-ventana-ajustes).
    // Se llama una vez con la conf ya leida (arranque) y cada vez que cambia en Ajustes.
    alCapsula: f => { oyentes.capsula.push(f); setTimeout(() => f(!!(conf && conf.capsula)), 0); },
    alAnimCompletas: f => { oyentes.animCompletas.push(f); setTimeout(() => f(animCompletas()), 0); },   // (5.a vuelta) "Animaciones completas" (true por defecto)
    alCapsulaColor: f => { oyentes.capsulaColor.push(f); setTimeout(() => f(capCol()), 0); },   // (27-oct, 4.a vuelta) color de la capsula: "blanca" (por defecto) | "negra"
    // (27-oct) la ventana NACE oculta (tauri.conf.json "visible": false) para que no se vea el destello del arranque. Aca NO se muestra
    // hasta que la pagina diga que el gato ya se dibujo (pintado(): primer cuadro de Lottie o del SVG + 1 requestAnimationFrame) o pasen 3,5 s
    // (hub caido, nada que dibujar). Ocultar pasa siempre. En modo "Aparecer solo cuando me necesitan" el arranque NO la muestra: sale con el primer aviso.
    ventana: si => { if (conf.visible === false) return; quiereVer = si; if (pintado || !si) inv("visible", { si }); avisar("visible", si); },
    pintado: () => { if (!confLista) { pintadoPend = true; return; } mostrarPintado(); },
  };
  let pintado = false, confLista = false, pintadoPend = false, quiereVer = null, tRespaldo = null;
  function mostrarPintado() {
    if (pintado) return; pintado = true; clearTimeout(tRespaldo);
    if (conf.visible === false || quiereVer === false || (conf.modo === "aviso" && quiereVer !== true)) return;
    inv("visible", { si: true });
  }

  T.event.listen("cursor", e => { window.__ultCursor = [Math.round(e.payload[0]), Math.round(e.payload[1]), Date.now() % 100000]; avisar("cursor", e.payload[0], e.payload[1]); });   // Rust mira el cursor cada 150 ms
  // (14-oct) arrastrar archivos a la mascota: Tauri entrega enter/over/drop/leave con las rutas y la posicion
  // (27-oct, soltar) cada evento nativo queda contado en window.__arr (lo lee el diagnostico fijo) y un fallo al registrar el oyente ya no es silencioso
  // (27-oct, soltar 2) CAUSA del "prohibido": el destino de arrastre que mandaba era el de WebView2 con AllowExternalDrop=false (lo deja asi dragDropEnabled:true) y
  // Tauri NUNCA recibia el evento (arr.n=0). Ahora tauri.conf.json trae "dragDropEnabled": false y el arrastre lo maneja WebView2 (DOM dragenter/dragover/drop):
  // aca se les hace preventDefault (cursor "copiar") y se traducen al mismo evento `companero-arrastre` que usa index.html. Las RUTAS no estan en el DOM:
  // al soltar se manda postMessageWithAdditionalObjects("kodama-soltar", files) y Rust (main.rs) devuelve el evento "kodama-soltar" con las rutas.
  // window.__arr.n = eventos recibidos por cualquiera de los dos caminos; dom = eventos DOM de arrastre de archivos; msg = soltadas enviadas a Rust.
  window.__arr = { n: 0, tipo: null, rutas: 0, ts: 0, err: null, dom: 0, msg: 0, via: null };
  const arrCuenta = (tipo, rutas, via) => { const a = window.__arr; a.n++; a.tipo = tipo; a.rutas = rutas; a.ts = Date.now() % 100000; a.via = via; };
  const arrDespachar = p => window.dispatchEvent(new CustomEvent("companero-arrastre", { detail: p }));
  try {   // camino de Tauri (solo si alguien vuelve a poner dragDropEnabled:true): no se usa con la config de hoy
    Promise.resolve(T.webview.getCurrentWebview().onDragDropEvent(e => {
      const p = e.payload || {}; arrCuenta(p.type, (p.paths || []).length, "tauri");
      arrDespachar(p);
    })).catch(err => { window.__arr.err = String(err && err.message || err); });
  } catch (e) { window.__arr.err = String(e && e.message || e); }
  T.event.listen("kodama-soltar", e => { const r = Array.isArray(e.payload) ? e.payload : []; arrCuenta("drop", r.length, "rust"); arrDespachar({ type: "drop", paths: r }); });
  {
    const esArchivo = e => { const t = e.dataTransfer && e.dataTransfer.types; return !!t && Array.prototype.indexOf.call(t, "Files") >= 0; };
    const pos = e => { const f = window.devicePixelRatio || 1; return { x: e.clientX * f, y: e.clientY * f }; };   // index.html divide por dpr (Tauri manda px fisicos)
    let dentro = false, vigilante = null;
    const salir = () => { clearTimeout(vigilante); vigilante = null; if (dentro) { dentro = false; arrDespachar({ type: "leave" }); } };
    const armar = () => { clearTimeout(vigilante); vigilante = setTimeout(salir, 900); };   // dragover llega cada ~50-350 ms: si deja de llegar, el arrastre salio o se cancelo
    const sobre = e => {
      if (!esArchivo(e)) return;
      e.preventDefault(); try { e.dataTransfer.dropEffect = "copy"; } catch (x) {}
      window.__arr.dom++;
      arrDespachar({ type: dentro ? "over" : "enter", position: pos(e) }); dentro = true; armar();
    };
    window.addEventListener("dragenter", sobre, true);
    window.addEventListener("dragover", sobre, true);
    // dragleave tambien salta al pasar de un elemento a otro: se espera 150 ms a que llegue el dragenter/dragover siguiente antes de dar el arrastre por terminado
    window.addEventListener("dragleave", e => { if (esArchivo(e)) { clearTimeout(vigilante); vigilante = setTimeout(salir, 150); } }, true);
    window.addEventListener("drop", e => {
      if (!esArchivo(e)) return;
      e.preventDefault(); window.__arr.dom++; salir();
      const fl = e.dataTransfer.files, wv = window.chrome && window.chrome.webview;
      if (fl && fl.length && wv && wv.postMessageWithAdditionalObjects) { window.__arr.msg++; try { wv.postMessageWithAdditionalObjects("kodama-soltar", fl); } catch (x) { window.__arr.err = String(x && x.message || x); } }
    }, true);
  }

  // ---- lo que en Electron hacia main.js ----
  const yo = T.window.getCurrentWindow();
  let escondidoPorPantalla = false;
  setInterval(() => inv("reafirmar"), 2000);   // Windows quita el "siempre visible" con pantalla completa
  setInterval(async () => {                    // se esconde mientras hay algo a pantalla completa (juego, video)
    if (conf.visible === false) return;
    try {
      const { completa } = await hub("/api/pantalla");
      if (completa && !escondidoPorPantalla) { escondidoPorPantalla = true; inv("visible", { si: false }); avisar("visible", false); }
      else if (!completa && escondidoPorPantalla) { escondidoPorPantalla = false; inv("visible", { si: true }); avisar("visible", true); }
    } catch (e) {}
  }, 3000);
  setInterval(async () => {                    // verificacion: si existe estado\escritorio-captura.pedido, un diagnostico FIJO
    try {                                      // (14-oct, auditoria) ya no evalua el contenido del archivo: cualquiera que escribiera ahi ejecutaba codigo con la clave a mano
      const expr = await inv("leer_pedido"); if (expr == null) return;
      const di = await inv("drop_info").catch(() => [null, null, null]);   // (27-oct, soltar 2) [AllowExternalDrop, mensajes "kodama-soltar" en Rust, rutas del ultimo]
      // (27-oct, 4.a vuelta) diagnostico FIJO ampliado: movimiento reducido, animaciones del navegador vivas (la respiracion del dormido), violaciones de CSP y estado del gato
      const r = JSON.stringify({ pj: (document.getElementById("pj") || {}).innerHTML?.length, err: window.__err || null,
        reducido: matchMedia("(prefers-reduced-motion: reduce)").matches, completas: animCompletas(), rmEfectivo: (typeof RM !== "undefined") ? RM : null, anims: document.getAnimations().map(a => a.playState).join(","),
        csp: window.__csp || [], estado: (typeof comp !== "undefined" && comp) ? comp.estado : null, dormida: typeof animDormida !== "undefined" ? animDormida : null,
        // (27-oct) "no puedo tocar la mascota": ultimo cursor que llego de Rust, que elemento hay ahi y si la ventana se cree interactiva
        sobre: !!window._sobre, ultCursor: window.__ultCursor || null, vista: [innerWidth, innerHeight], chica: typeof chica !== "undefined" ? chica : null,
        // (27-oct, zona tactil fija) escala que ve la pagina y la ultima zona mandada a Rust (px CSS, sin margenes del lado de Rust)
        dpr: window.devicePixelRatio, zona: window.__zona || null, zonaN: window.__zonaN || 0,
        // (27-oct, soltar) eventos de arrastre nativos recibidos (n, ultimo tipo, cuantas rutas, hora%100s) o el error al registrar el oyente
        arr: window.__arr || null, ext: di[0], msgsRust: di[1], rutasRust: di[2],
        enCursor: (() => { const c = window.__ultCursor; if (!c) return null; const el = document.elementFromPoint(c[0], c[1]);
          return el ? (el.id || el.tagName) + " < " + ((el.closest("[id]") || {}).id || "") : "nada"; })(),
        pieRect: (() => { const r = (document.getElementById("pie") || document.body).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); })() });
      inv("guardar_txt", { txt: String(r) });
    } catch (e) { inv("guardar_txt", { txt: "ERR " + e }); }
  }, 2000);
  // (14-oct) Windows manda la ventana oculta/minimizada a (-32000, -32000): esa posicion NO se guarda (la mascota
  // quedaba fuera de la pantalla al volver a abrirse)
  // (19-oct) VENTANA CHICA: la ventana transparente de 400x600 se redibujaba entera en cada cuadro de animacion
  // (~13 % de un nucleo con la PC en uso, medido). Sin globo, lista, aviso ni borrador abierto, queda del tamaño del gato
  // (200x210) pegada a la misma esquina de abajo a la derecha. conf.x/y SIEMPRE guardan la posicion de la ventana grande.
  // (19-oct, LShinox: "ajustarla un poco mas") 200x210 -> 172x186: lo justo para el gato, su nombre, la insignia y las "z"
  const GRANDE = [400, 600], CHICA = [172, 186], DX = GRANDE[0] - CHICA[0], DY = GRANDE[1] - CHICA[1];
  let chica = false, cola = Promise.resolve();
  // tras cambiar el tamaño o los clics, se fuerza un cuadro nuevo: con la animacion dormida la pagina no se redibujaba
  // y se veia un instante el fondo de la ventana (el "marco" que parpadea)
  const repintar = () => requestAnimationFrame(() => { document.body.style.opacity = ".999"; requestAnimationFrame(() => { document.body.style.opacity = ""; }); });
  async function tamano(si) {
    if (si === chica) return;
    const p = await yo.outerPosition(), f = await yo.scaleFactor(), x = p.x / f, y = p.y / f;
    chica = si;
    let r = si ? { x: x + DX, y: y + DY, w: CHICA[0], h: CHICA[1] } : { x: x - DX, y: y - DY, w: GRANDE[0], h: GRANDE[1] };
    // (19-oct) nunca debajo de la barra de tareas ni fuera de la pantalla: la ventana chica quedo 16 px debajo de la
    // barra y el gato no se veia ("no aparece la mascota")
    try {
      const m = (await T.window.currentMonitor()) || (await T.window.primaryMonitor());
      if (m) {
        const k = m.scaleFactor || 1, a = m.workArea || { position: m.position, size: m.size };
        const x0 = a.position.x / k, y0 = a.position.y / k, x1 = x0 + a.size.width / k, y1 = y0 + a.size.height / k;
        r.x = Math.min(Math.max(r.x, x0 - (r.w - 170)), x1 - r.w + 4);   // la parte del gato (abajo a la derecha) siempre adentro
        // +15: el dibujo del gato deja ~11 px libres debajo de las patas y #pie tiene 4 px de margen; asi las patas
        // apoyan en la barra de tareas (LShinox 19-oct: "no esta totalmente pegada a la barra")
        r.y = Math.min(Math.max(r.y, y0 - (r.h - 190)), y1 - r.h + 15);
      }
    } catch (e) {}
    await inv("limites", r);
    zonaYa();
    repintar();
  }
  window.companero.interactivo = si => { inv("interactivo", { si }); repintar(); };
  // (20-oct) APAGADO: achicar no bajaba el CPU (el costo es por cuadro, no por area: medido 19-oct) y al agrandar la
  // ventana se veia un cuadro del gato corrido en diagonal (LShinox). La ventana queda siempre de 400x600.
  window.companero.compacto = () => cola;   // tamano() queda por si se retoma
  // (22-oct, LShinox aprobo el prototipo) Ajustes DENTRO de la mascota: la misma ventana transparente se agranda
  // mientras el panel esta abierto (asi la mascota y el panel se animan juntos, sin dos ventanas que sincronizar)
  let enPanel = false;
  window.companero.panel = {
    geometria: async () => {
      const p = await yo.outerPosition(), s = await yo.outerSize(), f = await yo.scaleFactor();
      let a = null;
      try { const m = (await T.window.currentMonitor()) || (await T.window.primaryMonitor());
        if (m) { const k = m.scaleFactor || 1, w = m.workArea || { position: m.position, size: m.size };
          a = { x0: w.position.x / k, y0: w.position.y / k, x1: (w.position.x + w.size.width) / k, y1: (w.position.y + w.size.height) / k }; } } catch (e) {}
      return { x: p.x / f, y: p.y / f, w: s.width / f, h: s.height / f, area: a || { x0: 0, y0: 0, x1: screen.availWidth, y1: screen.availHeight } };
    },
    bordes: async (r, si) => { enPanel = si; await inv("limites", r); zonaYa(); repintar(); },
    hub: (ruta, cuerpo) => hub(ruta, cuerpo).catch(e => ({ ok: false, error: String(e.message || e) })),
    leer: () => ({ pj: pjVis(conf.pj), color: conf.color || "negro", florCactus: conf.florCactus !== false, ojos: !!conf.ojos,
                   modo: conf.modo === "aviso" ? "aviso" : "siempre", sonido: conf.sonido !== false, idioma: conf.idioma || "es", nueva,
                   sueno: sueno().on, suenoMin: sueno().min, loNuevoVisto: conf.loNuevoVisto || "", capsula: !!conf.capsula,
                   animCompletas: animCompletas(), capsulaColor: capCol(), ojosGato: conf.ojosGato === "gato" ? "gato" : "gatoPro" }),
    poner: async (k, v) => {   // lo mismo que hacian los items del menu de la bandeja
      if (k === "sueno") { conf.sueno = !!v; guardar(); avisar("sueno", sueno()); return; }
      if (k === "suenoMin") { conf.suenoMin = +v; guardar(); avisar("sueno", sueno()); return; }
      if (k === "capsula") { conf.capsula = !!v; guardar(); avisar("capsula", conf.capsula); return; }
      if (k === "animCompletas") { conf.animCompletas = !!v; guardar(); aplicarAnimCompletas(); return; }   // solo en esta PC: no pasa por compartirPj()
      if (k === "loNuevoVisto") { conf.loNuevoVisto = String(v); guardar(); return; }   // (26-oct) "Lo nuevo" visto, por version
      if (k === "capsulaColor") { conf.capsulaColor = v === "negra" ? "negra" : "blanca"; guardar(); compartirPj(); avisar("capsulaColor", capCol()); return; }
      if (k === "pj" && !MOSTRAR_BROTE && /^brote/.test(v)) return;   // (lanzamiento) Brote oculto
      if (k === "pj" && /^gato/.test(v)) conf.ojosGato = v === "gato" ? "gato" : "gatoPro";   // (4.a vuelta) se recuerda con que ojos estaba el gato al pasar a Brote y volver
      if (k === "pj" || k === "color") { conf[k] = v; guardar(); compartirPj(); avisar("pj", pjEfectivo()); }
      else if (k === "florCactus") { conf.florCactus = !!v; guardar(); compartirPj(); avisar("pj", pjEfectivo()); }
      else if (k === "ojos") { conf.ojos = !!v; guardar(); avisar("ojos", conf.ojos); }
      else if (k === "modo") { conf.modo = v ? "aviso" : "siempre"; guardar(); avisar("modo", conf.modo); }
      else if (k === "sonido") { conf.sonido = !!v; guardar(); avisar("sonido", conf.sonido); }
      else if (k === "idioma") { conf.idioma = v; guardar(); menu(); window.fijarIdioma && fijarIdioma(v); }
      else if (k === "esquina") { conf.x = conf.y = null; guardar(); await esquina(); }
      else if (k === "conectar") { try { const r = await hub("/api/ticket", {}); if (r && r.ticket) inv("abrir_url", { url: HUB + "/conectar.html?t=" + encodeURIComponent(r.ticket) }); } catch (e) {} }
      else if (k === "reportar") hub("/api/reporte", {}).catch(() => {});
    },
  };
  yo.onMoved(async () => { if (enPanel) return; try { const p = await yo.outerPosition(), f = await yo.scaleFactor(); if (p.x < -10000 || p.y < -10000) return; conf.x = Math.round(p.x / f) - (chica ? DX : 0); conf.y = Math.round(p.y / f) - (chica ? DY : 0); guardar(); } catch (e) {} });

  async function esquina() {
    // (15-oct) con la ventana oculta currentMonitor() puede dar null: antes se usaba 1920x1080 fijo y la mascota quedaba
    // medio afuera en pantallas con escala (1536x864 reales). Ahora: monitor principal o, si no, el tamaño de la pantalla.
    let m = null;
    try { m = (await T.window.currentMonitor()) || (await T.window.primaryMonitor()) || (await T.window.availableMonitors())[0]; } catch (e) {}
    const f = m ? (m.scaleFactor || 1) : 1;
    const a = m && m.workArea ? m.workArea : m ? { position: m.position, size: m.size } : { position: { x: 0, y: 0 }, size: { width: screen.availWidth, height: screen.availHeight } };
    // (19-oct) +15 abajo: las patas del gato apoyan en la barra de tareas (antes quedaban ~25 px arriba)
    const x = a.position.x / f + a.size.width / f - 400 - 12, y = a.position.y / f + a.size.height / f - 600 + 15;
    await yo.setPosition(new T.dpi.LogicalPosition(x + (chica ? DX : 0), y + (chica ? DY : 0)));
  }

  // la esquina de abajo a la derecha de la ventana grande (400x600) tiene que verse entera en alguna pantalla (x, y: logicos)
  async function enPantalla(x, y) {
    try {
      return (await T.window.availableMonitors()).some(m => {
        const f = m.scaleFactor || 1, x0 = m.position.x / f, y0 = m.position.y / f, w = m.size.width / f, h = m.size.height / f;
        return x + 230 >= x0 && x + 400 <= x0 + w + 20 && y + 430 >= y0 && y + 600 <= y0 + h + 20;
      });
    } catch (e) { return false; }
  }

  // ---- (26-oct) cambio de escala de Windows (la mascota pasa a otro monitor, o cambias el % de escala) ----
  // En Coucou (#892) el bug era un lienzo que no seguia a devicePixelRatio. Aca el gato es SVG y el navegador lo vuelve a
  // rasterizar solo; lo que hay que cuidar es la VENTANA: se le devuelve su tamaño logico (400x600, o el chico) con la escala nueva
  // y, si quedo fuera de la pantalla, se manda a la esquina. Se escucha el evento de Tauri y, de respaldo, la media query de
  // resolucion VOLVIENDO A ARMARLA tras cada cambio (la que se crea una sola vez deja de avisar despues del primer cambio).
  let tEscala = null;
  const escalaCambio = () => { clearTimeout(tEscala); tEscala = setTimeout(reajustarEscala, 250); };
  async function reajustarEscala() {
    try {
      if (enPanel) { repintar(); return; }   // con Ajustes abierto, su geometria se calcula al abrirlo y cerrarlo
      const p = await yo.outerPosition(), f = await yo.scaleFactor();
      if (p.x < -10000 || p.y < -10000) return;   // oculta o minimizada: no hay nada que ajustar
      const x = p.x / f, y = p.y / f, [w, h] = chica ? CHICA : GRANDE;
      if (!(await enPantalla(x - (chica ? DX : 0), y - (chica ? DY : 0)))) { conf.x = conf.y = null; guardar(); await esquina(); }
      else { await inv("limites", { x, y, w, h }); zonaYa(); }
    } catch (e) {}
    repintar();
  }
  window.__escalaCambio = escalaCambio;   // para probarlo sin un segundo monitor
  try { yo.onScaleChanged(escalaCambio); } catch (e) {}
  (function rearmar() {
    try { matchMedia("(resolution: " + devicePixelRatio + "dppx)").addEventListener("change", () => { rearmar(); escalaCambio(); }, { once: true }); } catch (e) {}
  })();

  // ---- icono junto al reloj (bandeja) ----
  const EN = { "Ocultar": "Hide", "Mostrar": "Show", "Personaje": "Character", "Gato": "Cat", "Gato ojos lisos": "Cat plain eyes", "Ojos": "Eyes", "Con pupila": "With pupil", "Lisos": "Plain", "Brote": "Sprout", "Brote dos hojas": "Two-leaf sprout", "Brote otoñal": "Autumn sprout", "Brote cactus": "Cactus sprout", "Color del gato": "Cat color", "Negro": "Black", "Naranja": "Orange", "Brote cactus (bolitas)": "Cactus sprout (bumps)", "Cactus con flor": "Cactus with flower","Blanco": "White", "Gris azulado": "Blue gray", "Esmoquin": "Tuxedo",
    "Sonidos": "Sounds", "Quitar «No molestar»": "Turn off «Do not disturb»", "No molestar hasta mañana": "Do not disturb until tomorrow",
    "Volver a la esquina": "Back to the corner", "Reportar un problema": "Report a problem", "Bloquear celular": "Lock phone", "Desbloquear celular": "Unlock phone", "Conectar celular": "Connect phone", "Aparecer solo cuando me necesitan": "Only show up when I'm needed", "Actualizar a": "Update to", "Ojos siguen el mouse": "Eyes follow the mouse", "Salir": "Quit", "Ajustes…": "Settings…", "Editar animaciones": "Edit animations", "Mostrar aviso de prueba": "Show a test notice" };
  const L = s => (conf.idioma === "en" && EN[s]) || s;
  let bandeja = null, itemVisible = null;
  // (28-oct) en modo "Aparecer solo cuando me necesitan" la pagina escondia la ventana al instante: "Mostrar" es explicito, asi que se
  // avisa con manual=true (la pagina hace entrar al gato a escena) o "panel" (Ajustes: abrirPanel muestra la ventana el mismo)
  async function alternar(paraAjustes) {
    conf.visible = conf.visible === false; guardar();
    inv("visible", { si: conf.visible }); avisar("visible", conf.visible, conf.visible ? (paraAjustes === true ? "panel" : true) : undefined);
    // (21-oct, LShinox: "siempre sale Ocultar, nunca Mostrar") el menu nuevo de setMenu no siempre se refleja en
    // Windows: se cambia el texto del item que ya esta en la bandeja y despues se rearma igual
    try { if (itemVisible) await itemVisible.setText(L(conf.visible === false ? "Mostrar" : "Ocultar")); } catch (e) {}
    menu();
  }
  let nueva = null;   // version nueva disponible (GET /api/actualizacion)
  let celBloqueado = false;   // (26-oct) bloqueo del celular; si cambia desde el celular, el menu se rehace solo
  setInterval(async () => { try { if (!!(await hub("/api/bloqueo")).bloqueado !== celBloqueado) menu(); } catch (e) {} }, 30000);
  async function menu() {
    try { nueva = (await hub("/api/actualizacion")).version || null; } catch (e) {}
    try { celBloqueado = !!(await hub("/api/bloqueo")).bloqueado; } catch (e) {}
    const M = T.menu, it = (text, action, extra = {}) => M.MenuItem.new(Object.assign({ text, action }, extra));
    const pjs = await M.Submenu.new({ text: L("Personaje"), items: await Promise.all([["gato", "Gato"], ["brote5", "Brote"], ["broteDosHojas", "Brote dos hojas"], ["broteOtono", "Brote otoñal"], ["broteCactus", "Brote cactus"], ["broteCactusBolitas", "Brote cactus (bolitas)"]].filter(([v]) => MOSTRAR_BROTE || v === "gato").map(([v, n]) =>
      M.CheckMenuItem.new({ text: L(n), checked: v === "gato" ? /^gato/.test(pjVis(conf.pj)) : pjVis(conf.pj) === v,   // (27-oct, 4.a vuelta) "Gato" ya no lleva los ojos: van en el submenu "Ojos"
        action: () => { conf.pj = v === "gato" ? (/^gato/.test(conf.pj || "gatoPro") ? (conf.pj || "gatoPro") : (conf.ojosGato === "gato" ? "gato" : "gatoPro")) : v; guardar(); compartirPj(); avisar("pj", pjEfectivo()); menu(); } }))) });
    const ojosGato = await M.Submenu.new({ text: L("Ojos"), items: await Promise.all([["gatoPro", "Con pupila"], ["gato", "Lisos"]].map(([v, n]) =>
      M.CheckMenuItem.new({ text: L(n), checked: (pjVis(conf.pj) === "gato" ? "gato" : "gatoPro") === v, action: () => { conf.pj = v; conf.ojosGato = v; guardar(); compartirPj(); avisar("pj", pjEfectivo()); menu(); } }))) });
    const colores = await M.Submenu.new({ text: L("Color del gato"), items: await Promise.all([["negro", "Negro"], ["naranja", "Naranja"], ["blanco", "Blanco"], ["gris", "Gris azulado"], ["esmoquin", "Esmoquin"]].map(([v, n]) =>
      M.CheckMenuItem.new({ text: L(n), checked: (conf.color || "negro") === v, action: () => { conf.color = v; guardar(); compartirPj(); avisar("pj", pjEfectivo()); menu(); } }))) });
    const idioma = await M.Submenu.new({ text: "Idioma / Language", items: await Promise.all([["es", "Español"], ["en", "English"]].map(([v, n]) =>
      M.CheckMenuItem.new({ text: n, checked: (conf.idioma || "es") === v, action: () => { conf.idioma = v; guardar(); window.fijarIdioma && fijarIdioma(v); menu(); } }))) });
    itemVisible = await it(L(conf.visible === false ? "Mostrar" : "Ocultar"), alternar);
    // (22-oct, LShinox aprobo) MENU CORTO: lo de todos los dias; el resto vive en "Ajustes…" (panel con el diseño del
    // celular). El menu largo de antes queda abajo solo si conf.json trae "menuLargo": true.
    if (!conf.menuLargo) {
      const corto = [
        itemVisible,
        await it(L(noMolestar() ? "Quitar «No molestar»" : "No molestar hasta mañana"), () => {
          if (noMolestar()) conf.noMolestarHasta = 0; else { const m = new Date(); m.setDate(m.getDate() + 1); m.setHours(8, 0, 0, 0); conf.noMolestarHasta = m.getTime(); }
          guardar(); avisar("noMolestar", conf.noMolestarHasta); menu(); }),
        await M.PredefinedMenuItem.new({ item: "Separator" }),
        ...(nueva ? [await it("● " + L("Actualizar a") + " " + nueva, () => hub("/api/actualizar", {}).catch(() => {}))] : []),
        await it(L("Ajustes…"), () => { if (conf.visible === false) alternar(true); avisar("ajustes"); }),
        await it(L("Volver a la esquina"), () => { conf.x = conf.y = null; guardar(); esquina(); }),   // (26-oct, LShinox) tambien en el menu corto
        // (26-oct) bloqueo de emergencia del celular (app y Telegram); desbloquear solo se puede aqui
        await it(celBloqueado ? "🔒 " + L("Desbloquear celular") : L("Bloquear celular"), async () => {
          try { await hub("/api/bloqueo", { activo: !celBloqueado }); } catch (e) {}
          menu(); }),
        await M.PredefinedMenuItem.new({ item: "Separator" }),
        await it(L("Salir"), () => inv("salir")),
      ];
      const mc = await M.Menu.new({ items: corto });
      if (bandeja) return bandeja.setMenu(mc);
      try { await T.tray.TrayIcon.removeById("companero"); } catch (e) {}
      bandeja = await T.tray.TrayIcon.new({ id: "companero", tooltip: "Kodama", icon: await T.app.defaultWindowIcon(), menu: mc,
        showMenuOnLeftClick: false, action: e => { if (e.type === "Click" && e.button === "Left" && e.buttonState === "Up") alternar(); } });
      return;
    }
    const items = [
      itemVisible, pjs, ...(pjVis(conf.pj).startsWith("gato") ? [ojosGato, colores] : []),   // (22-oct) el color es solo del gato; (4.a vuelta) los ojos tambien
      ...(MOSTRAR_BROTE && (conf.pj || "").startsWith("broteCactus") ? [await M.CheckMenuItem.new({ text: L("Cactus con flor"), checked: conf.florCactus !== false,
        action: () => { conf.florCactus = conf.florCactus === false; guardar(); compartirPj(); avisar("pj", pjEfectivo()); menu(); } })] : []),
      await M.CheckMenuItem.new({ text: L("Ojos siguen el mouse"), checked: !!conf.ojos, action: () => { conf.ojos = !conf.ojos; guardar(); avisar("ojos", conf.ojos); menu(); } }),
      // (21-oct) escondida hasta que un chat te necesita (sale del piso, avisa y se vuelve a ir)
      await M.CheckMenuItem.new({ text: L("Aparecer solo cuando me necesitan"), checked: conf.modo === "aviso", action: () => {
        conf.modo = conf.modo === "aviso" ? "siempre" : "aviso"; guardar(); avisar("modo", conf.modo); menu(); } }),
      await M.MenuItem.new({ text: L("Mostrar aviso de prueba"), action: () => avisar("atajo", "prueba") }),   // (16-oct) para sacarle captura
      await M.CheckMenuItem.new({ text: L("Sonidos"), checked: conf.sonido !== false, action: () => { conf.sonido = conf.sonido === false; guardar(); avisar("sonido", conf.sonido); menu(); } }),
      await it(L(noMolestar() ? "Quitar «No molestar»" : "No molestar hasta mañana"), () => {
        if (noMolestar()) conf.noMolestarHasta = 0; else { const m = new Date(); m.setDate(m.getDate() + 1); m.setHours(8, 0, 0, 0); conf.noMolestarHasta = m.getTime(); }
        guardar(); avisar("noMolestar", conf.noMolestarHasta); menu(); }),
      // (22-oct, LShinox) "Editar animaciones" ya no se muestra a los usuarios (se usan las animaciones que damos);
      // queda solo si conf.json de la mascota trae "editarAnimaciones": true (por si alguien lo pide)
      ...(conf.editarAnimaciones ? [await it(L("Editar animaciones"), async () => {   // (15-oct) ticket de un solo uso
        try { const r = await hub("/api/ticket", {}); if (r && r.ticket) inv("abrir_url", { url: HUB + "/ajustes.html?t=" + encodeURIComponent(r.ticket) }); } catch (e) {}
      })] : []),
      await it(L("Volver a la esquina"), () => { conf.x = conf.y = null; guardar(); esquina(); }),
      idioma,
      // (21-oct) asistente para conectar el celular (Telegram y/o la app con Tailscale); mismo ticket que "Editar animaciones"
      await it(L("Conectar celular"), async () => {
        try { const r = await hub("/api/ticket", {}); if (r && r.ticket) inv("abrir_url", { url: HUB + "/conectar.html?t=" + encodeURIComponent(r.ticket) }); } catch (e) {}
      }),
      // (21-oct) soporte por GitHub: arma el reporte (zip en el Escritorio) y abre el formulario del issue
      await it(L("Reportar un problema"), () => hub("/api/reporte", {}).catch(() => {})),
      // (21-oct) solo aparece si el hub encontro una version nueva en GitHub; instalar es siempre a pedido
      ...(nueva ? [await it(L("Actualizar a") + " " + nueva, () => hub("/api/actualizar", {}).catch(() => {}))] : []),
      await M.PredefinedMenuItem.new({ item: "Separator" }),
      await it(L("Salir"), () => inv("salir")),
    ];
    const m = await M.Menu.new({ items });
    if (bandeja) return bandeja.setMenu(m);
    try { await T.tray.TrayIcon.removeById("companero"); } catch (e) {}   // tras recargar la pagina (cambio de idioma)
    bandeja = await T.tray.TrayIcon.new({ id: "companero", tooltip: "Kodama", icon: await T.app.defaultWindowIcon(), menu: m,
      showMenuOnLeftClick: false, action: e => { if (e.type === "Click" && e.button === "Left" && e.buttonState === "Up") alternar(); } });
  }

  // ---- atajos globales: Ctrl+Shift+F10 globo, Ctrl+Shift+F11 responder al asomo ----
  async function atajos() {
    const G = T.globalShortcut;
    try { await G.unregisterAll(); } catch (e) {}   // tras recargar la pagina
    for (const [k, que] of [["Control+Shift+F10", "globo"], ["Control+Shift+F11", "asomo"]]) {
      try { await G.register(k, e => { if (!e || e.state === "Pressed") avisar("atajo", que); }); } catch (e) { console.log("atajo ocupado", k); }
    }
    // (22-oct) Ctrl+Shift+F12 abre/cierra Ajustes (atajo; tambien sirve para probarlo)
    try { await G.register("Control+Shift+F12", e => { if (!e || e.state === "Pressed") { if (conf.visible === false) alternar(true); avisar("ajustes"); } }); } catch (e) {}
  }

  // arranque: conf, posicion, idioma de la pagina, bandeja y atajos
  (async () => {
    try { conf = JSON.parse(await inv("conf_leer")); } catch (e) { conf = {}; }
    // (14-oct) la posicion guardada solo vale si cae dentro de alguna pantalla (si no, a la esquina)
    // la mascota vive en la esquina de abajo a la derecha de su ventana (400x600): esa esquina tiene que verse entera
    const dentro = conf.x != null && conf.y != null && await enPantalla(conf.x, conf.y);
    if (dentro) await yo.setPosition(new T.dpi.LogicalPosition(conf.x, conf.y)); else { conf.x = conf.y = null; await esquina(); }
    const id = conf.idioma === "en" ? "en" : "es";
    if ((localStorage.getItem("idioma") || "es") !== id && window.fijarIdioma) return fijarIdioma(id);
    // (27-oct) ya NO se muestra aca: la ventana sigue oculta hasta pintado() (ver `ventana` arriba); con "visible": false (la ocultaste desde la bandeja) se queda oculta
    confLista = true;
    if (conf.visible === false) inv("visible", { si: false });
    else if (pintadoPend) mostrarPintado();
    else tRespaldo = setTimeout(mostrarPintado, 3500);
    avisar("ojos", !!conf.ojos);   // (15-oct) ojos siguen el mouse (si lo activaste en la bandeja)
    avisar("sueno", sueno());      // (26-oct) ya con la conf leida (el alSueno inicial se dispara antes de leerla)
    avisar("capsula", !!conf.capsula);   // (27-oct) "Con cápsula"
    aplicarAnimCompletas();              // (5.a vuelta) "Animaciones completas" con la conf ya leida
    avisar("capsulaColor", capCol());
    menu(); atajos();
    // (22-oct, LShinox) la MISMA mascota en la PC y el celular: el hub guarda la eleccion (estado\personaje.json);
    // cada 8 s se mira si cambio en el celular. Lo que se elige en la bandeja se manda alla (ver compartirPj).
    hub("/api/personaje", {}).then(j => { if (!j.pj) compartirPj(); }).catch(() => {});   // la primera vez manda la de la PC
    setInterval(async () => {
      try {
        const j = await hub("/api/personaje", {});
        if (!j.pj) return;
        // (4.a vuelta) color de la capsula elegido en el celular: solo si el hub lo devuelve (el de hoy no lo guarda: ver ejecutor-log)
        if ((j.capsulaColor === "blanca" || j.capsulaColor === "negra") && j.capsulaColor !== capCol()) { conf.capsulaColor = j.capsulaColor; guardar(); avisar("capsulaColor", capCol()); }
        if (j.pj === conf.pj && (j.color || "negro") === (conf.color || "negro") && (j.florCactus !== false) === (conf.florCactus !== false)) return;
        if (/^gato/.test(j.pj)) conf.ojosGato = j.pj === "gato" ? "gato" : "gatoPro";
        conf.pj = j.pj; conf.color = j.color; conf.florCactus = j.florCactus !== false; guardar(); avisar("pj", pjEfectivo()); menu();
      } catch (e) {}
    }, 8000);
    // (21-oct) cada hora rearma el menu solo si cambio la version disponible (para que aparezca "Actualizar a vX")
    setInterval(async () => { try { if (((await hub("/api/actualizacion")).version || null) !== nueva) menu(); } catch (e) {} }, 3600000);
  })();
})();
