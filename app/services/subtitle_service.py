import re
from pathlib import Path
from typing import List

from app.models import Scene, SceneClip, SubtitleChunk


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def split_caption_to_chunks(text: str, max_len: int = 10) -> List[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    parts: List[str] = []
    queue = [cleaned]
    separators = ["。", "！", "？", "，", ",", "：", ":", "；", ";"]
    while queue:
        current = queue.pop(0)
        for sep in separators:
            if sep in current:
                before, after = current.split(sep, 1)
                if before:
                    queue.insert(0, after)
                    current = before + sep
                    break
        if len(current) <= max_len:
            parts.append(current)
        else:
            start = 0
            while start < len(current):
                parts.append(current[start : start + max_len])
                start += max_len
    return parts


def build_subtitles(scenes: List[Scene], clips: List[SceneClip]) -> List[SubtitleChunk]:
    subtitles: List[SubtitleChunk] = []
    for scene, clip in zip(scenes, clips):
        chunks = split_caption_to_chunks(scene.cap)
        if not chunks:
            continue
        total_chars = sum(len(c) for c in chunks)
        remaining = clip.end_ms - clip.start_ms
        start_ms = clip.start_ms
        for idx, chunk in enumerate(chunks):
            if idx == len(chunks) - 1:
                duration = remaining
            else:
                duration = round((clip.end_ms - clip.start_ms) * len(chunk) / total_chars)
                remaining -= duration
            end_ms = start_ms + duration
            subtitles.append(SubtitleChunk(text=chunk, start_ms=start_ms, end_ms=end_ms))
            start_ms = end_ms
    return subtitles


def format_timestamp(ms: int) -> str:
    seconds, millisecond = divmod(ms, 1000)
    minute, second = divmod(seconds, 60)
    hour, minute = divmod(minute, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d},{millisecond:03d}"


def export_srt(subtitles: List[SubtitleChunk], path: str) -> None:
    lines = []
    for idx, item in enumerate(sorted(subtitles, key=lambda s: s.start_ms), start=1):
        lines.append(str(idx))
        lines.append(f"{format_timestamp(item.start_ms)} --> {format_timestamp(item.end_ms)}")
        lines.append(item.text)
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
