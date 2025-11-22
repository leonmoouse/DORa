from typing import Optional

from pydantic import BaseModel, Field


class Scene(BaseModel):
    cap: str = Field(..., description="旁白文本")
    desc_prompt: str = Field(..., description="生图提示词")


class SceneAsset(BaseModel):
    scene: Scene
    image_url: str
    audio_path: str
    duration_ms: int


class SceneClip(BaseModel):
    asset: SceneAsset
    start_ms: int
    end_ms: int


class SubtitleChunk(BaseModel):
    text: str
    start_ms: int
    end_ms: int


class AnimationConfig(BaseModel):
    scene_index: int
    duration_ms: int
    phase_a_ratio: float = 0.25
    phase_b_ratio: float = 0.30
    phase_c_ratio: float = 0.45
    start_scale: float
    end_scale: float
    start_offset_x: float
    start_offset_y: float
    end_offset_x: float
    end_offset_y: float


class GenerateRequest(BaseModel):
    title: Optional[str]
    script: str
    voice_id: Optional[str] = None
    speed: Optional[float] = 1.0


class GenerateResponse(BaseModel):
    video_url: str
    subtitle_url: str
