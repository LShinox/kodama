// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Datos FICTICIOS para grabar la app del celular (GIF del repo). Nada de chats reales: solo "Mi proyecto", "Tesis" y "Web".
// Se inyecta antes que el resto de la pagina (herramientas\gifs\lanzamiento\armar_celular.py lo agrega a app.html de una copia).
(function () {
  const a = Date.now() / 1000;
  const E = { proyecto: { nombre: "Mi proyecto", estado: "termino", ultimo_ts: a - 120, visto: a - 60, tipo: "pregunta", n: 1, linea: "¿Publico la versión de hoy o la dejo para mañana?",
      mensajes: [{ yo: true, texto: "Revisa todo y dime si está listo", ts: a - 900 }, { yo: false, texto: "Revisé todo: está listo. ¿Publico la versión de hoy o la dejo para mañana?", ts: a - 120 }] },
    tesis: { nombre: "Tesis", estado: "reposo", visto: a - 400, ultimo_ts: a - 700, mensajes: [{ yo: false, texto: "Voy a compilar el documento para revisar los cambios.", ts: a - 60 }], permiso: { id: "ab12cd34", texto: "Bash: npm run build", ts: a - 5, cola: 1 } },
    web: { nombre: "Web", estado: "trabajando", haciendo: "editando index.html", fase: "ejecutando", fase_tipo: "comando", tareas: { h: 3, t: 7, a: "Revisar el capítulo 2" }, visto: a - 5, ultimo_ts: a - 600, mensajes: [] },
    _seleccion: "personales", _version: "1.0.0" };
  const R = o => new Response(JSON.stringify(o), { headers: { "Content-Type": "application/json" } }), real = window.fetch.bind(window);
  window.fetch = async (u, op) => { u = String(u);
    if (u.startsWith("api/estado")) return R(E); if (u.startsWith("api/personaje")) return R({ ok: true, pj: "gatoPro", color: "negro", florCactus: true });
    if (u.startsWith("api/")) return R({ ok: true }); return real(u, op); };
  window.EventSource = function () { this.readyState = 0; this.close = () => {}; this.addEventListener = () => {}; };
  try { localStorage.setItem("bienvenida", "1"); localStorage.setItem("tema", "claro"); } catch (e) {}
})();
