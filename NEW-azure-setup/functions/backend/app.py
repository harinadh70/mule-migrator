"""
MuleSoft to Spring Boot Migration Platform

Multi-page Flask application with:
  - Migration tool with inline editing
  - Swagger/OpenAPI generation
  - GitHub integration
  - JAR/WAR/Docker builds
  - Test execution with streaming output

Production:
  gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""
import os
import logging
from flask import Flask, request, Response
from flask_cors import CORS


def create_app():
    """Application factory."""
    application = Flask(__name__, static_folder="static", template_folder="templates")

    env = os.environ.get("FLASK_ENV", "production")
    application.config.update(
        ENV=env,
        DEBUG=(env == "development"),
        SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(32).hex()),
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )

    allowed_origins = os.environ.get("CORS_ORIGINS", "*")
    CORS(application, origins=allowed_origins.split(","))

    log_level = logging.DEBUG if application.config["DEBUG"] else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Architecture page (protected with Basic Auth)
    ARCH_USERNAME = os.environ.get("ARCH_USERNAME", "admin-username")
    ARCH_PASSWORD = os.environ.get("ARCH_PASSWORD", "admin-password")

    @application.route("/architecture")
    def architecture():
        auth = request.authorization
        if not (auth and auth.username == ARCH_USERNAME and auth.password == ARCH_PASSWORD):
            resp = Response("Login required to view this page.", 401)
            resp.headers["WWW-Authenticate"] = 'Basic realm="Architecture - Under Review"'
            return resp
        from flask import render_template
        return render_template("architecture.html")

    # Register all blueprints
    from blueprints import register_blueprints
    register_blueprints(application)

    return application


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
