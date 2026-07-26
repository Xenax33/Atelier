"""Assembly worker: stills + narration + word timings -> 1080x1920 master + sub-10MB proxy.

MoviePy 2.x API (no moviepy.editor). Motion = slow Ken-Burns zoom per still (ADR-0004:
no generative video on this card; clean motion over stills is the honest path).
Captions are burned in as grouped-word chunks synced to the whisper timings.
"""

from __future__ import annotations

import json
import pathlib

TARGET_W, TARGET_H = 1080, 1920
FONT = "C:/Windows/Fonts/arialbd.ttf"
PROXY_LIMIT_MB = 9.0  # Discord cap is 10; leave headroom


def _beat_durations(spec: dict, total: float) -> list[float]:
    """Split total audio time across hook+beats+payoff/cta proportional to word counts."""
    texts = [spec["hook"]] + [b["narration"] for b in spec["beats"]] + [spec["payoff"] + " " + spec["cta"]]
    counts = [max(1, len(t.split())) for t in texts]
    total_words = sum(counts)
    return [total * c / total_words for c in counts]


def _caption_chunks(words: list[dict], size: int = 3) -> list[tuple[str, float, float]]:
    chunks = []
    for i in range(0, len(words), size):
        group = words[i : i + size]
        text = " ".join(w["word"] for w in group)
        chunks.append((text, group[0]["start"], group[-1]["end"]))
    return chunks


def assemble(spec: dict, audio_path: str, image_paths: list[str], words_json: str,
             out_master: str, out_proxy: str) -> tuple[str, str]:
    from moviepy import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        TextClip,
    )

    audio = AudioFileClip(audio_path)
    total = audio.duration
    words = json.loads(pathlib.Path(words_json).read_text(encoding="utf-8"))

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

    # Captions: method="caption" WRAPS text inside a fixed-width box, so chunks can never
    # overflow the 9:16 frame (TASK-010: label-mode rendered one unwrapped line and long
    # chunks ran off both edges). 80px safe margins each side.
    caption_box_w = TARGET_W - 160
    text_clips = []
    for text, start, end in _caption_chunks(words):
        if end <= start:
            continue
        tc = (
            TextClip(
                text=text.upper(),
                font=FONT,
                font_size=58,
                color="white",
                stroke_color="black",
                stroke_width=6,
                method="caption",
                size=(caption_box_w, None),
                text_align="center",
            )
            .with_start(start)
            .with_duration(min(end - start + 0.08, total - start))
            .with_position(("center", int(TARGET_H * 0.72)))
        )
        text_clips.append(tc)

    video = CompositeVideoClip(clips + text_clips, size=(TARGET_W, TARGET_H)).with_audio(audio)
    video = video.with_duration(total)

    master = pathlib.Path(out_master)
    master.parent.mkdir(parents=True, exist_ok=True)
    # +faststart puts the moov atom at the file head so Discord/browsers can stream-preview
    # the mp4 (without it the attachment shows but won't play inline - user-reported bug).
    video.write_videofile(
        str(master), fps=30, codec="libx264", audio_codec="aac",
        preset="medium", threads=6, logger=None,
        ffmpeg_params=["-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )

    # Proxy: 540x960, bitrate budgeted to stay under the Discord cap.
    kbps = int(PROXY_LIMIT_MB * 8192 / total * 0.9)
    proxy = pathlib.Path(out_proxy)
    proxy_clip = video.resized((540, 960))
    proxy_clip.write_videofile(
        str(proxy), fps=30, codec="libx264", audio_codec="aac",
        preset="medium", threads=6, logger=None,
        bitrate=f"{kbps}k", ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    video.close()
    audio.close()
    return str(master), str(proxy)
