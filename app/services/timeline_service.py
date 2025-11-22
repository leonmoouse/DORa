from typing import List, Tuple

from app.models import SceneAsset, SceneClip


def build_scene_clips(assets: List[SceneAsset]) -> Tuple[List[SceneClip], int]:
    clips: List[SceneClip] = []
    current_ms = 0
    for asset in assets:
        start_ms = current_ms
        end_ms = current_ms + asset.duration_ms
        clips.append(SceneClip(asset=asset, start_ms=start_ms, end_ms=end_ms))
        current_ms = end_ms
    return clips, current_ms
