import os
import time
from flask import Flask, request, g
from dotenv import load_dotenv

from config import config_map
from extensions import db, migrate, jwt, cors, limiter

load_dotenv()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    limiter.init_app(app)

    # Import models so Alembic detects them
    with app.app_context():
        from models import user, device, customer, alert, ticket, patch, script, automation, report, billing, audit  # noqa

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

    @app.route("/api/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    # Request timing
    @app.before_request
    def _start_timer():
        g._start_time = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.monotonic() - getattr(g, "_start_time", time.monotonic())) * 1000
        app.logger.info("%s %s %s %.1fms", request.method, request.path, response.status_code, duration_ms)
        return response

    _register_error_handlers(app)
    return app


def _register_error_handlers(app):
    from sqlalchemy.exc import IntegrityError, OperationalError

    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "Bad request", "detail": str(e)}, 400

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {"error": "Method not allowed"}, 405

    @app.errorhandler(422)
    def unprocessable(e):
        return {"error": "Validation error", "detail": str(e)}, 422

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
