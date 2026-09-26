import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from celery.result import AsyncResult
from tasks import analyze_competitors_task
from models import init_db
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Competitor Analyzer RAG API", version="4.0")

# 🆕 API Key аутентификация
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# В production хранить в БД или .env
VALID_API_KEYS = {"sk-test-123", "sk-prod-456"}

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.on_event("startup")
async def startup():
    init_db()
    # 🆕 Инициализация Rate Limiter
    redis_connection = redis.from_url("redis://redis:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_connection)

class AnalysisRequest(BaseModel):
    niche: str
    geo: str
    query: str
    clear_db: bool = False

# 🆕 Добавляем зависимости
@app.post("/analyze", dependencies=[Depends(verify_api_key), Depends(RateLimiter(times=10, seconds=60))])
async def start_analysis(req: AnalysisRequest):
    task = analyze_competitors_task.apply_async(args=[req.niche, req.geo, req.query, req.clear_db])
    logger.info(f"Task {task.id} sent to queue")
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/analyze/{task_id}", dependencies=[Depends(verify_api_key)])
async def get_analysis_status(task_id: str):
    task = AsyncResult(task_id)
    response = {"task_id": task_id, "status": task.status, "meta": None, "result": None, "error": None}

    if task.status == "PENDING":
        response["meta"] = {"status": "Ожидание в очереди..."}
    elif task.status == "STARTED":
        response["meta"] = task.info
    elif task.status == "SUCCESS":
        response["result"] = task.result
    elif task.status == "FAILURE":
        response["error"] = str(task.result)

    return response

@app.get("/health")
async def health():
    return {"status": "ok"}