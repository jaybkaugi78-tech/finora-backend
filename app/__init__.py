
import os
from flask import Flask
from dotenv import load_dotenv
from .config import Config
from .extensions import cors, db, jwt, migrate

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": [os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")]}},
        supports_credentials=True,
    )

    from . import models  # noqa
    from .routes.health import health_bp
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.accounts import accounts_bp
    from .routes.categories import categories_bp
    from .routes.transactions import transactions_bp
    from .routes.budgets import budgets_bp
    from .routes.goals import goals_bp
    from .routes.bills import bills_bp
    from .routes.analytics import analytics_bp
    from .routes.notifications import notifications_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(accounts_bp, url_prefix="/api/accounts")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(transactions_bp, url_prefix="/api/transactions")
    app.register_blueprint(budgets_bp, url_prefix="/api/budgets")
    app.register_blueprint(goals_bp, url_prefix="/api/goals")
    app.register_blueprint(bills_bp, url_prefix="/api/bills")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    return app
