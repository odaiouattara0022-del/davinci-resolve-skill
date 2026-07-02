# Titles, Transforms & Fusion Access

## Text+ titles (the native way)

`InsertFusionTitleIntoTimeline` drops a Text+ at the **playhead** on the first free video track:

```python
timeline = project.GetCurrentTimeline()
timeline.SetCurrentTimecode("01:00:02:00")             # position the playhead first
title_item = timeline.InsertFusionTitleIntoTimeline("Text+")
assert title_item, "Insert failed — is the Edit page open and the track unlocked?"
```

Then edit the text through the item's Fusion comp:

```python
comp = title_item.GetFusionCompByIndex(1)
text_node = comp.FindToolByID("TextPlus")
text_node.SetInput("StyledText", "VASES D'HONNEUR")
text_node.SetInput("Font", "Montserrat")
text_node.SetInput("Style", "Bold")
text_node.SetInput("Size", 0.12)                        # fraction of frame height
text_node.SetInput("Red1", 0.83); text_node.SetInput("Green1", 0.68); text_node.SetInput("Blue1", 0.21)  # gold
```

Common TextPlus inputs: `StyledText`, `Font`, `Style`, `Size`, `Red1/Green1/Blue1/Alpha1` (fill color, 0–1), `Center` (position, `{1: x, 2: y}` in 0–1 space), `Tracking`, `Outline`/`Shadow` via shading elements.

## Animating with keyframes (fade/slide-in)

Animate any input by setting it at different comp times:

```python
comp.SetAttrs({"COMPN_CurrentTime": 0})
merge = comp.FindToolByID("Merge")                       # if compositing over background
text_node.SetInput("Size", 0.0, 0)                       # value, at frame 0
text_node.SetInput("Size", 0.12, 24)                     # full size at frame 24
```

For opacity fades on the **timeline item** (simpler and more editable for the user), keyframe in the UI or set static values:

```python
title_item.SetProperty("Opacity", 80.0)
```

## Transform properties on any clip (punch-ins, vertical reframes)

`TimelineItem.SetProperty` drives the Edit-page inspector — instantly visible and fully editable by the user:

```python
item.SetProperty("ZoomX", 1.2)          # 20% punch-in
item.SetProperty("ZoomY", 1.2)
item.SetProperty("Pan", 120.0)          # pixels
item.SetProperty("Tilt", -40.0)
item.SetProperty("RotationAngle", 2.0)
item.SetProperty("Opacity", 100.0)
item.SetProperty("CropLeft", 420.0)     # crop for split-screens
```

Read them back with `item.GetProperty("ZoomX")` to verify.

## Generators and backgrounds

```python
timeline.InsertGeneratorIntoTimeline("Solid Color")      # then grade/keyframe it
timeline.InsertFusionGeneratorIntoTimeline("Noise Gradient")
```

## Full Fusion comps on a clip

```python
comp = item.AddFusionComp()              # new comp on the clip
item.ImportFusionComp(r"D:\templates\lower_third.comp")  # reuse a saved template
item.ExportFusionComp(r"D:\templates\my_effect.comp", 1) # save for reuse
```

Inside a comp you have the standard Fusion scripting surface:

```python
bg   = comp.AddTool("Background", -32768, -32768)        # auto-position
text = comp.AddTool("TextPlus", -32768, -32768)
mrg  = comp.AddTool("Merge", -32768, -32768)
mrg.ConnectInput("Background", bg)
mrg.ConnectInput("Foreground", text)
out = comp.FindToolByID("MediaOut")
out.ConnectInput("Input", mrg)
```

Wrap batch comp edits in `comp.StartUndo("Build title")` / `comp.EndUndo(True)` so the user can Ctrl+Z your work as one step.

## Rules of thumb

- Prefer **timeline-item properties and Text+** over baked renders — the user must be able to tweak everything in the UI.
- Insert titles on a **dedicated upper track** (`timeline.AddTrack("video")`) so they never collide with footage.
- Font names must match installed fonts exactly; list them with `resolve.Fusion().FontManager.GetFontList()` if unsure.
