from celery import Celery

from app.config import get_settings

settings = get_settings()

celery = Celery("costadvisor")
celery.config_from_object("celeryconfig")
celery.autodiscover_tasks(["app.tasks"])

# Alias used by task modules
celery_app = celery
