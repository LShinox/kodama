<p align="right"><a href="README.es.md">Leer en español →</a></p>

<p align="center"><img src="docs/img/icono.png" width="96" alt="Kodama"></p>

# Kodama

**A free desktop cat for Windows that tells you when Claude Code, Codex or Antigravity is waiting for you,** and lets you approve permissions and reply from your phone.

Works with the Claude desktop app. The phone side is a web app (PWA): nothing to install from an app store, and no Kodama account.

**Free.** The source code is published here under the **PolyForm Noncommercial 1.0.0** license (source-available: free for
noncommercial use, not open source). You can also **download releases, report problems and suggest ideas**. See it in action on the **[project page](https://lshinox.github.io/kodama/)**.

| It notifies you | Reply from your phone | Settings on your PC |
|:---:|:---:|:---:|
| <img src="docs/img/mascota.gif" width="240" alt="The cat in its capsule: it works, asks a question, shows the list of chats waiting for you and takes a dropped file"> | <img src="docs/img/celular.gif" width="190" alt="The phone app: chats, a permission with Allow and Deny, and the lock"> | <img src="docs/img/ajustes.gif" width="240" alt="The Settings window slides out of the mascot, showing What's new"> |
| The cat changes with your chat. The capsule holds the notification, the bubble and the quick replies. | Chat list, quick replies and permissions with Allow / Deny. | The Settings window slides out of the mascot and tells you what's new. |

## What it does
- **A hand-animated cat** that lives next to the clock and changes with your chat: it waits, works, writes to you, receives your reply, sleeps or gets stuck. You pick the color (black, orange, white, blue-gray or tuxedo) and the eye style. Brote is still available as an alternative.
- **A capsule with everything inside:** the notification, the bubble and the quick replies come out of a white or black capsule attached to the mascot. It is optional (Settings).
- **Reply and approve from your phone:** an iPhone-style web app (PWA: you add it to the home screen, no App Store) over your own private network (Tailscale), or through Telegram. Permissions are approved with Allow, Deny (with a reason), "Always allow this" or "Allow for this task".
- **Task progress:** you see "3/7" on the chat card and next to its name in the bubble.
- **Thinking and running:** it tells whether the chat is thinking or running a command, a web search or a subagent.
- **Chats waiting for you:** a list inside the bubble, with archive per row.
- **Drop files onto the mascot:** its little paws grab them, they get attached, and you send them to the chat you choose.
- **Phone alarm and lock:** if a device that is not your phone signs in to your account, Kodama sounds the alarm and doesn't let it in. You can lock the phone from the phone itself or from the PC; it can only be unlocked on the PC.
- **Deep sleep:** when nothing changes, the mascot stays still, curled up like a lighthouse keeper's cat, and uses much less CPU. It wakes up with the mouse or a notification.
- **What's new:** when you update, Settings tells you what changed in that version.

## Install (Windows)
**Requirements**
- Windows 10 or 11.
- The **Claude desktop app**.
- Python 3.10 or newer. If it is missing, the installer offers to install it for you (Python 3.12 with winget, ~30 MB).
- Optional, for the phone: Telegram (a bot of your own) or Tailscale.
- The phone app is a **web app (PWA)**: you open it in your phone's browser and add it to the home screen. There is nothing to install from the App Store or Google Play.
- To uninstall, see [Uninstall](#uninstall).

Two ways to install, pick one:

**A. Tell your Claude.** In a chat on the Code tab, type:
> Install Kodama from github.com/LShinox/kodama

**B. One line in PowerShell:**
```powershell
irm https://raw.githubusercontent.com/LShinox/kodama/main/instalar.ps1 | iex
```

It is installed in your user folder (`Kodama`). If Python is missing, it offers to install it. The cat appears
when it finishes; your new chats will already notify you.

After that, it updates from the cat's menu (next to the Windows clock): when a new version is available,
"Update to …" appears. Every update is verified with Kodama's own digital signature (public key in `clave_publica.txt`)
before it is installed: if the file is not the original, it is not installed. This is not Windows code signing, so Windows
may still show its own warnings.

### Uninstall
From the `Kodama` folder, run `python instalar.py --quitar`. It removes Kodama's hooks and usage status line from
`~\.claude\settings.json`, the Codex and Antigravity hooks, and the Windows task. Your data stays in `Kodama\estado`;
add `--borrar-datos` to delete it too, and `--restaurar` to put `settings.json` back exactly as it was before
installing. Then delete the `Kodama` folder.

### Instructions for Claude (if you were asked to install Kodama)
Ask the questions with your multiple-choice question tool (**AskUserQuestion**), one card per step. If the cards
don't show up, ask the same thing in text. **Never ask the user for a key or a token in the chat.**

1. **"License" card:** summarize the license in 3 lines (`LICENSE.txt`: the code is under PolyForm Noncommercial 1.0.0; the art, animations and the name "Kodama" are all rights reserved), and what gets touched on their PC (the
   hooks in `~\.claude\settings.json`, with a backup; a Windows task "Kodama"; and, if they have them, the Codex and
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

## Privacy: what Kodama touches and what it sends
**What it touches on your PC**
- **Claude hooks:** it adds its own hooks (and a usage status line, only if you don't already have one) to `~\.claude\settings.json`, merged without overwriting yours. A timestamped backup copy is made first, next to it.
- **Other agents:** if you have Codex or Antigravity, it adds its hooks to `~\.codex\hooks.json` and `~\.gemini\config\hooks.json`, also with a backup.
- **A Windows task** named "Kodama" that starts Kodama when you sign in and, every 10 minutes, checks that it is running.
- Its files live in the `Kodama` folder of your user profile, including a private Python environment (`.venv`).

**What reaches your phone**
- The hooks read the chat's state, the text of your prompts, the assistant's last message, notifications and permission requests, only to show them in the capsule and on your phone. The text of a chat's messages is kept only for the chats that go to your phone.
- That text stays on your PC (Kodama's local server listens only on `127.0.0.1`) until it is sent to your phone.

**Where it goes**
- **Phone app:** the traffic goes over your own Tailscale private network, between your PC and your phone.
- **Phone notifications** use the standard Web Push service of your phone's system (Apple, Google or similar); the notification text is encrypted for your device.
- **Telegram:** if you connect it, the text you see in Telegram goes through Telegram's servers.
- Besides that, Kodama only contacts GitHub (to look for updates) and, while installing, PyPI (one small package) and winget (only if Python is missing).

**What it does not do:** there is no Kodama server, no Kodama account and no telemetry: the code contains no analytics or tracking calls. The problem report (cat's menu) is a file you review before sending, and it leaves out your messages and keys.

## Why not X?
Kodama is not trying to replace these; if one of them fits you better, use it.

| If you want… | Consider | Kodama adds |
|---|---|---|
| To continue the same Claude Code session from your phone, in Claude's own app | Claude's official **Remote Control** (included in Pro, Max, Team and Enterprise plans) | A visible cat on your desktop, Codex and Antigravity too, and no dependence on a Pro or Max plan |
| A full mobile app, with native iOS and Android apps, for several models | **Happy** (free, MIT, end-to-end encrypted) | A mascot and capsule on the Windows desktop, with a light alert layer instead of a full app |
| Notifications in the MacBook notch | **Vibe Notch**, **CodeIsland** (macOS only) | The same idea on Windows |

## Something not working?
In the cat's menu: **Report a problem**. It builds a file with what is needed to find the error (without your
messages or your keys), leaves it on your Desktop and opens the form here. Review the file and drag it onto the
form.

## Ideas and contributions
- **Ideas and improvements:** open an issue with the label *idea*.
- **Characters and animations:** if you want to design a new mascot, open an issue first. What you contribute is
  published with your name in the credits; by contributing it you agree that it becomes part of Kodama.

## Goals and wish list
Kodama is free and stays free. Contributions are voluntary ([Sponsor](https://github.com/sponsors/LShinox)).

Things sponsoring helps with:
- A Mac version and an iPhone app.
- Connecting without Tailscale, with a server of our own.
- More animations for the cat.
- WhatsApp (optional; Meta charges per message, so it would carry a cost).
- Minigames and a care mode (tamagotchi style).
- More mascots.
- A Microsoft Store version.

I keep working on these anyway, with or without contributions.

**Community wish list:** want something that isn't here? Open an issue with the label *deseo* (wish). The ones
that gather the most 👍 move up this list.

---
## License
- **Code:** [PolyForm Noncommercial 1.0.0](LICENSE.txt): free for noncommercial use. Required Notice: Copyright 2026 LShinox.
- **Art, animations, icons and the name "Kodama":** all rights reserved, not covered by the code license (see the end of [LICENSE.txt](LICENSE.txt)).

© 2026 LShinox · [License](LICENSE.txt) · [Licencia](LICENCIA.txt) (same text, English and Spanish)
