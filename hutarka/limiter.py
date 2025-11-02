from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging

def create_limiter(app=None):
    redis_url = os.getenv("REDIS_URL")

    if redis_url:
        if redis_url.startswith(("redis://", "rediss://")):
            scheme = redis_url.split("://")[0]
            rest = redis_url.split("://")[1]
            storage_uri = f"redis+{scheme}://{rest}"
        else:
            storage_uri = redis_url
        logging.info(f"✅ Using Redis for rate limiting: {storage_uri}")
    else:
        storage_uri = "memory://"
        logging.warning("⚠️ Redis URL not set — using in-memory rate limiter.")

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],
        storage_uri=storage_uri,
    )

    if app:
        limiter.init_app(app)

    return limiter


# создаём экземпляр без инициализации (app добавится в __init__.py)
limiter = create_limiter()
