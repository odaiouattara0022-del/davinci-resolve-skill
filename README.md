# DaVinci Resolve Skill

An [Agent Skill](https://agentskills.io) that teaches AI coding agents (Claude Code, Codex, Copilot CLI, Gemini CLI…) how to **edit video in DaVinci Resolve**: build timelines, cut clips, auto-remove silences, generate subtitles, color grade, add Text+ titles, and manage the render queue — all through the official Python scripting API that ships with Resolve.

*[Version française ci-dessous 🇫🇷](#-version-française)*

## What it can do

- 🎬 **Editing** — import media, create timelines, precise frame-accurate cuts, markers, compound clips
- ✂️ **Auto jump-cuts** — bundled script removes silences from interviews/podcasts via ffmpeg analysis
- 📝 **Subtitles** — auto-captions from audio, SRT export
- 🎨 **Color grading** — CDL look recipes, LUTs, grade copying, versions, PowerGrade stills
- ✨ **Titles & Fusion** — Text+ titles, transform animations, reusable `.comp` templates
- 📤 **Rendering** — format/codec setup, render queue management, progress monitoring

## Bonus — PyTerm, a personal Python studio

This repo also ships [`pyterm/`](pyterm/): a self-contained Python IDE + terminal
that **installs as a real app** — home-screen icon, launch screen, full screen,
offline. VS Code-style explorer, tabs, command palette and integrated REPL, with
two engines: **Pyodide** in the browser (zero setup, the one iOS allows) or the
**real CPython** on your machine via `pyterm/server/kernel.py` (full `pip`,
sockets, real disk).

- **iPhone / Android** — publish `pyterm/` over HTTPS (the bundled
  [Pages workflow](.github/workflows/pages.yml) does it on every push to `main`),
  open it in Safari or Chrome, then *Add to Home Screen* / *Install app*.
- **Desktop** — `python3 pyterm/server/kernel.py`, then open
  `http://127.0.0.1:8777` and install it from the address bar.

Full guide (in French): [`pyterm/README.md`](pyterm/README.md).

## Requirements

- DaVinci Resolve 18+ (free or Studio), **running**, with scripting enabled:
  `Preferences → System → General → External scripting using: Local`
- Python 3.6+
- `ffmpeg` on PATH (only for the silence auto-cut script)

## Install

**Claude Code** (plugin marketplace not needed — skills folder works everywhere):

```bash
# macOS / Linux
git clone https://github.com/odaiouattara0022-del/davinci-resolve-skill ~/.claude/skills/davinci-resolve

# Windows (PowerShell)
git clone https://github.com/odaiouattara0022-del/davinci-resolve-skill "$env:USERPROFILE\.claude\skills\davinci-resolve"
```

**Other agents** (Codex, Copilot CLI, Gemini CLI): clone into `~/.agents/skills/davinci-resolve` or your runtime's skills directory.

**With the [skills CLI](https://skills.sh):**

```bash
npx skills add odaiouattara0022-del/davinci-resolve-skill
```

Then just ask your agent things like:

> "Cut the silences out of interview.mp4 and build a jump-cut timeline"
> "Add a gold Text+ title at 2 seconds and grade all clips warmer"
> "Queue a 1080x1920 vertical export of the current timeline"

## Verify your setup

```bash
python scripts/resolve_bootstrap.py
# CONNECTED: DaVinci Resolve Studio 19.1
# Project:  My Project
# Timeline: Timeline 1 (3 video / 2 audio tracks)
```

## Structure

```
davinci-resolve-skill/
├── SKILL.md                      # entry point the agent reads first
├── references/
│   ├── api-reference.md          # practical API surface, by object
│   ├── workflows.md              # end-to-end recipes (import → cut → render)
│   ├── color-grading.md          # CDL, LUTs, versions, stills
│   └── fusion-titles.md          # Text+, transforms, Fusion comps
└── scripts/
    ├── resolve_bootstrap.py      # cross-platform connection helper
    └── auto_cut_silence.py       # silence removal → jump-cut timeline
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `NOT CONNECTED` | Resolve must be running; set external scripting to **Local** and restart Resolve |
| `ImportError: DaVinciResolveScript` | Non-default install path → set `RESOLVE_SCRIPT_API` / `RESOLVE_SCRIPT_LIB` env vars |
| API calls return `None` | Check the object chain is fresh; re-fetch after switching projects in the UI |

## License

MIT — see [LICENSE](LICENSE).

---

## 🇫🇷 Version française

Une **compétence d'agent** qui apprend aux agents IA (Claude Code, Codex, Copilot CLI, Gemini CLI…) à **monter des vidéos dans DaVinci Resolve** : timelines, découpes précises, suppression automatique des silences, sous-titres automatiques, étalonnage, titres Text+ et gestion des rendus — via l'API Python officielle fournie avec Resolve.

### Prérequis

- DaVinci Resolve 18+ (gratuit ou Studio), **ouvert**, avec le scripting activé :
  `Préférences → Système → Général → External scripting using : Local`
- Python 3.6+
- `ffmpeg` dans le PATH (uniquement pour la découpe automatique des silences)

### Installation

```bash
# Windows (PowerShell)
git clone https://github.com/odaiouattara0022-del/davinci-resolve-skill "$env:USERPROFILE\.claude\skills\davinci-resolve"

# macOS / Linux
git clone https://github.com/odaiouattara0022-del/davinci-resolve-skill ~/.claude/skills/davinci-resolve
```

Puis demandez simplement à votre agent :

> « Supprime les silences de interview.mp4 et monte une timeline en jump-cut »
> « Ajoute un titre Text+ doré à 2 secondes et réchauffe l'étalonnage de tous les plans »
> « Prépare un export vertical 1080x1920 de la timeline actuelle »

### Vérifier l'installation

```bash
python scripts/resolve_bootstrap.py
```

Si tout va bien, le script affiche `CONNECTED`, le nom du projet et de la timeline en cours.

### Licence

MIT — libre d'utilisation, de modification et de partage.
