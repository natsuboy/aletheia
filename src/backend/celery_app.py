from celery import Celery
from src.backend.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aletheia",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "src.ingestion.tasks.*": {"queue": "ingestion"},
        "src.wiki.tasks.*": {"queue": "wiki"},
    },
)

# 自动发现任务
celery_app.autodiscover_tasks(["src.ingestion", "src.wiki"])
