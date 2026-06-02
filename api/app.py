import os
from flask import Flask
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
