"""Автоматические тесты сервиса Bill Splitter.

Запуск: python -m pytest -v
"""

from fastapi.testclient import TestClient

import app_final
from app_final import app

client = TestClient(app)


def create_bill(**overrides):
    """Создаёт тестовый счёт и возвращает ответ сервиса в виде словаря."""
    payload = {
        "title": "Тестовый ужин",
        "participants": ["Аня", "Борис", "Вика"],
        "expenses": [{"description": "Ужин", "payer": "Аня", "amount": 3000}],
    }
    payload.update(overrides)
    response = client.post("/bills", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": app_final.APP_VERSION}


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Сервис работает"


def test_create_and_get_bill():
    bill = create_bill()
    assert bill["total"] == 3000

    response = client.get(f"/bills/{bill['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Тестовый ужин"


def test_list_bills_filter_by_participant():
    create_bill(participants=["Глеб", "Дина"],
                expenses=[{"description": "Кофе", "payer": "Глеб", "amount": 400}])

    response = client.get("/bills", params={"participant": "Глеб"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert all("Глеб" in bill["participants"] for bill in data["bills"])


def test_unknown_bill_returns_404():
    response = client.get("/bills/999999")
    assert response.status_code == 404
    assert "не найден" in response.json()["detail"]


def test_payer_must_be_participant():
    response = client.post("/bills", json={
        "title": "Ошибка",
        "participants": ["Аня", "Борис"],
        "expenses": [{"description": "Такси", "payer": "Незнакомец", "amount": 500}],
    })
    assert response.status_code == 422


def test_add_expense_to_bill():
    bill = create_bill()
    response = client.post(f"/bills/{bill['id']}/expenses",
                           json={"description": "Такси", "payer": "Борис", "amount": 600})
    assert response.status_code == 201
    assert response.json()["total"] == 3600


def test_delete_bill():
    bill = create_bill()
    assert client.delete(f"/bills/{bill['id']}").status_code == 204
    assert client.get(f"/bills/{bill['id']}").status_code == 404


def test_split_equal():
    bill = create_bill()  # Аня заплатила 3000 за троих
    response = client.get(f"/bills/{bill['id']}/split", params={"tip": 0})
    assert response.status_code == 200
    data = response.json()

    balances = {person["name"]: person["balance"] for person in data["people"]}
    assert balances == {"Аня": 2000, "Борис": -1000, "Вика": -1000}
    assert sorted((t["from"], t["to"], t["amount"]) for t in data["transfers"]) == [
        ("Борис", "Аня", 1000),
        ("Вика", "Аня", 1000),
    ]


def test_split_with_shared_by_and_tip():
    bill = create_bill(
        participants=["Аня", "Борис"],
        expenses=[
            {"description": "Пицца", "payer": "Аня", "amount": 1000},
            {"description": "Десерт", "payer": "Аня", "amount": 200, "shared_by": ["Борис"]},
        ],
    )
    data = client.get(f"/bills/{bill['id']}/split", params={"tip": 10}).json()
    assert data["total"] == 1320
    assert data["transfers"] == [{"from": "Борис", "to": "Аня", "amount": 770}]


def test_split_cents_add_up():
    bill = create_bill(expenses=[{"description": "Такси", "payer": "Аня", "amount": 100}])
    data = client.get(f"/bills/{bill['id']}/split", params={"tip": 0}).json()
    shares = [person["share"] for person in data["people"]]
    assert round(sum(shares), 2) == 100  # 33.34 + 33.33 + 33.33, копейки не теряются


def test_invalid_tip_returns_422():
    bill = create_bill()
    response = client.get(f"/bills/{bill['id']}/split", params={"tip": 150})
    assert response.status_code == 422


def test_default_tip_from_environment(monkeypatch):
    monkeypatch.setattr(app_final, "DEFAULT_TIP_PERCENT", 20.0)
    bill = create_bill()
    data = client.get(f"/bills/{bill['id']}/split").json()
    assert data["tip_percent"] == 20.0
    assert data["total"] == 3600


def test_invalid_tip_env_falls_back_to_zero(monkeypatch):
    monkeypatch.setenv("DEFAULT_TIP_PERCENT", "много")
    assert app_final.read_tip_percent() == 0.0
