// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// (04-nov) Prueba del plugin de OpenCode (opencode_plugin.js) con un cliente falso y un puente falso, todo en una carpeta temporal.
// Uso: node pruebas/probar_plugin_opencode.mjs  (sale con 1 si algo falla)
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = dirname(dirname(fileURLToPath(import.meta.url)));
const aSlash = p => p.replace(/\\/g, "/");
const tmp = mkdtempSync(join(tmpdir(), "kodama-prueba-plugin-oc-"));
const estado = join(tmp, "estado");
const registro = join(tmp, "registro.jsonl");
const falso = join(tmp, "puente_falso.mjs");
const plugin = join(tmp, "kodama.mjs");
const buzon = join(estado, "opencode");
mkdirSync(estado, { recursive: true });

// puente falso: anota cada evento (JSON por stdin) en registro.jsonl; a PermissionRequest responde "allow"
writeFileSync(falso, `
import { readFileSync, appendFileSync } from "node:fs";
const d = JSON.parse(readFileSync(0, "utf8"));
appendFileSync(${JSON.stringify(registro)}, JSON.stringify(d) + "\\n");
if (d.evento === "PermissionRequest" && d.tool_name === "AskUserQuestion") {
  const q = d.tool_input.questions[0];
  if (q.header === "NO") process.exit(0);   // sin decision: no imprime nada
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "allow", updatedInput: { questions: d.tool_input.questions, answers: { [q.question]: q.options[1].label } } } }));
} else if (d.evento === "PermissionRequest" && d.tool_input.command !== "SIN") process.stdout.write(JSON.stringify({ hookSpecificOutput: { decision: { behavior: "allow" } } }));   // "SIN": sin decision (salida vacia)
`);

// copia del plugin con las tres rutas cambiadas (node como "Python", el puente falso y la carpeta temporal)
const fuente = readFileSync(join(AQUI, "opencode_plugin.js"), "utf8");
writeFileSync(plugin, fuente.replace("__PY__", aSlash(process.execPath))
  .replace("__SCRIPT__", aSlash(falso))
  .replace("__ESTADO__", aSlash(estado)));

const llamadas = [];
const client = {
  session: {
    messages: async ({ path }) => {
      llamadas.push({ tipo: "messages", id: path.id });
      return { data: [{ info: { role: "assistant" }, parts: [{ type: "text", text: "hola" }] }] };
    },
    promptAsync: async pedido => { llamadas.push({ tipo: "promptAsync", pedido }); },
  },
  postSessionIdPermissionsPermissionId: async pedido => { llamadas.push({ tipo: "permiso", pedido }); },
  question: { reply: async pedido => { llamadas.push({ tipo: "respuesta_pregunta", pedido }); } },
};
// cliente sin metodo de respuesta a preguntas (como la 1.19.5): no deben salir preguntas al celular
const clienteSinPreguntas = { ...client, question: undefined };

let ok = 0;
const mal = [];
function ver(nombre, obtenido, esperado) {
  const iguales = JSON.stringify(obtenido) === JSON.stringify(esperado);
  if (iguales) ok++; else mal.push(nombre);
  console.log((iguales ? "OK  " : "MAL ") + nombre + (iguales ? "" : ` -> ${JSON.stringify(obtenido)} (esperado ${JSON.stringify(esperado)})`));
}
const esperar = ms => new Promise(r => setTimeout(r, ms));
const registrado = () => existsSync(registro)
  ? readFileSync(registro, "utf8").trim().split("\n").filter(Boolean).map(l => JSON.parse(l))
  : [];

let h = null;
try {
  const { Kodama } = await import(pathToFileURL(plugin).href);
  h = await Kodama({ client, directory: "C:/x" });

  // 1. sesion nueva -> SessionStart, con el titulo
  await h.event({ event: { type: "session.created", properties: { info: { id: "ses1", title: "Mi tarea" } } } });
  await esperar(800);
  ver("session.created manda SessionStart", registrado().filter(r => r.evento === "SessionStart").map(r => r.session_id), ["ses1"]);
  ver("SessionStart lleva el titulo", registrado().filter(r => r.evento === "SessionStart").map(r => r.titulo), ["Mi tarea"]);

  // 2. subagente (tiene parentID): no manda nada, ni su idle
  await h.event({ event: { type: "session.created", properties: { info: { id: "hija1", parentID: "ses1" } } } });
  await h.event({ event: { type: "session.idle", properties: { sessionID: "hija1" } } });
  await esperar(800);
  ver("subagente: no manda nada", registrado().filter(r => r.session_id === "hija1").length, 0);

  // 3. fin de turno -> Stop con el ultimo texto del asistente
  await h.event({ event: { type: "session.idle", properties: { sessionID: "ses1" } } });
  await esperar(800);
  ver("session.idle manda Stop con el texto", registrado().filter(r => r.evento === "Stop").map(r => r.texto), ["hola"]);

  // 4. permiso: dos avisos del mismo id -> una sola respuesta "once"
  const perm = { id: "perm1", sessionID: "ses1", type: "bash", title: "ls -la" };
  await h.event({ event: { type: "permission.updated", properties: perm } });
  await h.event({ event: { type: "permission.updated", properties: perm } });
  await esperar(800);
  const permisos = llamadas.filter(l => l.tipo === "permiso");
  ver("permiso: una sola respuesta aunque llegue dos veces", permisos.length, 1);
  ver("permiso: response once", permisos[0] && permisos[0].pedido.body.response, "once");
  ver("permiso: ruta de sesion y permiso", permisos[0] && permisos[0].pedido.path, { id: "ses1", permissionID: "perm1" });
  ver("permiso: PermissionRequest anotado una vez", registrado().filter(r => r.evento === "PermissionRequest").length, 1);

  // 5. mensaje escrito en la PC -> UserPromptSubmit
  await h["chat.message"]({ sessionID: "ses1" }, { parts: [{ type: "text", text: "hola desde la PC" }] });
  await esperar(800);
  ver("chat.message manda UserPromptSubmit", registrado().filter(r => r.evento === "UserPromptSubmit").map(r => r.texto), ["hola desde la PC"]);

  // 6. respuesta desde el celular -> llega a la sesion conocida, se borra, y su eco no se anota
  mkdirSync(buzon, { recursive: true });
  writeFileSync(join(buzon, "ses1.1.respuesta"), "respuesta del celu");
  const t0 = Date.now();
  while (Date.now() - t0 < 3000 && !llamadas.some(l => l.tipo === "promptAsync")) await esperar(100);
  const entregado = llamadas.find(l => l.tipo === "promptAsync");
  ver("respuesta llega a promptAsync en menos de 3 s", Boolean(entregado) && Date.now() - t0 < 3000, true);
  ver("promptAsync con el texto y la sesion", entregado && entregado.pedido,
    { path: { id: "ses1" }, body: { parts: [{ type: "text", text: "respuesta del celu" }] } });
  ver("el .respuesta se borra", existsSync(join(buzon, "ses1.1.respuesta")), false);
  await h["chat.message"]({ sessionID: "ses1" }, { parts: [{ type: "text", text: "respuesta del celu" }] });
  await esperar(800);
  ver("el eco de la respuesta no se anota como escrito en la PC",
    registrado().filter(r => r.evento === "UserPromptSubmit").map(r => r.texto), ["hola desde la PC"]);

  // 7. archivo de una sesion desconocida: no se toca
  writeFileSync(join(buzon, "ses9.1.respuesta"), "de otra ventana");
  await esperar(2500);
  ver("sesion desconocida: el archivo no se toca", existsSync(join(buzon, "ses9.1.respuesta")), true);
  ver("sesion desconocida: no llega a promptAsync", llamadas.filter(l => l.tipo === "promptAsync" && l.pedido.path.id === "ses9").length, 0);

  // 8. fase: antes de una herramienta -> PreToolUse con el nombre de Claude y file_path
  const de = (evento) => registrado().filter(r => r.evento === evento);
  await h["tool.execute.before"]({ tool: "bash", sessionID: "ses1", callID: "c1" }, { args: { command: "ls -la", description: "x" } });
  await h["tool.execute.before"]({ tool: "read", sessionID: "ses1", callID: "c2" }, { args: { filePath: "C:/x/a.txt" } });
  await h["tool.execute.before"]({ tool: "todoread", sessionID: "ses1", callID: "c3" }, { args: {} });
  await h["tool.execute.before"]({ tool: "bash", sessionID: "hija1", callID: "c4" }, { args: { command: "pwd" } });
  await esperar(800);
  ver("before bash -> PreToolUse Bash con command", de("PreToolUse").filter(r => r.tool_name === "Bash").map(r => r.tool_input.command), ["ls -la"]);
  ver("before read -> PreToolUse Read con file_path", de("PreToolUse").filter(r => r.tool_name === "Read").map(r => r.tool_input.file_path), ["C:/x/a.txt"]);
  ver("before todoread se salta; hija ignorada", de("PreToolUse").length, 2);

  // 9. despues de una herramienta -> PostToolUse con el nombre mapeado
  await h["tool.execute.after"]({ tool: "edit", sessionID: "ses1", callID: "c5", args: { filePath: "b.ts" } }, { title: "", output: "", metadata: {} });
  await h["tool.execute.after"]({ tool: "mi_tool", sessionID: "hija1", callID: "c6", args: {} }, { title: "", output: "", metadata: {} });
  await esperar(800);
  ver("after edit -> PostToolUse Edit con file_path", de("PostToolUse").filter(r => r.session_id === "ses1").map(r => [r.tool_name, r.tool_input.file_path]), [["Edit", "b.ts"]]);
  ver("after de hija ignorado", de("PostToolUse").filter(r => r.session_id === "hija1").length, 0);

  // 10. progreso de tareas -> PostToolUse TodoWrite con la lista
  await h.event({ event: { type: "todo.updated", properties: { sessionID: "ses1", todos: [
    { id: "1", content: "a", status: "completed", priority: "high" },
    { id: "2", content: "b", status: "in_progress", priority: "high" },
    { id: "3", content: "c", status: "pending", priority: "low" }] } } });
  await h.event({ event: { type: "todo.updated", properties: { sessionID: "hija1", todos: [] } } });
  await esperar(800);
  ver("todo.updated -> PostToolUse TodoWrite con todos", de("PostToolUse").filter(r => r.tool_name === "TodoWrite").map(r => r.tool_input),
    [{ todos: [{ content: "a", status: "completed" }, { content: "b", status: "in_progress" }, { content: "c", status: "pending" }] }]);

  // 11. error de sesion -> Notification y luego Stop, con el mismo texto
  await h.event({ event: { type: "session.error", properties: { sessionID: "ses1", error: { name: "UnknownError", data: { message: "Se cayo el modelo" } } } } });
  await h.event({ event: { type: "session.error", properties: { error: { name: "UnknownError", data: { message: "sin sesion" } } } } });
  await esperar(900);
  ver("session.error -> Notification con message", de("Notification").map(r => r.message), ["OpenCode: error — Se cayo el modelo"]);
  const ordenErr = registrado().filter(r => r.evento === "Notification" || r.evento === "Stop").map(r => r.evento);
  ver("session.error -> Notification antes que Stop", ordenErr.slice(-2), ["Notification", "Stop"]);
  ver("session.error -> Stop con el mismo texto", de("Stop").slice(-1).map(r => r.texto), ["OpenCode: error — Se cayo el modelo"]);

  // 12. pregunta -> PermissionRequest AskUserQuestion; la respuesta vuelve a question.reply
  await h.event({ event: { type: "question.asked", properties: { id: "q1", sessionID: "ses1", questions: [
    { question: "¿Cuál?", header: "Elige", options: [{ label: "Uno", description: "a" }, { label: "Dos", description: "b" }], multiple: false }] } } });
  await esperar(900);
  ver("question.asked -> PermissionRequest AskUserQuestion", de("PermissionRequest").filter(r => r.tool_name === "AskUserQuestion").map(r => r.tool_input),
    [{ questions: [{ question: "¿Cuál?", header: "Elige", options: [{ label: "Uno", description: "a" }, { label: "Dos", description: "b" }], multiSelect: false }] }]);
  ver("pregunta: question.reply con requestID y answers", llamadas.filter(l => l.tipo === "respuesta_pregunta").map(l => l.pedido),
    [{ path: { requestID: "q1" }, body: { answers: [["Dos"]] } }]);

  // 13. sin client.question ni serverUrl: no sale nada
  const modulo = await import(pathToFileURL(plugin).href);
  const h2 = await modulo.Kodama({ client: clienteSinPreguntas, directory: "C:/x" });
  await h2.event({ event: { type: "question.asked", properties: { id: "q2", sessionID: "ses1", questions: [{ question: "¿Otra?", header: "h", options: [{ label: "S", description: "" }, { label: "T", description: "" }] }] } } });
  await esperar(900);
  ver("sin reply ni serverUrl: no se manda la pregunta", de("PermissionRequest").filter(r => r.tool_name === "AskUserQuestion").length, 1);
  await h2.dispose();

  // 14. sin client.question pero con serverUrl: HTTP POST /question/{id}/reply?directory=
  const fetchReal = globalThis.fetch, pedidosHttp = [];
  globalThis.fetch = async (url, opts) => { pedidosHttp.push({ url, method: opts.method, headers: opts.headers, body: JSON.parse(opts.body) }); return { ok: true, status: 200 }; };
  try {
    const h3 = await modulo.Kodama({ client: clienteSinPreguntas, directory: "C:/mi proyecto", serverUrl: new URL("http://127.0.0.1:4197/") });
    await h3.event({ event: { type: "question.asked", properties: { id: "q3", sessionID: "ses1", questions: [{ question: "¿Rojo o azul?", header: "Color", options: [{ label: "rojo", description: "" }, { label: "azul", description: "" }] }] } } });
    await esperar(900);
    ver("HTTP: URL con requestID y directory codificado", pedidosHttp.map(p => p.url), ["http://127.0.0.1:4197/question/q3/reply?directory=C%3A%2Fmi%20proyecto"]);
    ver("HTTP: metodo POST y body con answers", pedidosHttp.map(p => [p.method, p.body]), [["POST", { answers: [["azul"]] }]]);
    ver("HTTP: cabecera JSON", pedidosHttp.map(p => p.headers["Content-Type"]), ["application/json"]);
    // 15. sin decision: no hay respuesta HTTP
    await h3.event({ event: { type: "question.asked", properties: { id: "q4", sessionID: "ses1", questions: [{ question: "NO", header: "NO", options: [{ label: "a", description: "" }, { label: "b", description: "" }] }] } } });
    await esperar(900);
    ver("sin decision: no hay POST", pedidosHttp.length, 1);
    await h3.dispose();
  } finally { globalThis.fetch = fetchReal; }

  // 16. (16-nov) `opencode run` (argv con "run") sin KODAMA_DESPERTAR: el plugin no engancha nada
  const argvReal = process.argv, envReal = process.env.KODAMA_DESPERTAR;
  delete process.env.KODAMA_DESPERTAR;
  process.argv = [argvReal[0], "opencode", "run", "x"];
  let hRun = null, hDes = null;
  try {
    const mRun = await import(pathToFileURL(plugin).href + "?run=1");
    hRun = await mRun.Kodama({ client, directory: "C:/x" });
  } finally { process.argv = argvReal; }
  ver("encargo oculto (run sin DESPERTAR): plugin vacio", Object.keys(hRun), []);

  // 17. latido: la instancia normal escribe vivo-<pid>.json con las sesiones conocidas (el intervalo corre cada 2 s)
  const latido = join(buzon, `vivo-${process.pid}.json`);
  await esperar(2500);
  ver("latido normal: vivo-<pid>.json con las sesiones conocidas", existsSync(latido) ? JSON.parse(readFileSync(latido, "utf8")).includes("ses1") : false, true);
  await h.dispose();
  ver("dispose borra vivo-<pid>.json", existsSync(latido), false);

  // 18. despertar (KODAMA_DESPERTAR=1): engancha, latido vacio, no consume respuestas, y rechaza permisos sin decision
  process.env.KODAMA_DESPERTAR = "1";
  process.argv = [argvReal[0], "opencode", "run", "x"];
  try {
    const mDes = await import(pathToFileURL(plugin).href + "?des=1");
    hDes = await mDes.Kodama({ client, directory: "C:/x" });
  } finally { process.argv = argvReal; delete process.env.KODAMA_DESPERTAR; }
  ver("despertar: el plugin engancha (tiene event)", typeof (hDes && hDes.event), "function");
  writeFileSync(join(buzon, "ses1.7.respuesta"), "no debe consumirse");
  await esperar(2500);
  ver("despertar: latido con lista vacia", existsSync(latido) ? readFileSync(latido, "utf8") : null, "[]");
  ver("despertar: no consume .respuesta", existsSync(join(buzon, "ses1.7.respuesta")), true);
  llamadas.length = 0;
  await hDes.event({ event: { type: "permission.updated", properties: { id: "perm9", sessionID: "ses1", type: "bash", title: "SIN" } } });
  await esperar(900);
  ver("despertar: permiso sin decision -> reject", llamadas.filter(l => l.tipo === "permiso").map(l => l.pedido.body.response), ["reject"]);
  await hDes.dispose();
  ver("despertar: dispose borra su latido", existsSync(latido), false);
} catch (e) {
  mal.push("excepcion: " + (e && e.stack ? e.stack : e));
  console.log("MAL excepcion: " + (e && e.stack ? e.stack : e));
} finally {
  if (h) await h.dispose();
  try { rmSync(tmp, { recursive: true, force: true }); } catch (e) {}
}

console.log(`\nprobar_plugin_opencode: ${ok} OK, ${mal.length} MAL`);
process.exit(mal.length ? 1 : 0);
