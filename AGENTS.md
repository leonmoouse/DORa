# Agents.md – 竖版漫画解说视频生成系统

## 0. 项目目标

从一段中文原始文案出发，自动完成：

1. 调用大模型将文案拆分为分镜，并生成每个分镜的画面提示词（哆啦A梦风格）。
2. 为每个分镜调用 TTS 接口生成旁白音频，并获取精确时长（毫秒）。
3. 为每个分镜调用生图接口生成竖版漫画风格图片（9:16，约 1K 分辨率）。
4. 按毫秒为单位构建完整时间线：
   - 每个分镜的起止时间
   - 每条字幕碎片的起止时间
5. 按以下规则生成成品：
   - **视频**：9:16 竖版，分辨率约 1080×1920，帧率 30 FPS，画面为分镜图片 + 约定的动画效果。
   - **音频**：使用拼接好的旁白音轨。
   - **字幕文件**：SRT（或可扩展），单行不超过 10 个汉字，与旁白严格对齐（毫秒级）。

前端只提供一个极简页面：

- 文案输入框
- 可选标题输入框
- 「生成」按钮
- 生成完成后展示视频播放器与字幕下载链接

不直接调用剪映 API，生成的视频与字幕由后期在剪映中导入。

---

## 1. 外部 API 与配置

所有外部访问参数应通过环境变量配置，不要在代码中硬编码。

### 1.1 大模型：分镜脚本与提示词

- **Base URL**：`https://new.12ai.org/v1`
- **鉴权**：`Authorization: Bearer $LLM_API_KEY`
- **兼容性假设**：接口为 OpenAI 风格的 `POST /chat/completions`（如与实际不符，可在实现时根据真实文档调整路径与字段）。
- **模型 ID**：使用者自配，如 `gemini-3-pro`。
- **System Prompt**：使用文档中给出的完整系统提示词，角色为“漫画分镜脚本师”，输出格式为：

  ```json
  {
    "scenes": [
      {
        "cap": "第一句文案",
        "desc_promopt": "哆啦A梦动漫风格，[描述]..."
      }
    ]
  }
  ```

  该 prompt 已在项目文档中给出，需原样使用以确保风格与 JSON 结构稳定。

**必须要求**：

- 使用 response_format / 温度等参数，确保模型返回严格 JSON 对象，根键名为 "scenes"。
- 如果解析失败，应抛出错误并返回给前端人类处理（不要静默吞掉）。

### 1.2 TTS：旁白音频生成

- **URL**：`https://api.coze.cn/v1/audio/speech`
- **鉴权**：`Authorization: Bearer $TTS_API_KEY`
- **请求头**：`Content-Type: application/json`
- **固定参数**：
  - `voice_id`: "7540911707150008374"
  - `emotion`: "coldness"
  - `response_format`: "mp3"
  - `speed`: 1
  - `sample_rate`: 24000
  - `loudness_rate`: 30
- **变量参数**：`input`（当前分镜的 cap 文本）
- **返回**：MP3 二进制音频数据（直接是音频流或 base64，具体按接口实现）。

**时长获取策略**：

- 将音频保存为临时 mp3 文件，通过 ffmpeg 或 pydub 读取音频时长，并统一转为毫秒：`duration_ms = round(duration_seconds * 1000)`。

### 1.3 生图：竖版漫画画面

- **同步创建任务 URL**：`https://api.wuyinkeji.com/api/img/nanoBanana-pro`
- **异步轮询 URL**：`https://api.wuyinkeji.com/api/img/drawDetail`
- **鉴权**：`Authorization: $IMG_API_KEY`（值为控制台中的密钥）
- **请求头**：`Content-Type: application/json;charset:utf-8;`
- **请求体字段**：
  - `prompt` (string, 必填)：使用 LLM 输出的 desc_promopt
  - `img_url` (可选)：本项目不使用
  - `aspectRatio` (string, 必填)：固定 "9:16"
- **返回（创建任务）**：
  ```json
  {
    "code": 200,
    "msg": "成功",
    "data": {
      "id": 23
    }
  }
  ```
- **返回（轮询结果）**：
  ```json
  {
    "code": 200,
    "msg": "成功",
    "data": {
      "id": 33,
      "status": 2,
      "size": "",
      "prompt": "...",
      "image_url": "https://...png",
      "fail_reason": "",
      "created_at": "...",
      "updated_at": "..."
    }
  }
  ```
- **状态**：
  - `0`: 排队中
  - `1`: 生成中
  - `2`: 成功
  - `3`: 失败
- **图片尺寸约束**：接口固定输出 9:16 纵向图片，约 1K 分辨率（例如 ~1080×1920），无需二次裁剪，只需要在视频合成时对齐分辨率即可。

**轮询策略**：

- 每隔 2–3 秒轮询一次。
- 最大等待时长如 60–120 秒，超时返回错误。

## 2. 系统整体架构

### 2.1 技术栈建议

- 后端：Python 3.11+、FastAPI、httpx/requests、pydantic、asyncio、ffmpeg（ffmpeg-python 或子进程）、pydub/ mutagen。
- 前端：简单静态 HTML + 原生 JavaScript（单页应用），由 FastAPI 静态路由提供。
- 运行环境需安装 ffmpeg 命令行工具。

### 2.2 逻辑组件（“Agents”）

- llm_segmenter：调用大模型，将原始文案拆成分镜并生成画面提示词。
- tts_service：调用 TTS API，为每个分镜生成旁白音频，并计算时长（毫秒）。
- image_service：调用生图 API，为每个分镜生成 9:16 图片，并轮询结果。
- subtitle_service：根据分镜文本与时长生成细分字幕行与时间线（单行 ≤ 10 字）。
- timeline_service：按毫秒构建完整时间线（音频、图像、字幕）。
- animation_service：基于时间线，为每个分镜生成动画参数（隐形→线稿→上色＋轻微移动）。
- video_renderer：根据时间线、图片与动画参数，用 ffmpeg/moviepy 生成 9:16、30 FPS 的 mp4 视频，并合成旁白音轨。
- api_server：对外 HTTP 接口（/api/generate），协调上述组件。
- frontend：文案输入页面。

## 3. 数据模型（核心结构）

使用 Python/pydantic 定义关键数据类型。

### 3.1 Scene（分镜定义）
```python
class Scene(BaseModel):
    cap: str           # 旁白文本
    desc_prompt: str   # 生图提示词
```

### 3.2 SceneAsset（分镜素材）
```python
class SceneAsset(BaseModel):
    scene: Scene
    image_url: str      # 生图 URL
    audio_path: str     # 本地保存的 mp3 路径
    duration_ms: int    # 音频时长，毫秒
```

### 3.3 SceneClip（时间线上的片段）
```python
class SceneClip(BaseModel):
    asset: SceneAsset
    start_ms: int
    end_ms: int
```

### 3.4 SubtitleChunk（字幕片段）
```python
class SubtitleChunk(BaseModel):
    text: str          # 不超过 10 个汉字
    start_ms: int
    end_ms: int
```

### 3.5 AnimationConfig（动画配置）
```python
class AnimationConfig(BaseModel):
    scene_index: int
    duration_ms: int
    # 三阶段时间分配比例，默认 [0.25, 0.30, 0.45]
    phase_a_ratio: float = 0.25   # 隐形 -> 线稿
    phase_b_ratio: float = 0.30   # 线稿 -> 上色
    phase_c_ratio: float = 0.45   # 上色 + 轻微运动
    # 镜头缩放和平移参数（相对值）
    start_scale: float
    end_scale: float
    start_offset_x: float
    start_offset_y: float
    end_offset_x: float
    end_offset_y: float
```

### 3.6 生成请求与响应
```python
class GenerateRequest(BaseModel):
    title: Optional[str]
    script: str
    voice_id: Optional[str] = None  # 默认使用全局配置
    speed: Optional[float] = 1.0

class GenerateResponse(BaseModel):
    video_url: str        # 后端静态可访问 URL
    subtitle_url: str     # SRT 文件 URL
```

## 4. 核心流程与各 Agent 逻辑

### 4.1 Orchestrator：主流程（后端入口）

```python
async def generate_video_pipeline(req: GenerateRequest) -> GenerateResponse:
    ...
```

1. 调用 llm_segmenter：输入 script，输出 List[Scene]。
2. 并发调用 tts_service 和 image_service：
   - 对每个 scene 开启异步任务，并行生成音频和图片。
   - 使用 asyncio.Semaphore 控制最大并发数（建议 8）。
3. 构建 SceneClip 时间线（timeline_service）：顺序分配 start_ms / end_ms。
4. 生成字幕碎片（subtitle_service）：单行 ≤ 10 字，按时长比例分配毫秒数。
5. 为每个分镜生成动画配置（animation_service）。
6. 调用 video_renderer 渲染视频并合成音轨。
7. 生成 SRT 字幕文件，返回 video_url 与 subtitle_url。

### 4.2 llm_segmenter：文案拆分与提示词生成

- 构造 messages：system 使用项目文档中的系统提示词，user 为原始文案。
- 调用 LLM API：`POST $LLM_BASE_URL/chat/completions`，要求 `response_format = {"type": "json_object"}`。
- 解析返回 JSON，根键必须为 `scenes`，字段缺失或类型错误需抛出异常。

### 4.3 image_service：生图

- 创建任务：POST nanoBanana-pro 接口，body 包含 prompt 与 aspectRatio。
- 轮询 drawDetail 接口，间隔 2–3 秒，最大等待 60–120 秒。
- 成功返回 image_url；失败或超时抛出异常。

### 4.4 subtitle_service：字幕拆分与时间线

- 文本拆分：按句号/逗号等分隔符切片，每段 ≤ 10 汉字，不足则强制截断。
- 时长分配：按字数比例分配分镜总时长，毫秒级；最后一段用剩余时长兜底。
- 输出 SubtitleChunk 列表并转换为全局时间。

### 4.5 tts_service：生成音频与时长

- 调用 TTS API 获取 mp3，保存临时文件。
- 使用 ffprobe 或 pydub 获取时长，转换为毫秒，返回 (file_path, duration_ms)。

### 4.6 timeline_service：场景时间线

- current_ms 从 0 开始，依次累加 asset.duration_ms 构建 SceneClip。
- 返回 clips 列表与 total_duration_ms。

### 4.7 animation_service：隐形 → 线稿 → 上色 + 轻微运动

- 阶段比例：A 0–25%，B 25–55%，C 55–100%。
- 缩放策略：
  - D < 3000ms：1.1 → 1.3
  - 3000–6000ms：1.05 → 1.2
  - D > 6000ms：1.0 → 1.1
- 平移方向按索引循环上下左右，偏移量为 2–3% 画幅。
- video_renderer 需生成 blank/line_art/color_full 三层图并按阶段混合，应用缩放和平移动画。

### 4.8 video_renderer：视频与音频合成

- 下载图片到本地，固定分辨率 1080×1920。
- 为每个 SceneClip 构造自定义 VideoClip，按阶段混合线稿/彩色并做平移缩放。
- 拼接所有 clip，设置 30 FPS，libx264 导出 mp4。
- 旁白音频按顺序合并后设置为视频音轨。

### 4.9 字幕文件导出

- 按 start_ms 排序生成 SRT：

```
index
HH:MM:SS,mmm --> HH:MM:SS,mmm
文本
```

- 提供毫秒到时间戳的转换函数。

## 5. REST API 设计

### 5.1 POST /api/generate

- 请求体：GenerateRequest。
- 响应体：GenerateResponse。
- 行为：同步调用生成流程，返回视频与字幕 URL；若生成时间过长，可后续扩展任务队列。
- 错误：外部调用失败/超时/解析失败需返回 4xx/5xx，并在前端显示错误信息。

## 6. 前端规范（极简）

- 页面元素：textarea#script-input、input#title-input、button#generate-btn、video#result-video、a#subtitle-link、div#status。
- 交互：
  - 校验文案非空，点击生成后禁用按钮并显示进度。
  - fetch POST /api/generate，成功后展示播放器与字幕链接，失败显示错误。
  - 样式保持极简，可用基础 CSS 增加间距。

## 7. 并发与性能要求

- 分镜级并发：对每个 Scene 并发调用 TTS 与生图，使用 asyncio.Semaphore（默认 8）。
- 轮询生图：每 2–3 秒一次，最大等待可配置。
- 清理策略：音视频与图片文件可按创建时间定期清理（如 24 小时）。

## 8. 日志与错误处理

- 记录每次外部请求的 URL、耗时、状态码、失败原因。
- 调试模式下保存 LLM 原始返回文本，便于排查 JSON 解析失败。
- 出错时尽量保留中间文件以便诊断，但不应阻塞新请求。
