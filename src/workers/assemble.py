"""Assembly worker: stills + narration + word timings -> 1080x1920 master + sub-10MB proxy.

MoviePy 2.x composites the Ken-Burns picture track ONLY (silent). Everything else is
one ffmpeg pass (R&D 2026-08-03, sections 3.2/3.3/3.6):
  - cuts land on REAL beat boundaries from beat_timing.json (written by per-segment TTS),
    not word-count proportions;
  - captions are ASS karaoke (per-word \\kf sweep) burned by libass with the in-repo OFL
    font - replaces per-TextClip PIL compositing and the old margin/clipping workaround;
  - the audio track is the ducked music mix at -14 LUFS from audiofx.build_final_audio.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

TARGET_W, TARGET_H = 1080, 1920
FONTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "assets" / "fonts"
CAPTION_FONT = "Archivo Black"  # SIL OFL 1.1, shipped in assets/fonts/
PROXY_LIMIT_MB = 9.0  # Discord cap is 10; leave headroom
CUT_LEAD_S = 0.12  # cut this far into the inter-beat gap (just after the last word)


def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def _run_ff(args: list[str], cwd: str | None = None) -> None:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-800:]}")


def _beat_durations(spec: dict, total: float) -> list[float]:
    """Fallback (no beat_timing.json, e.g. resumed pre-2026-08-03 runs): split total
    audio time across hook+beats+payoff/cta proportional to word counts."""
    texts = [spec["hook"]] + [b["narration"] for b in spec["beats"]] + [spec["payoff"] + " " + spec["cta"]]
    counts = [max(1, len(t.split())) for t in texts]
    total_words = sum(counts)
    return [total * c / total_words for c in counts]


def _durations_from_timing(timing: list[dict], total: float) -> list[float]:
    """Exact segment durations: each cut lands CUT_LEAD_S after the previous segment's
    last audio, inside the synthesis gap - the desync fix (R&D 3.6)."""
    boundaries = [0.0]
    for prev, nxt in zip(timing, timing[1:], strict=False):
        boundaries.append(min(nxt["start"], prev["end"] + CUT_LEAD_S))
    boundaries.append(max(total, boundaries[-1] + 0.1))
    return [b - a for a, b in zip(boundaries, boundaries[1:], strict=False)]


def _caption_chunks(words: list[dict], target_s: float = 1.9, max_words: int = 7,
                    min_s: float = 1.0) -> list[tuple[list[dict], float, float]]:
    """Group words into READABLE chunks by TIME, not a fixed word count (user feedback:
    3-word flashes were unreadable). A chunk closes when it reaches ~target_s seconds or
    max_words; chunks shorter than min_s get merged forward. Returns the word dicts so
    the ASS builder can karaoke-time each word."""
    chunks: list[tuple[list[dict], float, float]] = []
    group: list[dict] = []
    for w in words:
        group.append(w)
        span = group[-1]["end"] - group[0]["start"]
        if span >= target_s or len(group) >= max_words:
            chunks.append((group, group[0]["start"], group[-1]["end"]))
            group = []
    if group:
        chunks.append((group, group[0]["start"], group[-1]["end"]))
    merged: list[tuple[list[dict], float, float]] = []
    for c in chunks:
        if merged and (c[2] - c[1]) < min_s and len(merged[-1][0]) + len(c[0]) <= max_words + 2:
            prev = merged.pop()
            merged.append((prev[0] + c[0], prev[1], c[2]))
        else:
            merged.append(c)
    return merged


def _ass_time(s: float) -> str:
    s = max(s, 0.0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}"


def _build_ass(words: list[dict], out_path: pathlib.Path, total: float) -> pathlib.Path:
    """words.json -> karaoke .ass. Style notes: Alignment 2 (bottom-center) with
    MarginV 380 keeps the block above y=1540 (Shorts UI safe area); MarginR 140 clears
    the right-rail buttons; SecondaryColour is the pre-sweep grey the \\kf fill runs
    over. Outline 6 matches the old TextClip stroke - no clipping, libass pads glyphs."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {TARGET_W}\nPlayResY: {TARGET_H}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,{CAPTION_FONT},58,&H00FFFFFF,&H00C8C8C8,&H00000000,&H80000000,"
        "0,0,0,0,100,100,0,0,1,6,0,2,80,140,380,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for group, start, end in _caption_chunks(words):
        end = min(end + 0.08, total)
        if end <= start:
            continue
        parts = []
        for i, w in enumerate(group):
            nxt = group[i + 1]["start"] if i + 1 < len(group) else end
            cs = max(int(round((nxt - w["start"]) * 100)), 1)
            text = w["word"].upper().replace("{", "").replace("}", "").replace("\\", "")
            parts.append(f"{{\\kf{cs}}}{text}")
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{' '.join(parts)}\n"
        )
    out_path.write_text("".join(lines), encoding="utf-8-sig")
    return out_path


def _rel_or_escaped(target: pathlib.Path, base: pathlib.Path) -> str:
    """Path for an ffmpeg filter option: relative to the run cwd when possible, else
    absolute with the drive colon escaped. Always single-quoted - the filter option
    parser splits on bare ':' and chokes on spaces ("Side Projects")."""
    try:
        p = pathlib.Path(os.path.relpath(target, base)).as_posix()
    except ValueError:  # different drive
        p = target.as_posix().replace(":", r"\:")
    return f"'{p}'"


def assemble(spec: dict, audio_path: str, image_paths: list[str], words_json: str,
             out_master: str, out_proxy: str, music_dir: str | None = None,
             music_seed: str = "") -> tuple[str, str]:
    from moviepy import AudioFileClip, CompositeVideoClip, ImageClip

    from .audiofx import build_final_audio, pick_music

    with AudioFileClip(audio_path) as a:
        total = a.duration
    assets = pathlib.Path(audio_path).parent
    words = json.loads(pathlib.Path(words_json).read_text(encoding="utf-8"))

    timing_file = assets / "beat_timing.json"
    expected = 2 + len(spec["beats"])  # hook + beats + outro
    timing = json.loads(timing_file.read_text(encoding="utf-8")) if timing_file.exists() else []
    if len(timing) == expected:
        durations = _durations_from_timing(timing, total)
    else:
        durations = _beat_durations(spec, total)

    # Map images to segments: hook shares the first beat image; payoff/cta share the last.
    seg_images = [image_paths[0]] + list(image_paths) + [image_paths[-1]]
    seg_images = seg_images[: len(durations)]
    while len(seg_images) < len(durations):
        seg_images.append(image_paths[-1])

    clips = []
    t = 0.0
    base_scale = max(TARGET_W / 768, TARGET_H / 1344)  # cover the canvas
    for img_path, dur in zip(seg_images, durations, strict=True):
        clip = (
            ImageClip(img_path)
            .with_duration(dur)
            .with_start(t)
            .resized(lambda tt, d=dur, s=base_scale: s * (1.0 + 0.06 * (tt / max(d, 0.1))))
            .with_position("center")
        )
        clips.append(clip)
        t += dur

    master = pathlib.Path(out_master)
    master.parent.mkdir(parents=True, exist_ok=True)
    silent = master.with_name("video_silent.mp4")
    video = CompositeVideoClip(clips, size=(TARGET_W, TARGET_H)).with_duration(total)
    # Near-lossless intermediate: the burn/mux pass below re-encodes once at CRF 19.
    video.write_videofile(
        str(silent), fps=30, codec="libx264", audio=False,
        preset="medium", threads=6, logger=None,
        ffmpeg_params=["-crf", "16", "-pix_fmt", "yuv420p"],
    )
    video.close()

    ass = _build_ass(words, assets / "short.ass", total)
    mixed = build_final_audio(
        audio_path, master.with_name("final_audio.wav"),
        pick_music(music_dir, seed=music_seed) if music_dir else None, total,
    )

    # Burn + mux from the run assets dir so filter paths stay colon-free.
    sub = (f"subtitles=filename={_rel_or_escaped(ass, assets)}"
           f":fontsdir={_rel_or_escaped(FONTS_DIR, assets)}")
    # +faststart puts the moov atom at the file head so Discord/browsers can stream-preview
    # the mp4 (without it the attachment shows but won't play inline - user-reported bug).
    _run_ff([_ffmpeg(), "-hide_banner", "-y",
             "-i", str(silent), "-i", str(mixed),
             "-vf", sub, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(master)], cwd=str(assets))
    silent.unlink(missing_ok=True)

    # Proxy: 540x960, bitrate budgeted to stay under the Discord cap.
    video_kbps = max(int(PROXY_LIMIT_MB * 8192 / total * 0.9) - 110, 200)
    _run_ff([_ffmpeg(), "-hide_banner", "-y", "-i", str(master),
             "-vf", "scale=540:960", "-c:v", "libx264", "-preset", "medium",
             "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out_proxy)])
    return str(master), str(out_proxy)
