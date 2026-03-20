from __future__ import annotations

from pathlib import Path

from radar_preventivo import create_app

CSV_FIXTURE = """Data;QUANTIDADE;Motorista;Localidade;Tipo de Evento
01/01/2025;5;Motorista A;Local A;Aceleração
02/01/2025;4;Motorista B;Local A;Fadiga
03/01/2025;6;Motorista A;Local B;Aceleração
04/01/2025;3;Motorista C;Local C;Agressividade
05/01/2025;7;Motorista B;Local A;Fadiga
"""


def build_test_app(tmp_path: Path):
    data_file = tmp_path / "basedadosseguranca.csv"
    data_file.write_text(CSV_FIXTURE, encoding="utf-8")

    dismissed_file = tmp_path / "motoristas_desligados.csv"
    dismissed_file.write_text("Motoristas\n", encoding="utf-8")

    app = create_app(
        {
            "data_file": data_file,
            "dismissed_drivers_file": dismissed_file,
            "predictor_mode": "mock",
            "allow_demo_users": True,
            "secret_key": "test-secret",
            "bootstrap_prediction_date": "2025-01-06",
        }
    )
    app.config["TESTING"] = True
    return app


def login(client, email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]


def test_health_endpoint_returns_dataset_summary(tmp_path: Path):
    app = build_test_app(tmp_path)
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["records_loaded"] == 5
    assert payload["predictor_mode"] == "mock"


def test_predict_requires_authentication(tmp_path: Path):
    app = build_test_app(tmp_path)
    client = app.test_client()

    response = client.get("/predict?date=2025-01-06")

    assert response.status_code == 401


def test_analyst_can_login_and_predict(tmp_path: Path):
    app = build_test_app(tmp_path)
    client = app.test_client()
    token = login(client, "analista@radar.local", "Analista123!")

    response = client.get(
        "/predict?date=2025-01-06",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data_previsao"] == "2025-01-06"
    assert "top_10_motoristas_geral" in payload
    assert payload["meta"]["predictor_mode"] == "mock"


def test_admin_can_list_users(tmp_path: Path):
    app = build_test_app(tmp_path)
    client = app.test_client()
    token = login(client, "admin@radar.local", "Admin123!")

    response = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    users = response.get_json()["users"]
    assert len(users) == 3
    assert {user["role"] for user in users} == {"admin", "gestor", "analista"}


def test_non_admin_cannot_list_users(tmp_path: Path):
    app = build_test_app(tmp_path)
    client = app.test_client()
    token = login(client, "gestor@radar.local", "Gestor123!")

    response = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
