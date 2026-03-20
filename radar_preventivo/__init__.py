from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from .auth.service import AuthService
from .config import AppSettings
from .repositories.dataset_repository import CsvDatasetRepository
from .repositories.user_repository import JsonUserRepository
from .routes.auth import auth_bp
from .routes.health import health_bp
from .routes.predictions import predictions_bp
from .services.prediction_service import PredictionService


def create_app(overrides: dict | None = None) -> Flask:
    settings = AppSettings.from_env().with_overrides(overrides or {})

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["JSON_SORT_KEYS"] = False
    app.config["SETTINGS"] = settings

    CORS(
        app,
        resources={r"/*": {"origins": settings.cors_origins}},
        allow_headers=["Authorization", "Content-Type"],
        methods=["GET", "POST", "OPTIONS"],
    )

    app.extensions["prediction_service"] = PredictionService(
        settings=settings,
        dataset_repository=CsvDatasetRepository(settings),
    )
    app.extensions["auth_service"] = AuthService(
        settings=settings,
        user_repository=JsonUserRepository(settings),
    )

    prediction_service: PredictionService = app.extensions["prediction_service"]
    prediction_service.initialize()

    register_blueprints(app)
    register_root_routes(app)
    return app


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(predictions_bp)


def register_root_routes(app: Flask) -> None:
    @app.get("/")
    def root():
        settings: AppSettings = app.config["SETTINGS"]
        return jsonify(
            {
                "application": "radar-preventivo",
                "status": "online",
                "predictor_mode": settings.predictor_mode,
                "auth_enabled": True,
                "public_endpoints": ["/", "/health", "/auth/login"],
                "protected_endpoints": ["/auth/me", "/auth/users", "/predict"],
            }
        )
