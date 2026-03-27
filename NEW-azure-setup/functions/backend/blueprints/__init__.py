"""
Blueprint registration for the multi-page MuleSoft-to-SpringBoot migrator.
"""


def register_blueprints(app):
    """Import and register all application blueprints."""
    from .main import main_bp
    from .migration import migration_bp
    from .swagger import swagger_bp
    from .github_bp import github_bp
    from .build import build_bp
    from .settings_bp import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(migration_bp)
    app.register_blueprint(swagger_bp)
    app.register_blueprint(github_bp)
    app.register_blueprint(build_bp)
    app.register_blueprint(settings_bp)
