from redis import Redis
from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required to run queue worker")
    redis_conn = Redis.from_url(settings.redis_url)
    worker = Worker([settings.queue_name], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()

