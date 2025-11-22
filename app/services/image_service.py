import asyncio
import time

from app import config
from app.utils.http import get_json, post_json

CREATE_URL = "https://api.wuyinkeji.com/api/img/nanoBanana-pro"
POLL_URL = "https://api.wuyinkeji.com/api/img/drawDetail"


async def _create_task(prompt: str) -> int:
    headers = {
        "Authorization": config.IMG_API_KEY or "",
        "Content-Type": "application/json;charset:utf-8;",
    }
    body = {
        "prompt": prompt,
        "aspectRatio": "9:16",
    }
    response = await post_json(CREATE_URL, headers=headers, data=body)
    data = response.json()
    if data.get("code") != 200:
        raise ValueError(f"生图创建任务失败：{data}")
    task_id = data.get("data", {}).get("id")
    if task_id is None:
        raise ValueError("生图创建任务未返回 id")
    return int(task_id)


async def _poll_task(task_id: int) -> str:
    headers = {"Authorization": config.IMG_API_KEY or ""}
    deadline = time.time() + config.IMG_POLL_TIMEOUT
    while time.time() < deadline:
        response = await get_json(f"{POLL_URL}?id={task_id}", headers=headers)
        data = response.json()
        if data.get("code") != 200:
            raise ValueError(f"生图轮询失败：{data}")
        detail = data.get("data") or {}
        status = detail.get("status")
        if status == 2:
            image_url = detail.get("image_url")
            if not image_url:
                raise ValueError("生图成功但未返回 image_url")
            return image_url
        if status == 3:
            raise ValueError(f"生图生成失败：{detail.get('fail_reason')}")
        await asyncio.sleep(config.IMG_POLL_INTERVAL)
    raise TimeoutError("生图轮询超时")


async def generate_image(desc_prompt: str) -> str:
    task_id = await _create_task(desc_prompt)
    return await _poll_task(task_id)
