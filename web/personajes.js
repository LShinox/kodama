// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Kodama v3 (13-oct-2026): Brote y Lucero como componente reusable.
// Uso: const c = Companero.crear(elemento, "brote"|"lucero", "juegos"|"musica"|"dnd"|null); c.ir("trabajando");
// Estados: reposo, trabajando, escribio (te escribió), enviado (llegó tu respuesta), dormido, atascado.
// Expresiones de ojos: normal, feliz (^ ^), dormido (— —), sorpresa (o o), triste (cejitas caídas), concentrado.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  // ---- AJUSTES (13-oct): todo lo que LShinox puede tocar desde el panel; valores por defecto = los actuales ----
  const DEF = {
    respiracion: { duracion: 1.75, amplitud: .035 },
    gestos: { reposoMin: 6, reposoMax: 10, trabajandoMin: 1.6, trabajandoMax: 3.2 },
    parpadeo: { cierre: .07, apertura: .13, cadaMin: 2.2, cadaMax: 5.4, doble: .22 },
    cara: { cambio: .12 },
    resorte: { rigidez: 60, freno: 9 },
    toque: { salto: 6, rebote: 1.7 },
    acurrucar: { cuerpo: 1.1, cola: 1.4 },
    mirar: { rango: 3.5, velocidad: .28 },
  };
  const AJ = () => { const u = window.CompaneroAjustes || {}; const o = {}; for (const k in DEF) o[k] = Object.assign({}, DEF[k], u[k] || {}); return o; };

  // ---------- dibujo ----------
  // estilos de ojo del gato: "invertido" (todo blanco, brillo negro), "pupila" (blanco con pupila grande mirando arriba),
  // "jiji" (ovalo blanco con pupila vertical al centro)
  const OJO_ESTILO = {
    invertido: (cx, cy, r) => `<ellipse cx="${cx}" cy="${cy}" rx="${r * .86}" ry="${r}" fill="#fff"/><circle cx="${cx + r * .56}" cy="${cy - r * .58}" r="${r * .46}" fill="#1f1c22"/>`,
    pupila: (cx, cy, r) => `<circle cx="${cx}" cy="${cy}" r="${r * 1.05}" fill="#fff"/><g class="pupila"><circle cx="${cx}" cy="${cy + r * .1}" r="${r * .6}" fill="#1f1c22"/><circle cx="${cx + r * .2}" cy="${cy - r * .1}" r="${r * .18}" fill="#fff"/></g>`,
    jiji: (cx, cy, r) => `<ellipse cx="${cx}" cy="${cy}" rx="${r * .8}" ry="${r * 1.05}" fill="#fff"/><g class="pupila"><ellipse cx="${cx}" cy="${cy + r * .08}" rx="${r * .3}" ry="${r * .56}" fill="#1f1c22"/><circle cx="${cx + r * .1}" cy="${cy - r * .22}" r="${r * .1}" fill="#fff"/></g>`,
  };
  // recorte de parpado para "concentrado": borde superior curvo a 30 % del alto del ojo
  const PARPADO = (id, cx1, cx2, cy, r) => `<clipPath id="${id}"><path d="M${cx1 - r * 1.6} ${cy - r * .05} Q${cx1} ${cy - r * .42} ${cx1 + r * 1.6} ${cy - r * .05} L${cx1 + r * 1.6} ${cy + r * 2} L${cx1 - r * 1.6} ${cy + r * 2} Z M${cx2 - r * 1.6} ${cy - r * .05} Q${cx2} ${cy - r * .42} ${cx2 + r * 1.6} ${cy - r * .05} L${cx2 + r * 1.6} ${cy + r * 2} L${cx2 - r * 1.6} ${cy + r * 2} Z"/></clipPath>`;
  const OJOS = (cx1, cx2, cy, r, col = "#2b2622", estilo = null, idc = "pc" + Math.random().toString(36).slice(2, 7)) => `
    <g class="ojos">
      ${estilo ? `<g class="exp exp-normal"><g class="parpado">${OJO_ESTILO[estilo](cx1, cy, r)}</g><g class="parpado">${OJO_ESTILO[estilo](cx2, cy, r)}</g></g>
      <g class="exp exp-sorpresa" opacity="0">${OJO_ESTILO[estilo](cx1, cy, r * 1.18)}${OJO_ESTILO[estilo](cx2, cy, r * 1.18)}</g>
      <g class="exp exp-concentrado" opacity="0"><defs>${PARPADO(idc, cx1, cx2, cy, r)}</defs><g clip-path="url(#${idc})">${OJO_ESTILO[estilo](cx1, cy, r)}${OJO_ESTILO[estilo](cx2, cy, r)}</g></g>` : `
      <g class="exp exp-normal">
        <g class="parpado"><ellipse cx="${cx1}" cy="${cy}" rx="${r * .86}" ry="${r}" fill="${col}"/><circle cx="${cx1 + r * .28}" cy="${cy - r * .34}" r="${r * .36}" fill="#fff"/><circle cx="${cx1 - r * .3}" cy="${cy + r * .4}" r="${r * .15}" fill="#fff" opacity=".9"/></g>
        <g class="parpado"><ellipse cx="${cx2}" cy="${cy}" rx="${r * .86}" ry="${r}" fill="${col}"/><circle cx="${cx2 + r * .28}" cy="${cy - r * .34}" r="${r * .36}" fill="#fff"/><circle cx="${cx2 - r * .3}" cy="${cy + r * .4}" r="${r * .15}" fill="#fff" opacity=".9"/></g>
      </g>
      `}
      <g class="exp exp-feliz" opacity="0">
        <path d="M${cx1 - r} ${cy + 2} Q${cx1} ${cy - r * 1.3} ${cx1 + r} ${cy + 2}" fill="none" stroke="${col}" stroke-width="3.4" stroke-linecap="round"/>
        <path d="M${cx2 - r} ${cy + 2} Q${cx2} ${cy - r * 1.3} ${cx2 + r} ${cy + 2}" fill="none" stroke="${col}" stroke-width="3.4" stroke-linecap="round"/>
      </g>
      <g class="exp exp-dormido" opacity="0">
        <path d="M${cx1 - r} ${cy + 1} Q${cx1} ${cy + r * .9} ${cx1 + r} ${cy + 1}" fill="none" stroke="${col}" stroke-width="3" stroke-linecap="round"/>
        <path d="M${cx2 - r} ${cy + 1} Q${cx2} ${cy + r * .9} ${cx2 + r} ${cy + 1}" fill="none" stroke="${col}" stroke-width="3" stroke-linecap="round"/>
      </g>

      ${estilo ? "" : `<g class="exp exp-sorpresa" opacity="0">
        <circle cx="${cx1}" cy="${cy}" r="${r * 1.05}" fill="${col}"/><circle cx="${cx1 + r * .35}" cy="${cy - r * .4}" r="${r * .4}" fill="#fff"/><circle cx="${cx1 - r * .35}" cy="${cy + r * .4}" r="${r * .18}" fill="#fff"/>
        <circle cx="${cx2}" cy="${cy}" r="${r * 1.05}" fill="${col}"/><circle cx="${cx2 + r * .35}" cy="${cy - r * .4}" r="${r * .4}" fill="#fff"/><circle cx="${cx2 - r * .35}" cy="${cy + r * .4}" r="${r * .18}" fill="#fff"/>
      </g>`}
      <g class="exp exp-triste" opacity="0">
        <ellipse cx="${cx1}" cy="${cy + 1}" rx="${r * .7}" ry="${r * .85}" fill="${col}"/><circle cx="${cx1 + r * .25}" cy="${cy - r * .2}" r="${r * .28}" fill="#fff"/>
        <ellipse cx="${cx2}" cy="${cy + 1}" rx="${r * .7}" ry="${r * .85}" fill="${col}"/><circle cx="${cx2 + r * .25}" cy="${cy - r * .2}" r="${r * .28}" fill="#fff"/>
        <path d="M${cx1 - r * 1.1} ${cy - r * 1.3} L${cx1 + r * .6} ${cy - r * 1.7}" stroke="${col}" stroke-width="2.4" stroke-linecap="round"/>
        <path d="M${cx2 + r * 1.1} ${cy - r * 1.3} L${cx2 - r * .6} ${cy - r * 1.7}" stroke="${col}" stroke-width="2.4" stroke-linecap="round"/>
      </g>
      ${estilo ? "" : `<g class="exp exp-concentrado" opacity="0"><defs>${PARPADO(idc, cx1, cx2, cy, r)}</defs><g clip-path="url(#${idc})">
        <ellipse cx="${cx1}" cy="${cy}" rx="${r * .86}" ry="${r}" fill="${col}"/><circle cx="${cx1 + r * .28}" cy="${cy - r * .34}" r="${r * .36}" fill="#fff"/>
        <ellipse cx="${cx2}" cy="${cy}" rx="${r * .86}" ry="${r}" fill="${col}"/><circle cx="${cx2 + r * .28}" cy="${cy - r * .34}" r="${r * .36}" fill="#fff"/>
      </g></g>`}
    </g>`;

  // accesorio por chat (se dibuja sobre la cabeza / al costado)
  // Accesorios v2 (13-oct, estudio iconos-ux §2.3): degradado propio, contorno del tono oscuro de su color,
  // sombra sobre el cuerpo y un brillo; nunca tapan los ojos. `pj` = "brote" | "lucero" (Lucero va mas arriba).
  function accesorio(acc, pj) {
    if (!acc) return "";
    const g = "a" + Math.random().toString(36).slice(2, 7), L = pj === "lucero";
    const grad = (id, a, b) => `<linearGradient id="${g}${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
    if (acc === "juegos") {
      const dy = L ? -6 : 0, c = L ? "#cdbdf5" : "#a9db7c";
      return `<g class="accesorio" data-acc="juegos"><defs>${grad("c", "#7C8BF7", "#4F5CCB")}</defs><g transform="translate(0 ${dy})">
        <ellipse cx="60" cy="114" rx="22" ry="3" fill="#000" opacity=".12"/>
        <circle cx="40" cy="103" r="8" fill="url(#${g}c)" stroke="#3A43A0" stroke-width="2.2"/><circle cx="80" cy="103" r="8" fill="url(#${g}c)" stroke="#3A43A0" stroke-width="2.2"/>
        <rect x="38" y="92" width="44" height="20" rx="10" fill="url(#${g}c)" stroke="#3A43A0" stroke-width="2.2"/>
        <rect x="44.5" y="98" width="9" height="3.4" rx="1.2" fill="#fff"/><rect x="47.3" y="95.2" width="3.4" height="9" rx="1.2" fill="#fff"/>
        <circle class="boton" cx="72" cy="98" r="2.8" fill="#FFC94A"/><circle class="boton" cx="78" cy="103" r="2.8" fill="#F2879B"/>
        <ellipse cx="60" cy="95" rx="12" ry="1.6" fill="#fff" opacity=".45"/>
        <circle cx="35" cy="98" r="4.2" fill="${c}" stroke="#3a3530" stroke-width="1.6"/><circle cx="85" cy="98" r="4.2" fill="${c}" stroke="#3a3530" stroke-width="1.6"/>
      </g></g>`;
    }
    if (acc === "musica") {
      const banda = L ? "M25 62 C22 30 98 30 95 62" : "M24 74 C22 38 98 38 96 74", y = L ? 64 : 76, ry = L ? 10 : 11, rx = L ? 6.5 : 7;
      return `<g class="accesorio" data-acc="musica"><defs>${grad("p", "#F7A3B3", "#E0667F")}</defs>
        <path d="${banda}" fill="none" stroke="#4A4458" stroke-width="5.5" stroke-linecap="round"/>
        <path d="${banda}" fill="none" stroke="#7A7088" stroke-width="1.6" stroke-linecap="round" transform="translate(0 -1.5)"/>
        <g class="almohadilla"><ellipse cx="${L ? 22 : 21}" cy="${y}" rx="${rx}" ry="${ry}" fill="url(#${g}p)" stroke="#B8465F" stroke-width="2.2"/><ellipse cx="${L ? 22 : 21}" cy="${y}" rx="3.6" ry="6.5" fill="#FFC9D4"/></g>
        <g class="almohadilla"><ellipse cx="${L ? 98 : 99}" cy="${y}" rx="${rx}" ry="${ry}" fill="url(#${g}p)" stroke="#B8465F" stroke-width="2.2"/><ellipse cx="${L ? 98 : 99}" cy="${y}" rx="3.6" ry="6.5" fill="#FFC9D4"/></g>
      </g>`;
    }
    if (acc === "dnd") {
      const dy = L ? -8 : 0;
      return `<g class="accesorio" data-acc="dnd"><defs>${grad("d", "#B79CF2", "#8B6CE0")}</defs><g transform="translate(0 ${dy})"><g class="dado">
        <ellipse cx="21" cy="113" rx="12" ry="2.5" fill="#000" opacity=".12"/>
        <path d="M19 84 L31 91 L31 105 L19 112 L7 105 L7 91 Z" fill="url(#${g}d)" stroke="#5B43A8" stroke-width="2.2" stroke-linejoin="round"/>
        <path d="M19 91 L26 103 L12 103 Z" fill="#D6C4FA" opacity=".6"/>
        <path d="M19 91 L19 84 M26 103 L31 105 M12 103 L7 105 M19 91 L31 91 M19 91 L7 91 M26 103 L19 112 M12 103 L19 112" stroke="#5B43A8" stroke-width="1.4" stroke-linecap="round"/>
        <ellipse cx="14" cy="89" rx="3.5" ry="1.6" fill="#fff" opacity=".5" transform="rotate(-30 14 89)"/>
      </g></g></g>`;
    }
    if (acc === "instalaciones") {
      const dy = L ? -9 : 0;
      return `<g class="accesorio" data-acc="instalaciones"><defs>${grad("h", "#FFD768", "#FFB300")}</defs><g transform="translate(0 ${dy})"><g class="casco">
        <path d="M27 57 C27 27 93 27 93 57 Z" fill="url(#${g}h)" stroke="#B5780B" stroke-width="2.2" stroke-linejoin="round"/>
        <rect x="27" y="45" width="66" height="3.5" fill="#3A3530" opacity=".25"/>
        <rect x="56" y="31" width="8" height="24" rx="2" fill="#E59A00"/>
        <rect x="23" y="55" width="74" height="7" rx="3.5" fill="url(#${g}h)" stroke="#B5780B" stroke-width="2.2"/>
        <ellipse class="destello" cx="42" cy="40" rx="6" ry="3" fill="#fff" opacity=".5" transform="rotate(-25 42 40)"/>
      </g></g></g>`;
    }
    return "";
  }

  const SVG = {
    // Brote v3: más redondo (cabeza grande, cuerpo de gota), contorno marrón suave, ojos bajos y separados
    brote: (acc) => `
      <svg viewBox="0 0 120 120" class="pj pj-brote">
        <ellipse class="sombra" cx="60" cy="112" rx="28" ry="4" fill="#3a3530" opacity=".10"/>
        <g class="mueve"><g class="cuerpo">
          <g class="hoja">
            <path d="M60 30 C47 27 43 11 57 5 C69 11 70 25 60 30 Z" fill="#8fcf5f" stroke="#3a3530" stroke-width="2.6" stroke-linejoin="round"/>
            <path d="M60 28 C59 21 59 15 59.5 10" fill="none" stroke="#5e9c3a" stroke-width="2" stroke-linecap="round"/>
          </g>
          <path class="silueta" d="M60 29 C88 29 101 52 100 76 C99 100 82 109 60 109 C38 109 21 100 20 76 C19 52 32 29 60 29 Z" fill="#a9db7c" stroke="#3a3530" stroke-width="3"/>
          <ellipse cx="60" cy="83" rx="30" ry="24" fill="#f7f1dd"/>
          ${OJOS(48, 72, 74, 6.2)}
          ${accesorio(acc, "brote")}
        </g></g>
      </svg>`,
    // Lucero v3: cúpula opaca y redonda, luz como "corazón" interno, 3 patitas-tentáculo cortas, una sola antena con estrella
    lucero: (acc) => `
      <svg viewBox="0 0 120 120" class="pj pj-lucero">
        <defs><radialGradient id="glw-${Math.random().toString(36).slice(2, 7)}" class="glwdef"><stop offset="0" stop-color="#fff3b0" stop-opacity=".95"/><stop offset=".6" stop-color="#ffe27a" stop-opacity=".45"/><stop offset="1" stop-color="#ffd659" stop-opacity="0"/></radialGradient></defs>
        <ellipse class="sombra" cx="60" cy="114" rx="24" ry="4" fill="#3a3530" opacity=".10"/>
        <g class="mueve"><g class="cuerpo">
          <g class="tentaculos">
            <path class="tent" d="M45 84 C42 94 47 99 44 106" fill="none" stroke="#b7a3ec" stroke-width="7" stroke-linecap="round"/>
            <path class="tent" d="M60 86 C58 96 62 101 60 108" fill="none" stroke="#b7a3ec" stroke-width="7" stroke-linecap="round"/>
            <path class="tent" d="M75 84 C78 94 73 99 76 106" fill="none" stroke="#b7a3ec" stroke-width="7" stroke-linecap="round"/>
          </g>
          <g class="antena">
            <path d="M60 30 C60 22 64 18 66 14" fill="none" stroke="#3a3530" stroke-width="2.6" stroke-linecap="round"/>
            <path class="estrella" d="M67 5 L69 10 L74 10.5 L70 13.5 L71.5 18.5 L67 15.5 L62.5 18.5 L64 13.5 L60 10.5 L65 10 Z" fill="#ffd659" stroke="#3a3530" stroke-width="1.8" stroke-linejoin="round"/>
          </g>
          <path class="silueta" d="M20 82 C16 48 36 29 60 29 C84 29 104 48 100 82 C90 91 30 91 20 82 Z" fill="#cdbdf5" stroke="#3a3530" stroke-width="3" stroke-linejoin="round"/>
          <ellipse class="luz" cx="60" cy="78" rx="24" ry="10" fill="#ffd659" opacity=".6"/>
          ${OJOS(47, 73, 60, 6)}
          ${accesorio(acc, "lucero")}
        </g></g>
      </svg>`,
  };

  // ---------- versiones 4 (mochi: más redondo y apretable) y 5 (peluche: borde de felpa y costura) ----------
  const FELPA = () => "";   // (13-oct) sin filtro: el feTurbulence calentaba el iPhone; la felpa ahora es un trazo punteado
  const uid = () => Math.random().toString(36).slice(2, 7);
  // contorno peludo: recorre un ovalo y alterna puntas cortas; se calcula una sola vez al crear el personaje
  function pelo(cx, cy, rx, ry, desde = 0, hasta = 360, puntas = 44, largo = 3.2) {
    // borde de nube/peluche: arquitos suaves (curvas Q) hacia afuera, con largo apenas variable
    const pt = (ang, k) => [cx + Math.cos(ang) * rx * k, cy + Math.sin(ang) * ry * k];
    let [x0, y0] = pt(desde * Math.PI / 180, 1), d = `M${x0.toFixed(1)} ${y0.toFixed(1)}`;
    for (let i = 1; i <= puntas; i++) {
      const a1 = (desde + (hasta - desde) * i / puntas) * Math.PI / 180, am = (desde + (hasta - desde) * (i - .5) / puntas) * Math.PI / 180;
      const k = 1 + largo * (0.8 + Math.random() * 0.4) / Math.max(rx, ry);
      const [qx, qy] = pt(am, k), [x1, y1] = pt(a1, 1);
      d += ` Q${qx.toFixed(1)} ${qy.toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`;
    }
    return d + (hasta - desde >= 360 ? " Z" : "");
  }
  const CUERPO_BROTE = "M60 37 C86 37 100 56 100 80 C100 99 86 105 60 105 C34 105 20 99 20 80 C20 56 34 37 60 37 Z";
  const FILTRO_PELO = '<filter id="fp" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="2.6"/></filter>';
  // (21-oct, LShinox) variantes del Brote: el de siempre, "dos hojas" abiertas, "otoñal" (naranja) y "cactus" (sin hoja,
  // con espinitas suaves y una florcita). Misma silueta y esqueleto: todas usan las mismas animaciones.
  const TEMAS_BROTE = {
    verde:  { c1: "#D6F0BC", c2: "#B2DD8C", linea: "#7fb35a", panza1: "#F6FBEA", panza2: "#DDF0C2", sombra: "#3E6B2A", hoja1: "#8fcf5f", hoja2: "#a3dc74" },
    otono:  { c1: "#FBE2A8", c2: "#F2BE6A", linea: "#C98A3A", panza1: "#FFF8E8", panza2: "#FCE7C0", sombra: "#8A5A1E", hoja1: "#F08A2E", hoja2: "#F6A949" },
    cactus: { c1: "#B9DE9A", c2: "#86BF66", linea: "#4E7D3A", panza1: "#EEF7E2", panza2: "#D3EBBE", sombra: "#2E5222", hoja1: "", hoja2: "" },
  };
  const peloURL = {};
  function hornearPelo(tema) {
    if (typeof document === "undefined" || peloURL[tema] !== undefined) return;
    peloURL[tema] = null;
    const T = TEMAS_BROTE[tema], g = `<linearGradient id="gp" x1=".25" y1="0" x2=".75" y2="1"><stop offset="0" stop-color="${T.c1}"/><stop offset="1" stop-color="${T.c2}"/></linearGradient>`;
    const s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 132 132" width="528" height="528"><defs>${FILTRO_PELO}${g}</defs><path d="${CUERPO_BROTE}" fill="url(#gp)" stroke="${T.linea}" stroke-width="2.6" filter="url(#fp)"/></svg>`;
    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas"); c.width = c.height = 528; c.getContext("2d").drawImage(img, 0, 0);
        peloURL[tema] = c.toDataURL("image/png");
        document.querySelectorAll(`.pelo-vivo[data-tema="${tema}"]`).forEach(el => {   // los ya dibujados pasan a la imagen
          const im = document.createElementNS(NS, "image");
          im.setAttribute("class", "silueta"); im.setAttribute("href", peloURL[tema]);
          ["x", "y"].forEach(k => im.setAttribute(k, "-6")); ["width", "height"].forEach(k => im.setAttribute(k, "132"));
          el.replaceWith(im);
        });
      } catch (e) {}
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s);
  }
  hornearPelo("verde");
  function cuerpoPeludo(f, tema = "verde") {
    hornearPelo(tema);
    if (peloURL[tema]) return `<image class="silueta" href="${peloURL[tema]}" x="-6" y="-6" width="132" height="132"/>`;
    return `<defs>${FILTRO_PELO.replace('id="fp"', `id="fp${f}"`)}</defs><path class="silueta pelo-vivo" data-tema="${tema}" d="${CUERPO_BROTE}" fill="url(#bc${f})" stroke="${TEMAS_BROTE[tema].linea}" stroke-width="2.6" filter="url(#fp${f})"/>`;
  }
  // (21-oct, 2.a vuelta de LShinox) flor del cactus: 5 petalos con degrade y centro amarillo, apoyada en la coronilla
  function florCactus(linea, f) {
    const pet = [0, 72, 144, 216, 288].map(a => `<ellipse cx="60" cy="27.6" rx="3.3" ry="5.2" transform="rotate(${a} 60 32.6)" fill="url(#fl${f})" stroke="${linea}" stroke-width="1.3"/>`).join("");
    return `<g class="hoja"><defs><radialGradient id="fl${f}" cx=".5" cy=".85" r=".9"><stop offset="0" stop-color="#F48FB0"/><stop offset="1" stop-color="#FDD3DF"/></radialGradient></defs>
            <g transform="rotate(-12 60 34)">${pet}<circle cx="60" cy="32.6" r="2.9" fill="#FFD95A" stroke="${linea}" stroke-width="1.1"/>
            <circle cx="59" cy="31.8" r=".7" fill="#E9A92A"/><circle cx="61.2" cy="33.2" r=".7" fill="#E9A92A"/></g></g>`;
  }
  function hojaBrote(forma, T, linea, f, conFlor) {
    if (forma === "cactus" || forma === "cactusB") return "";   // (21-oct) la flor del cactus va DELANTE del cuerpo (ver broteSuave)
    if (forma === "doshojas" || forma === "otono") return `<g class="hoja">
            <path d="M60 39 C52 39 40 35 34 25 C45 21 57 27 60 39 Z" fill="${T.hoja1}" stroke="${linea}" stroke-width="2.4" stroke-linejoin="round"/>
            <path d="M60 39 C68 39 80 35 86 25 C75 21 63 27 60 39 Z" fill="${T.hoja2}" stroke="${linea}" stroke-width="2.4" stroke-linejoin="round"/>
            <path d="M58 36 C51 33 45 30 40 26 M62 36 C69 33 75 30 80 26" fill="none" stroke="${linea}" stroke-width="1.2" opacity=".5"/></g>`;
    return `<g class="hoja">
            <path d="M60 39 C51 36 46 27 50 19 C57 21 61 30 60 39 Z" fill="${T.hoja1}" stroke="${linea}" stroke-width="2.4" stroke-linejoin="round"/>
            <path d="M60 39 C69 36 74 27 70 19 C63 21 59 30 60 39 Z" fill="${T.hoja2}" stroke="${linea}" stroke-width="2.4" stroke-linejoin="round"/></g>`;
  }
  // espinas del cactus, dos estilos (21-oct): "areolas" = puntito con 3 espinitas finas hacia afuera, repartidas por el
  // cuerpo sin tocar la cara; "bolitas" = como la hoja de Codex, puntas redondeadas crema que asoman del borde
  // (21-oct, LShinox: "dejemos la version de antes") rayitas cortas y claras alrededor del borde
  const ESPINAS = [[27, 62, -40], [22, 80, -90], [30, 97, -140], [93, 62, 40], [98, 80, 90], [90, 97, 140], [44, 45, -20], [76, 45, 20]]
    .map(([x, y, a]) => `<path d="M${x} ${y} l0 -5" transform="rotate(${a} ${x} ${y})" stroke="#FFF6D8" stroke-width="2.2" stroke-linecap="round"/>`).join("");
  // bolitas: puntos y angulos MEDIDOS sobre la silueta real del cuerpo (getPointAtLength en el navegador, 21-oct):
  // a -97/-60/-25/25/60/97 grados desde el centro 60,71, cada una perpendicular al borde y con la base 1,5 px adentro.
  // Mas abiertas arriba (±25) para que sin flor no quede un hueco grande.
  const BOLITAS = (linea) => [[20.1, 75.9, -86], [27.9, 52.5, -55], [45.3, 39.4, -19], [74.7, 39.4, 19], [92.1, 52.5, 55], [99.9, 75.9, 86]].map(([x, y, n]) =>
    `<path d="M-4.6 1.5 Q0 -10 4.6 1.5 Z" transform="translate(${x} ${y}) rotate(${n})" fill="#F6F0C9" stroke="${linea}" stroke-width="1.5" stroke-linejoin="round"/>`).join("");
  function broteSuave(acc, peluche, forma = "brote", conFlor = true) {
    const tema = forma === "otono" ? "otono" : forma.startsWith("cactus") ? "cactus" : "verde", T = TEMAS_BROTE[tema];
    const f = uid(), cuerpo = peluche ? "#c4e6a3" : "#b5e08c", linea = tema !== "verde" ? T.linea : peluche ? "#7fb35a" : "#5e9c3a";
    const filtro = "";
    return `
      <svg viewBox="0 0 120 120" class="pj pj-brote">
        <defs>${peluche ? FELPA("f" + f) : ""}
          <linearGradient id="bc${f}" x1=".25" y1="0" x2=".75" y2="1"><stop offset="0" stop-color="${tema !== "verde" ? T.c1 : peluche ? "#D6F0BC" : "#CFEEAA"}"/><stop offset="1" stop-color="${tema !== "verde" ? T.c2 : peluche ? "#B2DD8C" : "#A2D575"}"/></linearGradient>
          <radialGradient id="bs${f}" cx=".5" cy=".42" r=".66"><stop offset=".58" stop-color="${T.sombra}" stop-opacity="0"/><stop offset="1" stop-color="${T.sombra}" stop-opacity=".30"/></radialGradient>
          <radialGradient id="bb${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff" stop-opacity=".65"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
          <radialGradient id="bp${f}" cx=".5" cy=".35" r=".7"><stop offset="0" stop-color="${T.panza1}"/><stop offset="1" stop-color="${T.panza2}"/></radialGradient>
          <linearGradient id="oj${f}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#241915"/><stop offset="1" stop-color="#5B4439"/></linearGradient>
          <radialGradient id="sg${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#3A3530" stop-opacity=".22"/><stop offset="1" stop-color="#3A3530" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse class="sombra" cx="60" cy="109" rx="34" ry="4.5" fill="url(#sg${f})"/>
        <g class="mueve"><g class="cuerpo">
          ${hojaBrote(forma, T, linea, f, conFlor)}
          ${peluche ? cuerpoPeludo(f, tema) : `<path class="silueta" d="M60 37 C86 37 100 56 100 80 C100 99 86 105 60 105 C34 105 20 99 20 80 C20 56 34 37 60 37 Z" fill="url(#bc${f})" stroke="${linea}" stroke-width="2.6"/>`}
          ${forma === "cactus" ? ESPINAS : forma === "cactusB" ? BOLITAS(linea) : ""}
          ${forma.startsWith("cactus") && conFlor ? florCactus(linea, f) : ""}
          <path d="M60 37 C86 37 100 56 100 80 C100 99 86 105 60 105 C34 105 20 99 20 80 C20 56 34 37 60 37 Z" fill="url(#bs${f})"/>
          <ellipse cx="60" cy="88" rx="26" ry="13" fill="url(#bp${f})"/>
          <ellipse cx="79" cy="50" rx="11" ry="6" fill="url(#bb${f})" transform="rotate(-32 79 50)"/><circle cx="88" cy="58" r="1.8" fill="#fff" opacity=".85"/>
          <ellipse class="mejilla" cx="37" cy="86" rx="6.5" ry="3.8" fill="rgb(255,120,150)" opacity=".38"/>
          <ellipse class="mejilla" cx="83" cy="86" rx="6.5" ry="3.8" fill="rgb(255,120,150)" opacity=".38"/>
          ${peluche ? `<path d="M60 41 C82 41 95 57 95 77 C95 96 81 104 60 104 C39 104 25 96 25 77 C25 57 38 41 60 41 Z" fill="none" stroke="${linea}" stroke-width="1.3" stroke-dasharray="3 3" opacity=".55"/>` : ""}
          ${OJOS(46, 74, 79, 7.0, `url(#oj${f})`)}
          ${accesorio(acc, "brote")}
        </g></g>
      </svg>`;
  }
  function luceroSuave(acc, peluche) {
    const f = uid(), cuerpo = peluche ? "#ddd2fa" : "#d3c5f7", linea = peluche ? "#a493e0" : "#8f7bd6", tent = peluche ? "#cfc2f6" : "#c0aff1";
    const filtro = "";
    return `
      <svg viewBox="0 0 120 120" class="pj pj-lucero">
        <defs>${peluche ? FELPA("f" + f) : ""}<radialGradient id="glw-${f}" class="glwdef"><stop offset="0" stop-color="#fff3b0" stop-opacity=".95"/><stop offset=".6" stop-color="#ffe27a" stop-opacity=".45"/><stop offset="1" stop-color="#ffd659" stop-opacity="0"/></radialGradient></defs>
        <defs><linearGradient id="lc${f}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EFE8FF"/><stop offset=".55" stop-color="${peluche ? "#D8CCF8" : "#CDBDF5"}"/><stop offset="1" stop-color="#B8A6EE"/></linearGradient>
          <radialGradient id="ls${f}" cx=".5" cy=".45" r=".68"><stop offset=".58" stop-color="#5B47B0" stop-opacity="0"/><stop offset="1" stop-color="#5B47B0" stop-opacity=".28"/></radialGradient>
          <radialGradient id="lb${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff" stop-opacity=".65"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
          <radialGradient id="lg${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFD659" stop-opacity=".35"/><stop offset="1" stop-color="#FFD659" stop-opacity="0"/></radialGradient>
          <linearGradient id="lt${f}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9B8F4"/><stop offset="1" stop-color="#B3A0EE"/></linearGradient></defs>
        <ellipse class="sombra" cx="60" cy="114" rx="23" ry="4" fill="#3a3530" opacity=".10"/>
        <ellipse class="resplandor" cx="60" cy="110" rx="34" ry="7" fill="url(#lg${f})"/>
        <g class="mueve"><g class="cuerpo">
          <g class="tentaculos">
            <path class="tent" d="M42 84 C40 91 44 95 42 101" fill="none" stroke="url(#lt${f})" stroke-width="8.5" stroke-linecap="round"/>
            <path class="tent" d="M54 86 C53 93 56 97 54 104" fill="none" stroke="url(#lt${f})" stroke-width="8.5" stroke-linecap="round"/>
            <path class="tent" d="M66 86 C67 93 64 97 66 104" fill="none" stroke="url(#lt${f})" stroke-width="8.5" stroke-linecap="round"/>
            <path class="tent" d="M78 84 C80 91 76 95 78 101" fill="none" stroke="url(#lt${f})" stroke-width="8.5" stroke-linecap="round"/>
          </g>
          <g class="antena">
            <path d="M60 34 C60 27 61 23 62 20" fill="none" stroke="${linea}" stroke-width="2.6" stroke-linecap="round"/>
            <circle class="estrella" cx="62.5" cy="16.5" r="5" fill="#ffe27a" stroke="${linea}" stroke-width="2.2"/>
          </g>
          <path class="silueta" d="M23 79 C19 50 37 33 60 33 C83 33 101 50 97 79 C88 89 32 89 23 79 Z" fill="url(#lc${f})" stroke="${linea}" stroke-width="2.6" stroke-linejoin="round" ${filtro}/>
          <path d="M23 79 C19 50 37 33 60 33 C83 33 101 50 97 79 C88 89 32 89 23 79 Z" fill="url(#ls${f})"/>
          ${peluche ? `<path d="${pelo(60, 79, 38.5, 46, 180, 360, 28)} Z" fill="url(#lc${f})" stroke="${linea}" stroke-width="1.6" stroke-linejoin="round"/>` : ""}
          ${peluche ? `<path d="M28 77 C25 53 40 38 60 38 C80 38 95 53 92 77" fill="none" stroke="${linea}" stroke-width="1.3" stroke-dasharray="3 3" opacity=".55"/>` : ""}
          <ellipse class="luz" cx="60" cy="77" rx="22" ry="9" fill="#ffd659" opacity=".6"/>
          <ellipse cx="80" cy="45" rx="10" ry="5.5" fill="url(#lb${f})" transform="rotate(-32 80 45)"/><circle cx="90" cy="52" r="1.8" fill="#fff" opacity=".85"/>
          <ellipse class="mejilla" cx="35" cy="70" rx="6" ry="3.5" fill="rgb(255,120,150)" opacity=".38"/>
          <ellipse class="mejilla" cx="85" cy="70" rx="6" ry="3.5" fill="rgb(255,120,150)" opacity=".38"/>
          ${OJOS(47, 73, 61, 7.2)}
          ${accesorio(acc, "lucero")}
        </g></g>
      </svg>`;
  }
  SVG.brote4 = acc => broteSuave(acc, false);
  SVG.brote5 = acc => broteSuave(acc, true);
  SVG.broteDosHojas = acc => broteSuave(acc, true, "doshojas");   // (21-oct) variantes elegidas por LShinox
  SVG.broteOtono = acc => broteSuave(acc, true, "otono");
  SVG.broteCactus = acc => broteSuave(acc, true, "cactus");
  SVG.broteCactusBolitas = acc => broteSuave(acc, true, "cactusB");
  SVG["broteCactus-sinflor"] = acc => broteSuave(acc, true, "cactus", false);   // (21-oct) "Cactus con flor" apagado
  SVG["broteCactusBolitas-sinflor"] = acc => broteSuave(acc, true, "cactusB", false);
  SVG.lucero4 = acc => luceroSuave(acc, false);
  SVG.lucero5 = acc => luceroSuave(acc, true);

  // ---------- 13-oct: gato negro y puercoespines (pedido de LShinox) ----------
  // Mismo esqueleto que Brote (mueve > cuerpo, ojos, sombra) para que usen todas las animaciones.
  function puas(cx, cy, rx, ry, desde = 150, hasta = 390, n = 17, largo = 11) {
    const P = (a, k) => [cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k];
    let d = "";
    for (let i = 0; i <= n * 2; i++) {
      const a = (desde + (hasta - desde) * i / (n * 2)) * Math.PI / 180;
      const k = i % 2 ? 1 + (largo * (.85 + Math.random() * .3)) / rx : 1;
      const [x, y] = P(a, k); d += (i ? " L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
    }
    return d + " Z";
  }
  function gato(acc, estilo = null) {
    // 13-oct (LShinox): minimalista, UN solo bloque negro (cuerpo + orejas en la misma silueta), sin cola,
    // ojos claros sin brillos y mejillas SOLO en ocasiones (al estar feliz), como Coucou. Inspiración Baymax: poco y expresivo.
    const f = uid();
    const SIL = "M60 105 C34 105 20 99 20 80 C20 67 23 59 28 53 L30.5 33.5 Q31.5 27.5 36.5 31 L48 41.5 Q60 38.5 72 41.5 L83.5 31 Q88.5 27.5 89.5 33.5 L92 53 C97 59 100 67 100 80 C100 99 86 105 60 105 Z";
    return `
      <svg viewBox="0 0 120 120" class="pj pj-gato">
        <defs><radialGradient id="gs${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#3A3530" stop-opacity=".25"/><stop offset="1" stop-color="#3A3530" stop-opacity="0"/></radialGradient></defs>
        <ellipse class="sombra" cx="60" cy="109" rx="34" ry="4.5" fill="url(#gs${f})"/>
        <g class="mueve"><g class="cuerpo">
          <g class="cola-atras"><path d="M88 100 C110 102 119 82 114 63 C111 54 101 56 105 65 C110 78 106 92 86 94" fill="none" stroke="#1f1c22" stroke-width="8" stroke-linecap="round"/></g>
          <path class="silueta" d="${SIL}" fill="#1f1c22" stroke="#1f1c22" stroke-width="2" stroke-linejoin="round"/>
          <g class="cola-frente" opacity="0">
            <path class="trazo" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M98 93 C101 105 80 109 58 107 C40 106 24 105 18 97 C13 90 14 83 21 81" fill="none" stroke="#5A5364" stroke-width="10" stroke-linecap="round"/>
            <path class="trazo" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M98 93 C101 105 80 109 58 107 C40 106 24 105 18 97 C13 90 14 83 21 81" fill="none" stroke="#1f1c22" stroke-width="8" stroke-linecap="round"/>
          </g>
          <ellipse class="mejilla ocasional" cx="35" cy="87" rx="6.5" ry="3.6" fill="rgb(255,120,150)" opacity="0"/>
          <ellipse class="mejilla ocasional" cx="85" cy="87" rx="6.5" ry="3.6" fill="rgb(255,120,150)" opacity="0"/>
          ${estilo ? OJOS(45, 75, 78, 9.6, "#fff", estilo) : OJOS(46, 74, 76, 7.6, "#F4F1EA")}
          ${accesorio(acc, "brote")}
        </g></g>
      </svg>`;
  }
  function puercoespin(acc, conHoja) {
    const f = uid(), cara = "#F3DFC4", puaC = "#7A5A44", puaL = "#53392A", cuerpoC = "#B08865";
    return `
      <svg viewBox="0 0 120 120" class="pj pj-puerco">
        <defs><linearGradient id="pc${f}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9A7151"/><stop offset="1" stop-color="${puaC}"/></linearGradient>
          <radialGradient id="pf${f}" cx=".5" cy=".4" r=".7"><stop offset="0" stop-color="#FBF0E0"/><stop offset="1" stop-color="${cara}"/></radialGradient>
          <radialGradient id="ps${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#3A3530" stop-opacity=".22"/><stop offset="1" stop-color="#3A3530" stop-opacity="0"/></radialGradient></defs>
        <ellipse class="sombra" cx="60" cy="109" rx="36" ry="4.5" fill="url(#ps${f})"/>
        <g class="mueve"><g class="cuerpo">
          <g class="puas"><path d="${puas(60, 78, 41, 36)}" fill="url(#pc${f})" stroke="${puaL}" stroke-width="2.2" stroke-linejoin="round"/></g>
          <g class="antena">
            <circle cx="36" cy="48" r="6" fill="${cuerpoC}" stroke="${puaL}" stroke-width="2"/><circle cx="36" cy="48" r="3" fill="#f2a5b4"/>
            <circle cx="84" cy="48" r="6" fill="${cuerpoC}" stroke="${puaL}" stroke-width="2"/><circle cx="84" cy="48" r="3" fill="#f2a5b4"/>
          </g>
          <path class="silueta" d="M60 46 C84 46 98 62 98 82 C98 99 84 105 60 105 C36 105 22 99 22 82 C22 62 36 46 60 46 Z" fill="url(#pf${f})" stroke="${puaL}" stroke-width="2.4"/>
          <ellipse cx="80" cy="60" rx="8" ry="4" fill="#fff" opacity=".45" transform="rotate(-30 80 60)"/>
          <ellipse class="mejilla" cx="37" cy="88" rx="6.5" ry="3.8" fill="rgb(255,120,150)" opacity=".42"/>
          <ellipse class="mejilla" cx="83" cy="88" rx="6.5" ry="3.8" fill="rgb(255,120,150)" opacity=".42"/>
          ${OJOS(47, 73, 78, 7.2)}
          ${conHoja ? `<g class="hoja">
            <path d="M88 103 C78 94 79 76 94 68 C103 83 100 97 88 103 Z" fill="#8fcf5f" stroke="#5e9c3a" stroke-width="2.2" stroke-linejoin="round"/>
            <path d="M88 101 C89 90 91 80 93 72" fill="none" stroke="#5e9c3a" stroke-width="1.6" stroke-linecap="round"/>
          </g>
          <circle cx="83" cy="99" r="4.6" fill="${cuerpoC}" stroke="${puaL}" stroke-width="1.8"/><circle cx="92" cy="101" r="4.6" fill="${cuerpoC}" stroke="${puaL}" stroke-width="1.8"/>` : ""}
          ${accesorio(acc, "brote")}
        </g></g>
      </svg>`;
  }
  SVG.gato = acc => gatoPro(acc, "lisos");   // (13-oct) todos los gatos con orejas y parpados
  SVG.gatoInv = acc => gato(acc, "invertido");
  SVG.gatoPup = acc => gatoPro(acc, "pupila");
  SVG.gatoJiji = acc => gato(acc, "jiji");

  // ---------- 13-oct: GATO "PRO" (estudios gato-expresiones + ojos-tiernos) ----------
  // Rig: cuerpo + 2 orejas separadas (misma silueta de antes), parpados del color del cuerpo, ojo crema con
  // pupila que mira y se dilata (.mira > .pup), UN brillo. Las expresiones salen de orejas + parpados + pupila + cuerpo.
  // (21-oct, LShinox) colores del gato para elegir: mismo rig y mismas animaciones; cambian cuerpo, contorno, ojos (en los
  // claros los ojos van oscuros) y un dibujo encima recortado a la silueta (rayas, manchas, pecho blanco).
  const COLORES_GATO = {
    negro:   { N: "#1f1c22", borde: "#5A5364", ojo: "#FFF4DE", pup: "#1f1c22", marcas: "" },
    naranja: { N: "#F2A65A", borde: "#B9702F", ojo: "#3A2A20", pup: "#1f1c22", marcas: "rayas" },
    blanco:  { N: "#FAF7F2", borde: "#8C8494", ojo: "#3A3340", pup: "#1f1c22", marcas: "" },
    gris:    { N: "#77808F", borde: "#4C5361", ojo: "#FFF4DE", pup: "#1f1c22", marcas: "" },
    esmoquin:{ N: "#1f1c22", borde: "#5A5364", ojo: "#FFF4DE", pup: "#1f1c22", marcas: "pecho" },
  };
  function gatoPro(acc, tipoOjo = "pro", color = "negro") {
    const P = COLORES_GATO[color] || COLORES_GATO.negro;
    const f = uid(), N = P.N, claro = P.ojo !== "#FFF4DE";
    const CUERPO = "M60 105 C34 105 20 99 20 80 C20 67 23 59 28 53 L48 41.5 Q60 38.5 72 41.5 L92 53 C97 59 100 67 100 80 C100 99 86 105 60 105 Z";
    const OI = "M26 57 L30.5 33.5 Q31.5 27.5 36.5 31 L51 43 L54 68 L29 72 Z", OD = "M94 57 L89.5 33.5 Q88.5 27.5 83.5 31 L69 43 L66 68 L91 72 Z";
    const SC = claro ? P.ojo : "#FFF4DE";   // ojo: crema en los oscuros, oscuro en los claros
    const OJO = {
      pro: (cx, cy) => `<ellipse cx="${cx}" cy="${cy}" rx="8.4" ry="9.2" fill="${SC}"/><g class="mira"><ellipse class="pup" cx="${cx}" cy="${cy + .6}" rx="5.4" ry="5.4" fill="${claro ? "#120F14" : N}"/><circle cx="${cx + 2}" cy="${cy - 1.6}" r="1.9" fill="#fff"/></g>`,
      lisos: (cx, cy) => `<ellipse cx="${cx}" cy="${cy}" rx="7.4" ry="8.6" fill="${claro ? P.ojo : "#F4F1EA"}"/><g class="mira"></g>`,
      pupila: (cx, cy) => `<circle cx="${cx}" cy="${cy}" r="9.4" fill="#fff"/><g class="mira"><ellipse class="pup" cx="${cx}" cy="${cy + 1}" rx="5.6" ry="5.6" fill="${N}"/><circle cx="${cx + 1.8}" cy="${cy - 1.2}" r="1.7" fill="#fff"/></g>`,
    };
    const ojo = (cx, cy) => `<g class="parpado">${OJO[tipoOjo](cx, cy)}</g>`;
    const par = `${ojo(44, 79)}${ojo(76, 79)}`;
    const arco = (d) => `<path d="M${36} 79 Q44 ${79 + d} 52 79" fill="none" stroke="${SC}" stroke-width="3.4" stroke-linecap="round"/><path d="M68 79 Q76 ${79 + d} 84 79" fill="none" stroke="${SC}" stroke-width="3.4" stroke-linecap="round"/>`;
    const contorno = color === "negro" || color === "esmoquin" ? N : P.borde;
    // (21-oct, 2.a vuelta) rayas del naranja: cuñas que se afinan (como pelo), no trazos parejos; van ENCIMA de los
    // parpados (son pelo, se ven igual con los ojos cerrados). (x1,y1) base ancha -> (x2,y2) punta.
    const cuna = (x1, y1, x2, y2, w) => {
      const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1, px = -dy / L * w / 2, py = dx / L * w / 2;
      return `<path d="M${(x1 + px).toFixed(1)} ${(y1 + py).toFixed(1)} Q${(x1 + dx * .55 + px * .6).toFixed(1)} ${(y1 + dy * .55 + py * .6).toFixed(1)} ${x2} ${y2} Q${(x1 + dx * .55 - px * .6).toFixed(1)} ${(y1 + dy * .55 - py * .6).toFixed(1)} ${(x1 - px).toFixed(1)} ${(y1 - py).toFixed(1)} Z"/>`;
    };
    const MARCAS = {
      rayas: `<g fill="#D07A2E" opacity=".85">${cuna(60, 40, 60, 55, 4.2)}${cuna(51, 42, 53.5, 53, 3.4)}${cuna(69, 42, 66.5, 53, 3.4)}`
        + `${cuna(20, 75, 31, 77.5, 3.6)}${cuna(20, 83, 30, 83.5, 3.4)}${cuna(100, 75, 89, 77.5, 3.6)}${cuna(100, 83, 90, 83.5, 3.4)}`
        + `${cuna(41, 104, 44, 97, 3.4)}${cuna(79, 104, 76, 97, 3.4)}</g>`,
      // esmoquin: pecho blanco abajo y dos patitas blancas apoyadas en el piso
      pecho: `<path d="M50 106 C50 100 54 96 60 96 C66 96 70 100 70 106 Z" fill="#FAF7F2"/><ellipse cx="45" cy="104" rx="6.5" ry="3.6" fill="#FAF7F2"/><ellipse cx="75" cy="104" rx="6.5" ry="3.6" fill="#FAF7F2"/>`,
    };
    const marcas = P.marcas ? `<g clip-path="url(#sil${f})">${MARCAS[P.marcas]}</g>` : "";
    const orejaI = N, orejaD = N;
    return `
      <svg viewBox="0 0 120 120" class="pj pj-gato">
        <defs><radialGradient id="gs${f}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#3A3530" stop-opacity=".25"/><stop offset="1" stop-color="#3A3530" stop-opacity="0"/></radialGradient>
          <clipPath id="piso${f}"><rect x="-60" y="-80" width="240" height="185.6"/></clipPath>
          <clipPath id="sil${f}"><path d="${CUERPO}"/></clipPath></defs>
        <ellipse class="sombra" cx="60" cy="109" rx="34" ry="4.5" fill="url(#gs${f})"/>
        <line class="piso" x1="60" y1="105.6" x2="60" y2="105.6" stroke="#8C8494" stroke-width="1.6" stroke-linecap="round" opacity="0"/>
        <g clip-path="url(#piso${f})">
        <!-- (14-oct) PISO: todo lo que baja de y=105,6 se corta. Al aplastarse contra el piso la base queda plana y al
             acechar se "funde" con el. La linea .piso se dibuja del centro a los costados cuando apoya. -->
        <g class="mueve"><g class="cuerpo">
          <g class="cola-atras">${color !== "negro" && color !== "esmoquin" ? `<path d="M88 100 C110 102 119 82 114 63 C111 54 101 56 105 65 C110 78 106 92 86 94" fill="none" stroke="${P.borde}" stroke-width="10" stroke-linecap="round"/>` : ""}<path d="M88 100 C110 102 119 82 114 63 C111 54 101 56 105 65 C110 78 106 92 86 94" fill="none" stroke="${N}" stroke-width="8" stroke-linecap="round"/></g>
          <!-- (14-oct) la cola dibuja signos al lado de la cabeza en vez del circulito: ? = pregunta, ¡ = permiso/error -->
          <g class="signo signo-preg" opacity="0">
            <path class="trazo-s" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M92 96 C102 96 104 89 104 81 L104 64 C104 57 113 54 113 44 C113 36 108 30.5 102.5 30.5 C98.5 30.5 96 33 96 36.5" fill="none" stroke="#5A5364" stroke-width="9.5" stroke-linecap="round"/>
            <path class="trazo-s" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M92 96 C102 96 104 89 104 81 L104 64 C104 57 113 54 113 44 C113 36 108 30.5 102.5 30.5 C98.5 30.5 96 33 96 36.5" fill="none" stroke="${N}" stroke-width="7.5" stroke-linecap="round"/>
          </g>
          <g class="signo signo-excl" opacity="0">
            <path class="trazo-s" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M92 96 C102 96 104 90 104 82 L104 51" fill="none" stroke="#5A5364" stroke-width="9.5" stroke-linecap="round"/>
            <path class="trazo-s" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M92 96 C102 96 104 90 104 82 L104 51" fill="none" stroke="${N}" stroke-width="7.5" stroke-linecap="round"/>
            <circle class="punto-s" cx="104" cy="39" r="4.6" fill="${N}" stroke="#5A5364" stroke-width="1"/>
          </g>
          <path class="oreja-i" d="${OI}" fill="${orejaI}" stroke="${contorno}" stroke-width="2" stroke-linejoin="round"/>
          <path class="oreja-d" d="${OD}" fill="${orejaD}" stroke="${contorno}" stroke-width="2" stroke-linejoin="round"/>
          <path class="silueta" d="${CUERPO}" fill="${N}" stroke="${contorno}" stroke-width="2" stroke-linejoin="round"/>
          ${P.marcas !== "rayas" ? marcas : ""}
          <g class="cola-frente" opacity="0">
            <path class="trazo" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M98 91 C101 101 80 104 58 103.5 C40 103 24 101 18 94 C13 88 14 82 21 80" fill="none" stroke="#5A5364" stroke-width="10" stroke-linecap="round"/>
            <path class="trazo" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M98 91 C101 101 80 104 58 103.5 C40 103 24 101 18 94 C13 88 14 82 21 80" fill="none" stroke="${N}" stroke-width="8" stroke-linecap="round"/>
          </g>
          <ellipse class="mejilla ocasional" cx="31" cy="91" rx="7.5" ry="4.4" fill="rgb(255,120,150)" opacity="0"/>
          <ellipse class="mejilla ocasional" cx="89" cy="91" rx="7.5" ry="4.4" fill="rgb(255,120,150)" opacity="0"/>
          <g class="ojos">
            <g class="exp exp-normal">${par}</g>
            <g class="exp exp-sorpresa" opacity="0">${par}</g>
            <g class="exp exp-triste" opacity="0">${par}</g>
            <g class="exp exp-concentrado" opacity="0">${par}</g>
            <g class="exp exp-feliz" opacity="0">${arco(-11)}</g>
            <g class="exp exp-dormido" opacity="0">${arco(8)}</g>
          </g>
          <path class="lid-i" d="M31 46 H57 V70.5 Q44 63.5 31 70.5 Z" fill="${N}"/>
          <path class="lid-d" d="M63 46 H89 V70.5 Q76 63.5 63 70.5 Z" fill="${N}"/>
          ${P.marcas === "rayas" ? marcas : ""}
          ${accesorio(acc, "brote")}
        </g></g>
        </g>
      </svg>`;
  }
  SVG.gatoPro = acc => gatoPro(acc);
  Object.keys(COLORES_GATO).forEach(c => {   // (21-oct) "gatoPro-naranja", "gato-calico"…: el color va pegado al tipo
    SVG["gatoPro-" + c] = acc => gatoPro(acc, "pro", c);
    SVG["gato-" + c] = acc => gatoPro(acc, "lisos", c);
  });

  SVG.puerco = acc => puercoespin(acc, false);
  SVG.puercohoja = acc => puercoespin(acc, true);


  // ---------- animación ----------
  const EXPR = ["normal", "feliz", "dormido", "sorpresa", "triste", "concentrado"];

  function crear(host, tipo, acc) {
    host.innerHTML = SVG[tipo](acc);
    const svg = host.querySelector("svg");
    const q = s => svg.querySelector(s), qa = s => svg.querySelectorAll(s);
    const grad = svg.querySelector(".glwdef");
    if (grad) { svg.querySelector(".luz").setAttribute("fill", `url(#${grad.id})`); }
    const cuerpo = q(".cuerpo"), ojos = q(".ojos"), sombra = q(".sombra");
    const hoja = q(".hoja"), luz = q(".luz"), estrella = q(".estrella"), antena = q(".antena"), tents = qa(".tent"), accesorio = q(".accesorio");
    gsap.set(cuerpo, { transformOrigin: "50% 100%" });
    gsap.set([hoja, antena].filter(Boolean), { transformOrigin: "50% 100%" });
    gsap.set([luz, estrella, accesorio].filter(Boolean), { transformOrigin: "50% 50%" });
    gsap.set(tents, { transformOrigin: "50% 0%" });
    gsap.set(qa(".parpado"), { transformOrigin: "50% 50%" });
    gsap.set(qa(".exp"), { transformOrigin: "50% 50%" });
    gsap.set(sombra, { transformOrigin: "50% 50%" });

    let estado = null, loop = null, expr = "normal", vivo = true, timers = [];
    const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); return t; };

    // cambio de expresión: los ojos se "aplastan" y vuelven con la nueva cara (como un parpadeo)
    // cambio de expresión: los ojos se "aplastan" y vuelven con la nueva cara (como un parpadeo).
    // El cambio ocurre cuando la línea de tiempo LLEGA a ese punto (no al armarla): antes, dos cambios
    // armados juntos (p.ej. sorpresa -> feliz) se pisaban y los ojos desaparecían o quedaban dos caras.
    let caraTl = null;
    function cara(nueva, dur = AJ().cara.cambio) {
      return gsap.timeline().call(() => {
        if (nueva === expr) return;
        if (caraTl) caraTl.kill();
        const de = q(".exp-" + expr), a = q(".exp-" + nueva); expr = nueva;
        qa(".exp").forEach(x => gsap.set(x, x === de ? { opacity: 1, scaleY: 1 } : { opacity: 0, scaleY: 1 }));
        const mej = qa(".mejilla.ocasional");
        if (mej.length) gsap.to(mej, nueva === "feliz" ? { opacity: .5, duration: .2, overwrite: true } : { opacity: 0, duration: .6, overwrite: true });
        caraTl = gsap.timeline()
          .to(de, { scaleY: .05, duration: dur, ease: "power2.in" })
          .set(de, { opacity: 0, scaleY: 1 })
          .set(a, { opacity: 1, scaleY: .05 })
          .to(a, { scaleY: 1, duration: dur * 1.6, ease: "back.out(3)" });
      });
    }
    function parpadear() {
      if (expr === "feliz" || expr === "dormido") return;
      const el = expr === "normal" ? qa(".parpado") : q(".exp-" + expr);
      const p = AJ().parpadeo;
      const uno = () => gsap.timeline().to(el, { scaleY: .06, duration: p.cierre, ease: "power3.in" }).to(el, { scaleY: 1, duration: p.apertura, ease: "power3.out" });
      const t = uno(); if (Math.random() < p.doble) t.add(uno(), "+=.03");
      return t;
    }
    function parpadeo() {
      if (!vivo) return;
      parpadear();
      const pp = AJ().parpadeo; later(parpadeo, (pp.cadaMin + Math.random() * (pp.cadaMax - pp.cadaMin)) * 1000);
    }
    // ---- director de gestos: en vez de un loop fijo, elige al azar un gesto distinto cada pocos segundos ----
    const mueve = q(".mueve");
    gsap.set(mueve, { transformOrigin: "50% 100%" });
    // ---- resorte secundario (estudio Mochi: k=60, c=9 ~ 1.2 Hz, ~10 % de rebote): hoja, antena y
    // tentáculos se atrasan y se acomodan solos cuando el cuerpo se mueve ----
    const resortes = [q(".hoja"), q(".antena"), q(".tentaculos"), q(".cola")].filter(Boolean).map(el => {
      const w = document.createElementNS(NS, "g"); el.parentNode.insertBefore(w, el); w.appendChild(el);
      const tenta = el.classList.contains("tentaculos") || el.classList.contains("cola");
      gsap.set(w, { transformOrigin: el.classList.contains("cola") ? "0% 100%" : tenta ? "50% 0%" : "50% 100%" });
      return { w, a: 0, v: 0, tenta };
    });
    let prevY = null, prevR = 0, vyS = 0, vrS = 0;
    const tic = (time, dt) => {
      const s = Math.min(dt, 50) / 1000; if (!s) return;
      const y = gsap.getProperty(mueve, "y") + gsap.getProperty(cuerpo, "y");
      const r = gsap.getProperty(mueve, "rotation") + gsap.getProperty(cuerpo, "rotation");
      if (prevY === null) { prevY = y; prevR = r; return; }
      // velocidad suavizada (filtro exponencial) y zona muerta: sin esto el ruido de cuadro a cuadro hacia temblar hoja/antena
      vyS += ((y - prevY) / s - vyS) * .2; vrS += ((r - prevR) / s - vrS) * .2; prevY = y; prevR = r;
      for (const o of resortes) {
        let objetivo = gsap.utils.clamp(-22, 22, (o.tenta ? -1 : 1) * vyS * .05 - vrS * .3);
        if (Math.abs(objetivo) < .6) objetivo = 0;
        const rs = AJ().resorte; o.v += (rs.rigidez * (objetivo - o.a) - rs.freno * o.v) * s; o.a += o.v * s;
        if (Math.abs(o.a) < .02 && Math.abs(o.v) < .02 && objetivo === 0) { if (o.a !== 0) { o.a = 0; o.v = 0; gsap.set(o.w, { rotation: 0 }); } continue; }
        const ang = Math.round(o.a * 10) / 10;   // pasos de 0,1 grado: evita el "zumbido" de subpixel
        if (ang !== o.ult) { o.ult = ang; gsap.set(o.w, { rotation: ang }); }
      }
    };
    gsap.ticker.add(tic);
    // la hoja / antena salen POR ENCIMA de auriculares y casco
    const accEl = q(".accesorio");
    if (accEl && /musica|instalaciones/.test(accEl.dataset.acc || "")) resortes.filter(o => !o.tenta).forEach(o => cuerpo.appendChild(o.w));
    // insignia de estado (estudio §2.2): esquina superior derecha, fuera del cuerpo
    const INS = {
      permiso: ["#FFC94A", '<rect x="93.6" y="21" width="3" height="8" rx="1.5" fill="#3A3530"/><circle cx="95" cy="34" r="1.8" fill="#3A3530"/>'],
      pregunta: ["#5BC8F5", '<path d="M91 24.5 C91 20.5 99 20.5 99 25 C99 28 95 28 95 30.5" fill="none" stroke="#3A3530" stroke-width="3.2" stroke-linecap="round"/><circle cx="95" cy="34.5" r="1.8" fill="#3A3530"/>'],
      error: ["#C93A55", '<rect x="93.6" y="21" width="3" height="8" rx="1.5" fill="#fff"/><circle cx="95" cy="34" r="1.8" fill="#fff"/>'],
      termino: ["#8FCF5F", '<path d="M89.5 28.5 L93.5 32.5 L100.5 23.5" fill="none" stroke="#3A3530" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'],
    };
    const ins = document.createElementNS(NS, "g"); ins.setAttribute("class", "insignia"); svg.appendChild(ins);
    gsap.set(ins, { svgOrigin: "95 28", scale: 0 });
    let insTipo = null, insPulso = null;
    function insignia(tipo) {
      if (tipo === insTipo) return; insTipo = tipo;
      if (esGato && estado === "escribio") {
        if (tipo === "pregunta") gsap.to(mueve, { rotation: 10, duration: .26, ease: "back.out(1.4)", delay: .2 });
        else if (tipo === "permiso") { gsap.to([lidI, lidD], { y: 3, rotation: (i) => i ? 12 : -12, duration: .3, ease: "sine.out" }); gsap.to(pups, { attr: { rx: 6.8, ry: 6.8 }, duration: .3 }); gsap.to(mueve, { rotation: 5, duration: .3 }); }
      }
      if (insPulso) { insPulso.kill(); insPulso = null; }
      if (signoP) return signo(tipo);   // (14-oct) el gato no usa el circulito: la cola dibuja el signo
      gsap.to(ins, { scale: 0, duration: .09, ease: "power2.in", overwrite: true, onComplete: () => {
        if (!tipo || !INS[tipo]) return;
        const anillo = matchMedia("(prefers-color-scheme: dark)").matches ? "#FFFDF8" : "#3A3530";   // en modo oscuro el anillo claro se ve
        ins.innerHTML = `<circle cx="95" cy="28" r="15" fill="${INS[tipo][0]}" stroke="${anillo}" stroke-width="3"/>` + INS[tipo][1];
        gsap.to(ins, { scale: 1, duration: .28, ease: "back.out(1.7)", delay: .1, overwrite: true });
        if (tipo === "permiso" || tipo === "pregunta") insPulso = gsap.to(ins, { scale: 1.08, duration: .6, yoyo: true, repeat: -1, ease: "sine.inOut", delay: .5 });
      } });
    }
    const R = gsap.utils.random, pick = a => a[Math.floor(Math.random() * a.length)];
    const colaAtras = q(".cola-atras"), colaFrente = q(".cola-frente");
    // ---- (14-oct) piso y signos con la cola (pedido de LShinox) ----
    const piso = q(".piso"), signoP = q(".signo-preg"), signoE = q(".signo-excl");
    // la linea del piso nace debajo del centro y se estira a los costados ("el sobrante sale por los costados")
    function pisoVer(on, d = .35) {
      if (!piso) return;
      gsap.to(piso, { attr: { x1: on ? 22 : 60, x2: on ? 98 : 60 }, opacity: on ? .8 : 0, duration: d, ease: on ? "power2.out" : "power2.in", overwrite: true });
    }
    // la cola sale por detras a la derecha y dibuja "?" (pregunta) o "¡" (permiso / error) al lado de la cabeza
    function signo(tipo) {
      const quiere = tipo === "pregunta" ? signoP : (tipo === "permiso" || tipo === "error") ? signoE : null;
      [signoP, signoE].forEach(g => {
        if (!g || g === quiere) return;
        const tr = g.querySelectorAll(".trazo-s"), pt = g.querySelector(".punto-s");
        if (pt) gsap.to(pt, { scale: 0, svgOrigin: "104 39", duration: .15, overwrite: true });
        gsap.to(tr, { strokeDashoffset: 1, duration: .35, ease: "power2.in", overwrite: true, onComplete: () => { if (g !== quiere) gsap.set(g, { opacity: 0 }); } });
      });
      if (!quiere) return;
      const tr = quiere.querySelectorAll(".trazo-s"), pt = quiere.querySelector(".punto-s");
      gsap.killTweensOf(tr); gsap.set(quiere, { opacity: 1 }); gsap.set(tr, { strokeDashoffset: 1 });
      if (pt) gsap.set(pt, { scale: 0, svgOrigin: "104 39" });
      gsap.to(tr, { strokeDashoffset: 0, duration: .75, ease: "power1.inOut", delay: .2 });
      if (pt) gsap.to(pt, { scale: 1, duration: .35, ease: "back.out(2.4)", delay: .9 });
    }
    const orejaI = q(".oreja-i"), orejaD = q(".oreja-d"), lidI = q(".lid-i"), lidD = q(".lid-d"), pups = qa(".pup"), miras = qa(".mira");
    const esGato = !!(orejaI && lidI);
    if (esGato) {
      gsap.set(orejaI, { svgOrigin: "38 48" }); gsap.set(orejaD, { svgOrigin: "82 48" });
      gsap.set(lidI, { svgOrigin: "44 69.8" }); gsap.set(lidD, { svgOrigin: "76 69.8" });
    }
    // pose del gato por estado (estudio gato-expresiones §4): orejas, parpados (bajada y giro) y pupila
    const POSE = {
      reposo:     { oi: -3, od: 3, lid: -2, rot: 0, pup: 5.4 },
      trabajando: { oi: 8, od: -8, lid: 5.5, rot: 2, pup: 5.8 },   // parpado afinado, la pupila NO se achica
      escribio:   { oi: -14, od: 3, lid: -2, rot: 0, pup: 6.6 },
      enviado:    { oi: -3, od: 3, lid: 5, rot: 0, pup: 5.8, retraso: .6 },
      atascado:   { oi: -30, od: 30, lid: 3, rot: -14, pup: 6.4 },
      dormido:    { oi: -14, od: 14, lid: -2, rot: 0, pup: 5.4 },
    };
    function pose(e) {
      const p = POSE[e]; if (!esGato || !p) return;
      const d = { duration: .45, ease: "power2.out", delay: p.retraso || 0, overwrite: true };
      gsap.to(orejaI, { rotation: p.oi, ...d }); gsap.to(orejaD, { rotation: p.od, ...d });
      gsap.to(lidI, { y: p.lid, rotation: p.rot, ...d }); gsap.to(lidD, { y: p.lid, rotation: -p.rot, ...d });
      gsap.to(pups, { attr: { rx: p.pup, ry: p.pup }, ...d });
      gsap.to(miras, { x: 0, y: 0, ...d });
    }
    if (colaAtras) gsap.set(colaAtras, { svgOrigin: "88 98", scale: 0, rotation: -40 });
    let accion = null, ultimo = "";
    const GESTOS = {
      reposo: {
        mirar() {   // mira a un costado e inclina la cabeza hacia ahí
          const mr = AJ().mirar, x = R(-mr.rango, mr.rango), y = R(0, 1.5), pup = [...qa(".pupila"), ...miras];   // nunca hacia arriba: se leia preocupado
          if (pup.length) gsap.timeline().to(pup, { x: x * .9, y: y * .9, duration: .25, ease: "power3.out" }).to(pup, { x: 0, y: 0, duration: .4, ease: "power2.inOut" }, "+=1.2");
          return gsap.timeline().to(ojos, { x, y, duration: mr.velocidad, ease: "power3.out" })
            .to(mueve, { rotation: x * 1.1, duration: .55, ease: "sine.inOut" }, 0)
            .to(ojos, { x: 0, y: 0, duration: .4, ease: "power2.inOut" }, "+=" + R(.6, 1.6))
            .to(mueve, { rotation: 0, duration: .6, ease: "sine.inOut" }, "<");
        },
        saltito() {
          // (14-oct) aplastarse = bajar un poco CONTRA el piso: la parte que pasa de la linea se corta y la base queda plana
          const h = R(6, 12);
          return gsap.timeline().call(() => pisoVer(true, .2))
            .to(mueve, { y: 2.5, scaleY: .84, scaleX: 1.12, duration: .07, ease: "power3.out" })
            .to(mueve, { y: -h, scaleY: 1.08, scaleX: .95, duration: .13, ease: "power3.out" })
            .to(sombra, { scale: .8, duration: .13 }, "<")
            .to(mueve, { y: 3, scaleY: .9, scaleX: 1.08, duration: .17, ease: "power3.in" })
            .to(sombra, { scale: 1, duration: .17 }, "<")
            .to(mueve, { y: 0, scaleY: 1, scaleX: 1, duration: .28, ease: "back.out(1.7)" })
            .call(() => pisoVer(false, .4), null, "+=.25");
        },
        estirarse() {
          return gsap.timeline().add(cara("concentrado"))
            .to(mueve, { scaleY: 1.13, scaleX: .92, duration: .7, ease: "sine.out" }, 0)
            .to([hoja, antena].filter(Boolean), { rotation: R(-12, 12), duration: .7 }, 0)
            .to(mueve, { scaleY: 1, scaleX: 1, duration: .6, ease: "elastic.out(1,.7)" }, "+=.35")
            .to([hoja, antena].filter(Boolean), { rotation: 0, duration: .6, ease: "elastic.out(1,.7)" }, "<")
            .add(cara("normal"), "<.1");
        },
        balanceo() {
          const a = R(4, 8), n = Math.round(R(2, 3));
          const t = gsap.timeline();
          for (let i = 0; i < n; i++) t.to(mueve, { rotation: i % 2 ? a : -a, duration: R(.35, .5), ease: "sine.inOut" });
          return t.to(mueve, { rotation: 0, duration: .4, ease: "sine.inOut" });
        },
        sacudir() {   // la hoja (o la antena) hace "boing"
          const el = hoja || antena;
          return gsap.timeline().to(el, { rotation: R(-25, -15), duration: .12, ease: "power2.out" })
            .to(el, { rotation: 0, duration: .9, ease: "elastic.out(1,.6)" })
            .to(ojos, { y: -1.5, duration: .15, yoyo: true, repeat: 1 }, 0);
        },
        sonrisa() {
          return gsap.timeline().add(cara("feliz"))
            .to(mueve, { rotation: R(-5, 5), y: -2, duration: .4, ease: "sine.inOut" }, 0)
            .to(mueve, { rotation: 0, y: 0, duration: .5, ease: "sine.inOut" }, "+=" + R(.8, 1.6))
            .add(cara("normal"), "<");
        },
        bostezo() {
          return gsap.timeline().add(cara("dormido", .2))
            .to(mueve, { scaleY: 1.08, scaleX: .95, duration: .8, ease: "sine.inOut" }, 0)
            .to(mueve, { scaleY: 1, scaleX: 1, duration: .5, ease: "back.out(2)" }, "+=.3")
            .add(cara("normal", .15), "<")
            .to(qa(".parpado"), { scaleY: .1, duration: .06, yoyo: true, repeat: 3 }, "+=.1");
        },
        parpadeoLento() {   // "te quiero" de gato: baja los parpados, cierra, abre despacio
          return gsap.timeline()
            .to([lidI, lidD], { y: 5, duration: .35, ease: "sine.inOut" }, 0)
            .to(pups, { attr: { rx: 5.9, ry: 5.9 }, duration: .35 }, 0)
            .add(cara("dormido", .12), .38).add(cara("normal", .15), 1.25)
            .to([lidI, lidD], { y: -2, duration: .5, ease: "sine.out" }, 1.3)
            .to(pups, { attr: { rx: 5.4, ry: 5.4 }, duration: .6 }, 1.3);
        },
        radar() {   // una oreja se gira hacia un ruido y mira
          const l = R(-16, -10);
          return gsap.timeline().to(orejaI, { rotation: l, duration: .12, ease: "power2.out" }, 0)
            .to(miras, { x: -2.4, duration: .25, ease: "power3.out" }, 0)
            .to(orejaD, { rotation: 6, duration: .15 }, .09)
            .to(orejaI, { rotation: 8, duration: .16 }, ">+.5")
            .to([orejaI, orejaD], { rotation: (i) => i ? 3 : -3, duration: .38, ease: "sine.inOut" }, ">+.1")
            .to(miras, { x: 0, duration: .3 }, "<");
        },
        ladeo() {   // inclina la cabeza con curiosidad
          const k = Math.random() < .5 ? -1 : 1;
          return gsap.timeline().to(mueve, { rotation: k * 10, duration: .26, ease: "back.out(1.4)" })
            .to(pups, { attr: { rx: 6.2, ry: 6.2 }, duration: .2 }, 0)
            .to(k < 0 ? orejaI : orejaD, { rotation: k < 0 ? -12 : 12, duration: .2 }, 0)
            .to(mueve, { rotation: 0, duration: .5, ease: "sine.inOut" }, "+=1.1")
            .to(pups, { attr: { rx: 5.4, ry: 5.4 }, duration: .4 }, "<")
            .to([orejaI, orejaD], { rotation: (i) => i ? 3 : -3, duration: .4 }, "<");
        },
        acecho() {   // se agacha, menea, salta... y "yo no fui"
          // (14-oct) se agacha HUNDIENDOSE en el piso (se funde con el: lo de abajo se corta en la linea), salta y cae plano
          const k = Math.random() < .5 ? -1 : 1, tl = gsap.timeline();
          tl.call(() => pisoVer(true), null, 0)
            .to(mueve, { y: 9, scaleY: .9, scaleX: 1.1, duration: .45, ease: "power2.out" }, 0)
            .to(pups, { attr: { rx: 6.8, ry: 6.8 }, duration: .16 }, 0)
            .to(lidI, { y: 3, rotation: 6, duration: .3 }, 0).to(lidD, { y: 3, rotation: -6, duration: .3 }, 0)
            .to(miras, { x: k * 1.6, y: -1, duration: .25, ease: "power3.out" }, .1);
          for (let i = 0; i < 6; i++) tl.to(mueve, { x: i % 2 ? 1.5 : -1.5, duration: .075, ease: "sine.inOut" });
          return tl.to(mueve, { x: k * 10, y: -24, scaleY: 1.15, scaleX: .92, rotation: k * 6, duration: .22, ease: "power2.out" })
            .to(mueve, { y: 3, scaleY: .9, scaleX: 1.08, rotation: 0, duration: .15, ease: "power2.in" })
            .to(mueve, { x: 0, y: 0, scaleX: 1, scaleY: 1, duration: .3, ease: "back.out(1.7)" })
            .call(() => pisoVer(false, .5), null, "+=.4")
            .to([lidI, lidD], { y: 8, rotation: 0, duration: .25 }, "<")
            .to(miras, { x: -k * 1.6, y: .5, duration: .2 }, "<")
            .to({}, { duration: .7 })
            .to([lidI, lidD], { y: -2, duration: .3 }).to(miras, { x: 0, y: 0, duration: .3 }, "<")
            .to(pups, { attr: { rx: 5.4, ry: 5.4 }, duration: .4 }, "<");
        },
        colita() {   // gato: la cola asoma por detras, se menea y se esconde
          const n = Math.round(R(2, 3)), tl = gsap.timeline()
            .to(colaAtras, { scale: 1, rotation: 0, duration: .45, ease: "back.out(1.7)" });
          for (let i = 0; i < n; i++) tl.to(colaAtras, { rotation: i % 2 ? 8 : -10, duration: R(.35, .5), ease: "sine.inOut" });
          return tl.to(colaAtras, { rotation: 0, duration: .3, ease: "sine.inOut" })
            .to(colaAtras, { scale: 0, rotation: -40, duration: .4, ease: "power2.in" }, "+=" + R(.4, 1.2));
        },
        brillo() {   // Lucero: la luz y la estrella titilan / Brote: la hoja se ilumina
          return gsap.timeline().to([luz, estrella, hoja].filter(Boolean), { scale: 1.25, duration: .25, yoyo: true, repeat: 1, ease: "sine.inOut" })
            .to(ojos, { y: -2, duration: .25, yoyo: true, repeat: 1 }, 0);
        },
      },
      trabajando: {
        leer() { return gsap.timeline().to(ojos, { x: -2.5, duration: R(.4, .6), ease: "sine.inOut" }).to(ojos, { x: 2.5, duration: R(.5, .8), ease: "sine.inOut" }).to(ojos, { x: 0, duration: .3 }); },
        pensar() {
          return gsap.timeline().add(cara("normal"))
            .to(ojos, { x: R(-3, 3), y: -3, duration: .3, ease: "power2.out" }, 0)
            .to(mueve, { rotation: R(-7, 7), duration: .5, ease: "sine.inOut" }, 0)
            .to(ojos, { x: 0, y: 1.5, duration: .3 }, "+=" + R(.8, 1.5))
            .to(mueve, { rotation: 0, duration: .5 }, "<")
            .add(cara("concentrado"), "<");
        },
        teclear() { return gsap.timeline().to(mueve, { y: -2.5, duration: .1, yoyo: true, repeat: Math.round(R(5, 9)), ease: "sine.inOut" }); },
        idea() {
          return gsap.timeline().add(cara("sorpresa"))
            .to(mueve, { y: -9, duration: .18, ease: "power2.out" }, 0)
            .to([hoja, antena, luz].filter(Boolean), { scale: 1.3, duration: .18 }, 0)
            .to(mueve, { y: 0, duration: .3, ease: "bounce.out" })
            .to([hoja, antena, luz].filter(Boolean), { scale: 1, duration: .4, ease: "elastic.out(1,.7)" }, "<")
            .add(cara("concentrado"), "+=.3");
        },
      },
    };
    // que gestos puede hacer ESTE personaje (segun las piezas que tiene)
    function disponible(n) {
      if (n === "brillo") return !!(luz || hoja);
      if (n === "sacudir") return !!(hoja || antena) && !esGato;
      if (n === "colita") return !!colaAtras;
      if (["parpadeoLento", "radar", "ladeo", "acecho"].includes(n)) return esGato;
      if (n === "bostezo") return !esGato;
      return true;
    }
    const pocoMovimiento = () => window.Companero ? window.Companero.reducido() : false;   // (5.a vuelta) se mira en cada vuelta: el ajuste "Animaciones completas" puede cambiar
    function director() {
      if (!vivo) return;
      if (pocoMovimiento()) { later(director, 8000); return; }   // sin gestos al azar: solo estados, parpadeo y respiracion
      const lista = GESTOS[estado];
      if (lista && (!accion || !accion.isActive())) {
        const nombres = Object.keys(lista).filter(n => n !== ultimo && disponible(n));
        ultimo = pick(nombres); accion = lista[ultimo]();
      }
      const g = AJ().gestos;
      later(director, estado === "trabajando" ? R(g.trabajandoMin, g.trabajandoMax) * 1000 : R(g.reposoMin, g.reposoMax) * 1000);
    }
    function vistazo() {}   // reemplazado por el director

    function base(t) {   // vuelve a la pose neutra con suavidad
      return t.to(cuerpo, { x: 0, y: 0, rotation: 0, scaleX: 1, scaleY: 1, duration: .45, ease: "back.out(1.8)" }, 0)
        .to(mueve, { x: 0, y: 0, rotation: 0, scaleX: 1, scaleY: 1, duration: .4, ease: "sine.out" }, 0)
        .to(ojos, { x: 0, y: 0, duration: .3 }, 0)
        .to(sombra, { scale: 1, opacity: .10, duration: .4 }, 0)
        .to([hoja, antena, accesorio].filter(Boolean), { rotation: 0, scale: 1, scaleX: 1, y: 0, duration: .6, ease: "elastic.out(1,.7)" }, 0)
        .to([luz].filter(Boolean), { scale: 1, opacity: .6, duration: .5 }, 0)
        .to(tents, { rotation: 0, duration: .5 }, 0);
    }
    // respiración con ritmo y profundidad que cambian en cada ciclo (no se siente como un metrónomo)
    const respirar = (amp = .03, dur = 1.7) => gsap.timeline({ repeat: -1, yoyo: true, repeatRefresh: true })
      .to(cuerpo, { scaleX: () => 1 + amp * R(.6, 1.2), scaleY: () => 1 - amp * R(.6, 1.2), duration: () => dur * R(.8, 1.25), ease: "sine.inOut" })
      .to(sombra, { scale: () => 1 + amp * 2, duration: () => dur * R(.8, 1.25), ease: "sine.inOut" }, 0);

    const EST = {
      reposo(t) {
        base(t); t.add(cara("normal"), 0);
        t.add(() => {
          loop = respirar(AJ().respiracion.amplitud, AJ().respiracion.duracion);
          if (hoja) loop.to(hoja, { rotation: 6, duration: 1.7, ease: "sine.inOut" }, 0);
          if (luz) loop.to(luz, { opacity: .7, scale: .94, duration: 1.7, ease: "sine.inOut" }, 0).to(cuerpo, { y: -3, duration: 1.7, ease: "sine.inOut" }, 0)
                       .to(tents, { rotation: 7, stagger: .25, duration: 1.7, ease: "sine.inOut" }, 0);
        });
      },
      trabajando(t) {
        t.to(cuerpo, { scaleY: .93, scaleX: 1.06, y: 0, rotation: 0, duration: .14, ease: "power2.in" }, 0)
         .add(cara("concentrado"), 0)
         .to(cuerpo, { scaleY: 1, scaleX: 1, duration: .4, ease: "back.out(3)" })
         .to(ojos, { y: 1.5, duration: .3 }, 0);
        t.add(() => {
          // fondo continuo y suave; los gestos (leer, pensar, teclear, idea) los pone el director al azar
          loop = respirar(.02, .9);
          if (hoja) loop.to(hoja, { scaleX: -1, duration: () => R(.45, .7), ease: "sine.inOut" }, 0);            // la hoja gira como hélice, a ritmo variable
          if (luz) loop.to(luz, { scale: () => R(1.05, 1.2), opacity: 1, duration: () => R(.3, .6), ease: "sine.inOut" }, 0)
                       .to(estrella, { rotation: "+=36", duration: .9, ease: "none" }, 0)
                       .to(tents, { rotation: () => R(6, 13), duration: () => R(.3, .5), stagger: .08, ease: "sine.inOut" }, 0);
          const tipoAcc = accesorio && accesorio.dataset.acc;
          if (tipoAcc === "juegos") loop.to(qa(".boton"), { opacity: .45, duration: .25, stagger: .12, ease: "none" }, 0).to(accesorio, { rotation: () => R(-3, 3), duration: .33, ease: "sine.inOut" }, 0);
          else if (tipoAcc === "musica") loop.to(qa(".almohadilla"), { scale: 1.06, duration: .268, transformOrigin: "50% 50%", ease: "sine.inOut" }, 0);
          else if (tipoAcc === "dnd") loop.to(q(".dado"), { rotation: "+=90", transformOrigin: "50% 50%", duration: 1, ease: "back.out(1.7)" }, 0);
          else if (tipoAcc === "instalaciones") loop.to(q(".casco"), { y: -1.5, duration: .3, ease: "sine.inOut" }, 0).fromTo(q(".destello"), { x: -8 }, { x: 38, duration: 1.2, ease: "sine.inOut" }, 0);
        });
      },
      escribio(t) {   // te escribió: salto de "¡ey!" y te saluda con la mirada
        t.to(cuerpo, { scaleY: .85, scaleX: 1.12, y: 0, rotation: 0, duration: .13, ease: "power2.in" }, 0)
         .add(cara("sorpresa"), 0)
         .to(ojos, { x: 0, y: -1, duration: .2 }, 0)
         .to(cuerpo, { y: -20, scaleY: 1.08, scaleX: .94, duration: .22, ease: "power2.out" })
         .to([hoja, antena].filter(Boolean), { scale: 1.2, duration: .22, ease: "back.out(3)" }, "<")
         .to(luz || {}, { scale: 1.4, opacity: 1, duration: .22 }, "<")
         .to(sombra, { scale: .7, opacity: .05, duration: .22 }, "<")
         .to(cuerpo, { y: 0, scaleY: .9, scaleX: 1.08, duration: .18, ease: "power2.in" })
         .to(sombra, { scale: 1, opacity: .1, duration: .18 }, "<")
         .to(cuerpo, { scaleY: 1, scaleX: 1, duration: .5, ease: "elastic.out(1,.7)" })
         .add(cara("feliz"), "-=.4");
        t.add(() => {
          loop = gsap.timeline({ repeat: -1, repeatDelay: R(.9, 1.8), repeatRefresh: true });
          loop.to(cuerpo, { rotation: -6, duration: .16, ease: "sine.inOut" }).to(cuerpo, { rotation: 6, duration: .2, ease: "sine.inOut" })
              .to(cuerpo, { rotation: 0, duration: .16, ease: "sine.inOut" })
              .to(cuerpo, { y: -7, duration: .16, yoyo: true, repeat: 1, ease: "power2.out" });
          if (hoja) loop.to(hoja, { rotation: -16, duration: .18, yoyo: true, repeat: 3, ease: "sine.inOut" }, 0);
          if (luz) loop.to(luz, { scale: 1.35, duration: .2, yoyo: true, repeat: 3 }, 0).to(estrella, { scale: 1.3, duration: .2, yoyo: true, repeat: 3 }, 0);
        });
      },
      enviado(t) {   // llegó tu respuesta: saltito con vuelta y vuelve a trabajar contento
        t.add(cara("feliz"), 0)
         .to(cuerpo, { scaleY: .82, scaleX: 1.14, y: 0, rotation: 0, duration: .15, ease: "power2.in" }, 0)
         .to(cuerpo, { y: -34, scaleY: 1.1, scaleX: .92, rotation: 360, duration: .9, ease: "power3.inOut" })
         .to(sombra, { scale: .6, opacity: .04, duration: .5 }, "<")
         .add(() => chispas(host), "<.15")
         .to(cuerpo, { y: 0, scaleY: 1, scaleX: 1, duration: .3, ease: "power2.in" })
         .to(sombra, { scale: 1, opacity: .1, duration: .3 }, "<")
         .to(cuerpo, { scaleY: .86, scaleX: 1.1, duration: .07 })
         .to(cuerpo, { scaleY: 1, scaleX: 1, duration: .6, ease: "back.out(1.7)" })
         .set(cuerpo, { rotation: 0 });
        t.add(() => { loop = respirar(.025, 1.2); });
      },
      dormido(t) {
        t.add(cara("normal"), 0)
         .to(qa(".parpado"), { scaleY: .45, duration: .6, ease: "sine.inOut" }, 0)             // cabecea
         .to(qa(".parpado"), { scaleY: .85, duration: .25 })                                    // se resiste
         .to(qa(".parpado"), { scaleY: .2, duration: .5, ease: "sine.inOut" })
         .add(cara("dormido", .2))
         .set(qa(".parpado"), { scaleY: 1 })
         .to(cuerpo, { y: 3, rotation: -4, scaleY: .96, scaleX: 1.03, duration: 1.4, ease: "sine.inOut" }, .2)
         .to(ojos, { x: 0, y: 1.5, duration: 1 }, .2)
         .to(hoja || {}, { rotation: 58, duration: 1.3, ease: "bounce.out" }, .6)
         .to(luz || {}, { opacity: .3, scale: .8, duration: 1.6, ease: "sine.inOut" }, .4)
         .to(antena || {}, { rotation: 25, duration: 1.3, ease: "bounce.out" }, .6)
         .to(tents, { rotation: 0, duration: 1 }, .3);
        t.add(() => {
          loop = respirar(.05, 2.4);
          const zz = () => { if (estado !== "dormido" || !vivo) return; zeta(host); later(zz, 1700); }; zz();
        });
      },
      atascado(t) {   // algo falló: se encoge, ojitos tristes, tiembla un poquito
        t.add(cara("triste"), 0)
         .to(cuerpo, { scaleY: .92, scaleX: 1.04, y: 2, rotation: 0, duration: .5, ease: "power2.out" }, 0)
         .to(ojos, { x: 0, y: 2, duration: .4 }, 0)
         .to(hoja || {}, { rotation: 35, duration: .7, ease: "power2.out" }, 0)
         .to(antena || {}, { rotation: -18, duration: .7, ease: "power2.out" }, 0)
         .to(luz || {}, { opacity: .5, scale: .85, duration: .6 }, 0);
        t.add(() => {
          loop = gsap.timeline({ repeat: -1, repeatDelay: 1.6 })
            .to(cuerpo, { x: -1.5, duration: .05, yoyo: true, repeat: 5, ease: "none" })
            .to(cuerpo, { x: 0, duration: .05 });
          if (luz) loop.to(luz, { opacity: .25, duration: .2, yoyo: true, repeat: 1 }, 0);
        });
      },
    };

    function ir(e) {
      if (!EST[e]) return;
      if (loop) loop.kill(); loop = null;
      gsap.killTweensOf([cuerpo, ojos, sombra, hoja, luz, antena, estrella, accesorio, ...tents].filter(Boolean));
      gsap.killTweensOf(qa(".parpado"));
      if (accion) accion.kill(); accion = null; ultimo = "";
      gsap.killTweensOf(mueve);
      gsap.to(mueve, { x: 0, y: 0, rotation: 0, scaleX: 1, scaleY: 1, duration: .3, ease: "sine.out" });
      gsap.set(qa(".parpado"), { scaleY: 1 });
      estado = e;
      if (colaAtras) gsap.to(colaAtras, { scale: 0, rotation: -40, duration: .3, overwrite: true });
      if (esGato) { gsap.killTweensOf([orejaI, orejaD, lidI, lidD, ...pups, ...miras]); pose(e); }
      if (colaFrente) {
        const tr = colaFrente.querySelectorAll(".trazo");
        if (e === "dormido") {
          // (14-oct) arrancar siempre desde cero: si quedaba a medias un "esconder la cola" anterior, su onComplete la
          // dejaba invisible (opacity 0) aunque ya estuviera durmiendo
          gsap.killTweensOf(tr); gsap.killTweensOf(colaFrente);
          gsap.set(tr, { strokeDashoffset: 1 });
          gsap.set(colaFrente, { opacity: 1 });
          // acurrucarse en UN solo movimiento continuo: se inclina y se agacha mientras la cola lo va rodeando,
          // y termina de acomodarse sin rebote (antes eran 3 pasos con frenadas y un back.out)
          gsap.timeline({ delay: .6 })
            .to(mueve, { rotation: -5, scaleY: .93, scaleX: 1.05, y: 2, duration: AJ().acurrucar.cuerpo, ease: "sine.inOut" }, 0)
            // (14-oct, LShinox: mejorar la cola al acurrucarse) primero la cola asoma por detras a la derecha y baja,
            // y desde ese mismo punto rodea el frente hasta dejar la punta levantada a la izquierda
            .to(colaAtras || {}, { scale: 1, rotation: 25, duration: .35, ease: "back.out(1.6)" }, .1)
            .to(colaAtras || {}, { scale: 0, rotation: 60, duration: .3, ease: "power2.in" }, .5)
            .to(tr, { strokeDashoffset: 0, duration: AJ().acurrucar.cola, ease: "power1.inOut" }, .45)
            .to(mueve, { rotation: -2.5, scaleY: .95, scaleX: 1.03, y: 2, duration: .9, ease: "sine.out" }, 1.1)
            .call(() => pisoVer(true, .6), null, .2);   // (14-oct) acostado: apoyado y plano sobre su piso
        } else {
          pisoVer(false);
          gsap.to(tr, { strokeDashoffset: 1, duration: .45, ease: "power2.in", overwrite: true, onComplete: () => { if (estado !== "dormido") gsap.set(colaFrente, { opacity: 0 }); } });   // sin esto queda un puntito (tapa redonda)
        }
      }
      const t = gsap.timeline(); EST[e](t);
      if (e !== "dormido") later(parpadear, 120);
      return t;
    }
    parpadeo(); later(director, R(1500, 3000));
    function pausar(si) { vivo = !si; [loop, accion].forEach(x => x && (si ? x.pause() : x.resume())); if (si) gsap.ticker.remove(tic); else { gsap.ticker.add(tic); parpadeo(); later(director, R(1500, 3000)); } }
    // ---- toque (estudio mascotas-adorables §toque): respuesta en <= 70 ms; mantener = caricia; 3 toques = cosquillas ----
    const mejillas = [...qa(".mejilla")];
    mejillas.forEach(m => { m.dataset.base = m.getAttribute("opacity") || "1"; });
    let caricia = null, toques = [], previa = null;
    function tocar() {
      const ahora = performance.now(); toques = toques.filter(x => ahora - x < 700); toques.push(ahora);
      if (toques.length >= 3) { toques = []; return cosquillas(); }
      gsap.timeline().to(mueve, { scaleY: .9, scaleX: 1.08, duration: .07, ease: "power3.out" })
        .to(mueve, { y: -AJ().toque.salto, scaleY: 1.05, scaleX: .97, duration: .13, ease: "power3.out" })
        .to(mueve, { y: 0, scaleY: 1, scaleX: 1, duration: .3, ease: `back.out(${AJ().toque.rebote})` });
      gsap.to(ojos, { x: 0, y: -1.5, duration: .15, yoyo: true, repeat: 1 });
    }
    function cosquillas() {
      previa = expr; cara("feliz");
      gsap.to(mejillas, { opacity: .8, duration: .2, overwrite: true });
      gsap.timeline().to(mueve, { rotation: 7, duration: .07, yoyo: true, repeat: 7, ease: "sine.inOut" }).to(mueve, { rotation: 0, duration: .15 })
        .call(() => { cara(previa || "normal"); restaurarMejillas(); });
    }
    function restaurarMejillas() { mejillas.forEach(m => gsap.to(m, { opacity: +m.dataset.base, duration: .6, overwrite: true })); }
    function acariciar(si) {
      if (si) {
        if (caricia) return;
        previa = expr;
        caricia = gsap.timeline()
          .to(mueve, { scaleY: .95, scaleX: 1.04, duration: .35, ease: "sine.out" })
          .call(() => { cara("feliz"); gsap.to(mejillas, { opacity: .8, duration: .2, overwrite: true }); }, null, .35)
          .to(mueve, { rotation: 4, duration: .6, yoyo: true, repeat: -1, ease: "sine.inOut" }, .4)
          .call(() => corazon(host), null, 1.6);
      } else {
        if (!caricia) return tocar();
        caricia.kill(); caricia = null;
        gsap.timeline().to(mueve, { rotation: 0, scaleY: 1.04, scaleX: .97, duration: .25, ease: "sine.out" })   // suspiro
          .to(mueve, { scaleY: 1, scaleX: 1, duration: .5, ease: "sine.inOut" })
          .call(() => { cara(previa && previa !== "feliz" ? previa : "normal"); restaurarMejillas(); }, null, "+=.3");
      }
    }
    function gesto(n) {
      const f = (GESTOS.reposo || {})[n] || (GESTOS.trabajando || {})[n];
      if (!f || !disponible(n)) return false;
      if (accion) accion.kill(); accion = f(); ultimo = n; return true;
    }
    function nombresGestos() { return [...Object.keys(GESTOS.reposo), ...Object.keys(GESTOS.trabajando)]; }
    // (14-oct, idea de Coucou) le estas arrastrando algo encima: se estira, abre los ojos y para las orejas, listo para
    // atraparlo; al soltar lejos vuelve a su pose
    function atrapar(si) {
      if (!esGato) return;
      if (si) {
        gsap.to(mueve, { scaleY: 1.07, scaleX: .96, y: -2, duration: .25, ease: "back.out(2)", overwrite: "auto" });
        gsap.to(pups, { attr: { rx: 7.2, ry: 7.2 }, duration: .2, overwrite: "auto" });
        gsap.to([orejaI, orejaD], { rotation: (i) => i ? 10 : -10, duration: .2, overwrite: "auto" });
        pisoVer(true);
      } else {
        gsap.to(mueve, { scaleY: 1, scaleX: 1, y: 0, duration: .35, ease: "sine.out", overwrite: "auto" });
        pose(estado); pisoVer(estado === "dormido");
      }
    }
    // (15-oct) mirar hacia un punto: nx, ny entre -1 y 1 (desde el centro del personaje); null = vuelve a mirar al frente.
    // La mascota lo usa con el mouse encima o con un archivo arrastrado encima (y siempre, si lo activas en la bandeja).
    function mirarA(nx, ny) {
      const pup = [...qa(".pupila"), ...miras];
      if (nx == null) { gsap.to([ojos, ...pup], { x: 0, y: 0, duration: .35, ease: "power2.out", overwrite: "auto" }); return; }
      nx = Math.max(-1, Math.min(1, nx)); ny = Math.max(-1, Math.min(1, ny));
      gsap.to(ojos, { x: nx * 3.2, y: ny * (ny < 0 ? 1.2 : 2), duration: .18, ease: "power2.out", overwrite: "auto" });
      if (pup.length) gsap.to(pup, { x: nx * 1.4, y: ny * 1, duration: .18, ease: "power2.out", overwrite: "auto" });
    }
    return { ir, pausar, insignia, tocar, acariciar, gesto, atrapar, mirarA, nombresGestos, cosquillas, get estado() { return estado; },
      // (19-oct) "ocupado": hay un gesto en curso (la mascota de PC sube los cuadros por segundo)
      get ocupado() { return !!(accion && accion.isActive()); },
      destruir() { vivo = false; gsap.ticker.remove(tic); timers.forEach(clearTimeout); if (loop) loop.kill(); if (accion) accion.kill(); } };
  }

  // chispas y "z": viven DENTRO del personaje (posición absoluta en su caja), así nunca quedan flotando
  // encima de otras pantallas; y no se generan si el personaje no está a la vista.
  function visible(host) { return !document.hidden && host.isConnected && host.offsetParent !== null; }
  function capa(host) { if (getComputedStyle(host).position === "static") host.style.position = "relative"; return host; }
  function chispas(host) {
    if (!visible(host)) return;
    const cols = ["#ffd659", "#8fcf5f", "#b7a3ec", "#7cc6f2", "#f2879b"], w = host.clientWidth, h = host.clientHeight; capa(host);
    for (let i = 0; i < 14; i++) {
      const d = document.createElement("div");
      d.style.cssText = `position:absolute;left:${w / 2}px;top:${h * .35}px;width:${6 + Math.random() * 5}px;height:${6 + Math.random() * 5}px;border-radius:${Math.random() < .5 ? "50%" : "2px"};background:${cols[i % cols.length]};pointer-events:none`;
      host.appendChild(d);
      gsap.to(d, { x: gsap.utils.random(-w * .55, w * .55), y: gsap.utils.random(-h * .55, h * .1), rotation: gsap.utils.random(-180, 180), opacity: 0, duration: gsap.utils.random(.7, 1.2), ease: "power2.out", onComplete: () => d.remove() });
    }
  }
  function corazon(host) {
    if (!visible(host)) return;
    const w = host.clientWidth, h = host.clientHeight, d = document.createElement("div"); capa(host);
    d.textContent = "♥"; d.style.cssText = `position:absolute;left:${w * .62}px;top:${h * .08}px;font:700 ${Math.max(14, w * .14)}px system-ui;color:#f2879b;pointer-events:none`;
    host.appendChild(d);
    gsap.fromTo(d, { opacity: 0, scale: .3 }, { opacity: 1, scale: 1.1, y: -h * .12, duration: .5, ease: "back.out(2)", onComplete: () => gsap.to(d, { opacity: 0, y: -h * .25, duration: .8, delay: .4, onComplete: () => d.remove() }) });
  }
  function zeta(host) {
    if (!visible(host) || host.querySelectorAll(".zeta").length > 2) return;
    const w = host.clientWidth, h = host.clientHeight, d = document.createElement("div"); capa(host);
    d.className = "zeta"; d.textContent = "z";
    d.style.cssText = `position:absolute;left:${w * .66}px;top:${h * .12}px;font:700 ${Math.max(11, w * .1)}px system-ui;color:#9c94c9;pointer-events:none`;
    host.appendChild(d);
    gsap.fromTo(d, { opacity: 0, scale: .5 }, { opacity: 1, scale: 1.15, x: w * .12, y: -h * .18, duration: 2, ease: "sine.out", onComplete: () => gsap.to(d, { opacity: 0, duration: .4, onComplete: () => d.remove() }) });
  }

  // (26-oct) adornos DOM de siempre, para que personajes-lottie.js (el gato Lottie) los reuse
  // (27-oct, 5.a vuelta) "Animaciones completas" (por aparato, NO se sincroniza; encendido por defecto): encendido = la mascota ignora
  // prefers-reduced-motion y hace todo (gestos al azar, guiño, morph de la capsula, respiracion); apagado = respeta el ajuste de Windows/iOS.
  // PC: companero-tauri.js fija window.KODAMA_ANIM_COMPLETAS (booleano); celular: localStorage "animCompletas" ("0" = apagado) o el mismo booleano.
  const animCompletas = () => { if (typeof window.KODAMA_ANIM_COMPLETAS === "boolean") return window.KODAMA_ANIM_COMPLETAS; try { if (localStorage.getItem("animCompletas") === "0") return false; } catch (e) {} return true; };
  const reducido = () => !animCompletas() && matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.Companero = { DEF, crear, animCompletas, reducido, adornos: { chispas, corazon, zeta }, ESTADOS:["reposo", "trabajando", "escribio", "enviado", "dormido", "atascado"] };
})();
