from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from radar_preventivo.auth import auth_required
from radar_preventivo.services import PredictionService

predictions_bp = Blueprint("predictions", __name__)


@predictions_bp.get("/predict")
@auth_required("admin", "gestor", "analista")
def get_prediction():
    prediction_service: PredictionService = current_app.extensions["prediction_service"]

    try:
        return jsonify(prediction_service.predict_for_date(request.args.get("date")))
    except ValueError as exc:
        return jsonify({"error": str(exc), "requested_date": request.args.get("date")}), 400
    except LookupError as exc:
        payload = exc.args[0] if exc.args else {"error": "Data fora do intervalo de previsao."}
        return jsonify(payload), 404
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Erro interno ao gerar previsao: {exc}"}), 500
