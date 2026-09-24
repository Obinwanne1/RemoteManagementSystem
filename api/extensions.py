from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
    # Every other Redis-backed component in this app (utils/cache.py, utils/events.py,
    # utils/rate_limit.py) fails OPEN when Redis is unreachable. Without this,
    # Flask-Limiter's RATELIMIT_DEFAULT (applied to every request) raises
    # redis.exceptions.ConnectionError on its own before a view ever runs, which the
    # generic Exception handler turns into a 500 for 100% of traffic — a Redis blip
    # taking down the whole API, the opposite of every other component's behavior.
    in_memory_fallback_enabled=True,
    in_memory_fallback=["200 per minute"],
)
compress = Compress()
