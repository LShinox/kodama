// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Kodama: el GATO ("gatoPro" y "gato", con sus colores) usa las animaciones hechas a mano en After Effects y exportadas a
// Lottie (web/lottie/*.json, lienzo 360x360, 30 fps, expresiones ya horneadas). Brote y los demas personajes NO cambian:
// siguen con el motor GSAP/SVG de personajes.js.
//
// Como se engancha: este archivo va DESPUES de personajes.js y lottie_light.min.js. Guarda el motor viejo como
// Companero.crearSVG y deja Companero.crear = crearLottie, que tiene la MISMA API (ir, gesto, pausar, tocar, cosquillas,
// acariciar, atrapar, mirarA, insignia, nombresGestos, estado, ocupado, destruir). Asi app.html y la mascota solo suman
// la linea <script>.
//
// VUELTA ATRAS (sin tocar codigo): localStorage "kodama.lottie" = "0" (y recargar), o window.KODAMA_LOTTIE = false, o
// ajustes.json con { "lottie": false }. Si lottie-web o un JSON no cargan, el gato cae solo al motor de siempre.
//
// Lo que NO cubre el gato Lottie (usa el motor de siempre): los accesorios por chat y cualquier personaje que no sea gato.
// (27-oct) Los JSON traen capas con "cl" (herramientas\lottie_capas.py): pupila (gatoPro), esmoquin (pecho blanco) y rayas (naranja).
// (27-oct, 3.a vuelta) Esas capas YA NO se ocultan por CSS: Tauri agrega un nonce a style-src de la CSP, y con el nonce el navegador ignora
// 'unsafe-inline' -> un <style> creado en tiempo de ejecucion se BLOQUEA y el negro mostraba las rayas y el pecho. Ahora `filtrar()` las
// QUITA del JSON antes de cargarlo (segun tipo y color) y la respiracion del dormido va con la API de animaciones (no usa CSS inyectado).
(function () {
  "use strict";
  const C = window.Companero;
  if (!C || !window.lottie || !window.gsap) return;   // sin lottie-web o sin motor base: no se toca nada
  const crearSVG = C.crear;
  const SRC = document.currentScript && document.currentScript.src;
  const BASE = SRC ? new URL("lottie/", SRC).href : "lottie/";
  // los cuadros los mandamos nosotros, siempre enteros (ver "reloj"): no hace falta tocar el subframe de lottie

  const R = (a, b) => a + Math.random() * (b - a), pick = a => a[Math.floor(Math.random() * a.length)];
  const NS = "http://www.w3.org/2000/svg";
  const ESTADOS = ["reposo", "trabajando", "escribio", "enviado", "dormido", "atascado"];
  // gestos que el director puede sortear por estado (los mismos nombres del motor viejo; "bostezo" ahora tambien es del gato)
  const LISTA = {
    reposo: ["mirar", "saltito", "estirarse", "balanceo", "sonrisa", "bostezo", "parpadeoLento", "radar", "ladeo", "acecho", "colita"],
    trabajando: ["leer", "pensar", "teclear", "idea"],
  };
  // "guino" (gesto_guino.json, hecho con herramientas\lottie_guino.py desde gesto_ladeo): NO entra en el sorteo del director; se usa
  // como variante de "enviado" (1 de cada 3) y como saludo al abrir la mascota / la app del celular.
  // "agarrar" (gesto_agarrar.json, 27-oct: las PATITAS pata-d/pata-i salen, agarran el archivo y lo abrazan): tampoco entra en el sorteo; lo dispara index.html al SOLTAR un archivo.
  const TODOS = new Set([...LISTA.reposo, ...LISTA.trabajando, "guino", "agarrar"]);
  const PROB_GUINO_ENVIADO = 1 / 3;
  // animaciones que tienen variante _b2; b3 = b2 en espejo (sin archivo nuevo)
  const CON_B2 = new Set(["estado_escribio", "estado_enviado", "gesto_leer", "gesto_pensar", "gesto_sonrisa"]);
  // gestos donde el cuerpo casi no se mueve: a veces se mezcla la cola (capa_colita.json) DETRAS
  const CON_COLITA = new Set(["leer", "mirar", "parpadeoLento", "radar"]);
  const PROB_COLITA = .4;
  // (27-oct, cola nueva) hay DOS colas para mezclar detras: capa_colita (la de siempre) y capa_colita_enviado (la cola de estado_enviado re-animada por el dueño, sin el salto del cuerpo:
  // solo la cola y sus nulos, con el cuerpo quieto). Se elige una al azar. ESTADOS quietos (reposo y trabajando, con la respiracion): tambien pueden llevarla, con menos probabilidad.
  // ESPEJO: la cola puede salir con scaleX -1 sobre su capa de forma INDEPENDIENTE del gesto (COLA_ESPEJO_LIBRE; si fuera de la cabeza se viera mal, queda en false y solo se espeja con el gesto).
  const COLAS = ["capa_colita", "capa_colita_enviado"];
  const COLA_ESTADOS = new Set(["reposo", "trabajando"]);
  const PROB_COLITA_ESTADO = .2, PROB_COLITA_ESPEJO = .5, COLA_ESPEJO_LIBRE = true;
  // estados cuyo archivo NO es un bucle (el cuadro final es otra pose que el inicial: dormido se acuesta, atascado se encoge).
  // (27-oct) ATASCADO: tras la primera vuelta repite el tramo [21, ultimo]: el cuadro 21 es la misma pose que el ultimo
  // (diferencia de pixeles 0,019 en 255; un paso de temblor mide 2,1), asi que el salto no se nota y sigue temblando.
  // Equivale a playSegments([21, fin]) pero con el reloj propio (30 fps, cuadros enteros).
  const BUCLE = { atascado: 21 };
  // DORMIDO: no tiene tramo limpio (se acuesta y termina asentandose; ningun cuadro posterior vuelve a otro anterior):
  // se queda en la ultima pose y RESPIRA con element.animate (escala 3,5 % vertical, 3,5 s; ver respirar()), no congelado.
  const RETENER = new Set(["dormido"]);
  // estados que se ven con menos cuadros (respiracion lenta): ahorra CPU y no se nota
  const LENTOS = new Set(["estado_reposo", "estado_dormido"]);

  // ---------- interruptor ----------
  function activo() {
    try { if (localStorage.getItem("kodama.lottie") === "0") return false; } catch (e) {}
    if (window.KODAMA_LOTTIE === false) return false;
    if ((window.CompaneroAjustes || {}).lottie === false) return false;
    return true;
  }
  const RE_GATO = /^gato(Pro)?(-(negro|naranja|blanco|gris|esmoquin))?$/;   // "gatoPro", "gato", "gatoPro-naranja", "gato-gris"…

  // ---------- colores: se recolorea el JSON antes de cargarlo ----------
  // mismos colores que COLORES_GATO de personajes.js (N = cuerpo, borde = contorno, ojo = ojos en los claros)
  const PAL = {
    // ojoLiso: color de los ojos LISOS (sin pupila). Naranja con ojos lisos = ojos blancos; con pupila (gatoPro) el ojo de siempre (ojo).
    naranja: { N: "#F2A65A", borde: "#B9702F", ojo: "#3A2A20", ojoLiso: "#FFFFFF", pup: "#120F14" },
    blanco: { N: "#FAF7F2", borde: "#8C8494", ojo: "#3A3340", pup: "#120F14" },
    gris: { N: "#77808F", borde: "#4C5361", ojo: null, pup: "#1F1C22" },   // (6.a vuelta) pupila oscura como la del negro (antes llevaba el color del cuerpo)
    // (8.a vuelta) NEGRO y ESMOQUIN: el cuerpo, los ojos y la pupila quedan como en el JSON (N = #1F1C22); solo el CONTORNO (silueta, orejas, trazos de la base de la oreja) pasa a un tono
    // apenas mas claro que el cuerpo (#433D4B) para que se note la linea sin parecer gris. La cola NO cambia (su borde #5A5364 sigue igual: `oscuro` la salta) ni la capsula (sin tapas de oreja).
    negro: { N: "#1F1C22", borde: "#433D4B", ojo: null, pup: null, oscuro: true },
    // (27-oct, celular2) `pata`: relleno de las patitas (pata-d/pata-i) = el blanco del pecho del esmoquin (#FAF7F2); el contorno sigue #433D4B. Los demas colores no lo definen.
    esmoquin: { N: "#1F1C22", borde: "#433D4B", ojo: null, pup: null, oscuro: true, pata: "#FAF7F2" },
  };
  // capas con "cl": se QUITAN del JSON segun el tipo (gatoPro = con pupila; gato = ojos lisos) y el color. Nada de CSS inyectado (ver arriba).
  function filtrar(d, color, pro) {
    const fuera = l => (l.cl === "pupila" && !pro) || (l.cl === "esmoquin" && color !== "esmoquin") || (l.cl === "rayas" && color !== "naranja");
    // (7.a vuelta) tapa-oreja (lottie_capas.py): oreja y cabeza como una sola pieza (tapa el contorno de la cabeza donde cruza la base de cada oreja, con un mate de la oreja).
    // (8.a vuelta) Ahora el contorno se ve en TODOS los colores (negro y esmoquin lo llevan un poco mas claro): las capas tapa-oreja se conservan siempre.
    const limpiar = ls => ls.filter(l => !fuera(l));
    if (Array.isArray(d.layers)) d.layers = limpiar(d.layers);
    for (const a of d.assets || []) if (Array.isArray(a.layers)) a.layers = limpiar(a.layers);
    return d;
  }
  const H2 = h => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255, 1];
  const IGUAL = (a, b) => Array.isArray(a) && a.length >= 3 && Math.abs(a[0] - b[0]) < .003 && Math.abs(a[1] - b[1]) < .003 && Math.abs(a[2] - b[2]) < .003;
  const ORIG = { cuerpo: [.1216, .1098, .1333], borde: [.3529, .3255, .3922], ojo: [.9569, .9451, .9176], ojoLinea: [1, .9569, .8706] };
  function recolorear(d, color, pro) {
    const P = PAL[color]; if (!P) return d;
    if (P.oscuro && d.w === 480) return d;   // capsula (aparecer/desaparecer_capsula): sin las capas de oreja, el contorno claro mostraria la linea entera; queda como estaba
    const cuerpo = H2(P.N), borde = H2(P.borde), ojo = P.ojo ? H2(P.ojo) : null;
    const ojoVisto = ojo && !pro && P.ojoLiso ? H2(P.ojoLiso) : ojo;   // ojos lisos (y sus parpados cerrados): ojoLiso si el color lo define
    const nuevo = (c, trazoDeContorno) => {
      if (IGUAL(c, ORIG.cuerpo)) return trazoDeContorno ? borde : cuerpo;
      if (IGUAL(c, ORIG.borde)) return borde;
      // (6.a vuelta) con pupila el OJO (relleno) queda crema como el del gato negro; solo se recolorean los trazos de ojo cerrado (arcos)
      if (ojoVisto && IGUAL(c, ORIG.ojoLinea)) return ojoVisto;
      if (ojoVisto && !pro && IGUAL(c, ORIG.ojo)) return ojoVisto;
      return null;
    };
    function pintar(items, contorno) {
      for (const s of items || []) {
        if (s.ty === "gr") { pintar(s.it, contorno); continue; }
        if ((s.ty !== "fl" && s.ty !== "st") || !s.c) continue;
        const trazo = s.ty === "st" && contorno;
        if (s.c.a === 1 && Array.isArray(s.c.k)) {   // animado: se recolorea cada fotograma clave
          for (const kf of s.c.k) for (const campo of ["s", "e"]) if (kf[campo]) { const n = nuevo(kf[campo], trazo); if (n) kf[campo] = n.slice(); }
        } else { const n = nuevo(s.c.k, trazo); if (n) s.c.k = n.slice(); }
      }
    }
    function rellenar(items, c) {   // solo los RELLENOS ("fl"); los trazos (contorno y deditos) quedan en #433D4B
      for (const s of items || []) {
        if (s.ty === "gr") { rellenar(s.it, c); continue; }
        if (s.ty !== "fl" || !s.c) continue;
        if (s.c.a === 1 && Array.isArray(s.c.k)) { for (const kf of s.c.k) for (const campo of ["s", "e"]) if (kf[campo]) kf[campo] = c.slice(); }
        else s.c.k = c.slice();
      }
    }
    const capas = d.w === 480 ? [] : [...(d.layers || [])];            // capsula: el fondo de la pastilla no es del gato
    for (const a of d.assets || []) capas.push(...(a.layers || []));
    const pup = P.pup ? H2(P.pup) : null;
    for (const l of capas) {
      if (l.ty !== 4) continue;
      if (l.cl === "pupila") {   // la pupila lleva su propio color (no el del cuerpo); el brillo queda blanco; el ojo grande es oscuro en los claros
        for (const g of l.shapes || []) {
          const c = g.nm === "pupila" ? pup : null;   // (6.a vuelta) el ojo grande ("ojo-pro") queda crema en TODOS los colores, como en el negro
          if (c) for (const it of g.it || []) if (it.ty === "fl") it.c.k = c.slice();
        }
        continue;
      }
      if (l.cl === "esmoquin" || l.cl === "rayas") continue;
      if (P.oscuro && /^cola/.test(l.nm || "")) continue;   // negro/esmoquin: la cola (borde #5A5364) queda como estaba
      pintar(l.shapes, /^(silueta|oreja|pata)/.test(l.nm || ""));   // (27-oct) pata-d/pata-i: mismo relleno y contorno que el cuerpo
      if (P.pata && /^pata-/.test(l.nm || "")) rellenar(l.shapes, H2(P.pata));   // esmoquin: patitas blancas como el pecho (solo el relleno)
    }
    return d;
  }

  // ---------- carga a pedido (JSON en memoria) ----------
  const textos = new Map();   // nombre -> Promise<string>
  function texto(nombre) {
    let p = textos.get(nombre);
    if (!p) {
      p = fetch(BASE + nombre + ".json").then(r => { if (!r.ok) throw new Error("lottie " + nombre + " " + r.status); return r.text(); });
      p.catch(() => textos.delete(nombre));
      textos.set(nombre, p);
    }
    return p;
  }
  const pelajeCocido = new Map();   // "color|p/l|nombre" -> texto ya filtrado y recoloreado (p = con pupila, l = ojos lisos)
  async function datos(nombre, color, pro) {
    const k = color + "|" + (pro ? "p" : "l") + "|" + nombre; let s = pelajeCocido.get(k);
    if (s === undefined) { const t = await texto(nombre); s = JSON.stringify(recolorear(filtrar(JSON.parse(t), color, !!pro), color, !!pro)); pelajeCocido.set(k, s); }
    return JSON.parse(s);   // lottie-web modifica el objeto: siempre una copia nueva
  }

  // insignia de estado (misma que Brote): circulo de color arriba a la derecha con el signo
  const INS = {
    permiso: ["#FFC94A", '<rect x="93.6" y="21" width="3" height="8" rx="1.5" fill="#3A3530"/><circle cx="95" cy="34" r="1.8" fill="#3A3530"/>'],
    pregunta: ["#5BC8F5", '<path d="M91 24.5 C91 20.5 99 20.5 99 25 C99 28 95 28 95 30.5" fill="none" stroke="#3A3530" stroke-width="3.2" stroke-linecap="round"/><circle cx="95" cy="34.5" r="1.8" fill="#3A3530"/>'],
    error: ["#FFC94A", '<rect x="93.6" y="21" width="3" height="8" rx="1.5" fill="#3A3530"/><circle cx="95" cy="34" r="1.8" fill="#3A3530"/>'],   // (9.a vuelta) "!" siempre ambar (permiso o error)
    termino: ["#8FCF5F", '<path d="M89.5 28.5 L93.5 32.5 L100.5 23.5" fill="none" stroke="#3A3530" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'],
  };

  function nuevo(host, tipoOriginal, color, conPupila) {
    let estado = null, visual = null, vivo = true, oculto = false, enGesto = false, muerto = false, viejo = null;
    let act = null, cola = null, ultCola = "", tok = 0, tokCola = 0, timers = [], ultGesto = "", ultVar = {}, caricia = false, toques = [], zzTok = 0;
    let faseG = null;   // (27-oct, idea de clawd #1018) gesto de la fase del chat: "teclear" (ejecutando) | "pensar" (pensando) | null. El estado sigue siendo "trabajando".
    const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); return t; };
    // (5.a vuelta) "Animaciones completas" (encendido por defecto, por aparato): encendido ignora prefers-reduced-motion; apagado lo respeta. Se mira en cada uso.
    const pocoMov = () => C.reducido ? C.reducido() : matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---- DOM: host > pj > cam (150 %: el lienzo de Lottie es 360 = 240 del personaje + 60 de borde por lado) > mira > animaciones
    host.innerHTML = "";
    if (getComputedStyle(host).position === "static") host.style.position = "relative";
    const pj = document.createElement("div"); pj.className = "lt-pj lt-c-" + color + (conPupila ? " lt-pro" : ""); pj.style.cssText = "position:absolute;inset:0;pointer-events:none";
    // (27-oct) window.KODAMA_LOTTIE_BAJA = fraccion del alto del host que se baja el gato Lottie (la mascota de PC la fija: el piso del
    // Lottie dormido quedaba 3,75 px sobre el borde inferior; medido en el host de 128 px). Sin fijar = 0 (celular, igual que antes).
    const baja = +window.KODAMA_LOTTIE_BAJA || 0;
    const cam = document.createElement("div"); cam.style.cssText = "position:absolute;left:-25%;top:" + (-25 + baja * 100).toFixed(3) + "%;width:150%;height:150%";
    const mira = document.createElement("div"); mira.style.cssText = "position:absolute;inset:0;transition:transform .18s ease-out;transform-origin:50% 75%";   // (27-oct) 75 %: el pie del gato, para que se incline (atrapar) sin despegarse del piso
    cam.appendChild(mira); pj.appendChild(cam); host.appendChild(pj);
    let insSvg = null, ins = null, insTipo = null, insPulso = null;

    // ---- una animacion = un div con su lottie; se manejan a mano los cuadros (bucle) para poder bajar los cuadros por segundo
    function crearEnt(nombre, z, espejo, rapido, mod) {   // mod (opcional): retoca la copia del JSON antes de cargarla (ver modAtento)
      return datos(nombre, color, conPupila).then(d => {
        if (muerto) return null;
        if (mod) mod(d);
        const cont = document.createElement("div");
        cont.style.cssText = "position:absolute;inset:0;opacity:0;z-index:" + z + (espejo ? ";transform:scaleX(-1)" : "");
        mira.appendChild(cont);
        const anim = window.lottie.loadAnimation({ container: cont, renderer: "svg", loop: false, autoplay: false, animationData: d,
          rendererSettings: { preserveAspectRatio: "xMidYMid meet", progressiveLoad: false } });
        anim.goToAndStop(0, true);
        return { nombre, cont, anim, espejo, ms: 0, ult: -1, total: Math.max(1, Math.round(anim.totalFrames)), fr: anim.frameRate || 30,
          salto: LENTOS.has(nombre) && !rapido ? 2 : 1, fin: false, muerta: false, alFin: null, bucle: null };
      });
    }
    // fundidos: los mueve el mismo reloj (no CSS transition), asi nunca quedan a medias si la ventana no pinta
    let fades = [];
    function fundir(e, b, ms, fin) {
      if (!ms || !vivo || document.hidden) { e.cont.style.opacity = String(b); if (fin) fin(); return; }
      fades = fades.filter(f => f.e !== e); fades.push({ e, a: +e.cont.style.opacity || 0, b, ms, t: 0, fin }); arrancar();
    }
    function terminarFundidos() { const l = fades; fades = []; for (const f of l) { f.e.cont.style.opacity = String(f.b); if (f.fin) f.fin(); } }
    function destruirEnt(e) { if (!e || e.destruida) return; if (e.debajo) { const d = e.debajo; e.debajo = null; destruirEnt(d); } e.destruida = true; e.muerta = true; fades = fades.filter(f => f.e !== e); try { if (e.resp) e.resp.cancel(); } catch (x) {} try { e.anim.destroy(); } catch (x) {} e.cont.remove(); }
    // respiracion del dormido (4.a vuelta): escala vertical 3,5 % (y 1,2 % a lo ancho) apoyada en el piso (50 % 75,3 % del lienzo), ciclo de 3,5 s,
    // con la API de animaciones del navegador (element.animate): NO usa CSS inyectado (la CSP de Tauri lo bloquea) ni el reloj propio de los cuadros.
    // La curva es un coseno (suave) en 15 pasos por segundo: asi la ventana transparente se repinta 15 veces por segundo y no 60 (el costo es por cuadro).
    // Sigue en el espejo (scaleX negativo, como el contenedor) y se pausa/continua desde pausar().
    const RESP_MS = 3500, RESP_FPS = 15, RESP_Y = .035, RESP_X = .012;
    let seguirRespirando = false;   // pausar(true, true): el gato "duerme" (cuadro fijo) pero la ventana sigue visible -> el dormido sigue respirando
    function respirar(e) {
      try {
        e.cont.style.transformOrigin = "50% 75.3%";
        const n = Math.round(RESP_MS / 1000 * RESP_FPS), sg = e.espejo ? -1 : 1, kf = [];
        for (let i = 0; i <= n; i++) {
          const k = .5 - .5 * Math.cos(2 * Math.PI * i / n);
          kf.push({ transform: "scale(" + (sg * (1 + RESP_X * k)).toFixed(4) + "," + (1 + RESP_Y * k).toFixed(4) + ")", easing: "steps(1, end)" });
        }
        e.resp = e.cont.animate(kf, { duration: RESP_MS, iterations: Infinity });
        if (!vivo && !seguirRespirando) e.resp.pause();
      } catch (x) {}
    }
    function mostrar(e, ms) { fundir(e, 1, ms); arrancar(); }
    function quitar(e, ms) {
      if (!e) return; e.muerta = true; e.fin = true;
      if (!ms) return destruirEnt(e);
      fundir(e, 0, ms, () => destruirEnt(e));
    }
    // (5.a vuelta) FUNDIDO "NUEVO ENCIMA DEL VIEJO": antes el viejo bajaba a 0 mientras el nuevo subia desde 0, y a la mitad del fundido el gato quedaba
    // semitransparente (~75 % de opacidad): se veian las orejas duplicadas y, con la colita mezclada DETRAS, la cola a traves de la cabeza ("lineas de las orejas
    // que se juntan o se duplican"). Ahora el viejo queda opaco y congelado, el nuevo sube ENCIMA (z-index 3) y el viejo se destruye al terminar. Mientras tanto el
    // nuevo guarda al viejo en `debajo`: si otro cambio lo destruye a medias, el viejo se va con el.
    function cambiar(e, ms) {
      const v = act; act = e; aplicarOjos(e);
      if (v && ms && vivo && !document.hidden && !v.destruida) {
        const z0 = e.cont.style.zIndex; e.cont.style.zIndex = "3";
        v.muerta = true; v.fin = true; v.alFin = null; e.debajo = v;
        fundir(e, 1, ms, () => { e.cont.style.zIndex = z0; e.debajo = null; destruirEnt(v); });
        arrancar(); return;
      }
      if (v) quitar(v, ms); mostrar(e, ms);
    }

    // ---- reloj: avanza los cuadros a mano (30 fps; 15 en los estados lentos). Sin nada activo, se apaga solo (0 % de CPU).
    let raf = 0, ultT = 0;
    function tick(t) {
      raf = 0;
      const dt = ultT ? Math.min(t - ultT, 100) : 16; ultT = t;
      const fin = [];
      for (const e of [act, cola]) {
        if (!e || e.fin || e.muerta) continue;
        e.ms += dt;
        if (e.bucle != null && e.ms * e.fr / 1000 >= e.total) e.ms -= Math.ceil((e.ms * e.fr / 1000 - e.total + .001) / (e.total - e.bucle)) * (e.total - e.bucle) * 1000 / e.fr;   // vuelve al tramo [bucle, fin]
        const f = Math.floor(e.ms * e.fr / 1000 / e.salto) * e.salto;
        if (f >= e.total) { e.fin = true; e.anim.goToAndStop(e.total - 1, true); fin.push(e); continue; }
        if (f !== e.ult) { e.ult = f; e.anim.goToAndStop(f, true); if (e === act && (ojoC[0] || ojoC[1])) aplicarOjos(e); }   // lottie reescribe el transform de la capa: se vuelve a sumar el offset de las pupilas
      }
      if (fades.length) {
        const hechos = [];
        for (const f of fades) { f.t += dt; const k = Math.min(1, f.t / f.ms); f.e.cont.style.opacity = String(f.a + (f.b - f.a) * k); if (k >= 1) hechos.push(f); }
        if (hechos.length) { fades = fades.filter(f => !hechos.includes(f)); for (const f of hechos) if (f.fin) f.fin(); }
      }
      for (const e of fin) if (e.alFin && !e.muerta) e.alFin(e);
      if (vivo && !document.hidden && (fades.length || [act, cola].some(e => e && !e.fin && !e.muerta))) raf = requestAnimationFrame(tick);
    }
    function arrancar() { if (!raf && vivo && !document.hidden && !muerto) { ultT = 0; raf = requestAnimationFrame(tick); } }
    function parar() { if (raf) cancelAnimationFrame(raf); raf = 0; terminarFundidos(); }
    const alVis = () => { if (document.hidden) parar(); else arrancar(); };
    document.addEventListener("visibilitychange", alVis);

    // ---- variantes: b1 / b2 / b3 (= b2 en espejo), sin repetir la misma dos veces seguidas
    function variante(base) {
      if (base === "gesto_guino") return { nombre: base, espejo: Math.random() < .5 };   // un solo archivo; el espejo guiña con el otro ojo
      if (!CON_B2.has(base)) return { nombre: base, espejo: false };
      const v = pick(["b1", "b2", "b3"].filter(x => x !== ultVar[base])); ultVar[base] = v;
      return v === "b1" ? { nombre: base, espejo: false } : { nombre: base + "_b2", espejo: v === "b3" };
    }

    function caer(motivo) {   // algo no cargo: se vuelve al motor de siempre, en el mismo lugar y estado
      if (viejo || muerto) return;
      try { console.warn("[lottie] vuelvo al motor viejo:", motivo && motivo.message || motivo); } catch (x) {}
      limpiar(); document.removeEventListener("visibilitychange", alVis);
      host.innerHTML = ""; viejo = crearSVG(host, tipoOriginal, null);
      if (estado) viejo.ir(estado); if (!vivo) viejo.pausar(true);
    }
    function limpiar() { parar(); timers.forEach(clearTimeout); timers = []; tok++; tokCola++; destruirEnt(act); destruirEnt(cola); act = cola = null; if (insSvg) { insSvg.remove(); insSvg = ins = null; } }

    // ---- estados (bucle) ----
    function ponerEstado(ms) {
      const mi = ++tok, base = "estado_" + visual, v = variante(base);
      crearEnt(v.nombre, 1, v.espejo).then(e => {
        if (!e) return; if (mi !== tok || muerto) return destruirEnt(e);
        enGesto = false; e.alFin = vuelta; if (BUCLE[visual] != null) e.bucle = BUCLE[visual];
        // (4.a vuelta) la respiracion NO se salta con "movimiento reducido": en la PC del dueño Windows tiene los efectos de animacion apagados y WebView2 reporta
        // prefers-reduced-motion: reduce, y por eso no se veia. Es lenta (3,5 s) y de 3,5 %: no es un movimiento que moleste; lo demas (gestos al azar, guiño) lo respeta solo con "Animaciones completas" APAGADO (5.a vuelta; encendido por defecto = lo ignora y hace todo).
        if (RETENER.has(visual)) respirar(e);
        cambiar(e, ms);
        colaEstado();
      }).catch(caer);
    }
    // (27-oct, cola nueva) estados quietos (reposo y trabajando respiran con el cuerpo casi fijo): a veces llevan la cola detras (~20 % por vuelta del estado); los demas estados la quitan
    function colaEstado() {
      if (!COLA_ESTADOS.has(visual)) { if (cola) quitarCola(150); return; }
      if (cola || enGesto || oculto || !vivo || muerto || pocoMov()) return;
      // un poco despues de que el estado termine su fundido de entrada (120 ms): con el cuerpo a medias de opacidad la cola se veria a traves
      if (Math.random() < PROB_COLITA_ESTADO) later(() => { if (!cola && !enGesto && !oculto && vivo && !muerto && COLA_ESTADOS.has(visual)) colita(false); }, 260);
    }
    function vuelta(e) {   // terminó una vuelta del estado: sortea la siguiente variante
      if (e !== act || e.muerta || muerto) return;
      if (RETENER.has(visual)) return;   // dormido: termina en la pose y se queda ahi (respira por CSS); atascado no llega aqui: es bucle
      if (estado === "enviado" && visual === "enviado") { visual = "reposo"; return ponerEstado(220); }   // el salto de "llegó tu respuesta" es UNA vez; luego respira
      const v = variante("estado_" + visual);
      if (v.nombre === e.nombre) { e.cont.style.transform = v.espejo ? "scaleX(-1)" : ""; e.espejo = v.espejo; e.ms = 0; e.ult = -1; e.fin = false; arrancar(); colaEstado(); }
      else { const mi = ++tok; crearEnt(v.nombre, 1, v.espejo).then(n => { if (!n) return; if (mi !== tok || muerto) return destruirEnt(n); n.alFin = vuelta; cambiar(n, 0); colaEstado(); }).catch(caer); }
    }

    // ---- gestos (una vez y vuelve al estado) ----
    function jugar(n) {
      if (viejo) return false;
      if (!TODOS.has(n) || oculto || !vivo || muerto) return false;
      const v = variante("gesto_" + n), mi = ++tok; enGesto = true; ultGesto = n;
      crearEnt(v.nombre, 2, v.espejo, true).then(e => {
        if (!e) return; if (mi !== tok || muerto) return destruirEnt(e);
        e.alFin = fin => { if (fin !== act) return; enGesto = false; if (cola && !COLA_ESPEJO_LIBRE && cola.espejo) quitar(cola, 250); ponerEstado(100); };
        cambiar(e, 60);
        if (cola && !CON_COLITA.has(n)) quitarCola(120);   // una cola de un estado/gesto anterior no sigue detras de un gesto con mucho movimiento
        if (CON_COLITA.has(n) && Math.random() < PROB_COLITA) colita(v.espejo);
      }).catch(() => { if (mi === tok) { enGesto = false; ponerEstado(0); } });   // un gesto que no carga no tumba al gato
      return true;
    }
    // elige cola + espejo sin repetir la misma combinacion dos veces seguidas
    function elegirCola(espejoGesto) {
      const op = [];
      for (const n of COLAS) for (const esp of (COLA_ESPEJO_LIBRE ? [false, true] : [!!espejoGesto])) if (n + "|" + esp !== ultCola) op.push([n, esp]);
      if (!op.length) return [COLAS[0], !!espejoGesto];
      if (!COLA_ESPEJO_LIBRE) return pick(op);
      const esp = Math.random() < PROB_COLITA_ESPEJO, delEsp = op.filter(x => x[1] === esp);
      return pick(delEsp.length ? delEsp : op);
    }
    function colita(espejoGesto, nombre, espejoForzado) {   // nombre/espejoForzado (opcionales): para probar una cola concreta
      const [n, espejo] = nombre ? [nombre, !!espejoForzado] : elegirCola(espejoGesto);
      const mc = ++tokCola;
      crearEnt(n, 0, espejo, true).then(e => {
        if (!e) return; if (mc !== tokCola || muerto) return destruirEnt(e);
        ultCola = n + "|" + espejo;
        const v = cola; cola = e; if (v) quitar(v, 0);
        e.alFin = f => { if (f === cola) { quitar(f, 150); cola = null; } };
        mostrar(e, 60);
      }).catch(() => {});
    }
    function quitarCola(ms) { tokCola++; if (cola) { quitar(cola, ms); cola = null; } }

    // ---- director: cada pocos segundos sortea un gesto del estado ----
    function director() {
      if (!vivo || viejo || muerto) return;
      const g = Object.assign({}, C.DEF.gestos, (window.CompaneroAjustes || {}).gestos || {});
      if (!pocoMov() && !enGesto && !oculto) {
        const lista = LISTA[estado];
        // (27-oct) mientras el chat ejecuta algo / piensa, el director prefiere SU gesto (teclear / pensar) en vez de sortear entre los 4
        if (lista) jugar(estado === "trabajando" && faseG && lista.includes(faseG) ? faseG : pick(lista.filter(n => n !== ultGesto)));
      }
      later(director, (estado === "trabajando" ? R(g.trabajandoMin, g.trabajandoMax) : R(g.reposoMin, g.reposoMax)) * 1000);
    }

    // ---- adornos de siempre (chispas, corazon, zeta) ----
    const A = C.adornos || {};
    function zetas() { const mi = ++zzTok; const zz = () => { if (mi !== zzTok || estado !== "dormido" || !vivo || muerto) return; A.zeta && A.zeta(host); later(zz, 1700); }; zz(); }

    // ---- API ----
    function ir(e) {
      if (viejo) return viejo.ir(e);
      if (!ESTADOS.includes(e)) return;
      estado = e; visual = e; zzTok++; quitarCola(150);
      if (e !== "trabajando") faseG = null;
      if (e === "enviado") later(() => { if (estado === "enviado") A.chispas && A.chispas(host); }, 450);
      if (e === "dormido") zetas();
      // "enviado": 1 de cada 3 veces es el guiño (y luego respira como reposo); si no se puede jugar, la animacion de siempre
      if (e === "enviado" && !pocoMov() && !oculto && vivo && Math.random() < PROB_GUINO_ENVIADO) { visual = "reposo"; if (jugar("guino")) return; visual = "enviado"; }
      if (!oculto) ponerEstado(120);
    }
    function pausar(si, respira) {   // respira = (4.a vuelta) la ventana sigue visible: el dormido no deja de respirar aunque el resto quede en cuadro fijo
      if (viejo) return viejo.pausar(si);
      vivo = !si; pj.classList.toggle("lt-pausa", si);
      seguirRespirando = !!(si && respira && window.KODAMA_RESPIRA_EN_SUENO !== false && estado === "dormido");
      if (act && act.resp) { try { if (si && !seguirRespirando) act.resp.pause(); else act.resp.play(); } catch (x) {} }   // la respiracion del dormido se pausa con el gato (salvo que la ventana siga visible)
      if (si) { timers.forEach(clearTimeout); timers = []; parar(); }
      else { arrancar(); later(director, R(1500, 3000)); if (estado === "dormido") zetas(); }
    }
    function insignia(tipo) {
      if (viejo) return viejo.insignia(tipo);
      if (tipo === insTipo) return; insTipo = tipo;
      if (!insSvg) {
        insSvg = document.createElementNS(NS, "svg"); insSvg.setAttribute("viewBox", "0 0 120 120");
        insSvg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none;z-index:5" + (oculto ? ";opacity:0" : "");
        ins =document.createElementNS(NS, "g"); ins.setAttribute("class", "insignia"); insSvg.appendChild(ins); host.appendChild(insSvg);
        gsap.set(ins, { svgOrigin: "95 28", scale: 0 });
      }
      if (insPulso) { insPulso.kill(); insPulso = null; }
      gsap.to(ins, { scale: 0, duration: .09, ease: "power2.in", overwrite: true, onComplete: () => {
        if (!tipo || !INS[tipo] || muerto) return;
        const anillo = matchMedia("(prefers-color-scheme: dark)").matches ? "#FFFDF8" : "#3A3530";
        ins.innerHTML = `<circle cx="95" cy="28" r="15" fill="${INS[tipo][0]}" stroke="${anillo}" stroke-width="3"/>` + INS[tipo][1];
        gsap.to(ins, { scale: 1, duration: .28, ease: "back.out(1.7)", delay: .1, overwrite: true });
        if (tipo === "permiso" || tipo === "pregunta") insPulso = gsap.to(ins, { scale: 1.08, duration: .6, yoyo: true, repeat: -1, ease: "sine.inOut", delay: .5 });
      } });
    }
    function cosquillas() { if (viejo) return viejo.cosquillas(); jugar("balanceo"); }
    function tocar() {
      if (viejo) return viejo.tocar();
      const ahora = performance.now(); toques = toques.filter(x => ahora - x < 700); toques.push(ahora);
      if (toques.length >= 3) { toques = []; return cosquillas(); }
      jugar("saltito");
    }
    function acariciar(si) {
      if (viejo) return viejo.acariciar(si);
      if (si) {
        if (caricia) return; caricia = true; jugar("sonrisa");
        later(() => { if (caricia) A.corazon && A.corazon(host); }, 1600);
      } else { if (!caricia) return tocar(); caricia = false; }
    }
    // (27-oct, arrastre) ATENTO: un archivo pasa por encima de la mascota (dragenter/dragover). NO hay archivo nuevo de After Effects: la pose sale del propio
    // estado_reposo (mismo rig: capas ojo-* / pupila-* / oreja-*) retocado en memoria (modAtento): OJOS grandes y ORejas abiertas hacia afuera, en bucle mientras dure el
    // arrastre. Al entrar hace un saltito (WAAPI sobre el contenedor: sin CSS inyectado) y se inclina hacia el cursor (mirarA); al salir vuelve a su estado.
    // Con "Animaciones completas" apagado y movimiento reducido en el sistema (pocoMov) no cambia de pose. Antes llamaba al gesto "radar" (casi no se notaba).
    const ATENTO_OJO = 1.38, ATENTO_OREJA = 16;
    function esc(p, k) {   // multiplica x e y de una propiedad de escala (fija o con fotogramas clave)
      const m = a => { if (Array.isArray(a) && typeof a[0] === "number" && a.length >= 2) { a[0] *= k; a[1] *= k; } };
      if (!p) return; if (p.a === 1 && Array.isArray(p.k)) for (const f of p.k) { m(f.s); m(f.e); } else m(p.k);
    }
    function rot(p, g) {   // suma grados a una propiedad de rotacion (fija o con fotogramas clave)
      if (!p) return;
      if (p.a === 1 && Array.isArray(p.k)) { for (const f of p.k) { if (Array.isArray(f.s) && typeof f.s[0] === "number") f.s[0] += g; if (Array.isArray(f.e) && typeof f.e[0] === "number") f.e[0] += g; } }
      else if (typeof p.k === "number") p.k += g;
    }
    function modAtento(d) {
      const capas = [...(d.layers || [])]; for (const a of d.assets || []) capas.push(...(a.layers || []));
      for (const l of capas) {
        const nm = l.nm || "", ks = l.ks; if (!ks) continue;
        if (/^(ojo|pupila)-[di]$/.test(nm)) esc(ks.s, ATENTO_OJO);
        else if (/^oreja-[di]$/.test(nm) || /^tapa-oreja-[di]-mate$/.test(nm)) rot(ks.r, /-d(-|$)/.test(nm) ? ATENTO_OREJA : -ATENTO_OREJA);   // la mascara de la oreja gira con la oreja
      }
      return d;
    }
    let atrapando = false;
    function ponerAtento(salto) {
      const mi = ++tok; enGesto = true; ultGesto = "atento"; quitarCola(80);
      crearEnt("estado_reposo", 2, false, false, modAtento).then(e => {
        if (!e) return; if (mi !== tok || muerto) return destruirEnt(e);
        e.bucle = 0; e.alFin = null;   // bucle del cuadro 0 al final: dura lo que dure el arrastre
        cambiar(e, 70);
        if (salto) { try { e.cont.animate([{ transform: "translateY(0)" }, { transform: "translateY(-7%)", offset: .38, easing: "cubic-bezier(.3,.9,.4,1)" }, { transform: "translateY(0)" }], { duration: 400, easing: "cubic-bezier(.5,0,.9,.6)" }); } catch (x) {} }
      }).catch(() => { if (mi === tok) { enGesto = false; ponerEstado(0); } });
    }
    function atrapar(si) {
      if (viejo) return viejo.atrapar(si);
      if (si) {
        if (pocoMov() || oculto || !vivo || muerto) return;
        const primera = !atrapando; atrapando = true;
        if (!(enGesto && ultGesto === "atento")) ponerAtento(primera);
      } else if (atrapando) {
        atrapando = false; mira.style.transform = "";
        if (enGesto && ultGesto === "atento") { ultGesto = ""; ponerEstado(120); }
      }
    }
    // (27-oct, ajuste 2) MIRAR con Lottie: antes solo se corria todo el cuerpo 1,6 px (no se notaba: "los ojos no siguen"). Ahora se mueven las PUPILAS (capas pupila-d/i; con ojos
    // lisos, las capas ojo-d/i): offset en unidades del lienzo (360) aplicado al <g> de cada capa por CSSOM (style.transform = translate(...) + la matriz que lottie escribio en el
    // atributo transform; se re-lee en cada cuadro porque lottie lo reescribe), con suavizado propio (rAF solo mientras se mueven). Max OJO_U unidades (~3,2 px con el gato normal, menos
    // dentro de la capsula). Sirve tambien fuera del arrastre ("Ojos siguen el mouse"). Atrapando, el cuerpo ademas se inclina hasta 6 grados hacia el cursor.
    const OJO_U = 7;
    let ojoT = [0, 0], ojoC = [0, 0], rafO = 0;
    function capasOjo(e) {
      if (e.capasOjo) return e.capasOjo;
      const out = [];
      try {
        const els = (e.anim.renderer && e.anim.renderer.elements) || [];
        const busca = re => { for (const el of els) if (el && el.data && re.test(el.data.nm || "") && el.layerElement) out.push(el.layerElement); };
        busca(/^pupila-[di]$/); if (!out.length) busca(/^ojo-[di]$/);
      } catch (x) {}
      return (e.capasOjo = out);
    }
    function aplicarOjos(e) {
      if (!e || e.destruida || e.muerta) return;
      const gs = capasOjo(e); if (!gs.length) return;
      const s = e.espejo ? -1 : 1;
      for (const g of gs) {
        if (!ojoC[0] && !ojoC[1]) { if (g.style.transform) g.style.transform = ""; continue; }
        const m = /matrix\(([^)]+)\)/.exec(g.getAttribute("transform") || "");
        g.style.transform = `translate(${(ojoC[0] * s).toFixed(2)}px, ${ojoC[1].toFixed(2)}px)` + (m ? ` matrix(${m[1]})` : "");
      }
    }
    function pasoOjos() {
      rafO = 0;
      for (const i of [0, 1]) { ojoC[i] += (ojoT[i] - ojoC[i]) * .35; if (Math.abs(ojoT[i] - ojoC[i]) < .05) ojoC[i] = ojoT[i]; }
      aplicarOjos(act);
      if (vivo && !muerto && (ojoC[0] !== ojoT[0] || ojoC[1] !== ojoT[1])) rafO = requestAnimationFrame(pasoOjos);
    }
    function mirarA(nx, ny) {
      if (viejo) return viejo.mirarA(nx, ny);
      const k = v => Math.max(-1, Math.min(1, v));
      if (nx == null) { mira.style.transform = ""; ojoT = [0, 0]; }
      else {
        const G = atrapando ? 1 : 2;   // fuera del arrastre el mouse llega a 1 en la mitad de la distancia (index.html lo normaliza con 220 px)
        ojoT = [k(nx * G) * OJO_U, k((ny || 0) * G) * OJO_U * .7];
        mira.style.transform = `translate(${(k(nx) * 1.6).toFixed(2)}px,${(k(ny || 0) * 1).toFixed(2)}px)` + (atrapando ? ` rotate(${(k(nx) * 6).toFixed(1)}deg)` : "");   // el cuerpo se corre 1-2 px hacia donde mira; atrapando, ademas se inclina hasta 6 grados
      }
      if (!rafO && vivo && !muerto) rafO = requestAnimationFrame(pasoOjos);
      else if (!vivo) { ojoC = ojoT.slice(); aplicarOjos(act); }
    }
    function gesto(n) { if (viejo) return viejo.gesto(n === "agarrar" ? "saltito" : n); return jugar(n); }
    // (27-oct, idea de clawd #1018) fase = "ejecutando" -> gesto_teclear | "pensando" -> gesto_pensar | otra cosa -> nada. NO cambia el estado:
    // solo adelanta el gesto cuando la fase cambia; despues el director lo repite entre gesto y gesto (cada 1,6-3,2 s) mientras dure.
    function fase(f) {
      if (viejo) return;
      const nueva = f === "ejecutando" ? "teclear" : f === "pensando" ? "pensar" : null;
      if (nueva === faseG) return;
      faseG = nueva;
      if (nueva && estado === "trabajando" && !enGesto && !oculto && vivo && !muerto && !pocoMov()) jugar(nueva);
    }
    function nombresGestos() { return viejo ? viejo.nombresGestos() : [...LISTA.reposo, ...LISTA.trabajando]; }
    // entrada / salida (aparecer_normal / desaparecer_normal): el modo "aparecer solo cuando me necesitan" las usa
    function intro(nombre, queda) {
      if (viejo) return Promise.resolve();
      const mi = ++tok; quitarCola(80); enGesto = true;
      return new Promise(res => {
        crearEnt(nombre, 2, false, true).then(e => {
          if (!e) return res(); if (mi !== tok || muerto) { destruirEnt(e); return res(); }
          e.alFin = f => { if (f !== act) return res(); if (queda) { res(); } else { enGesto = false; ponerEstado(150); res(); } };
          cambiar(e, 0);
        }).catch(() => { enGesto = false; if (!queda) ponerEstado(0); res(); });
      });
    }
    const velarInsignia = si => { if (insSvg) insSvg.style.opacity = si ? "0" : ""; };   // la insignia no se queda flotando sin gato
    function aparecer() { oculto = false; velarInsignia(false); return intro("aparecer_normal", false); }
    function desaparecer() { oculto = true; velarInsignia(true); return intro("desaparecer_normal", true); }
    function destruir() {
      if (viejo) return viejo.destruir();
      muerto = true; vivo = false; limpiar(); document.removeEventListener("visibilitychange", alVis);
      if (insPulso) insPulso.kill(); pj.remove();
    }

    later(director, R(1500, 3000));
    const colaPrueba = (n, esp) => { if (viejo || !COLAS.includes(n)) return false; colita(false, n, esp); return true; };   // solo para pruebas: fuerza una cola concreta
    return { ir, pausar, insignia, tocar, acariciar, gesto, fase, atrapar, mirarA, nombresGestos, cosquillas, aparecer, desaparecer, colaPrueba, lottie: true,
      get estado() { return viejo ? viejo.estado : estado; },
      get ocupado() { return viejo ? viejo.ocupado : enGesto; },
      get oculto() { return oculto; },
      destruir };
  }

  function crearLottie(host, tipo, acc) {
    const m = RE_GATO.exec(tipo || "");
    if (!m || acc || !activo()) return crearSVG(host, tipo, acc);   // Brote y demas, accesorios, interruptor apagado
    return nuevo(host, tipo, m[3] || "negro", !!m[1]);   // "gatoPro" = con pupila; "gato" = ojos lisos
  }

  // Cápsula (aparecer_capsula / desaparecer_capsula, lienzo 480x140): lista pero todavia SIN usar: la mascota real no tiene
  // modo cápsula. Uso futuro: Companero.lottieCapsula(div, "aparecer"|"desaparecer", "negro").then(ctl => …; ctl.destruir())
  C.lottieCapsula = function (host, cual, color) {
    return datos((cual === "desaparecer" ? "desaparecer" : "aparecer") + "_capsula", color || "negro", false).then(d => new Promise(res => {
      const anim = window.lottie.loadAnimation({ container: host, renderer: "svg", loop: false, autoplay: true, animationData: d,
        rendererSettings: { preserveAspectRatio: "xMidYMid meet" } });
      const ctl = { anim, destruir() { try { anim.destroy(); } catch (e) {} } };
      anim.addEventListener("complete", () => res(ctl));
    }));
  };

  C.crearSVG = crearSVG; C.crearLottie = crearLottie; C.crear = crearLottie;
})();
