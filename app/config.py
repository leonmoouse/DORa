import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR.parent / "generated"
STATIC_DIR = BASE_DIR.parent / "static"

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3-pro")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://new.12ai.org/v1")

TTS_API_KEY = os.getenv("TTS_API_KEY")
TTS_DEFAULT_VOICE_ID = os.getenv("TTS_DEFAULT_VOICE_ID", "7540911707150008374")

IMG_API_KEY = os.getenv("IMG_API_KEY")
IMG_POLL_INTERVAL = float(os.getenv("IMG_POLL_INTERVAL", "2.5"))
IMG_POLL_TIMEOUT = float(os.getenv("IMG_POLL_TIMEOUT", "90"))

MAX_CONCURRENT_SCENES = int(os.getenv("MAX_CONCURRENT_SCENES", "8"))

VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))

DEBUG_SAVE_LLM_RAW = os.getenv("DEBUG_SAVE_LLM_RAW", "false").lower() == "true"

GENERATED_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
