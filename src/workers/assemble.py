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
# Cut-ins (R&D 7.1): segments at least this long get a second shot - a crop-reframe of
# the SAME approved still - halving the visual-change interval for free. Archival
# letterboxed frames are excluded (cropping a letterboxed diagram destroys it).
# Set CUTIN_MIN_S very high to disable.
CUTIN_MIN_S = 6.0
CUTIN_SCALE = 0.62   # crop covers 62% of the source frame
CUTIN_Y_BIAS = 0.4   # crop center sits at 40% height (subjects live upper-center in 9:16)
CUTIN_SPLIT = 0.55   # wide shot runs 55% of the segment, cut-in the rest


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
    """ASS H:MM:SS.cc timestamp. Integer centisecond math: float formatting could round
    59.998s to the malformed "59.100"-style "0:00:60.00" (review 2026-08-06)."""
    cs = max(int(round(s * 100)), 0)
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    sec, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


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


def _cutin_path(img_path: str) -> str:
    """Crop-reframe of an approved still (R&D 7.1): a free second shot. Center crop,
    biased toward the upper third where 9:16 subjects sit; written next to the source."""
    from PIL import Image

    src = pathlib.Path(img_path)
    out = src.with_name(src.stem + "_cutin.png")
    with Image.open(src) as img:
        cw, ch = int(img.width * CUTIN_SCALE), int(img.height * CUTIN_SCALE)
        left = (img.width - cw) // 2
        top = int((img.height - ch) * CUTIN_Y_BIAS)
        img.crop((left, top, left + cw, top + ch)).save(out)
    return str(out)


def assemble(spec: dict, audio_path: str, image_paths: list[str], words_json: str,
             out_master: str, out_proxy: str, music_dir: str | None = None,
             music_seed: str = "", archival_beats: list[int] | None = None) -> tuple[str, str]:
    from moviepy import AudioFileClip, CompositeVideoClip, ImageClip
    from PIL import Image

    from .audiofx import build_final_audio, pick_music

    # Everything absolute UP FRONT: the burn/mux ffmpeg pass below runs with cwd set to
    # the run assets dir, and the bot hands us paths relative to the REPO root ("state\runs\...")
    # - those break the moment cwd changes (live failure 2026-08-04 at Gate-3 assembly).
    audio_path = str(pathlib.Path(audio_path).resolve())
    words_json = str(pathlib.Path(words_json).resolve())
    image_paths = [str(pathlib.Path(p).resolve()) for p in image_paths]
    out_master = str(pathlib.Path(out_master).resolve())
    out_proxy = str(pathlib.Path(out_proxy).resolve())

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
    # A segment is archival-backed when the beat whose image it shows is archival - those
    # frames never get cut-ins (or any crop) because the letterbox IS the composition.
    archival = set(archival_beats or [])
    n_beats = len(image_paths)
    seg_beat = [0] + list(range(n_beats)) + [n_beats - 1]
    seg_images = [image_paths[0]] + list(image_paths) + [image_paths[-1]]
    seg_images = seg_images[: len(durations)]
    while len(seg_images) < len(durations):
        seg_images.append(image_paths[-1])
        seg_beat.append(n_beats - 1)

    def _kb_clip(path: str, start: float, dur: float) -> ImageClip:
        # Scale from the image's REAL size (was hardcoded 768x1344, which over-zoomed
        # 1080x1920 archival letterbox frames 1.4x and cropped them - fixed 2026-08-06).
        with Image.open(path) as im:
            s = max(TARGET_W / im.width, TARGET_H / im.height)
        return (ImageClip(path).with_duration(dur).with_start(start)
                .resized(lambda tt, d=dur, sc=s: sc * (1.0 + 0.06 * (tt / max(d, 0.1))))
                .with_position("center"))

    clips = []
    t = 0.0
    for j, (img_path, dur) in enumerate(zip(seg_images, durations, strict=True)):
        if dur >= CUTIN_MIN_S and seg_beat[j] not in archival:
            wide = dur * CUTIN_SPLIT
            clips.append(_kb_clip(img_path, t, wide))
            clips.append(_kb_clip(_cutin_path(img_path), t + wide, dur - wide))
        else:
            clips.append(_kb_clip(img_path, t, dur))
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
    # bt709 tags (R&D 7.4): untagged H.264 renders washed-out/shifted in some players and
    # after YouTube's transcode - tag what we actually produce (sRGB-ish -> bt709).
    _run_ff([_ffmpeg(), "-hide_banner", "-y",
             "-i", str(silent), "-i", str(mixed),
             "-vf", sub, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-color_range", "tv",
             "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(master)], cwd=str(assets))
    silent.unlink(missing_ok=True)

    # Proxy: 540x960, bitrate budgeted to stay under the Discord cap.
    video_kbps = max(int(PROXY_LIMIT_MB * 8192 / total * 0.9) - 110, 200)
    _run_ff([_ffmpeg(), "-hide_banner", "-y", "-i", str(master),
             "-vf", "scale=540:960", "-c:v", "libx264", "-preset", "medium",
             "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out_proxy)])
    return str(master), str(out_proxy)
