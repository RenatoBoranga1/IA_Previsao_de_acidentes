from __future__ import annotations

from functools import wraps

from flask import current_app, g, jsonify, request

from radar_preventivo.auth.service import AuthService


def auth_required(*allowed_roles: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            auth_service: AuthService = current_app.extensions["auth_service"]
            token = _extract_bearer_token(request.headers.get("Authorization"))
            user = auth_service.verify_token(token)

            if not user:
                return jsonify({"error": "Autenticacao obrigatoria para este recurso."}), 401

            if allowed_roles and user.role not in allowed_roles:
                return jsonify({"error": "Seu perfil nao possui permissao para este recurso."}), 403

            g.current_user = user
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None

    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1].strip()
