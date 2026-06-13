from datetime import datetime
from flask import Flask, render_template, request
from .config import Config
from .services.db import init_global_db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object(Config)

    init_global_db(app.config)

    @app.context_processor
    def inject_globals():
        return {
            "now": datetime.utcnow(),
            "config": app.config,
            "request": request,
        }

    @app.errorhandler(404)
    def not_found(e):
        return render_template("public/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("public/404.html"), 500

    # Register blueprints
    from .routes.public import public_bp
    from .routes.auth import auth_bp
    from .routes.reseller import reseller_bp
    from .routes.admin import admin_bp
    from .routes.webhook import webhook_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(reseller_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(webhook_bp)

    return app
