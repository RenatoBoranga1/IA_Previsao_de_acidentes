from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from radar_preventivo.auth import auth_required
from radar_preventivo.auth.service import AuthService


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Informe email e senha para autenticar."}), 400

    auth_service: AuthService = current_app.extensions["auth_service"]
    session_payload = auth_service.authenticate(email=email, password=password)
    if not session_payload:
        return jsonify({"error": "Credenciais invalidas ou usuario sem acesso."}), 401

    return jsonify(session_payload)


@auth_bp.get("/me")
@auth_required("admin", "gestor", "analista")
def me():
    auth_service: AuthService = current_app.extensions["auth_service"]
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    return jsonify(auth_service.build_session_payload(g.current_user, token))


@auth_bp.get("/users")
@auth_required("admin")
def list_users():
    auth_service: AuthService = current_app.extensions["auth_service"]
    return jsonify({"users": auth_service.list_users()})


@auth_bp.post("/logout")
@auth_required("admin", "gestor", "analista")
def logout():
    return jsonify({"message": "Logout concluido no cliente. Remova o token armazenado."})
