import uuid
from pathlib import Path
from typing import Dict, List

import httpx
import numpy as np
from moviepy.editor import AudioFileClip, VideoClip, concatenate_videoclips
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pydub import AudioSegment

from app import config
from app.models import AnimationConfig, SceneAsset, SceneClip


def _ensure_size(img: Image.Image) -> Image.Image:
    return img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.Resampling.LANCZOS)


def _generate_line_art(img: Image.Image) -> Image.Image:
    gray = img.convert("L").filter(ImageFilter.GaussianBlur(radius=1.2))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    inverted = ImageEnhance.Contrast(ImageOps.invert(edges)).enhance(2.0)
    base = Image.new("RGB", img.size, (240, 240, 240))
    return Image.blend(base, inverted.convert("RGB"), alpha=0.8)


def _load_layers(image_path: Path) -> Dict[str, Image.Image]:
    color = Image.open(image_path).convert("RGB")
    color = _ensure_size(color)
    blank = Image.new("RGB", color.size, (255, 255, 255))
    line_art = _generate_line_art(color)
    return {"color_full": color, "line_art": line_art, "blank": blank}


def _interpolate(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress


def _apply_transform(img: Image.Image, scale: float, offset_x: float, offset_y: float) -> Image.Image:
    w, h = img.size
    new_w, new_h = int(w * scale), int(h * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    dx = int(offset_x * h)
    dy = int(offset_y * h)
    paste_x = (w - new_w) // 2 + dx
    paste_y = (h - new_h) // 2 + dy
    canvas.paste(resized, (paste_x, paste_y))
    return canvas


def _blend_frames(layers: Dict[str, Image.Image], progress: float, anim: AnimationConfig) -> np.ndarray:
    phase_a_end = anim.phase_a_ratio
    phase_b_end = anim.phase_a_ratio + anim.phase_b_ratio

    if progress < phase_a_end:
        line_alpha = progress / phase_a_end
        color_alpha = 0.0
    elif progress < phase_b_end:
        local = (progress - phase_a_end) / (phase_b_end - phase_a_end)
        line_alpha = 1.0 - 0.6 * local
        color_alpha = local
    else:
        local = (progress - phase_b_end) / max(1e-6, 1 - phase_b_end)
        line_alpha = 0.4 * (1 - local)
        color_alpha = 1.0

    scale = _interpolate(anim.start_scale, anim.end_scale, progress)
    offset_x = _interpolate(anim.start_offset_x, anim.end_offset_x, progress)
    offset_y = _interpolate(anim.start_offset_y, anim.end_offset_y, progress)

    base = _apply_transform(layers["blank"], scale, offset_x, offset_y)
    line = _apply_transform(layers["line_art"], scale, offset_x, offset_y)
    color = _apply_transform(layers["color_full"], scale, offset_x, offset_y)

    frame = Image.blend(base, line, alpha=line_alpha)
    frame = Image.blend(frame, color, alpha=color_alpha)
    return np.array(frame)


def _build_scene_clip(layers: Dict[str, Image.Image], clip: SceneClip, anim: AnimationConfig) -> VideoClip:
    duration = (clip.end_ms - clip.start_ms) / 1000

    def make_frame(t: float):
        progress = min(max(t / duration, 0), 1)
        return _blend_frames(layers, progress, anim)

    return VideoClip(make_frame=make_frame, duration=duration)


def _merge_audios(assets: List[SceneAsset]) -> Path:
    combined = AudioSegment.empty()
    for asset in assets:
        combined += AudioSegment.from_file(asset.audio_path)
    target = config.GENERATED_DIR / f"voice_{uuid.uuid4().hex}.mp3"
    combined.export(target, format="mp3")
    return target


async def _download_image(url: str) -> Path:
    target = config.GENERATED_DIR / f"image_{uuid.uuid4().hex}.png"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        target.write_bytes(resp.content)
    return target


async def render_video(clips: List[SceneClip], animations: List[AnimationConfig]) -> Path:
    scene_videos: List[VideoClip] = []
    assets = [clip.asset for clip in clips]

    for clip, anim in zip(clips, animations):
        image_path = config.GENERATED_DIR / Path(clip.asset.image_url).name
        if not image_path.exists():
            image_path = await _download_image(clip.asset.image_url)
        layers = _load_layers(image_path)
        scene_videos.append(_build_scene_clip(layers, clip, anim))

    video = concatenate_videoclips(scene_videos, method="compose")
    audio_path = _merge_audios(assets)
    audio_clip = AudioFileClip(str(audio_path))
    final = video.set_audio(audio_clip).set_fps(config.VIDEO_FPS)

    output = config.GENERATED_DIR / f"video_{uuid.uuid4().hex}.mp4"
    final.write_videofile(
        str(output),
        codec="libx264",
        audio_codec="aac",
        fps=config.VIDEO_FPS,
        preset="medium",
    )
    final.close()
    audio_clip.close()
    for clip_video in scene_videos:
        clip_video.close()
    return output
