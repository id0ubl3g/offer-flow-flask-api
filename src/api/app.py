from src.extensions import init_extensions
from src.api.errors import register_error_handlers
from src.api.routes.auth import auth_bp
from src.api.routes.profile import profile_bp
from src.api.routes.offers import offers_bp

from flask import Flask

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

    init_extensions(app)
    register_error_handlers(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(offers_bp)

    return app