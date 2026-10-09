from src.extensions import init_extensions
from src.api.errors import register_error_handlers
from src.api.routes.auth import auth_bp
from src.api.routes.profile import profile_bp
from src.api.routes.offers import offers_bp
from src.api.routes.whatsapp import whatsapp_bp
from src.api.routes.webhooks import webhooks_bp
from src.api.routes.schedules import schedules_bp
from src.api.routes.dispatches import dispatches_bp
from src.api.routes.health import health_bp

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init_extensions(app)
    register_error_handlers(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(offers_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(dispatches_bp)
    app.register_blueprint(health_bp)

    return app