"""
Celery application configuration.

Sets up the Celery instance with Redis broker, task routes,
beat schedule for periodic jobs, and serialization settings.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hirepilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# ---------- Serialization ----------
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,  # 1 hour
)

# ---------- Task Routes ----------
celery_app.conf.task_routes = {
    "app.tasks.scraping.*": {"queue": "scraping"},
    "app.tasks.ai.*": {"queue": "ai"},
    "app.tasks.automation.*": {"queue": "automation"},
    "app.tasks.outreach.*": {"queue": "outreach"},
}

# ---------- Rate Limits ----------
celery_app.conf.task_annotations = {
    "app.tasks.automation.auto_apply_job": {"rate_limit": "5/h"},
    "app.tasks.outreach.send_connection_request": {"rate_limit": "10/h"},
    "app.tasks.outreach.send_followup_message": {"rate_limit": "8/h"},
    "app.tasks.scraping.scrape_jobs": {"rate_limit": "2/m"},
}

# ---------- Beat Schedule (periodic tasks) ----------
celery_app.conf.beat_schedule = {
    "scrape-jobs-every-6h": {
        "task": "app.tasks.scraping.scrape_jobs_periodic",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": (),
    },
    "cleanup-stale-applications-daily": {
        "task": "app.tasks.automation.cleanup_stale_applications",
        "schedule": crontab(minute=0, hour=3),  # 3 AM UTC
        "args": (),
    },
    "send-scheduled-followups": {
        "task": "app.tasks.outreach.send_scheduled_followups",
        "schedule": crontab(minute=0, hour="9,14"),  # 9 AM, 2 PM UTC
        "args": (),
    },
}

# ---------- Auto-discover tasks ----------
celery_app.autodiscover_tasks(["app.tasks"])
