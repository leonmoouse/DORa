# 竖版漫画解说视频生成系统（DORa）

DORa 旨在从一段中文原始文案自动生成哆啦 A 梦风格的竖版漫画解说视频：调用大模型拆分分镜，批量生成旁白音频与漫画风格图片，拼接时间线并导出视频与字幕文件。

## 核心能力

- **分镜脚本生成**：通过 LLM 将文案拆成分镜并产出生图提示词，严格返回 JSON 结构。
- **素材生成**：并发调用 TTS 和生图接口，为每个分镜生成音频（含毫秒级时长）与 9:16 图片。
- **时间线构建**：按毫秒计算每个分镜与字幕片段的起止时间，字幕单行不超过 10 个汉字。
- **视频合成**：在 1080×1920、30 FPS 画布上按三阶段动画（隐形→线稿→上色+轻微运动）混合图层，并合成旁白音轨。
- **前端与 API**：提供 `/api/generate` 接口和极简单页前端，输入文案后返回视频与 SRT 字幕下载链接。

## 技术选型

- **后端**：Python 3.11+、FastAPI、httpx/requests、pydantic、asyncio、ffmpeg（或 moviepy 包装）、pydub/mutagen。
- **前端**：静态 HTML + 原生 JavaScript，由 FastAPI 静态路由提供。
- **外部服务**：
  - LLM（`https://new.12ai.org/v1`，Bearer `$LLM_API_KEY`）。
  - TTS（`https://api.coze.cn/v1/audio/speech`，Bearer `$TTS_API_KEY`）。
  - 生图（`https://api.wuyinkeji.com/api/img/nanoBanana-pro` / `drawDetail`，Header `Authorization: $IMG_API_KEY`）。
- **运行依赖**：需在环境中安装 ffmpeg，所有访问凭证通过环境变量配置。

## 模块概览

- `llm_segmenter`：使用系统 Prompt 生成 `Scene` 列表（字段 `cap`、`desc_prompt`）。
- `tts_service`：为 `cap` 生成 mp3 并测时长；
- `image_service`：提交生图任务并轮询至获取 `image_url`；
- `subtitle_service`：按 10 字上限拆分字幕并生成 `SubtitleChunk` 时间线；
- `timeline_service`：顺序累加生成 `SceneClip`；
- `animation_service`：基于时长与索引生成缩放、平移及三阶段比例；
- `video_renderer`：下载图片、生成 blank/line_art/color_full 三层并混合输出 mp4；
- `api_server`：对外暴露 `/api/generate`，协调各 Agent；
- `frontend`：textarea 输入文案、可选标题，生成后展示视频与字幕链接。

## 开发与测试建议

1. 克隆仓库并确认安装 ffmpeg；设置环境变量 `LLM_API_KEY`、`TTS_API_KEY`、`IMG_API_KEY`。
2. 在本地创建虚拟环境并安装 `requirements.txt`，运行 `uvicorn app.main:app --reload` 启动服务，前端访问 `http://localhost:8000/static/index.html`。
3. 生成流程完全异步，`MAX_CONCURRENT_SCENES` 环境变量控制分镜级并发（默认 8）。
4. 生图接口默认每 2–3 秒轮询一次，超时/失败会抛出异常；LLM 返回的 JSON 解析失败同样抛错并透传到前端。
5. 视频导出统一使用 1080×1920、30 FPS，旁白按分镜顺序拼接；字幕以 SRT 导出并保证时间戳与音频对齐。
6. 开发调试时可将 `DEBUG_SAVE_LLM_RAW=true` 写入环境变量以保存 LLM 原始返回，方便排查。

## 当前仓库结构

- `AGENTS.md`：提供完整的项目规范与接口要求。
- `README.md`：概览项目定位、技术栈与开发建议（本文档）。
