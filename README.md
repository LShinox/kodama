<p align="right"><a href="README.es.md">Leer en español →</a></p>

<p align="center"><img src="docs/img/icono.png" width="96" alt="Kodama"></p>

# Kodama

A mascot on your desktop and an app on your phone that tell you when your **Claude Code** chats (and Codex and
Antigravity) need you, and let you answer them without going back to the chat.

**Free.** The source code is published here under the **PolyForm Noncommercial 1.0.0** license (source-available: free for
noncommercial use, not open source). You can also **download releases, report problems and suggest ideas**. See it in action on the **[Kodama in action](https://lshinox.github.io/kodama/)** page.

| It notifies you | Reply from your phone | Settings on your PC |
|:---:|:---:|:---:|
| <img src="docs/img/mascota.gif" width="240" alt="The cat in its capsule: it works, asks a question, shows the list of chats waiting for you and takes a dropped file"> | <img src="docs/img/celular.gif" width="190" alt="The phone app: chats, a permission with Allow and Deny, and the lock"> | <img src="docs/img/ajustes.gif" width="240" alt="The Settings window slides out of the mascot, showing What's new"> |
| The cat changes with your chat. The capsule holds the notification, the bubble and the quick replies. | Chat list, quick replies and permissions with Allow / Deny. | The Settings window slides out of the mascot and tells you what's new. |

## What it does
- **A hand-animated cat** that lives next to the clock and changes with your chat: it waits, works, writes to you, receives your reply, sleeps or gets stuck. You pick the color (black, orange, white, blue-gray or tuxedo) and the eye style. Brote is still available as an alternative.
- **A capsule with everything inside:** the notification, the bubble and the quick replies come out of a white or black capsule attached to the mascot. It is optional (Settings).
- **Reply and approve from your phone:** an iPhone-style app (over your own private network, Tailscale) or through Telegram. Permissions are approved with Allow, Deny (with a reason), "Always allow this" or "Allow for this task".
- **Task progress:** you see "3/7" on the chat card and next to its name in the bubble.
- **Thinking and running:** it tells whether the chat is thinking or running a command, a web search or a subagent.
- **Chats waiting for you:** a list inside the bubble, with archive per row.
- **Drop files onto the mascot:** its little paws grab them, they get attached, and you send them to the chat you choose.
- **Phone alarm and lock:** if a device that is not your phone signs in to your account, Kodama sounds the alarm and doesn't let it in. You can lock the phone from the phone itself or from the PC; it can only be unlocked on the PC.
- **Deep sleep:** when nothing changes, the mascot stays still, curled up like a lighthouse keeper's cat, and uses much less CPU. It wakes up with the mouse or a notification.
- **What's new:** when you update, Settings tells you what changed in that version.

## Install (Windows)
You need the **Claude desktop app**. Two ways, pick one:

**A. Tell your Claude.** In a chat on the Code tab, type:
> Install Kodama from github.com/LShinox/kodama

**B. One line in PowerShell:**
```powershell
irm https://raw.githubusercontent.com/LShinox/kodama/main/instalar.ps1 | iex
```

It is installed in your user folder (`Kodama`). If Python is missing, it offers to install it. The cat appears
when it finishes; your new chats will already notify you.

After that, it updates from the cat's menu (next to the Windows clock): when a new version is available,
"Update to …" appears. Every version is **signed**: if the file is not the original, it is not installed.

### Instructions for Claude (if you were asked to install Kodama)
Ask the questions with your multiple-choice question tool (**AskUserQuestion**), one card per step. If the cards
don't show up, ask the same thing in text. **Never ask the user for a key or a token in the chat.**

1. **"License" card:** summarize the license in 3 lines (`LICENSE.txt`: the code is under PolyForm Noncommercial 1.0.0; the art, animations and the name "Kodama" are all rights reserved), and what gets touched on their PC (the
   hooks in `~\.claude\settings.json`, with a backup; a Windows task "Companero"; and, if they have them, the Codex and
   Antigravity hooks; Python via winget if it is missing). Options: *I accept and install* / *No, thanks*.
2. **"Phone" card:** how they want notifications on their phone. Options: *Telegram only (nothing else to install)* /
   *Phone app (with Tailscale, the full one)* / *Both* / *PC only for now*.
3. **"Other agents" card** (only if `~\.codex` or `~\.gemini` exist): *Connect Codex and Antigravity* / *Claude only*.
4. With those answers, download `instalar.ps1` from this repo and run it with
   `powershell -NoProfile -ExecutionPolicy Bypass -File instalar.ps1 -Acepto -Si` (+ `-SoloClaude` if they chose *Claude only*).
5. If the script stops, show them the message as is. Don't skip it or "fix" it: if it says the signature is not
   valid, it does not get installed.
6. When done: tell them the cat is next to the clock (right-click = menu) and that they should open a new chat. If they chose
   Telegram or the phone app, tell them to follow the steps of **"Connect phone"** in the cat's menu (that is where they paste
   their Telegram token or scan the Tailscale QR codes, never in this chat).

## Something not working?
In the cat's menu: **Report a problem**. It builds a file with what is needed to find the error (without your
messages or your keys), leaves it on your Desktop and opens the form here. Review the file and drag it onto the
form.

## Ideas and contributions
- **Ideas and improvements:** open an issue with the label *idea*.
- **Characters and animations:** if you want to design a new mascot, open an issue first. What you contribute is
  published with your name in the credits; by contributing it you agree that it becomes part of Kodama.

## Goals and wish list
Kodama is free. **We accept voluntary contributions** ([Sponsor](https://github.com/sponsors/LShinox)): everything
that comes in is invested in these goals, in this order, and each one is announced right here when it is reached.

| Goal | Progress | What for |
|---|---|---|
| Windows code signing | `░░░░░░░░░░` 0 % | So Windows doesn't show "unknown publisher" when installing |
| Connection without Tailscale | `░░░░░░░░░░` 0 % | A server of our own to connect the phone without installing anything else |
| Apple license | `░░░░░░░░░░` 0 % | Mac version and iPhone app with Dynamic Island |
| More animations | `░░░░░░░░░░` 0 % | New gestures and variants of the cat, so it never looks the same |
| WhatsApp (optional, with a cost) | `░░░░░░░░░░` 0 % | Notifications and replies through WhatsApp too, in addition to Telegram and the app. Notifications you don't trigger are template messages that Meta charges per message, at a rate that varies by country and is not yet confirmed. It is not yet decided who pays for it: a Kodama number (the project covers it) or your own number (you pay Meta directly). Telegram and the app remain free |
| Minigames and care mode | `░░░░░░░░░░` 0 % | Short games while your chats work, and a pet you take care of (tamagotchi style), the same on PC and phone. They are turned on and off in Settings |
| More mascots | `░░░░░░░░░░` 0 % | The cat is the main mascot; Brote remains as an alternative and grows according to what the community asks for |

**Community wish list:** want something that isn't here? Open an issue with the label *deseo* (wish). The ones
that gather the most 👍 move up to the goals table.

---
## License
- **Code:** [PolyForm Noncommercial 1.0.0](LICENSE.txt): free for noncommercial use. Required Notice: Copyright 2026 LShinox.
- **Art, animations, icons and the name "Kodama":** all rights reserved, not covered by the code license (see the end of [LICENSE.txt](LICENSE.txt)).

© 2026 LShinox · [License](LICENSE.txt) · [Licencia](LICENCIA.txt) (same text, English and Spanish)
