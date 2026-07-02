#!/usr/bin/env python3
"""Auto-cut silences: build a jump-cut timeline from a media pool clip.

Runs ffmpeg silencedetect on the clip's source file, computes the speech
segments, and assembles them on a new timeline. The original clip and
timeline are never modified.

Usage:
    python auto_cut_silence.py --clip "interview.mp4"
    python auto_cut_silence.py --clip "podcast" --noise -35dB --min-silence 1.0 \
        --padding 0.2 --timeline-name "Podcast jumpcut"

Requires: DaVinci Resolve running, ffmpeg on PATH.
"""
import argparse
import re
import subprocess
import sys

from resolve_bootstrap import get_resolve

BATCH_SIZE = 50          # AppendToTimeline reliability limit
MIN_SEGMENT_SEC = 0.3    # drop micro-clips shorter than this


def find_clip(media_pool, name_fragment):
    """Search all bins for the first clip whose name contains name_fragment."""
    def walk(folder):
        for clip in folder.GetClipList() or []:
            if name_fragment.lower() in (clip.GetName() or "").lower():
                return clip
        for sub in folder.GetSubFolderList() or []:
            found = walk(sub)
            if found:
                return found
        return None
    return walk(media_pool.GetRootFolder())


def detect_silences(file_path, noise, min_silence, audio_stream):
    """Return [(start_sec, end_sec)] silence intervals via ffmpeg silencedetect."""
    cmd = ["ffmpeg", "-i", file_path, "-map", f"0:a:{audio_stream}",
           "-af", f"silencedetect=noise={noise}:d={min_silence}",
           "-vn", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]
    if not starts and "silencedetect" not in proc.stderr:
        sys.exit(f"ffmpeg failed:\n{proc.stderr[-800:]}")
    return list(zip(starts, ends[:len(starts)]))


def speech_segments(silences, duration, padding):
    """Complement of the silence intervals, padded, filtered."""
    segments, cursor = [], 0.0
    for s_start, s_end in silences:
        if s_start > cursor:
            segments.append((max(0.0, cursor - padding), min(duration, s_start + padding)))
        cursor = max(cursor, s_end)
    if cursor < duration:
        segments.append((max(0.0, cursor - padding), duration))
    return [(a, b) for a, b in segments if b - a >= MIN_SEGMENT_SEC]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip", required=True, help="media pool clip name (substring match)")
    ap.add_argument("--noise", default="-30dB", help="silence threshold (default -30dB)")
    ap.add_argument("--min-silence", type=float, default=1.0, help="min silence duration in s")
    ap.add_argument("--padding", type=float, default=0.15, help="seconds kept around speech")
    ap.add_argument("--audio-stream", type=int, default=0, help="audio stream index (0-based)")
    ap.add_argument("--timeline-name", default=None)
    args = ap.parse_args()

    resolve = get_resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        sys.exit("No project open in Resolve.")
    media_pool = project.GetMediaPool()

    clip = find_clip(media_pool, args.clip)
    if clip is None:
        sys.exit(f'No media pool clip matching "{args.clip}".')

    file_path = clip.GetClipProperty("File Path")
    fps = float(clip.GetClipProperty("FPS"))
    frames = int(clip.GetClipProperty("Frames") or 0)
    duration = frames / fps if frames else 0.0
    if not file_path or not duration:
        sys.exit("Clip has no readable file path or duration.")

    print(f"Analyzing {file_path} ({duration:.1f}s @ {fps}fps)...")
    silences = detect_silences(file_path, args.noise, args.min_silence, args.audio_stream)
    segments = speech_segments(silences, duration, args.padding)
    if not segments:
        sys.exit("No speech segments found — try a higher --noise threshold (e.g. -25dB).")

    kept = sum(b - a for a, b in segments)
    print(f"{len(silences)} silences -> {len(segments)} speech segments "
          f"({kept:.1f}s kept of {duration:.1f}s, -{100 * (1 - kept / duration):.0f}%)")

    name = args.timeline_name or f"{clip.GetName()} - jumpcut"
    timeline = media_pool.CreateEmptyTimeline(name)
    if timeline is None:
        sys.exit(f'Could not create timeline "{name}" (name already used?).')

    clip_infos = [{"mediaPoolItem": clip,
                   "startFrame": int(a * fps),
                   "endFrame": int(b * fps)} for a, b in segments]
    added = 0
    for i in range(0, len(clip_infos), BATCH_SIZE):
        batch = clip_infos[i:i + BATCH_SIZE]
        if media_pool.AppendToTimeline(batch):
            added += len(batch)
        else:
            print(f"WARNING: batch at segment {i} failed")

    print(f'Done: {added}/{len(clip_infos)} segments on timeline "{name}".')


if __name__ == "__main__":
    main()
