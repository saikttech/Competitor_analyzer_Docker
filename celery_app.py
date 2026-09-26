from celery import Celery
from config import REDIS_URL

celery_app = Celery(
    "competitor_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=360,
    worker_max_memory_per_child=512000,
    worker_max_tasks_per_child=10,
)