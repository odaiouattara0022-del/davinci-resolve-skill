---
name: davinci-resolve
description: Use when editing video in DaVinci Resolve - building timelines, cutting clips, importing media, color grading, applying LUTs or CDLs, adding titles or subtitles, auto-cutting silences, managing render queues, or automating any Resolve post-production task via its Python scripting API. Triggers include "DaVinci", "Resolve", "timeline", "media pool", "color grade", "render", "auto captions", "Text+".
---

# DaVinci Resolve Editing

Automate DaVinci Resolve with the Python scripting API (`DaVinciResolveScript`) that ships with every Resolve install. No plugins, no MCP server, no extra dependencies — just Resolve running and Python 3.6+.

## Requirements

- DaVinci Resolve **must be running** with a project open.
- **External scripts need scripting enabled**: Preferences → System → General → *External scripting using* = **Local**. (Resolve Studio unlocks network scripting; the free edition allows local external scripting in recent versions — if connection fails on free, run scripts from Workspace → Console instead.)
- `ffmpeg` on PATH only for the audio-analysis workflows (silence auto-cut).

## Quick Start

Always connect through the bundled helper — it handles the per-OS environment paths:

```bash
python scripts/resolve_bootstrap.py          # prints connection status, project, timeline
```

In your own scripts:

```python
from resolve_bootstrap import get_resolve

resolve = get_resolve()                       # raises with a clear message if Resolve isn't reachable
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
timeline = project.GetCurrentTimeline()
media_pool = project.GetMediaPool()
```

**Everything hangs off this object chain.** Get it first, every time:
`Resolve → ProjectManager → Project → (MediaPool | Timeline | Gallery)`

## Quick Reference

| Task | Call | Details |
|------|------|---------|
| Import media | `media_pool.ImportMedia([paths])` | [workflows.md](references/workflows.md) |
| New timeline | `media_pool.CreateEmptyTimeline(name)` | [workflows.md](references/workflows.md) |
| Add cut clips | `media_pool.AppendToTimeline([clip_infos])` | [workflows.md](references/workflows.md) |
| Auto-cut silences | `python scripts/auto_cut_silence.py` | [workflows.md](references/workflows.md) |
| Auto subtitles | `timeline.CreateSubtitlesFromAudio()` | [workflows.md](references/workflows.md) |
| Titles (Text+) | `timeline.InsertFusionTitleIntoTimeline("Text+")` | [fusion-titles.md](references/fusion-titles.md) |
| Grade a clip (CDL) | `item.SetCDL({...})` | [color-grading.md](references/color-grading.md) |
| Apply a LUT | `item.SetLUT(node_index, lut_path)` | [color-grading.md](references/color-grading.md) |
| Render | `project.AddRenderJob()` + `StartRendering()` | [workflows.md](references/workflows.md) |
| Full API surface | — | [api-reference.md](references/api-reference.md) |

## Golden Rules

1. **Check every return value.** The API signals failure by returning `None`, `False`, or an empty list — it almost never raises. Wrap the chain in explicit checks.
2. **Frames, not seconds.** `AppendToTimeline` clip infos, markers, and item positions use frames. Convert with the clip's real FPS: `frames = int(seconds * fps)` where `fps = float(clip.GetClipProperty("FPS"))`.
3. **Some calls are page-sensitive.** Thumbnails and stills need the Color page; switch with `resolve.OpenPage("color")` and switch back after.
4. **Batch `AppendToTimeline` calls** to ~50 clip infos per call on long edits — very large batches can silently drop clips.
5. **Ask before rendering.** Never start a render or overwrite output files without the user explicitly asking — queue the job and report instead.
6. **Build natively, keep it editable.** Prefer real timeline items, titles, and grades over importing pre-rendered media, so the user can adjust everything in the Resolve UI afterwards.
7. **Track indices start at 1**, and `GetTimelineByIndex` also starts at 1.

## Reference Files

- [references/api-reference.md](references/api-reference.md) — object model and the methods you'll actually use, by class.
- [references/workflows.md](references/workflows.md) — end-to-end recipes: import → timeline → cuts → subtitles → render, plus ffmpeg silence auto-cut.
- [references/color-grading.md](references/color-grading.md) — CDL, LUTs, versions, copying grades, stills/PowerGrades.
- [references/fusion-titles.md](references/fusion-titles.md) — Text+ titles, transform/zoom animations on timeline items, Fusion comp access.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `ImportError: DaVinciResolveScript` | Use `resolve_bootstrap.get_resolve()` — it sets `PYTHONPATH`/lib paths per OS |
| `get_resolve()` returns nothing | Resolve not running, or external scripting not set to **Local** in Preferences |
| Clips land at wrong times | You passed seconds; convert to frames with the clip's FPS |
| `AppendToTimeline` returns `None` | Malformed clip info dict, or `endFrame` beyond the clip's length |
| Timeline ops fail after switching projects in the UI | Re-fetch the whole object chain — old handles go stale |
| Subtitles/captions call fails | Needs Resolve 18.1+ and a timeline with audible speech on an enabled track |
