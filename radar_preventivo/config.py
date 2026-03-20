from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    base_dir: Path
    data_file: Path
    dismissed_drivers_file: Path
    auth_users_file: Path
    forecast_days: int
    recent_history_days: int
    predictor_mode: str
    secret_key: str
    token_ttl_seconds: int
    allow_demo_users: bool
    cors_origins: tuple[str, ...]
    bootstrap_prediction_date: str | None

    @classmethod
    def from_env(cls) -> "AppSettings":
        base_dir = Path(__file__).resolve().parent.parent
        cors_origins_raw = os.getenv("APP_CORS_ORIGINS", "*")
        cors_origins = tuple(
            origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()
        ) or ("*",)

        return cls(
            base_dir=base_dir,
            data_file=Path(os.getenv("APP_DATA_FILE", base_dir / "basedadosseguranca.csv")),
            dismissed_drivers_file=Path(
                os.getenv(
                    "APP_DISMISSED_DRIVERS_FILE",
                    base_dir / "motoristas_desligados.csv",
                )
            ),
            auth_users_file=Path(os.getenv("APP_AUTH_USERS_FILE", base_dir / "auth_users.json")),
            forecast_days=int(os.getenv("FORECAST_DAYS", "45")),
            recent_history_days=int(os.getenv("RECENT_HISTORY_DAYS", "14")),
            predictor_mode=os.getenv("APP_PREDICTOR_MODE", "neuralprophet").strip().lower(),
            secret_key=os.getenv("APP_SECRET_KEY", secrets.token_urlsafe(32)),
            token_ttl_seconds=int(os.getenv("APP_TOKEN_TTL_SECONDS", str(8 * 60 * 60))),
            allow_demo_users=os.getenv("APP_ALLOW_DEMO_USERS", "false").lower() == "true",
            cors_origins=cors_origins,
            bootstrap_prediction_date=os.getenv("APP_BOOTSTRAP_PREDICTION_DATE"),
        )

    def with_overrides(self, overrides: dict) -> "AppSettings":
        valid_overrides = {key: value for key, value in overrides.items() if hasattr(self, key)}
        return replace(self, **valid_overrides)
