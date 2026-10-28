// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
(() => {
  setTimeout(() => irVista("chats"), 2400);
  setTimeout(() => abrir("proyecto"), 4600);
  setTimeout(() => { try { cerrarChat(); } catch (e) {} }, 7600);
  setTimeout(() => abrir("tesis"), 8600);
  setTimeout(() => { $("perm-si").click(); }, 11200);
  setTimeout(() => { try { cerrarChat(); } catch (e) {} irVista("ajustes"); }, 12600);
  setTimeout(() => { const e = [...document.querySelectorAll("#v-ajustes .sec-cab")].find(x => x.textContent.trim() === "Seguridad"); if (e) e.scrollIntoView({ behavior: "smooth", block: "center" }); }, 14200);
})();