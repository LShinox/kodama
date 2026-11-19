// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// (04-nov-2026) Kodama para OpenCode. instalar.py copia este archivo a ~/.config/opencode/plugins/kodama.js cambiando las tres rutas de abajo.
// Manda los eventos a companero_opencode.py (avisos y permisos, igual que Claude Code) y entrega a la sesion lo que respondas desde la mascota o el celular
// (el hub lo deja en estado/opencode/<sesion>.<n>.respuesta). No lee nada mas ni usa la red; si Kodama no esta, no molesta: todo falla en silencio.
// (16-nov-2026) Fases "ejecutando"/"haciendo" (tool.execute.*), progreso de tareas (todo.updated), errores (session.error) y preguntas (question.asked). (16-nov) encargos ocultos, latido por proceso, despertar.
// API: tipos publicados en @opencode-ai/plugin y @opencode-ai/sdk 1.19.5 (hook `event`, eventos session.* y permission.*, client.session.*, postSessionIdPermissionsPermissionId).
import { spawn } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const PY = "__PY__", SCRIPT = "__SCRIPT__", ESTADO = "__ESTADO__";
const BUZON = join(ESTADO, "opencode");

// nombres de OpenCode -> nombres de Claude Code (los que entienden companero_hook.py y companero_hook_pre.py)
const NOMBRES = { bash: "Bash", edit: "Edit", write: "Write", patch: "Edit", multiedit: "Edit", read: "Read", grep: "Grep", glob: "Glob", list: "Glob", webfetch: "WebFetch", websearch: "WebSearch", task: "Task", todowrite: "TodoWrite" };
function nombreHerramienta(t) {
  const k = String(t || "").toLowerCase();
  if (!k || k === "todoread") return "";
  return NOMBRES[k] || String(t);
}
function entrada(args) {
  const x = args && typeof args === "object" ? { ...args } : {};
  const fp = x.filePath || x.path;
  if (fp && !x.file_path) x.file_path = fp;
  return x;
}

function llamar(datos) {
  return new Promise(ok => {
    let salida = "";
    try {
      const p = spawn(PY, [SCRIPT], { stdio: ["pipe", "pipe", "ignore"], windowsHide: true });
      p.stdout.on("data", b => { salida += b; });
      p.on("error", () => ok(""));
      p.on("close", () => ok(salida));
      p.stdin.on("error", () => {});
      p.stdin.end(JSON.stringify(datos));
    } catch (e) { ok(""); }
  });
}

export const Kodama = async ({ client, directory, serverUrl }) => {
  // (16-nov) `opencode run` = encargo de otro chat (sin ventana): Kodama no lo muestra. Salvo que lo lance Kodama para despertar un chat (KODAMA_DESPERTAR=1).
  const DESPERTAR = process.env.KODAMA_DESPERTAR === "1";
  if (process.argv.slice(1, 4).map(String).includes("run") && !DESPERTAR) return {};
  const hijas = new Set(), conocidas = new Set(), permisos = new Set(), enviados = new Set(), preguntas = new Set();
  const titulos = {};
  // (16-nov) respuesta a preguntas: client.question.reply si existe; si no, HTTP directo al servidor de OpenCode (POST /question/{requestID}/reply)
  const puedeResponderPreguntas = () => !!((client.question && typeof client.question.reply === "function") || serverUrl);
  async function responderPregunta(id, lista) {
    if (client.question && typeof client.question.reply === "function") {
      try { await client.question.reply({ path: { requestID: id }, body: { answers: lista } }); } catch (e) {}
      return;
    }
    if (!serverUrl) return;
    const ctl = new AbortController(), reloj10 = setTimeout(() => ctl.abort(), 10000);
    try {
      const url = `${String(serverUrl).replace(/\/$/, "")}/question/${encodeURIComponent(id)}/reply?directory=${encodeURIComponent(directory || "")}`;
      await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: lista }), signal: ctl.signal });
    } catch (e) {} finally { clearTimeout(reloj10); }
  }

  const ev = (evento, session_id, extra) => llamar({ evento, session_id, cwd: directory, titulo: titulos[session_id] || "", ...extra });

  async function ultimoTexto(id) {
    try {
      const r = await client.session.messages({ path: { id } });
      const lista = (r && r.data) || r || [];
      for (let i = lista.length - 1; i >= 0; i--) {
        const m = lista[i];
        if (m.info && m.info.role === "assistant") return (m.parts || []).filter(p => p.type === "text" && !p.synthetic).map(p => p.text).join("\n").trim();
      }
    } catch (e) {}
    return "";
  }

  async function responderPermiso(sessionID, id, response) {
    // (05-nov) el nombre cambia entre versiones: los tipos 1.19.5 dicen postSessionIdPermissionsPermissionId y la doc actual postSessionByIdPermissionsByPermissionId
    const responder = client.postSessionIdPermissionsPermissionId || client.postSessionByIdPermissionsByPermissionId;
    try { await responder.call(client, { path: { id: sessionID, permissionID: id }, body: { response } }); } catch (e) {}
  }

  async function pedirPermiso(p) {
    const sid = p.sessionID;
    if (!sid || !p.id || permisos.has(p.id) || hijas.has(sid)) return;
    permisos.add(p.id);
    const patron = Array.isArray(p.pattern) ? p.pattern.join(" ") : p.pattern || (Array.isArray(p.patterns) ? p.patterns.join(" ") : "");
    const salida = await ev("PermissionRequest", sid, { tool_name: p.type || p.permission || "OpenCode", tool_input: { command: p.title || patron || "" } });
    let decision = null;
    try { decision = JSON.parse(salida).hookSpecificOutput.decision.behavior; } catch (e) { if (DESPERTAR) await responderPermiso(sid, p.id, "reject"); return; }   // sin decision: se responde en OpenCode, como siempre (en un despertar nadie responde: se rechaza)
    if (decision === "allow") await responderPermiso(sid, p.id, "once");
    else if (decision === "deny") await responderPermiso(sid, p.id, "reject");
    else if (DESPERTAR) await responderPermiso(sid, p.id, "reject");
  }

  // (16-nov) pregunta de OpenCode (question.asked): se manda al celular como AskUserQuestion de Claude y la respuesta vuelve como answers
  async function pedirPregunta(p) {
    const sid = p.sessionID, id = p.id;
    if (!sid || !id || !Array.isArray(p.questions) || !p.questions.length || hijas.has(sid) || preguntas.has(id)) return;
    preguntas.add(id);
    const questions = p.questions.map(q => ({
      question: q.question, header: q.header,
      options: (q.options || []).map(o => ({ label: o.label, description: o.description })),
      multiSelect: !!q.multiple,
    }));
    const salida = await ev("PermissionRequest", sid, { tool_name: "AskUserQuestion", tool_input: { questions } });
    let answers = null;
    try { answers = JSON.parse(salida).hookSpecificOutput.updatedInput.answers; } catch (e) { return; }   // sin respuesta: se contesta en OpenCode
    if (!answers) return;
    const lista = p.questions.map(q => String(answers[q.question] || "").split(", ").filter(Boolean));
    if (!lista.some(x => x.length)) return;
    await responderPregunta(id, lista);
  }

  async function revisarRespuestas() {
    try {
      mkdirSync(BUZON, { recursive: true });
      writeFileSync(join(BUZON, "vivo"), "");   // el hub sabe que hay una OpenCode abierta
      writeFileSync(join(BUZON, `vivo-${process.pid}.json`), JSON.stringify(DESPERTAR ? [] : [...conocidas]));
      if (DESPERTAR) return;   // (16-nov) un despertar no consume respuestas: solo es el encargo de un chat
      for (const f of readdirSync(BUZON)) {
        if (!f.endsWith(".respuesta")) continue;
        const sid = f.split(".")[0];
        if (!conocidas.has(sid)) continue;   // puede ser de otra ventana de OpenCode
        const ruta = join(BUZON, f), text = readFileSync(ruta, "utf8");
        unlinkSync(ruta);
        if (!text.trim()) continue;
        enviados.add(text.trim());   // que chat.message no lo anote como escrito en la PC
        const pedido = { path: { id: sid }, body: { parts: [{ type: "text", text }] } };
        await (client.session.promptAsync ? client.session.promptAsync(pedido) : client.session.prompt(pedido));
      }
    } catch (e) {}
  }
  const reloj = setInterval(revisarRespuestas, 2000);
  if (reloj.unref) reloj.unref();

  return {
    dispose: async () => { clearInterval(reloj); try { unlinkSync(join(BUZON, `vivo-${process.pid}.json`)); } catch (e) {} },
    event: async ({ event }) => {
      const t = event && event.type, p = (event && event.properties) || {};
      if (t === "session.created" || t === "session.updated") {
        const s = p.info || {};
        if (!s.id) return;
        if (s.parentID) { hijas.add(s.id); return; }   // subagentes: no son un chat aparte
        conocidas.add(s.id); if (s.title) titulos[s.id] = s.title;
        if (t === "session.created") ev("SessionStart", s.id);
      } else if (t === "session.status") {
        if (p.sessionID && !hijas.has(p.sessionID)) conocidas.add(p.sessionID);
      } else if (t === "session.idle") {
        if (!p.sessionID || hijas.has(p.sessionID)) return;
        conocidas.add(p.sessionID);
        ev("Stop", p.sessionID, { texto: await ultimoTexto(p.sessionID) });
      } else if (t === "session.deleted") {
        const s = p.info || {};
        if (s.id && !hijas.has(s.id)) ev("SessionEnd", s.id);
      } else if (t === "session.error") {
        // (16-nov) error de la sesion: aviso al celular y Stop para que el chat no quede "trabajando"
        if (!p.sessionID || hijas.has(p.sessionID)) return;
        const e = p.error || {};
        const m = String((e.data && e.data.message) || e.message || e.name || "error desconocido").replace(/\s+/g, " ").trim();
        const msg = ("OpenCode: error — " + m).slice(0, 200);
        ev("Notification", p.sessionID, { message: msg });
        ev("Stop", p.sessionID, { texto: msg });
      } else if (t === "todo.updated") {
        // (16-nov) progreso de tareas "3 de 7": la lista entera, como TodoWrite de Claude Code
        if (!p.sessionID || hijas.has(p.sessionID)) return;
        const todos = (p.todos || []).map(x => ({ content: x.content, status: x.status }));
        ev("PostToolUse", p.sessionID, { tool_name: "TodoWrite", tool_input: { todos } });
      } else if (t === "permission.updated" || t === "permission.asked") {
        pedirPermiso(p);
      } else if (t === "question.asked") {
        if (puedeResponderPreguntas()) pedirPregunta(p);
      }
    },
    "tool.execute.before": async (input, output) => {
      try {
        const sid = input && input.sessionID;
        const tn = nombreHerramienta(input && input.tool);
        if (!sid || !tn || hijas.has(sid)) return;
        ev("PreToolUse", sid, { tool_name: tn, tool_input: entrada(output && output.args) });   // sin await: no frena la herramienta
      } catch (e) {}
    },
    "tool.execute.after": async (input) => {
      try {
        const sid = input && input.sessionID;
        const tn = nombreHerramienta(input && input.tool);
        if (!sid || !tn || hijas.has(sid)) return;
        ev("PostToolUse", sid, { tool_name: tn, tool_input: entrada(input.args) });   // sin await
      } catch (e) {}
    },
    "chat.message": async (input, output) => {
      const sid = input && input.sessionID;
      if (!sid || hijas.has(sid)) return;
      conocidas.add(sid);
      const texto = ((output && output.parts) || []).filter(x => x.type === "text" && !x.synthetic).map(x => x.text).join("\n").trim();
      if (!texto || enviados.delete(texto)) return;
      ev("UserPromptSubmit", sid, { texto });
    },
  };
};
