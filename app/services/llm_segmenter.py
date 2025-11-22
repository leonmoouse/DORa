import json
from typing import List

from pydantic import ValidationError

from app import config
from app.models import Scene
from app.utils.http import post_json

SYSTEM_PROMPT = """
你是一名经验丰富的漫画分镜脚本师，请将用户给出的中文旁白文案拆分为多个分镜，并为每个分镜生成哆啦A梦动漫风格的生图提示词。输出必须是 JSON 对象，根键为 scenes，内部为数组，每个元素包含 cap（旁白文本）与 desc_promopt（对应的画面提示词）。
""".strip()


def _parse_scenes(payload: str) -> List[Scene]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 返回非 JSON：{exc}") from exc

    if not isinstance(data, dict) or "scenes" not in data:
        raise ValueError("LLM 返回缺少 scenes 根键")

    scenes_raw = data.get("scenes")
    if not isinstance(scenes_raw, list):
        raise ValueError("LLM 返回的 scenes 不是数组")

    scenes: List[Scene] = []
    for idx, item in enumerate(scenes_raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {idx} 个分镜不是对象")
        try:
            scenes.append(Scene(cap=item["cap"], desc_prompt=item.get("desc_promopt") or item.get("desc_prompt")))
        except KeyError as exc:
            raise ValueError(f"分镜字段缺失：{exc}") from exc
        except ValidationError as exc:
            raise ValueError(f"分镜字段类型错误：{exc}") from exc
    return scenes


async def segment_script(script: str) -> List[Scene]:
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}" if config.LLM_API_KEY else "",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": script},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    response = await post_json(f"{config.LLM_BASE_URL}/chat/completions", headers=headers, data=payload)
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")

    if config.DEBUG_SAVE_LLM_RAW:
        (config.GENERATED_DIR / "llm_raw.json").write_text(content)

    scenes = _parse_scenes(content)
    if not scenes:
        raise ValueError("LLM 未返回有效分镜")
    return scenes
