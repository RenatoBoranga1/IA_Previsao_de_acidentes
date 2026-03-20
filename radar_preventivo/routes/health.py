from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from radar_preventivo.services import PredictionService

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def healthcheck():
    prediction_service: PredictionService = current_app.extensions["prediction_service"]
    return jsonify(prediction_service.health_payload())
