# tests/conftest.py
from collections.abc import Iterator
from dataclasses import dataclass, fields
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import items, reservations


@dataclass
class Storage:
    """Poignée sur l'état en mémoire de l'API, réservée aux tests."""
    items: dict[int, dict[str, Any]]
    reservations: dict[int, dict[str, Any]]

    def reset_all(self) -> None:
        for field in fields(self):
            getattr(self, field.name).clear()


@pytest.fixture
def storage() -> Iterator[Storage]:
    storage = Storage(items=items.FAKE_DB, reservations=reservations.FAKE_DB)
    storage.reset_all()
    yield storage
    storage.reset_all()


@pytest.fixture
def client(storage: Storage) -> TestClient:
    return TestClient(app)


@pytest.fixture
def item_velo(client: TestClient) -> dict[str, Any]:
    """Un item déjà créé, renvoyé tel que l'API l'expose."""
    response = client.post("/items", json={
        "titre": "Vélo de ville",
        "description": "Trois vitesses",
        "tarif_jour": 8.5,
    })
    assert response.status_code == 201
    return response.json()

@pytest.fixture
def reservation_active(client: TestClient, item_velo: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/reservations", json={
        "item_id": item_velo["id"],
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-05",
    })
    assert response.status_code == 201
    return response.json()