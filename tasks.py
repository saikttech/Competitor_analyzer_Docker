import logging
from celery_app import celery_app
from pipeline import run_pipeline

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="analyze_competitors_task", max_retries=2)
def analyze_competitors_task(self, niche: str, geo: str, query: str, clear_db: bool):
    try:
        self.update_state(state='STARTED', meta={'status': 'Парсинг и очистка данных...'})
        result_data = run_pipeline(niche, geo, query, clear_db)
        
        self.update_state(state='STARTED', meta={'status': 'Генерация отчета LLM...'})
        
        return {"status": "success", "data": result_data}
    except Exception as exc:
        logger.exception(f"Ошибка в задаче: {exc}")
        if "rate limit" in str(exc).lower() or "timeout" in str(exc).lower():
            raise self.retry(exc=exc, countdown=60)
        return {"status": "failed", "error": str(exc)}