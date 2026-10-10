import os
from datetime import timedelta
from flask import Flask, jsonify
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from .extensions import db, migrate, jwt, cors, limiter

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///finora_dev.sqlite3'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', ''),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=2),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=14),
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config['TESTING'] and len(app.config['JWT_SECRET_KEY']) < 32:
        raise RuntimeError('Set JWT_SECRET_KEY in .env (at least 32 characters).')
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    origins=[s.strip() for s in os.getenv('FRONTEND_ORIGINS','http://localhost:5173').split(',') if s.strip()]
    cors.init_app(app, resources={r'/api/*': {'origins': origins}})
    from . import models  # noqa: F401
    from .routes import blueprints
    for bp in blueprints:
        app.register_blueprint(bp, url_prefix='/api')
    @app.get('/api/health')
    def health():
        return jsonify(status='ok')
    @app.errorhandler(IntegrityError)
    def integrity_error(error):
        db.session.rollback()
        return jsonify(error='Conflicting or invalid database record.'), 409
    @app.errorhandler(404)
    def missing(error):
        return jsonify(error='Endpoint not found.'), 404
    @app.errorhandler(429)
    def limited(error):
        return jsonify(error='Too many requests. Please try later.'), 429
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return jsonify(error='Internal server error.'), 500
    return app
