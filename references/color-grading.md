# Color Grading via the API

Grades live on **TimelineItem** objects (per-clip node graphs). The API can set CDLs, LUTs, versions, and copy grades between clips — for anything finer (individual node parameters), grade one hero clip in the UI and propagate with `CopyGrades`.

```python
timeline = project.GetCurrentTimeline()
items = timeline.GetItemListInTrack("video", 1)
```

## CDL: the scriptable grade

A CDL (Color Decision List) gives you slope/offset/power per channel plus saturation — enough for full look recipes (warm/cool, teal-orange, film looks):

```python
# A warm "golden hour" recipe applied to node 1 of every clip
warm_look = {
    "NodeIndex": "1",
    "Slope":  "1.05 0.98 0.88",    # R G B multipliers (gain)
    "Offset": "0.01 0.00 -0.01",   # lift
    "Power":  "0.95 1.00 1.05",    # gamma (inverse response)
    "Saturation": "1.10",
}
for item in items:
    ok = item.SetCDL(warm_look)
    assert ok, f"CDL failed on {item.GetName()}"
```

All values are **strings**. Slope >1 brightens the channel; Power <1 brightens mids. Keep adjustments subtle (±0.15) and iterate while checking the viewer.

## LUTs

```python
lut = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Film Looks\Rec709 Kodak 2383 D65.cube"
item.SetLUT(1, lut)        # node index 1-based
current = item.GetLUT(1)   # verify
```

Custom LUTs: drop `.cube` files into the LUT folder above (macOS: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`), then `project.RefreshLUTList()`.

## Grade one, apply to all

```python
hero = items[0]            # grade this one in the UI or via SetCDL
hero.CopyGrades(items[1:]) # propagate to the rest
```

## Versions (non-destructive experiments)

```python
item.AddVersion("Look B - cooler", 0)       # 0 = local version
item.LoadVersionByName("Look B - cooler", 0)
item.GetVersionNameList(0)
item.LoadVersionByName("Version 1", 0)      # back to original
```

## Stills and PowerGrades

Grabbing stills requires the **Color page**:

```python
resolve.OpenPage("color")
still = timeline.GrabStill()
album = project.GetGallery().GetCurrentStillAlbum()
album.ExportStills([still], r"D:\exports\stills", "grade_ref", "png")
resolve.OpenPage("edit")
```

## Applying a saved grade (.drx)

```python
timeline.ApplyGradeFromDRX(r"D:\grades\hero_look.drx", 0, items)  # 0 = No keyframes
```

## Color groups

```python
group = project.AddColorGroup("Interviews")
for item in interview_items:
    item.AssignToColorGroup(group)
# Grade the group's pre/post clip graph once in the UI — applies to all members
```

## Verify visually, not blindly

After grading, grab a thumbnail to check the result instead of assuming success:

```python
resolve.OpenPage("color")
thumb = timeline.GetCurrentClipThumbnailImage()   # {"width":…, "height":…, "format":…, "data": base64}
```

Decode `thumb["data"]` (base64 RGB) to an image file and inspect it.
