import asyncio
from pathlib import Path
from typing import List

from app import config
from app.models import AnimationConfig, GenerateRequest, GenerateResponse, Scene, SceneAsset
from app.services import animation_service, image_service, llm_segmenter, subtitle_service, timeline_service, tts_service, video_renderer


async def _build_asset(scene: Scene, voice_id: str | None, speed: float | None, semaphore: asyncio.Semaphore) -> SceneAsset:
    async with semaphore:
        audio_task = asyncio.create_task(tts_service.generate_audio(scene.cap, voice_id=voice_id, speed=speed or 1.0))
        image_task = asyncio.create_task(image_service.generate_image(scene.desc_prompt))
        audio_path, duration_ms = await audio_task
        image_url = await image_task
        return SceneAsset(scene=scene, image_url=image_url, audio_path=audio_path, duration_ms=duration_ms)


async def generate_video_pipeline(req: GenerateRequest) -> GenerateResponse:
    scenes = await llm_segmenter.segment_script(req.script)

    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_SCENES)
    assets: List[SceneAsset] = await asyncio.gather(
        *[_build_asset(scene, req.voice_id, req.speed, semaphore) for scene in scenes]
    )

    clips, _ = timeline_service.build_scene_clips(assets)
    animations: List[AnimationConfig] = [
        animation_service.build_animation_config(idx, clip.end_ms - clip.start_ms) for idx, clip in enumerate(clips)
    ]
    subtitles = subtitle_service.build_subtitles(scenes, clips)

    video_path = await video_renderer.render_video(clips, animations)
    subtitle_path = config.GENERATED_DIR / f"subtitle_{Path(video_path).stem}.srt"
    subtitle_service.export_srt(subtitles, str(subtitle_path))

    return GenerateResponse(
        video_url=f"/generated/{Path(video_path).name}",
        subtitle_url=f"/generated/{subtitle_path.name}",
    )
