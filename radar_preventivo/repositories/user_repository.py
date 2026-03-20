from __future__ import annotations

import json
from functools import cached_property

from radar_preventivo.auth.security import hash_password, verify_password
from radar_preventivo.config import AppSettings
from radar_preventivo.models import ROLE_PROFILES, UserRecord


class JsonUserRepository:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @cached_property
    def _users(self) -> list[UserRecord]:
        if self.settings.auth_users_file.exists():
            payload = json.loads(self.settings.auth_users_file.read_text(encoding="utf-8"))
            return [self._to_user(record) for record in payload]

        if self.settings.allow_demo_users:
            return self._demo_users()

        return []

    def list_users(self) -> list[UserRecord]:
        return [user for user in self._users if user.active]

    def get_by_email(self, email: str | None) -> UserRecord | None:
        normalized_email = (email or "").strip().lower()
        for user in self.list_users():
            if user.email.lower() == normalized_email:
                return user
        return None

    @staticmethod
    def verify(user: UserRecord, password: str) -> bool:
        return verify_password(password, user.password_hash)

    def _to_user(self, record: dict) -> UserRecord:
        role = record["role"].strip().lower()
        if role not in ROLE_PROFILES:
            raise ValueError(f"Perfil de acesso desconhecido: {role}")

        return UserRecord(
            id=str(record["id"]),
            name=record["name"].strip(),
            email=record["email"].strip().lower(),
            role=role,
            password_hash=record["password_hash"].strip(),
            active=bool(record.get("active", True)),
        )

    def _demo_users(self) -> list[UserRecord]:
        seed_users = [
            {
                "id": "admin-demo",
                "name": "Admin Demo",
                "email": "admin@radar.local",
                "role": "admin",
                "password": "Admin123!",
            },
            {
                "id": "gestor-demo",
                "name": "Gestor Demo",
                "email": "gestor@radar.local",
                "role": "gestor",
                "password": "Gestor123!",
            },
            {
                "id": "analista-demo",
                "name": "Analista Demo",
                "email": "analista@radar.local",
                "role": "analista",
                "password": "Analista123!",
            },
        ]

        return [
            UserRecord(
                id=record["id"],
                name=record["name"],
                email=record["email"],
                role=record["role"],
                password_hash=hash_password(record["password"]),
            )
            for record in seed_users
        ]
