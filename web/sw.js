// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Service worker de Kodama: avisos (Web Push) y numero en el icono. (13-oct v2, estudio de UX)
// (14-oct) si la PC no responde, abrir la app muestra el diagnostico ("¿No puedes conectar?") en vez del error del
// navegador: se guarda una copia al instalar y solo se usa cuando la red falla (todo lo demas va siempre a la red)
const COPIA = "companero-diag-v1";
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil(caches.open(COPIA).then(c => c.add("diagnostico.html")).catch(() => {})); });
self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => caches.match("diagnostico.html").then(r => r || Response.error())));
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

// (14-oct) botones en el aviso (Android/Chrome; el iPhone no los muestra): responder sin abrir la app
const ACCIONES = {
  pregunta: [{ action: "r:Sí", title: "Sí" }, { action: "r:No", title: "No" }],
  termino: [{ action: "r:OK, adelante.", title: "OK ✅" }, { action: "r:Sigue con lo que ibas.", title: "Sigue ▶" }],
  permiso: [{ action: "p:allow", title: "✅ Permitir" }, { action: "p:deny", title: "⛔ Denegar" }],
};
self.addEventListener("push", e => {
  let d = {}; try { d = e.data.json(); } catch (err) { d = { titulo: "Kodama", cuerpo: e.data ? e.data.text() : "" }; }
  const n = d.notification || { title: d.titulo || "Kodama", body: d.cuerpo || "" };
  // (14-oct, auditoria) un permiso NO se aprueba desde el aviso si el aviso no lo muestra entero; (22-oct, mejora 4)
  // si el hub manda el pedido COMPLETO en el cuerpo ("completo"), si van Permitir/Denegar en el aviso
  const acciones = d.permiso ? (d.completo ? ACCIONES.permiso : []) : d.chat && ACCIONES[d.tipo] ? ACCIONES[d.tipo] : [];
  e.waitUntil((async () => {
    // siempre mostrar algo: si no, iOS puede revocar la suscripcion
    await self.registration.showNotification(n.title || "Kodama", { body: n.body || "", tag: d.chat || "companero",
      data: { chat: d.chat || "", permiso: d.permiso || "" }, actions: acciones });
    try { if (self.navigator.setAppBadge && typeof d.n === "number") d.n ? await self.navigator.setAppBadge(d.n) : await self.navigator.clearAppBadge(); } catch (err) {}
  })());
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const datos = e.notification.data || {}, chat = datos.chat || "";
  if (e.action) {   // tocaste un boton del aviso: se responde desde aca, sin abrir la app
    const [tipo, valor] = [e.action.slice(0, 1), e.action.slice(2)];
    const pedido = tipo === "p"
      ? fetch("api/permiso", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: datos.permiso, decision: valor }) })
      : fetch("api/responder", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chat, texto: valor }) });
    e.waitUntil(pedido.then(r => r.json()).then(j => self.registration.showNotification(j.ok ? "✓ Enviado" : "No se pudo enviar",
      { body: j.ok ? "" : (j.error || ""), tag: "companero-ok" })).catch(() => self.registration.showNotification("Sin conexión con la PC", { tag: "companero-ok" })));
    return;
  }
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(cs => {
    for (const c of cs) { c.postMessage({ abrir: chat }); return c.focus(); }
    return self.clients.openWindow("./" + (chat ? "#" + chat : ""));
  }));
});
