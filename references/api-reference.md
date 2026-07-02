# DaVinci Resolve Scripting API — Practical Reference

The methods you will actually use, by object. This is not the full API — it is the working subset for editing, grading, titling, and rendering. All methods return `None`/`False`/empty on failure; check every result.

Object chain (fetch fresh, in order, every script run):

```
Resolve
└── GetProjectManager() → ProjectManager
    └── GetCurrentProject() → Project
        ├── GetMediaPool() → MediaPool
        │   └── GetRootFolder() → Folder → MediaPoolItem(s)
        ├── GetCurrentTimeline() → Timeline
        │   └── GetItemListInTrack() → TimelineItem(s)
        └── GetGallery() → Gallery
```

## Resolve

| Method | Notes |
|--------|-------|
| `GetProjectManager()` | Entry point for everything |
| `OpenPage(name)` | `"media"`, `"cut"`, `"edit"`, `"fusion"`, `"color"`, `"fairlight"`, `"deliver"` |
| `GetCurrentPage()` | Returns current page name |
| `GetProductName()` / `GetVersionString()` | `"DaVinci Resolve Studio"` vs `"DaVinci Resolve"` |
| `GetMediaStorage()` | Browse mounted volumes outside the media pool |

## ProjectManager

| Method | Notes |
|--------|-------|
| `GetCurrentProject()` | Most scripts start here |
| `CreateProject(name)` | Returns Project or `None` if name exists |
| `LoadProject(name)` | Switches project |
| `SaveProject()` | Saves current project — call after batch changes |
| `GetProjectListInCurrentFolder()` | List of names |
| `ExportProject(name, filePath, withStillsAndLUTs)` | `.drp` backup |
| `ImportProject(filePath)` | Import `.drp` |

## Project

| Method | Notes |
|--------|-------|
| `GetMediaPool()` / `GetCurrentTimeline()` / `GetGallery()` | Child objects |
| `GetTimelineCount()` / `GetTimelineByIndex(i)` | **1-based** index |
| `SetCurrentTimeline(timeline)` | Activate a timeline |
| `GetSetting(key)` / `SetSetting(key, value)` | e.g. `"timelineFrameRate"`, `"timelineResolutionWidth"`, `"timelineResolutionHeight"` — values are strings |
| `SetRenderSettings(dict)` | See render keys below |
| `GetRenderFormats()` / `GetRenderCodecs(format)` | Discover valid format/codec pairs |
| `SetCurrentRenderFormatAndCodec(format, codec)` | e.g. `("mp4", "H264")` |
| `LoadRenderPreset(name)` / `SaveAsNewRenderPreset(name)` | Named presets |
| `AddRenderJob()` | Queues current settings; returns job id string |
| `DeleteAllRenderJobs()` | Clear the queue |
| `StartRendering(job_ids=None, isInteractiveMode=False)` | **Only when the user asked to render** |
| `IsRenderingInProgress()` | Poll while rendering |
| `GetRenderJobStatus(job_id)` | `{"JobStatus": "Complete"/"Rendering"/..., "CompletionPercentage": n}` |

Common `SetRenderSettings` keys: `TargetDir`, `CustomName`, `FormatWidth`, `FormatHeight`, `FrameRate`, `MarkIn`, `MarkOut`, `SelectAllFrames` (bool), `ExportVideo` (bool), `ExportAudio` (bool), `AudioCodec`, `VideoQuality`.

## MediaStorage

| Method | Notes |
|--------|-------|
| `GetMountedVolumeList()` | Drive roots |
| `GetSubFolderList(path)` / `GetFileList(path)` | Browse |
| `AddItemListToMediaPool(paths)` | Alternative import path |

## MediaPool

| Method | Notes |
|--------|-------|
| `ImportMedia([paths])` | Returns list of MediaPoolItem |
| `GetRootFolder()` / `AddSubFolder(folder, name)` / `SetCurrentFolder(folder)` | Bin management |
| `CreateEmptyTimeline(name)` | Returns Timeline (becomes current) |
| `CreateTimelineFromClips(name, [items])` | One-shot assembly, full clips |
| `AppendToTimeline([items])` or `AppendToTimeline([clip_infos])` | The editing workhorse — see below |
| `DeleteTimelines([timelines])` / `DeleteClips([items])` | Destructive — confirm first |
| `ImportTimelineFromFile(path, options)` | AAF/EDL/XML/DRT |
| `AutoSyncAudio([items], settings)` | Sync separate audio by waveform |
| `RelinkClips([items], folderPath)` | Fix offline media |

`clip_info` dict for `AppendToTimeline`:

```python
{
    "mediaPoolItem": item,      # MediaPoolItem object, required
    "startFrame": 120,          # source in-point, frames, 0-based in the media file
    "endFrame": 360,            # source out-point
    "trackIndex": 1,            # optional, 1-based video track
    "recordFrame": 86400,       # optional, absolute timeline position in frames
}
```

## Folder

`GetName()`, `GetClipList()`, `GetSubFolderList()` — recurse from `GetRootFolder()` to find clips by name.

## MediaPoolItem

| Method | Notes |
|--------|-------|
| `GetName()` | Clip name |
| `GetClipProperty(name)` | `"File Path"`, `"FPS"`, `"Duration"`, `"Resolution"`, `"Frames"`, `"Format"` — no arg returns a dict of all |
| `SetClipProperty(name, value)` | e.g. `("Alpha mode", "Premultiplied")` |
| `GetMetadata(key=None)` / `SetMetadata(key, value)` | Scene/Shot/Keywords etc. |
| `AddMarker(frame, color, name, note, duration, customData)` | Frame relative to clip start |
| `GetMarkers()` | `{frame: {"color":…, "name":…}}` |
| `AddFlag(color)` / `SetClipColor(color)` | Organization |
| `LinkProxyMedia(path)` / `UnlinkProxyMedia()` | Proxies |
| `TranscribeAudio()` | Resolve 18.5+ audio transcription |

## Timeline

| Method | Notes |
|--------|-------|
| `GetName()` / `SetName(name)` | |
| `GetStartFrame()` / `GetEndFrame()` | Timelines usually start at 3600×fps (01:00:00:00) |
| `GetTrackCount(type)` | `"video"`, `"audio"`, `"subtitle"` |
| `GetItemListInTrack(type, index)` | **1-based** track index |
| `AddTrack(type)` / `DeleteTrack(type, index)` | |
| `SetTrackName(type, index, name)` / `SetTrackEnable(type, index, bool)` / `SetTrackLock(type, index, bool)` | |
| `GetCurrentTimecode()` / `SetCurrentTimecode("01:00:10:00")` | Move the playhead |
| `GetCurrentVideoItem()` | Item under playhead |
| `AddMarker(frame, color, name, note, duration, customData)` | Frame is **absolute** (offset by start frame) |
| `InsertFusionTitleIntoTimeline("Text+")` | At playhead, on first free track — see fusion-titles.md |
| `InsertTitleIntoTimeline("Text")` | Legacy title |
| `InsertGeneratorIntoTimeline("Solid Color")` | Generators |
| `CreateCompoundClip([items], {"startTimecode":…, "name":…})` | Group items |
| `CreateFusionClip([items])` | Send to Fusion |
| `CreateSubtitlesFromAudio(settings=None)` | Auto captions, Resolve 18.1+; settings dict optional |
| `DetectSceneCuts()` | Auto scene detection |
| `Export(filePath, exportType, exportSubType)` | e.g. `timeline.Export("t.aaf", resolve.EXPORT_AAF, resolve.EXPORT_AAF_NEW)`; also `EXPORT_FCP_7_XML`, `EXPORT_DRT`, `EXPORT_EDL`, `EXPORT_SRT` (subtitles) |
| `GetSetting(key)` / `SetSetting(key, value)` | Per-timeline overrides |
| `DuplicateTimeline(name)` | Safe experimentation copy |
| `GrabStill()` | Color page only; returns GalleryStill |

## TimelineItem

| Method | Notes |
|--------|-------|
| `GetName()` / `GetDuration()` | |
| `GetStart()` / `GetEnd()` | Absolute timeline frames |
| `GetLeftOffset()` | Source offset (frames trimmed from head) |
| `GetProperty(key)` / `SetProperty(key, value)` | Transform: `"ZoomX"`, `"ZoomY"`, `"Pan"`, `"Tilt"`, `"RotationAngle"`, `"Opacity"`, `"CropLeft"`… |
| `GetMediaPoolItem()` | Back-reference to source clip |
| `AddMarker(frame, …)` | Frame relative to item start |
| `SetClipColor(color)` / `SetClipEnabled(bool)` | |
| `SetCDL({...})` / `SetLUT(nodeIdx, path)` / `GetLUT(nodeIdx)` | See color-grading.md |
| `AddVersion(name, type)` / `LoadVersionByName(name, type)` | type: 0 local, 1 remote |
| `CopyGrades([targetItems])` | Grade one, copy to many |
| `AddFusionComp()` / `GetFusionCompByIndex(1)` / `ImportFusionComp(path)` / `ExportFusionComp(path, index)` | `.comp` files |
| `Stabilize()` | Runs stabilization analysis |
| `SmartReframe()` | Studio only — set `"Super Scale"`-style reframe for vertical crops |
| `CreateMagicMask(mode)` | Studio only |

## Gallery (stills / PowerGrades)

```python
gallery = project.GetGallery()
album = gallery.GetCurrentStillAlbum()
still = timeline.GrabStill()                      # Color page
album.ExportStills([still], folder, prefix, "png")  # formats: dpx, cin, tif, jpg, png, ppm, bmp, xpm
```

## Marker and clip colors

`"Blue"`, `"Cyan"`, `"Green"`, `"Yellow"`, `"Red"`, `"Pink"`, `"Purple"`, `"Fuchsia"`, `"Rose"`, `"Lavender"`, `"Sky"`, `"Mint"`, `"Lemon"`, `"Sand"`, `"Cocoa"`, `"Cream"`

## Timecode ↔ frames

```python
def tc_to_frames(tc, fps):
    h, m, s, f = map(int, tc.split(":"))
    return int(round((h * 3600 + m * 60 + s) * fps)) + f

def frames_to_tc(frames, fps):
    fps_i = int(round(fps))
    f = frames % fps_i
    s = frames // fps_i
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}:{f:02d}"
```
