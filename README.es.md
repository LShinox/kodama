<p align="right"><a href="README.md">Read in English →</a></p>

<p align="center"><img src="docs/img/icono.png" width="96" alt="Kodama"></p>

# Kodama

Una mascota en tu escritorio y una app en tu celular que te avisan cuando tus chats de **Claude Code** (y de Codex y
Antigravity) te necesitan, y te dejan responderles sin ir al chat.

**Gratis.** El código fuente se publica aquí con la licencia **PolyForm Noncommercial 1.0.0** (código disponible: gratis
para uso no comercial, no es código abierto). También puedes **descargar las versiones, reportar problemas y proponer ideas**. Míralo en acción en la página **[Kodama en acción](https://lshinox.github.io/kodama/)**.

| Te avisa | Responde desde el celular | Ajustes en la PC |
|:---:|:---:|:---:|
| <img src="docs/img/mascota.gif" width="240" alt="El gato en su cápsula: trabaja, pregunta, lista de chats que te esperan y soltar un archivo"> | <img src="docs/img/celular.gif" width="190" alt="La app del celular: chats, un permiso con Permitir y Denegar, y el bloqueo"> | <img src="docs/img/ajustes.gif" width="240" alt="La ventana de Ajustes sale de la mascota, con Lo nuevo"> |
| El gato cambia con tu chat. En la cápsula están el aviso, el globo y las respuestas rápidas. | Lista de chats, respuestas rápidas y permisos con Permitir / Denegar. | La ventana de Ajustes sale de la mascota y te cuenta qué hay de nuevo. |

## Qué hace
- **Un gato animado a mano** que vive junto al reloj y cambia con tu chat: espera, trabaja, te escribe, recibe tu respuesta, duerme o se atora. Eliges color (negro, naranja, blanco, gris azulado o esmoquin) y tipo de ojos. Brote sigue disponible como alternativa.
- **Cápsula con todo adentro:** el aviso, el globo y las respuestas rápidas salen de una cápsula blanca o negra pegada a la mascota. Es opcional (Ajustes).
- **Responder y aprobar desde el celular:** una app con diseño de iPhone (por tu propia red privada, Tailscale) o por Telegram. Los permisos se aprueban con Permitir, Denegar (con motivo), «Permitir siempre esto» o «Permitir en esta tarea».
- **Progreso de tareas:** ves «3/7» en la tarjeta del chat y junto a su nombre en el globo.
- **Pensando y ejecutando:** distingue si el chat está pensando o ejecutando un comando, una búsqueda web o un subagente.
- **Chats que te esperan:** una lista dentro del globo, con archivar por fila.
- **Soltar archivos sobre la mascota:** sus patitas los agarran, se adjuntan y los envías al chat que elijas.
- **Alarma y bloqueo del celular:** si entra a tu cuenta un aparato que no es tu celular, Kodama suena la alarma y no lo deja pasar. Puedes bloquear el celular desde el propio celular o desde la PC; solo se desbloquea en la PC.
- **Sueño profundo:** cuando nada cambia, la mascota se queda quieta, hecha un ovillo como el gato de un farero, y gasta mucho menos CPU. Se despierta con el mouse o con un aviso.
- **Lo nuevo:** al actualizar, Ajustes te cuenta qué cambió en esa versión.

## Instalar (Windows)
Necesitas la **app de escritorio de Claude**. Dos formas, elige una:

**A. Díselo a tu Claude.** En un chat de la pestaña Code escribe:
> Instala Kodama desde github.com/LShinox/kodama

**B. Una línea en PowerShell:**
```powershell
irm https://raw.githubusercontent.com/LShinox/kodama/main/instalar.ps1 | iex
```

Queda en tu carpeta de usuario (`Kodama`). Si te falta Python, te ofrece instalarlo. El gato aparece al
terminar; tus chats nuevos ya avisan.

Después se actualiza desde el menú del gato (junto al reloj de Windows): cuando hay una versión nueva aparece
"Actualizar a …". Cada versión va **firmada**: si el archivo no es el original, no se instala.

### Instrucciones para Claude (si te pidieron instalar Kodama)
Haz las preguntas con tu herramienta de preguntas con opciones (**AskUserQuestion**), una tarjeta por paso. Si las
tarjetas no aparecen, pregunta lo mismo en texto. **Nunca le pidas una clave o un token en el chat.**

1. **Tarjeta "Licencia":** resume en 3 líneas la licencia (`LICENCIA.txt`: el código va con PolyForm Noncommercial 1.0.0; el arte, las animaciones y el nombre "Kodama" son todos los derechos reservados) y qué se toca en su PC (los
   hooks de `~\.claude\settings.json` con respaldo, una tarea de Windows "Companero", y si los tiene, los hooks de
   Codex y Antigravity; Python con winget si falta). Opciones: *Acepto e instalo* / *No, gracias*.
2. **Tarjeta "Celular":** cómo quiere los avisos en el celular. Opciones: *Solo Telegram (sin instalar nada más)* /
   *App del celular (con Tailscale, la completa)* / *Las dos* / *Por ahora solo la PC*.
3. **Tarjeta "Otros agentes"** (solo si existen `~\.codex` o `~\.gemini`): *Conectar Codex y Antigravity* / *Solo Claude*.
4. Con esas respuestas, baja `instalar.ps1` de este repo y córrelo con
   `powershell -NoProfile -ExecutionPolicy Bypass -File instalar.ps1 -Acepto -Si` (+ `-SoloClaude` si eligió *Solo Claude*).
5. Si el script corta, muéstrale el mensaje tal cual. No lo saltes ni lo "arregles": si dice que la firma no es
   válida, no se instala.
6. Al terminar: dile que el gato está junto al reloj (clic derecho = menú) y que abra un chat nuevo. Si eligió
   Telegram o la app del celular, dile que siga los pasos de **"Conectar celular"** en el menú del gato (ahí pega
   su token de Telegram o escanea los QR de Tailscale, nunca en este chat).

## ¿Algo falla?
En el menú del gato: **Reportar un problema**. Arma un archivo con lo necesario para encontrar el error (sin tus
mensajes ni tus claves), lo deja en tu Escritorio y abre el formulario aquí. Revisa el archivo y arrástralo al
formulario.

## Ideas y aportes
- **Ideas y mejoras:** abre un issue con la etiqueta *idea*.
- **Personajes y animaciones:** si quieres diseñar una mascota nueva, abre un issue primero. Lo que aportes se
  publica con tu nombre en los créditos; al aportarlo aceptas que pase a formar parte de Kodama.

## Metas y lista de deseos
Kodama es gratis. **Aceptamos aportes voluntarios** ([Sponsor](https://github.com/sponsors/LShinox)): todo lo
que entra se invierte en estas metas, en este orden, y cada una se publica aquí mismo cuando se cumple.

| Meta | Avance | Para qué |
|---|---|---|
| Firma de Windows | `░░░░░░░░░░` 0 % | Que Windows no muestre "editor desconocido" al instalar |
| Conexión sin Tailscale | `░░░░░░░░░░` 0 % | Un servidor propio para conectar el celular sin instalar nada más |
| Licencia de Apple | `░░░░░░░░░░` 0 % | Versión para Mac y app de iPhone con Isla Dinámica |
| Más animaciones | `░░░░░░░░░░` 0 % | Gestos y variantes nuevas del gato, para que nunca se vea igual |
| WhatsApp (opcional, con costo) | `░░░░░░░░░░` 0 % | Avisos y respuestas también por WhatsApp, además de Telegram y la app. Los avisos que tú no provocas son mensajes de plantilla que Meta cobra por mensaje, con una tarifa que cambia según el país y que todavía no está confirmada. Aún no está decidido quién lo paga: un número de Kodama (lo asume el proyecto) o tu propio número (lo pagas tú directamente a Meta). Telegram y la app siguen siendo gratis |
| Minijuegos y modo cuidado | `░░░░░░░░░░` 0 % | Juegos cortos mientras tus chats trabajan y una mascota que cuidas (tipo tamagotchi), igual en la PC y el celular. Se prenden y se apagan en Ajustes |
| Más mascotas | `░░░░░░░░░░` 0 % | El gato es la mascota principal; Brote sigue como alternativa y crece según lo que pida la comunidad |

**Lista de deseos de la comunidad:** ¿quieres algo que no está? Abre un issue con la etiqueta *deseo*. Los que
juntan más 👍 suben a la tabla de metas.

---
## Licencia
- **Código:** [PolyForm Noncommercial 1.0.0](LICENCIA.txt): gratis para uso no comercial. Required Notice: Copyright 2026 LShinox.
- **Arte, animaciones, iconos y el nombre "Kodama":** todos los derechos reservados, no cubiertos por la licencia del código (ver el final de [LICENCIA.txt](LICENCIA.txt)).

© 2026 LShinox · [Licencia](LICENCIA.txt) · [License](LICENSE.txt) (mismo texto, en inglés y español)
