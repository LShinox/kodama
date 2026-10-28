// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Arma la carpeta ui\ de la mascota en Tauri a partir de la pagina de la mascota (escritorio\index.html):
// cambia las rutas ../web/ -> web/, quita la CSP de la pagina (la pone tauri.conf.json, que ademas deja hablar
// con el hub) y agrega companero-tauri.js, que hace de puente entre la pagina, la ventana y el hub.
// (26-oct) tambien copia el gato Lottie: personajes-lottie.js y la carpeta web\lottie\ (lottie-web 5.12.2 light + los JSON).
const fs = require("fs"), path = require("path");
const AQUI = __dirname, RAIZ = path.join(AQUI, ".."), UI = path.join(AQUI, "ui");
fs.mkdirSync(path.join(UI, "web", "lottie"), { recursive: true });
let html = fs.readFileSync(path.join(RAIZ, "escritorio", "index.html"), "utf8");
html = html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>\s*/i, "")
           .replace(/\.\.\/web\//g, "web/")
           .replace(/<title>/i, '<script src="companero-tauri.js"></script>\n<title>');
fs.writeFileSync(path.join(UI, "index.html"), html);
for (const f of ["gsap.min.js", "personajes.js", "personajes-lottie.js", "i18n.js"]) fs.copyFileSync(path.join(RAIZ, "web", f), path.join(UI, "web", f));
const LOT = path.join(RAIZ, "web", "lottie");
// (27-oct, 4.a vuelta) solo archivos: web\lottie\muestras\ (muestras de ojos de "atascado") es una carpeta y no va a la mascota
for (const e of fs.readdirSync(LOT, { withFileTypes: true })) if (e.isFile()) fs.copyFileSync(path.join(LOT, e.name), path.join(UI, "web", "lottie", e.name));
console.log("ui listo:", fs.readdirSync(UI).join(", "), "| lottie:", fs.readdirSync(path.join(UI, "web", "lottie")).length, "archivos");
