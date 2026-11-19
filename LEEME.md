# Kodama — guía de uso

Una mascota en tu escritorio y una app en tu celular que te avisan cuando tus chats de IA (Claude Code, Codex,
OpenCode o Antigravity) te necesitan, y te dejan responderles sin ir al chat. © 2026 LShinox — código bajo PolyForm Noncommercial 1.0.0; ver `LICENCIA.txt`.

## Qué necesitas
- Windows 10/11 con al menos una IA de código: **Claude Code** (app de Claude, pestaña Code, o la CLI), **Codex**,
  **OpenCode** o **Antigravity** (ver "Con qué agentes funciona"). Instálala y ábrela una vez antes de Kodama.
- **Python 3.10+** (python.org). La mascota de escritorio ya viene compilada: no necesitas instalar nada más para ella.
- Opcional, para el celular: **Tailscale** (gratis) en la PC y en el celular, con la misma cuenta.
- Opcional, para avisos por Telegram: un bot propio (se crea con @BotFather).

## Instalar
1. Copia la carpeta de Kodama donde quieras (por ejemplo `C:\Apps\Kodama`).
2. Abre una terminal en esa carpeta y prueba sin tocar nada: `python instalar.py --prueba`
3. Si todo se ve bien: `python instalar.py` (te muestra la licencia, pregunta antes de cada descarga y respalda
   la configuración de tus IA antes de cambiarla). Conecta las IA que encuentre; si instalas otra después, vuelve a correrlo.
4. Abre tus chats de nuevo: Kodama empieza a funcionar en los chats nuevos.

Para quitarlo: `python instalar.py --quitar` (tus datos quedan; con `--borrar-datos` se borran).

## Configurar (`config.json`)
- `raices_personales` / `excluir_carpetas`: qué chats sigue (por carpeta). Ej.: todo lo de `%USERPROFILE%\Proyectos`
  menos `%USERPROFILE%\Proyectos\Trabajo`. Cada chat nuevo en esas carpetas aparece solo.
- `nombres`, `emoji_carpeta`, `ocultar`: cómo se muestra cada chat y cuáles esconder.
- `url_publica`: la dirección de la app del celular (la que te da `tailscale serve`).
- `token_telegram`: ruta al archivo con el token de tu bot (vacío = sin Telegram).

## Usar
- **La mascota** muestra el chat que más te necesita. Tócala para abrir el globo: lees el resumen y respondes.
  El nombre de abajo cambia de chat (o deja "Automático"). Arrástrala desde el borde izquierdo.
- **Responder cuenta como tuyo** cuando el chat te está esperando (el globo dice "⏳ Te está esperando"): pasa
  cuando el chat termina preguntándote algo, o cuando estás lejos de la PC. Ahí un "OK" sirve para aprobar.
  Si el chat ya no espera, tu mensaje llega igual, pero Claude no lo toma como aprobación.
- **Permisos**: si un chat pide permiso y estás lejos (o con la app del celular abierta), te llega
  "Permitir / Denegar". Si no respondes en ~2 min, se pregunta en la PC como siempre.
- **Silenciar** un chat: 🔕 en Telegram o 🔔 en la app del celular. **No molestar hasta mañana**: menú del
  ícono junto al reloj. **Idioma**: ES/EN en el celular y en ese menú.
- Atajos: **Ctrl+Shift+F10** abre/cierra el globo; **Ctrl+Shift+F11** responde al aviso que se asomó.

## Con qué agentes funciona
- **Claude Code (recomendado):** es para lo que está hecho Kodama y donde anda todo: avisos, responder desde
  la mascota o el celular, permisos, preguntas con opciones, aprobar el plan, ver archivos y el uso del plan.
- **Codex (OpenAI, app o CLI; viene con los planes de ChatGPT):** avisos cuando una sesión termina o pregunta,
  aprobar o denegar sus permisos desde el celular y responderle mientras te espera. Para activarlo: el instalador
  deja `~\.codex\hooks.json` y tú los revisas una vez dentro de Codex con `/hooks`. Las sesiones de Codex que lanza
  un chat de Claude (por ejemplo para generar imágenes) no aparecen.
- **OpenCode:** sirve para usar Kodama con ChatGPT Plus o Pro, con DeepSeek (clave de API, pago por uso) o con
  modelos gratis. Avisos, permisos y responder, como con Codex. El instalador deja un complemento en
  `~\.config\opencode\plugins\kodama.js`. Ojo: OpenCode lee `~\.claude\CLAUDE.md` y se lo manda al modelo; si no
  quieres, pon `OPENCODE_DISABLE_CLAUDE_CODE=1`.
- **Sin Claude Code:** todo lo anterior funciona igual; solo faltan el medidor de uso y los grupos de la app de
  Claude (Kodama los oculta). El plan gratis de Claude no incluye Claude Code.
- **DeepSeek Harness** (el agente propio de DeepSeek): todavía no es compatible; para DeepSeek usa OpenCode.
- **Antigravity (Google), compatible en etapa 1:** cada conversación aparece en la mascota y el celular, se ve
  "trabajando" y avisa cuando termina. Todavía no se aprueban permisos ni se le escribe desde aquí. El instalador
  deja `~\.gemini\config\hooks.json` (hook "kodama").

## Si algo falla
- En el celular: "¿No puedes conectar?" (debajo de los chats) revisa todo en orden y dice qué hacer.
- La PC relanza Kodama sola cada 10 minutos. Un respaldo diario queda en `respaldos\`.
