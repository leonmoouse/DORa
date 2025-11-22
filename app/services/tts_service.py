import uuid
from pathlib import Path
from typing import Optional, Tuple

from pydub import AudioSegment

from app import config
from app.utils.http import post_json


def _write_audio(content: bytes, suffix: str = "mp3") -> Path:
    path = config.GENERATED_DIR / f"audio_{uuid.uuid4().hex}.{suffix}"
    path.write_bytes(content)
    return path


def _calc_duration_ms(path: Path) -> int:
    audio = AudioSegment.from_file(path)
    return round(audio.duration_seconds * 1000)


async def generate_audio(text: str, voice_id: Optional[str] = None, speed: float = 1.0) -> Tuple[str, int]:
    headers = {
        "Authorization": f"Bearer {config.TTS_API_KEY}" if config.TTS_API_KEY else "",
        "Content-Type": "application/json",
    }
    body = {
        "input": text,
        "voice_id": voice_id or config.TTS_DEFAULT_VOICE_ID,
        "emotion": "coldness",
        "response_format": "mp3",
        "speed": speed,
        "sample_rate": 24000,
        "loudness_rate": 30,
    }
    response = await post_json("https://api.coze.cn/v1/audio/speech", headers=headers, data=body, timeout=120.0)
    audio_bytes = response.content
    audio_path = _write_audio(audio_bytes)
    duration_ms = _calc_duration_ms(audio_path)
    return str(audio_path), duration_ms
