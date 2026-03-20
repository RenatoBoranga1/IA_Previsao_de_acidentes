from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from radar_preventivo.config import AppSettings
from radar_preventivo.models import ROLE_PROFILES, UserRecord
from radar_preventivo.repositories.user_repository import JsonUserRepository


class AuthService:
    def __init__(self, settings: AppSettings, user_repository: JsonUserRepository) -> None:
        self.settings = settings
        self.user_repository = user_repository
        self.serializer = URLSafeTimedSerializer(settings.secret_key, salt="radar-preventivo-auth")

    def authenticate(self, email: str, password: str) -> dict | None:
        user = self.user_repository.get_by_email(email)
        if not user or not self.user_repository.verify(user, password):
            return None

        token = self._issue_token(user)
        return self.build_session_payload(user=user, token=token)

    def _issue_token(self, user: UserRecord) -> str:
        return self.serializer.dumps(
            {
                "sub": user.id,
                "email": user.email,
                "role": user.role,
            }
        )

    def verify_token(self, token: str | None) -> UserRecord | None:
        if not token:
            return None

        try:
            payload = self.serializer.loads(token, max_age=self.settings.token_ttl_seconds)
        except (BadSignature, SignatureExpired):
            return None

        return self.user_repository.get_by_email(payload.get("email"))

    def build_session_payload(self, user: UserRecord, token: str) -> dict:
        role_profile = ROLE_PROFILES.get(user.role)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.token_ttl_seconds,
            "user": {
                **user.to_safe_dict(),
                "role_description": role_profile.description if role_profile else "",
            },
        }

    def list_users(self) -> list[dict]:
        return [user.to_safe_dict() for user in self.user_repository.list_users()]
