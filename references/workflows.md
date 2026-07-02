# Editing Workflows — End-to-End Recipes

Every recipe assumes the standard chain is already fetched:

```python
from resolve_bootstrap import get_resolve

resolve = get_resolve()
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
media_pool = project.GetMediaPool()
```

## 1. Import media and build a rough cut

```python
clips = media_pool.ImportMedia([r"D:\footage\A001.mp4", r"D:\footage\A002.mp4"])
assert clips, "Import failed — check the paths exist and are readable"

timeline = media_pool.CreateEmptyTimeline("Rough Cut v1")
assert timeline, "Timeline name already taken?"

# Full clips, in order:
media_pool.AppendToTimeline(clips)
```

## 2. Precise cuts with clip_info dicts

Cut specific source ranges instead of whole clips. Frames are 0-based within the source media:

```python
clip = clips[0]
fps = float(clip.GetClipProperty("FPS"))

def sec(t):  # seconds → source frames
    return int(round(t * fps))

cuts = [(4.0, 9.5), (22.0, 31.0), (47.2, 55.0)]   # keep these ranges
clip_infos = [
    {"mediaPoolItem": clip, "startFrame": sec(a), "endFrame": sec(b)}
    for a, b in cuts
]

# Batch ~50 per call on long edits
for i in range(0, len(clip_infos), 50):
    result = media_pool.AppendToTimeline(clip_infos[i:i + 50])
    assert result, f"Append failed at batch {i}"
```

To place a clip at an exact timeline position, add `"recordFrame"`: absolute timeline frame (remember timelines usually start at `timeline.GetStartFrame()`, typically 86400 at 24 fps = 01:00:00:00).

## 3. Auto-cut silences (jump-cut editing)

Use the bundled script — it runs ffmpeg `silencedetect` on the source file, computes speech segments, and assembles a new timeline:

```bash
python scripts/auto_cut_silence.py --clip "interview.mp4" \
    --noise -32dB --min-silence 0.8 --padding 0.15
```

How it works (if you need to adapt it):

1. `clip.GetClipProperty("File Path")` → source file.
2. `ffmpeg -i <file> -af silencedetect=noise=-32dB:d=0.8 -vn -f null -` → parse `silence_start` / `silence_end` pairs from stderr.
3. Speech segments = complement of silences, padded by ±0.15 s, dropping segments shorter than 0.3 s.
4. Convert seconds → frames with the clip FPS, build `clip_info` dicts, `AppendToTimeline` in batches.

MKV/multi-stream sources: check streams with `ffmpeg -i file`, pick the right one with `-map 0:a:0`.

## 4. Auto subtitles / captions

```python
timeline = project.GetCurrentTimeline()
ok = timeline.CreateSubtitlesFromAudio()          # Resolve 18.1+, uses default language settings
```

With explicit settings (constants live on the `resolve` object):

```python
settings = {
    resolve.SUBTITLE_LANGUAGE: resolve.AUTO_CAPTION_ENGLISH,
    resolve.SUBTITLE_CAPTION_PRESET: resolve.AUTO_CAPTION_SUBTITLE_DEFAULT,
    resolve.SUBTITLE_CHARS_PER_LINE: 42,
    resolve.SUBTITLE_LINE_BREAK: resolve.AUTO_CAPTION_LINE_DOUBLE,
}
timeline.CreateSubtitlesFromAudio(settings)
```

Export subtitles: `timeline.Export("subs.srt", resolve.EXPORT_SRT)` — some versions need a subtitle export subtype; check `GetVersionString()` if it fails.

## 5. Markers as an edit map

Markers survive UI work and make great hand-off points between automation and the human editor:

```python
start = timeline.GetStartFrame()
timeline.AddMarker(start + 240, "Red", "Hook", "Punch-in here", 1, "")
markers = timeline.GetMarkers()   # {frameOffset: {"color":…, "name":…, "note":…}}
```

## 6. Scene detection on baked footage

For source files that are already-edited exports (re-cutting a master):

```python
timeline.DetectSceneCuts()        # adds cuts on the current timeline
```

## 7. Render queue (queue, don't fire)

```python
project.SetCurrentRenderFormatAndCodec("mp4", "H264")
project.SetRenderSettings({
    "TargetDir": r"D:\exports",
    "CustomName": "rough_cut_v1",
    "SelectAllFrames": True,       # or use MarkIn/MarkOut
    "ExportVideo": True,
    "ExportAudio": True,
})
job_id = project.AddRenderJob()
print(f"Queued render job {job_id} — start it from the Deliver page or ask me to start it.")
```

Only call `project.StartRendering()` when the user explicitly asked to render. To monitor:

```python
import time
project.StartRendering()
while project.IsRenderingInProgress():
    status = project.GetRenderJobStatus(job_id)
    print(status.get("CompletionPercentage"), "%")
    time.sleep(2)
```

Vertical/social exports: set `"FormatWidth": 1080, "FormatHeight": 1920` in render settings, or duplicate the timeline and change `timeline.SetSetting("useCustomSettings", "1")` + resolution settings for a true vertical edit.

## 8. Multi-version teasers from one edit

Pattern for cutting N short verticals from a master timeline:

```python
master = project.GetCurrentTimeline()
for i, (tc_in, tc_out) in enumerate([("01:00:05:00", "01:00:20:00"),
                                     ("01:01:10:00", "01:01:25:00")], 1):
    t = master.DuplicateTimeline(f"Teaser {i} 9x16")
    # trim by setting render Mark In/Out per teaser, or rebuild via AppendToTimeline
```

## 9. Save your work

```python
pm.SaveProject()   # after any batch of changes
```
