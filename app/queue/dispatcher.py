from rq import Queue
from redis import Redis

from app.core.config import get_settings


def get_queue() -> Queue | None:
    settings = get_settings()
    if not settings.queue_enabled or not settings.redis_url:
        return None
    redis_conn = Redis.from_url(settings.redis_url)
    return Queue(settings.queue_name, connection=redis_conn)


def enqueue_webhook_message(message_data: dict, event_id: int | None) -> str | None:
    queue = get_queue()
    if not queue:
        return None
    job = queue.enqueue("app.queue.tasks.process_webhook_message", message_data, event_id, job_timeout=120)
    return job.id

