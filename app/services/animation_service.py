from app.models import AnimationConfig


def build_animation_config(scene_index: int, duration_ms: int) -> AnimationConfig:
    if duration_ms < 3000:
        start_scale, end_scale = 1.1, 1.3
    elif duration_ms <= 6000:
        start_scale, end_scale = 1.05, 1.2
    else:
        start_scale, end_scale = 1.0, 1.1

    direction = scene_index % 4
    offsets = {
        0: (0.0, 0.02, 0.0, -0.03),
        1: (0.02, 0.0, -0.03, 0.0),
        2: (-0.02, 0.0, 0.03, 0.0),
        3: (0.0, -0.02, 0.0, 0.03),
    }[direction]

    return AnimationConfig(
        scene_index=scene_index,
        duration_ms=duration_ms,
        start_scale=start_scale,
        end_scale=end_scale,
        start_offset_x=offsets[0],
        start_offset_y=offsets[1],
        end_offset_x=offsets[2],
        end_offset_y=offsets[3],
    )
