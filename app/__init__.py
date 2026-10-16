
import os
from datetime import timedelta

from flask import Flask, jsonify
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

from .extensions import (
    db,
    migrate,
    jwt,
    cors,
    limiter,
)


def create_app(test_config=None):
    load_dotenv()

    app = Flask(__name__)

    app_env = os.getenv(
        "APP_ENV",
        "development",
    ).strip().lower()

    is_production = app_env == "production"

    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite:///finora_dev.sqlite3",
    )

    jwt_secret = os.getenv(
        "JWT_SECRET_KEY",
        "",
    )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 1800,
        },

        JWT_SECRET_KEY=jwt_secret,

        JWT_ACCESS_TOKEN_EXPIRES=timedelta(
            hours=2
        ),

        JWT_REFRESH_TOKEN_EXPIRES=timedelta(
            days=14
        ),

        JWT_BLOCKLIST_ENABLED=True,

        JSON_SORT_KEYS=False,

        MAX_CONTENT_LENGTH=10 * 1024 * 1024,

        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=is_production,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config:
        app.config.update(test_config)

    if not app.config.get("TESTING"):
        if len(app.config["JWT_SECRET_KEY"]) < 32:
            raise RuntimeError(
                "Set JWT_SECRET_KEY in .env "
                "(at least 32 characters)."
            )

    if is_production:
        if not database_url.startswith(
            ("postgresql://", "postgresql+")
        ):
            raise RuntimeError(
                "Production requires PostgreSQL."
            )

        if os.getenv(
            "RATELIMIT_STORAGE_URI",
            "memory://",
        ).startswith("memory://"):
            raise RuntimeError(
                "Production requires persistent "
                "rate-limit storage such as Redis."
            )

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # Configure CORS
    origins = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]

    if is_production:
        if not origins or any(
            not origin.startswith("https://")
            for origin in origins
        ):
            raise RuntimeError(
                "Production FRONTEND_ORIGINS "
                "must use HTTPS."
            )

    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": origins,
            }
        },
    )

    # Import models so migrations can discover them.
    from . import models  # noqa: F401
    from .models import RevokedToken

    # Reject revoked access and refresh tokens.
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(
        jwt_header,
        jwt_payload,
    ):
        jti = jwt_payload.get("jti")

        if not jti:
            return True

        revoked = (
            db.session.query(RevokedToken.id)
            .filter_by(jti=jti)
            .first()
        )

        return revoked is not None

    # Register API routes
    from .routes import blueprints

    for blueprint in blueprints:
        app.register_blueprint(
            blueprint,
            url_prefix="/api",
        )

    # Health endpoint
    @app.get("/api/health")
    def health():
        return jsonify(
            status="ok",
        )

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        response.headers[
            "Referrer-Policy"
        ] = "strict-origin-when-cross-origin"

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), microphone=(), "
            "geolocation=()"
        )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        if is_production:
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"

        return response

    # Database conflict handler
    @app.errorhandler(IntegrityError)
    def integrity_error(error):
        db.session.rollback()

        return jsonify(
            error=(
                "Conflicting or invalid "
                "database record."
            )
        ), 409

    # Missing endpoint handler
    @app.errorhandler(404)
    def missing(error):
        return jsonify(
            error="Endpoint not found."
        ), 404

    # Rate limit handler
    @app.errorhandler(429)
    def limited(error):
        return jsonify(
            error=(
                "Too many requests. "
                "Please try later."
            )
        ), 429

    # Internal server error handler
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()

        return jsonify(
            error="Internal server error."
        ), 500

    return app
