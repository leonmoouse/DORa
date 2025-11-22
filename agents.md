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
该 prompt 已在项目文档中给出，需原样使用以确保风格与 JSON 结构稳定。
视频项目api信息


必须要求：

使用 response_format / 温度等参数，确保模型返回严格 JSON 对象，根键名为 "scenes"。

如果解析失败，应抛出错误并返回给前端人类处理（不要静默吞掉）。

1.2 TTS：旁白音频生成
URL：https://api.coze.cn/v1/audio/speech

鉴权：Authorization: Bearer $TTS_API_KEY

请求头：

Content-Type: application/json

固定参数：

voice_id: "7540911707150008374"

emotion: "coldness"

response_format: "mp3"

speed: 1

sample_rate: 24000

loudness_rate: 30

变量参数：

input: 当前分镜的 cap 文本

返回：

MP3 二进制音频数据（直接是音频流或 base64，具体按接口实现）。

时长获取策略：

将音频保存为临时 mp3 文件，通过 ffmpeg 或 pydub 读取音频时长，并统一转为毫秒：

duration_ms = round(duration_seconds * 1000)

1.3 生图：竖版漫画画面
同步创建任务 URL：https://api.wuyinkeji.com/api/img/nanoBanana-pro

异步轮询 URL：https://api.wuyinkeji.com/api/img/drawDetail

鉴权：

Authorization: $IMG_API_KEY（值为控制台中的密钥）

请求头：

Content-Type: application/json;charset:utf-8;

请求体字段：

prompt (string, 必填)：使用 LLM 输出的 desc_promopt

img_url (可选)：本项目不使用

aspectRatio (string, 必填)：固定 "9:16"

返回（创建任务）：

json
复制代码
{
  "code": 200,
  "msg": "成功",
  "data": {
    "id": 23
  }
}
返回（轮询结果）：

json
复制代码
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
状态：

status：

0: 排队中

1: 生成中

2: 成功

3: 失败

图片尺寸约束：

接口固定输出 9:16 纵向图片，约 1K 分辨率（例如 ~1080×1920），无需二次裁剪，只需要在视频合成时对齐分辨率即可。

轮询策略：

每隔 2–3 秒轮询一次。

最大等待时长如 60–120 秒，超时返回错误。

2. 系统整体架构
2.1 技术栈建议
后端：

Python 3.11+

FastAPI（REST API）

httpx 或 requests（调用外部 API）

pydantic（请求/响应模型）

asyncio（并发）

ffmpeg（通过 ffmpeg-python 或直接子进程）

pydub 或 mutagen（音频时长计算）

前端：

简单静态 HTML + 原生 JavaScript（单页应用）

由 FastAPI 的静态路由直接提供

运行环境：

本地或服务器需安装 ffmpeg 命令行工具。

2.2 逻辑组件（“Agents”）
llm_segmenter：调用大模型，将原始文案拆成分镜并生成画面提示词。

tts_service：调用 TTS API，为每个分镜生成旁白音频，并计算时长（毫秒）。

image_service：调用生图 API，为每个分镜生成 9:16 图片，并轮询结果。

subtitle_service：根据分镜文本与时长生成细分字幕行与时间线（单行 ≤ 10 字）。

timeline_service：按毫秒构建完整时间线（音频、图像、字幕）。

animation_service：基于时间线，为每个分镜生成动画参数（隐形→线稿→上色＋轻微移动）。

video_renderer：根据时间线、图片与动画参数，用 ffmpeg/moviepy 生成 9:16、30 FPS 的 mp4 视频，并合成旁白音轨。

api_server：对外 HTTP 接口（/api/generate），协调上述组件。

frontend：文案输入页面。

3. 数据模型（核心结构）
使用 Python/pydantic 定义关键数据类型。

3.1 Scene（分镜定义）
python
复制代码
class Scene(BaseModel):
    cap: str           # 旁白文本
    desc_prompt: str   # 生图提示词
3.2 SceneAsset（分镜素材）
python
复制代码
class SceneAsset(BaseModel):
    scene: Scene
    image_url: str      # 生图 URL
    audio_path: str     # 本地保存的 mp3 路径
    duration_ms: int    # 音频时长，毫秒
3.3 SceneClip（时间线上的片段）
python
复制代码
class SceneClip(BaseModel):
    asset: SceneAsset
    start_ms: int
    end_ms: int
3.4 SubtitleChunk（字幕片段）
python
复制代码
class SubtitleChunk(BaseModel):
    text: str          # 不超过 10 个汉字
    start_ms: int
    end_ms: int
3.5 AnimationConfig（动画配置）
python
复制代码
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
3.6 生成请求与响应
python
复制代码
class GenerateRequest(BaseModel):
    title: Optional[str]
    script: str
    voice_id: Optional[str] = None  # 默认使用全局配置
    speed: Optional[float] = 1.0

class GenerateResponse(BaseModel):
    video_url: str        # 后端静态可访问 URL
    subtitle_url: str     # SRT 文件 URL
4. 核心流程与各 Agent 逻辑
4.1 Orchestrator：主流程（后端入口）
函数签名建议：

python
复制代码
async def generate_video_pipeline(req: GenerateRequest) -> GenerateResponse:
    ...
步骤：

调用 llm_segmenter：

输入：script 原始文案。

输出：List[Scene]。

并发调用 tts_service 和 image_service：

对于 scenes 列表中的每个元素，开启一个异步任务：

并发调用：

tts_service.generate_audio(scene.cap)

image_service.generate_image(scene.desc_prompt)

收集结果组装为 SceneAsset。

使用信号量控制最大并发数（如 8）。

构建 SceneClip 时间线（timeline_service）：

从 start_ms = 0 开始，按顺序给每个分镜分配：

clip.start_ms = current_ms

clip.end_ms = current_ms + asset.duration_ms

current_ms = clip.end_ms

返回 List[SceneClip] 和总时长 total_duration_ms.

生成字幕碎片（subtitle_service）：

输入：scenes 中每个 cap，以及对应的 SceneClip 时长。

输出：List[SubtitleChunk]，已转换为全局时间。

约束：每条 SubtitleChunk.text 长度 ≤ 10 个汉字。

详见 4.4。

为每个分镜生成动画配置（animation_service）：

对每个 SceneClip 根据索引和时长生成 AnimationConfig。

调用 video_renderer 渲染视频：

输入：

所有 SceneAsset 的图片文件路径

所有 SceneClip 时间信息

所有 AnimationConfig

合并后的旁白音频文件（见 4.5）

输出：

video_path：mp4 文件路径

生成字幕文件（subtitle_service）：

输入：List[SubtitleChunk]

输出：subtitles.srt 文件路径。

返回给前端：

将 video_path 和 subtitles_path 映射为静态 URL。

返回 GenerateResponse。

4.2 llm_segmenter：文案拆分与提示词生成
核心函数：

python
复制代码
async def segment_script(script: str) -> List[Scene]:
    ...
逻辑：

构造 messages：

system: 项目文档中给出的完整 system prompt（哆啦A梦风格、角色逻辑、输出格式约束）。

user: 用户原始文案 script。

调用 LLM API：

POST $LLM_BASE_URL/chat/completions

显式要求 response_format = { "type": "json_object" }（如果提供）。

解析 choices[0].message.content：

解析为 JSON 对象，检查根键为 "scenes"，值为数组。

对每个元素提取 cap 和 desc_promopt，映射为 Scene。

若字段缺失或类型错误，抛出异常。

4.3 image_service：生图
核心函数：

python
复制代码
async def generate_image(desc_prompt: str) -> str:
    ...
逻辑：

发送创建任务请求：

POST https://api.wuyinkeji.com/api/img/nanoBanana-pro

headers: 授权 + Content-Type

body：

prompt: desc_prompt

aspectRatio: "9:16"

检查返回 code == 200 且存在 data.id，取出 task_id。

轮询：

GET https://api.wuyinkeji.com/api/img/drawDetail?id={task_id}

间隔：2–3 秒

条件：

status == 2：成功，返回 data.image_url

status == 3：失败，抛出异常并含 fail_reason

超时：例如 60 秒，超过则抛出超时异常。

返回 image_url。

4.4 subtitle_service：字幕拆分与时间线
目标：在每个分镜内，将 cap 拆分成多行，单行 ≤ 10 个汉字，并根据字数分配该分镜的总时长，最终输出全局时间线。

主要函数：

python
复制代码
def split_caption_to_chunks(text: str, max_len: int = 10) -> List[str]:
    ...

def build_subtitles(scenes: List[Scene], clips: List[SceneClip]) -> List[SubtitleChunk]:
    ...
4.4.1 文本拆分规则
清洗文本：

去掉重复空格、多余符号（可保留句号、问号、感叹号等正常标点）。

按优先级分隔符切片：

["。", "！", "？", "，", ",", "：", ":", "；", ";"]

对每一片段再做长度检查：

若长度 ≤ max_len，直接使用。

若长度 > max_len，则在不破坏中文字符的前提下，每 max_len 个汉字强制切分。

最终保证每个字符串长度 ≤ 10。

4.4.2 时长分配
设当前分镜总时长为 D（毫秒），拆分后得到 k 个片段，字数分别为 len_i。

计算总字数 L = sum(len_i)。

对前 k-1 个片段：

dur_i = round(D * len_i / L)

最后一个片段：

dur_last = D - sum(dur_0..dur_k-2)（防止累计误差）。

每个片段的全局时间：

第一段：

start_ms = clip.start_ms

end_ms = start_ms + dur_0

第 i 段：

start_ms = 前一段 end_ms

end_ms = start_ms + dur_i

输出 SubtitleChunk 列表。

4.5 tts_service：生成音频与时长
核心函数：

python
复制代码
async def generate_audio(text: str, voice_id: Optional[str] = None, speed: float = 1.0) -> Tuple[str, int]:
    ...
逻辑：

组装请求体：

使用默认 voice_id（未传则使用配置）。

其它参数使用项目文档中的默认值。

POST https://api.coze.cn/v1/audio/speech：

获取 mp3 音频数据。

将音频写入临时文件（例如 /tmp/audio_{uuid}.mp3）。

使用 ffprobe 或 pydub.AudioSegment 获取时长（秒），转换为毫秒：

duration_ms = round(duration_seconds * 1000)。

返回 (file_path, duration_ms)。

4.6 timeline_service：场景时间线
函数：

python
复制代码
def build_scene_clips(assets: List[SceneAsset]) -> Tuple[List[SceneClip], int]:
    ...
逻辑：

current_ms = 0

按顺序遍历 assets：

start_ms = current_ms

end_ms = current_ms + asset.duration_ms

current_ms = end_ms

构造 SceneClip 列表。

返回 (clips, total_duration_ms=current_ms)。

4.7 animation_service：隐形 → 线稿 → 上色 + 轻微运动
这部分只生成参数，具体渲染由 video_renderer 实现。

函数：

python
复制代码
def build_animation_config(scene_index: int, duration_ms: int) -> AnimationConfig:
    ...
约定：

三阶段时间比：

Phase A：隐形 → 线稿出现：0 ~ 0.25D

Phase B：线稿 → 上色混合：0.25D ~ 0.55D

Phase C：上色 + 轻微镜头运动：0.55D ~ D

缩放策略（根据时长）：

D < 3000ms（短句）：start_scale = 1.1, end_scale = 1.3

3000ms ≤ D ≤ 6000ms：start_scale = 1.05, end_scale = 1.2

D > 6000ms：start_scale = 1.0, end_scale = 1.1

平移方向（按索引循环）：

i % 4 == 0：略向上移动（start_offset_y = 0.02, end_offset_y = -0.03）

i % 4 == 1：略向左（start_offset_x = 0.02, end_offset_x = -0.03）

i % 4 == 2：略向右（反向）

i % 4 == 3：略向下（反向）

偏移量为相对画幅高度/宽度的比例（例如 0.03 表示 3% 高度）。

图像版本：

实现时，video_renderer 需在本地为每张图片生成三种版本：

blank：单色背景。

line_art：通过 OpenCV/ Pillow:

转灰度 → 高斯模糊 → Canny 边缘 → 反色 → 叠加到浅色背景。

color_full：原彩色图（保持 1080×1920）。

渲染时的混合规则：

Phase A：

背景：blank

线稿：透明度 0 → 1

彩色：透明度 0

Phase B：

线稿：透明度 1 → 0.4

彩色：透明度 0 → 1

Phase C：

彩色：透明度 1

线稿：可选保留 0–0.2

应用缩放和平移动画（from start_scale/offset to end_scale/offset）

4.8 video_renderer：视频与音频合成
建议使用 moviepy 封装 ffmpeg，逻辑相对清晰。

关键任务：

下载图片到本地（如果尚未下载）。

为每个 SceneClip 构建一个 ImageClip 或自定义 VideoClip：

分辨率固定为 1080×1920。

时长：duration_ms / 1000 秒。

在 make_frame(t) 函数中，根据当前 t 所处的阶段（A/B/C）读取对应的混合参数（线稿/彩色透明度、缩放、平移），输出帧。

合并所有 clip：

concatenate_videoclips，使用 method="compose"。

旁白音频合并：

将所有 SceneAsset.audio_path 读入，按顺序拼接成一条 AudioFileClip 或通过 pydub 先合成后再加载。

将音频设置为最终视频的 audio。

导出视频：

编码参数：

帧率：fps=30

编码器：libx264

宽高：1080×1920

输出 video.mp4。

4.9 字幕文件导出
生成 SRT 文件：

python
复制代码
def export_srt(subtitles: List[SubtitleChunk], path: str) -> None:
    ...
每一条 SRT 记录格式：

ruby
复制代码
index
HH:MM:SS,mmm --> HH:MM:SS,mmm
文本

时间转换函数：将毫秒转为 HH:MM:SS,mmm。

保证按照 start_ms 排序输出。

5. REST API 设计
5.1 POST /api/generate
请求体：GenerateRequest

响应体：GenerateResponse

行为：

同步方式：调用 generate_video_pipeline，等待生成完成后直接返回 video_url 与 subtitle_url。

若生成时间偏长，可后续扩展为任务队列模式（当前文档可先实现同步方案）。

错误处理：

任何外部 API 调用失败、超时、解析失败时，应返回 4xx/5xx 状态码及错误原因。

前端展示错误信息。

6. 前端规范（极简）
前端为单页静态应用，由后端直接提供 /index.html。

6.1 页面结构
一个文本区域 textarea#script-input 用于输入原始文案。

一个文本输入 input#title-input（可选）。

一个按钮 button#generate-btn。

一个视频播放器 video#result-video（隐藏，直到有结果）。

一个字幕下载链接 a#subtitle-link（隐藏，直到有结果）。

一个状态文本区域 div#status.

6.2 交互逻辑
用户输入文案（必填）和可选标题。

点击「生成」按钮：

若文案为空，则提示错误。

禁用按钮，状态显示「生成中…」。

使用 fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, script }) })。

当响应成功：

从 JSON 中拿到 video_url, subtitle_url。

设置 video.src = video_url，显示播放器。

设置字幕下载链接 href = subtitle_url，显示链接。

状态显示「生成完成」。

重新启用按钮。

当响应失败：

状态显示错误信息。

重新启用按钮。

页面样式保持极简，只需 basic CSS 做一点间距。

7. 并发与性能要求
分镜级并发：

对每个 Scene 并发调用 TTS 与生图。

使用 asyncio.Semaphore(MAX_CONCURRENT_SCENES) 控制并发数，默认值建议 8。

单分镜内部并发：

TTS 与生图可以在同一个任务内使用 asyncio.gather 并行。

轮询生图：

轮询间隔 2–3 秒，最大次数配置化。

清理策略：

视频与音频、图片文件可定期清理（如按创建时间删除 24 小时前的文件）。

8. 日志与错误处理
对每一次外部请求记录：

请求 URL、耗时、返回状态码、失败原因。

对 LLM 返回的原始文本在调试模式下保存，以便排查 JSON 解析失败问题。

出错时，尽量保留中间文件以诊断问题，但不阻塞新请求。

