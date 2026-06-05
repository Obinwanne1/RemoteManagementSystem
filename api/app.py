import os
import time
import uuid
from flask import Flask, request, g
from dotenv import load_dotenv

from config import config_map
from extensions import db, migrate, jwt, cors, limiter

load_dotenv()


def _validate_env():
    """Abort startup if critical env vars are missing or insecure."""
    errors = []
    secret_key = os.getenv("SECRET_KEY", "")
    jwt_key = os.getenv("JWT_SECRET_KEY", "")
    sa_password = os.getenv("SUPERADMIN_PASSWORD", "")
    org_token = os.getenv("ORG_REGISTRATION_TOKEN", "")

    if len(secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    if len(jwt_key) < 32:
        errors.append("JWT_SECRET_KEY must be at least 32 characters")
    if not sa_password:
        errors.append("SUPERADMIN_PASSWORD must be set")
    if len(sa_password) < 10:
        errors.append("SUPERADMIN_PASSWORD must be at least 10 characters")
    if not org_token or org_token in ("change-this-to-a-secure-random-token", ""):
        errors.append("ORG_REGISTRATION_TOKEN must be set to a unique random value")

    if errors:
        raise RuntimeError("Environment configuration errors:\n  - " + "\n  - ".join(errors))


def create_app(config_name=None):
    _validate_env()

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
    cors.init_app(app, resources={r"/api/*": {"origins": [o.strip() for o in allowed_origins]}})
    limiter.init_app(app)

    # Warn when running in insecure development mode
    if config_name != "production":
        app.logger.warning(
            "Running in '%s' mode — JWT cookies are NOT secure. "
            "Set FLASK_ENV=production for HTTPS deployments.",
            config_name,
        )

    # Import models so Alembic detects them
    with app.app_context():
        from models import user, device, customer, alert, ticket, patch, script, automation, report, billing, audit  # noqa
        try:
            from utils.builtin_scripts import ensure_builtin_scripts
            ensure_builtin_scripts()
        except Exception:
            app.logger.warning("Could not sync built-in scripts (DB may not be ready yet)")
        try:
            from utils.superadmin import ensure_superadmin
            ensure_superadmin()
        except Exception:
            app.logger.warning("Could not ensure superadmin (DB may not be ready yet)")

    # Register blueprints
    from routes.auth import auth_bp
    from routes.agents import agents_bp
    from routes.customers import customers_bp
    from routes.devices import devices_bp
    from routes.alerts import alerts_bp
    from routes.tickets import tickets_bp
    from routes.patches import patches_bp
    from routes.scripts import scripts_bp
    from routes.automation import automation_bp
    from routes.reports import reports_bp
    from routes.billing import billing_bp
    from routes.network import network_bp
    from routes.dashboard import dashboard_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(agents_bp, url_prefix="/api/agents")
    app.register_blueprint(customers_bp, url_prefix="/api/customers")
    app.register_blueprint(devices_bp, url_prefix="/api/devices")
    app.register_blueprint(alerts_bp, url_prefix="/api")
    app.register_blueprint(tickets_bp, url_prefix="/api/tickets")
    app.register_blueprint(patches_bp, url_prefix="/api/patches")
    app.register_blueprint(scripts_bp, url_prefix="/api/scripts")
    app.register_blueprint(automation_bp, url_prefix="/api/automation")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(billing_bp, url_prefix="/api/billing")
    app.register_blueprint(network_bp, url_prefix="/api/network")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.route("/api/health")
    def health():
        from sqlalchemy import text
        import redis as redis_lib
        checks: dict = {"version": "1.0.0", "db": False, "redis": False}
        try:
            db.session.execute(text("SELECT 1"))
            checks["db"] = True
        except Exception:
            pass
        try:
            r = redis_lib.from_url(app.config.get("REDIS_URL", "redis://localhost:6379/0"))
            r.ping()
            checks["redis"] = True
        except Exception:
            pass
        checks["status"] = "ok" if checks["db"] and checks["redis"] else "degraded"
        from flask import jsonify as _j
        return _j(checks), (200 if checks["status"] == "ok" else 503)

    # Request timing + correlation ID
    @app.before_request
    def _start_timer():
        g._start_time = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def _log_request(response):
        duration_ms = (time.monotonic() - getattr(g, "_start_time", time.monotonic())) * 1000
        rid = getattr(g, "request_id", "-")
        app.logger.info(
            "[%s] %s %s %s %.1fms",
            rid, request.method, request.path, response.status_code, duration_ms,
        )
        response.headers["X-Request-ID"] = rid
        return response

    _register_error_handlers(app)
    return app


def _register_error_handlers(app):
    from sqlalchemy.exc import IntegrityError, OperationalError
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_exceeded(e):
        return {"error": "Too many requests. Please slow down."}, 429

    @app.errorhandler(429)
    def too_many_requests(e):
        return {"error": "Too many requests. Please slow down."}, 429

    @app.errorhandler(400)
    def bad_request(e):
        app.logger.warning("Bad request: %s", e)
        return {"error": "Bad request"}, 400

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {"error": "Method not allowed"}, 405

    @app.errorhandler(422)
    def unprocessable(e):
        app.logger.warning("Validation error: %s", e)
        return {"error": "Validation error"}, 422

    @app.errorhandler(IntegrityError)
    def db_integrity(e):
        db.session.rollback()
        app.logger.warning("IntegrityError: %s", e.orig)
        return {"error": "Conflict: duplicate or constraint violation"}, 409

    @app.errorhandler(OperationalError)
    def db_operational(e):
        db.session.rollback()
        app.logger.error("DB OperationalError: %s", e)
        return {"error": "Database unavailable"}, 503

    @app.errorhandler(Exception)
    def unhandled(e):
        app.logger.exception("Unhandled exception")
        return {"error": "Internal server error"}, 500


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
