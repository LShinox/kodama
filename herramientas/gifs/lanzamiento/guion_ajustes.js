// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Guion del GIF de Ajustes (pagina REAL de la mascota + hub falso). Se evalua con grabar.js despues de cargar grabar.html.
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const HUB = "http://127.0.0.1:8795";
  await fetch(HUB + "/_set", { method: "POST", body: JSON.stringify({ esc: "reposo" }) }); await cargar();
  const cap = document.createElement("div");
  Object.assign(cap.style, { position: "fixed", zIndex: "300", left: "10px", top: "10px", font: "600 13px Segoe UI, sans-serif", background: "rgba(28,28,30,.78)", color: "#fff", padding: "4px 10px", borderRadius: "8px", pointerEvents: "none" });
  document.body.appendChild(cap);
  const dec = t => { cap.textContent = t; };
  for (let i = 0; i < 60 && !(typeof comp !== "undefined" && comp && chat); i++) await sleep(250);
  await sleep(1200);
  dec("Ajustes: la ventana sale de la mascota"); abrirPanel("inicio"); await sleep(3200);
  const ir = n => { const e = document.querySelector('#ajpc [data-ir="' + n + '"]'); if (e) e.click(); };
  dec("Personaje y color"); ir("personaje"); await sleep(2400);
  const o = document.querySelectorAll("#aj-colores .o"); if (o[1]) o[1].click(); await sleep(1800);
  if (o[0]) o[0].click(); await sleep(1200);
  document.querySelector('#ajpc [data-p="personaje"] .at').click(); await sleep(1200);
  dec("Y todo lo demás: cápsula, sueño profundo, alarma"); const cu = document.querySelector("#ajpc .cu"); if (cu) cu.scrollTo({ top: 400, behavior: "smooth" }); await sleep(2600);
  if (cu) cu.scrollTo({ top: 0, behavior: "smooth" }); await sleep(900);
  cerrarPanel(); await sleep(2200);
  window.__gifFin = true;
})();
