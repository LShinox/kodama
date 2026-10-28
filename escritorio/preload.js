// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("companero", {
  conf: () => ipcRenderer.invoke("conf"),
  estado: () => ipcRenderer.invoke("estado"),
  responder: (chat, texto, foto) => ipcRenderer.invoke("responder", chat, texto, foto),
  interactivo: si => ipcRenderer.send("interactivo", si),
  escribir: si => ipcRenderer.send("escribir", si),
  arrastrar: (dx, dy) => ipcRenderer.send("arrastrar", dx, dy),
  alCambiarPj: f => ipcRenderer.on("pj", (_e, v) => f(v)),
  alVisible: f => ipcRenderer.on("visible", (_e, v) => f(v)),
  inactivo: () => ipcRenderer.invoke("inactivo"),
  ajustes: () => ipcRenderer.invoke("ajustes"),
  grupos: () => ipcRenderer.invoke("grupos"),
  grupo: id => ipcRenderer.invoke("grupo", id),
  liberar: chat => ipcRenderer.invoke("liberar", chat),
  abrir: (url, texto) => ipcRenderer.send("abrir", url, texto),
  alCursor: f => ipcRenderer.on("cursor", (_e, x, y) => f(x, y)),
  alAtajo: f => ipcRenderer.on("atajo", (_e, v) => f(v)),
  alNoMolestar: f => ipcRenderer.on("noMolestar", (_e, v) => f(v)),
  alSonido: f => ipcRenderer.on("sonido", (_e, v) => f(v)),
});
