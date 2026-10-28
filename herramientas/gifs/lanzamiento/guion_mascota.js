// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Guion del GIF de la mascota (pagina REAL de la mascota + hub falso con chats FICTICIOS). Se evalua con grabar.js despues de cargar grabar.html.
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const HUB = "http://127.0.0.1:8795";
  const esc = async e => { await fetch(HUB + "/_set", { method: "POST", body: JSON.stringify({ esc: e }) }); await cargar(); };
  const cap = document.createElement("div");
  Object.assign(cap.style, { position: "fixed", zIndex: "200", left: "10px", top: "158px", font: "600 13px Segoe UI, sans-serif", background: "rgba(28,28,30,.78)", color: "#fff", padding: "4px 10px", borderRadius: "8px", pointerEvents: "none" });
  document.body.appendChild(cap);
  const dec = t => { cap.textContent = t; };
  const fan = document.createElement("div"); fan.textContent = "📄 informe.pdf";
  Object.assign(fan.style, { position: "fixed", zIndex: "100", pointerEvents: "none", font: "600 12px Segoe UI, sans-serif", background: "#fff", color: "#222", padding: "4px 9px", borderRadius: "8px", boxShadow: "0 4px 14px rgba(0,0,0,.35)", display: "none", left: "0px", top: "0px", whiteSpace: "nowrap" });
  document.body.appendChild(fan);
  const arr = (tipo, x, y) => {
    const dt = new DataTransfer(); dt.items.add(new File(["x"], "informe.pdf"));
    (document.elementFromPoint(x, y) || document.body).dispatchEvent(new DragEvent(tipo, { bubbles: true, cancelable: true, clientX: x, clientY: y, dataTransfer: dt }));
  };
  const centro = () => { const r = (document.body.classList.contains("caps") ? $("pie") : $("pj")).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  for (let i = 0; i < 60 && !(typeof comp !== "undefined" && comp && chat); i++) await sleep(250);
  await esc("reposo"); await sleep(900);
  dec("Te acompaña en una esquina"); await sleep(2000);
  dec("Tu chat trabaja: pensando… (3/7)"); await esc("pensando"); await sleep(400); abrirEn("tesis"); await sleep(2600);
  dec("Ejecutando un comando… (3/7)"); await esc("ejecutando"); await sleep(2400);
  cerrar(); await sleep(700);
  dec("Termina y te pregunta algo"); await esc("pregunta"); await sleep(3400);
  dec("Respondes sin ir al chat"); $("asresp").click(); await sleep(2600);
  dec("Y ves los chats que te esperan"); await esc("dos"); await sleep(1000);
  const lp = $("blistap"); if (lp) lp.click(); await sleep(2800);
  cerrar(); await sleep(800);  dec("Suelta un archivo sobre ella"); const [cx, cy] = centro();
  for (let i = 0; i <= 14; i++) { const k = i / 14, x = cx - 120 + 110 * k, y = cy - 150 + 130 * k; fan.style.display = "block"; fan.style.left = (x + 8) + "px"; fan.style.top = (y + 8) + "px"; arr(i === 0 ? "dragenter" : "dragover", x, y); await sleep(110); }
  window.__RUTAS = ["C:\\Documentos\\informe.pdf"]; fan.style.display = "none"; arr("drop", cx, cy); await sleep(2600);
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await sleep(700);
  window.__gifFin = true;
})();

