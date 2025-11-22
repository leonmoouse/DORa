from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config
from app.models import GenerateRequest, GenerateResponse
from app.services.orchestrator import generate_video_pipeline

app = FastAPI(title="竖版漫画解说视频生成系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    if not req.script.strip():
        raise HTTPException(status_code=400, detail="script 不能为空")
    try:
        return await generate_video_pipeline(req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/")
async def root():
    return {"message": "请访问 /static/index.html 体验前端页面"}


app.mount("/generated", StaticFiles(directory=config.GENERATED_DIR), name="generated")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
