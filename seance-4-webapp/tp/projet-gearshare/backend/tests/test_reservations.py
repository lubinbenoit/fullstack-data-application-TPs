from typing import Any

import pytest
from fastapi.testclient import TestClient


# ---------- CRÉATION ----------

def test_creer_reservation_renvoie_201_et_statut_active(
    client: TestClient, item_velo: dict[str, Any]
) -> None:
    response = client.post("/reservations", json={
        "item_id": item_velo["id"],
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-05",
    })

    assert response.status_code == 201
    corps = response.json()
    assert corps["id"] == 1
    assert corps["statut"] == "active"
    # Then : relisible par GET
    assert client.get("/reservations/1").json() == corps


def test_creer_reservation_dates_inversees_renvoie_422(
    client: TestClient, item_velo: dict[str, Any]
) -> None:
    response = client.post("/reservations", json={
        "item_id": item_velo["id"],
        "date_debut": "2026-09-05",
        "date_fin": "2026-09-01",
    })

    assert response.status_code == 422


@pytest.mark.parametrize("item_id", [0, -1])
def test_creer_reservation_item_id_invalide_renvoie_422(
    client: TestClient, item_id: int
) -> None:
    response = client.post("/reservations", json={
        "item_id": item_id, "date_debut": "2026-09-01", "date_fin": "2026-09-05",
    })

    assert response.status_code == 422


# ---------- LISTAGE ----------

def test_lister_avec_filtre_item_id(
    client: TestClient, item_velo: dict[str, Any]
) -> None:
    # Given : une réservation sur le vélo, une sur un autre item.
    client.post("/items", json={"titre": "Perceuse", "tarif_jour": 4.0})
    client.post("/reservations", json={
        "item_id": item_velo["id"], "date_debut": "2026-09-01", "date_fin": "2026-09-05",
    })
    client.post("/reservations", json={
        "item_id": 2, "date_debut": "2026-10-01", "date_fin": "2026-10-05",
    })

    response = client.get("/reservations", params={"item_id": item_velo["id"]})

    assert [r["item_id"] for r in response.json()] == [item_velo["id"]]


# ---------- ANNULATION ----------

def test_annuler_renvoie_200_et_statut_annulee(
    client: TestClient, reservation_active: dict[str, Any]
) -> None:
    response = client.post(f"/reservations/{reservation_active['id']}/annuler")

    assert response.status_code == 200
    assert response.json()["statut"] == "annulee"


def test_annuler_deux_fois_renvoie_409(
    client: TestClient, reservation_active: dict[str, Any]
) -> None:
    # Given : la réservation a déjà été annulée.
    client.post(f"/reservations/{reservation_active['id']}/annuler")

    # When : seconde annulation.
    response = client.post(f"/reservations/{reservation_active['id']}/annuler")

    # Then : conflit, et la réservation reste annulée.
    assert response.status_code == 409
    assert client.get(f"/reservations/{reservation_active['id']}").json()["statut"] == "annulee"


def test_annuler_reservation_absente_renvoie_404(client: TestClient) -> None:
    response = client.post("/reservations/999/annuler")

    assert response.status_code == 404


def test_get_reservation_absente_renvoie_404(client: TestClient) -> None:
    response = client.get("/reservations/999")

    assert response.status_code == 404