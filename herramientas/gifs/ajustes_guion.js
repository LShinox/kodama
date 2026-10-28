// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// guion del GIF de Ajustes: solo el escritorio; visible -> abrir/cerrar; despues en capsula -> abrir/cerrar
(() => {
  document.querySelector("main").style.padding = "0";
  document.querySelectorAll("h1, .sub, .controles, h3, .notas, #pista").forEach(e => e.style.display = "none");
  const esc = document.getElementById("esc"); esc.style.borderRadius = "0"; esc.style.height = "760px";
  window.scrollTo(0, 0); pintarReposo();
  setTimeout(() => abrirAjustes("inicio"), 600);
  setTimeout(() => cerrarVen(), 3600);
  setTimeout(() => { document.querySelector("#c-modo [data-m=visCaps]").click(); }, 5600);
  setTimeout(() => abrirAjustes("inicio"), 6100);
  setTimeout(() => cerrarVen(), 9100);
})();
