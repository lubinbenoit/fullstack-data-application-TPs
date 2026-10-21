from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Storage   # si pytest se plaint de l'import, supprimez cette ligne (voir note)


# ---------- LECTURES ----------

def test_lister_vide_renvoie_liste_vide(client: TestClient) -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == []


def test_creer_item_renvoie_201_et_est_relisible(client: TestClient) -> None:
    payload = {"titre": "Vélo de ville", "description": "Trois vitesses", "tarif_jour": 8.5}

    response = client.post("/items", json=payload)

    assert response.status_code == 201
    corps = response.json()
    assert corps["id"] == 1
    assert corps["titre"] == "Vélo de ville"
    assert corps["disponible"] is True          # valeur par défaut du schéma
    # Then : l'item est relisible par GET
    assert client.get("/items/1").json() == corps


def test_get_item_absent_renvoie_404(client: TestClient) -> None:
    response = client.get("/items/999")

    assert response.status_code == 404


def test_lister_avec_skip_limit(client: TestClient, storage: Storage) -> None:
    # Given : cinq items, insérés directement (cas légitime d'usage de storage).
    for i in range(1, 6):
        storage.items[i] = {"id": i, "titre": f"Item {i}", "description": None,
                            "tarif_jour": 5.0, "disponible": True}

    response = client.get("/items", params={"skip": 1, "limit": 2})

    assert [item["id"] for item in response.json()] == [2, 3]


def test_lister_filtre_q_ignorant_la_casse(client: TestClient) -> None:
    client.post("/items", json={"titre": "Vélo de ville", "tarif_jour": 8.5})
    client.post("/items", json={"titre": "Perceuse", "tarif_jour": 4.0})

    response = client.get("/items", params={"q": "VELO"})

    assert [item["titre"] for item in response.json()] == ["Vélo de ville"]


def test_lister_filtre_disponible(client: TestClient) -> None:
    client.post("/items", json={"titre": "Vélo", "tarif_jour": 8.5})
    client.post("/items", json={"titre": "Perceuse", "tarif_jour": 4.0, "disponible": False})

    response = client.get("/items", params={"disponible": "false"})

    assert [item["titre"] for item in response.json()] == ["Perceuse"]


@pytest.mark.parametrize("params", [
    {"limit": 0},       # sous la borne ge=1
    {"limit": 500},     # au-dessus de le=100
    {"skip": -1},       # négatif
])
def test_lister_parametres_invalides_renvoient_422(client: TestClient, params: dict) -> None:
    response = client.get("/items", params=params)

    assert response.status_code == 422


# ---------- VALIDATION À LA CRÉATION ----------

@pytest.mark.parametrize(
    ("payload", "champ_en_erreur"),
    [
        ({"titre": "ab", "tarif_jour": 8.5}, "titre"),                        # trop court
        ({"titre": "x" * 121, "tarif_jour": 8.5}, "titre"),                  # trop long
        ({"titre": "Vélo", "tarif_jour": 0}, "tarif_jour"),                  # nul
        ({"titre": "Vélo", "tarif_jour": -3}, "tarif_jour"),                 # négatif
        ({"titre": "Vélo"}, "tarif_jour"),                                   # manquant
        ({"titre": "Vélo", "tarif_jour": 8.5, "couleur": "rouge"}, "couleur"),  # inconnu → extra="forbid"
    ],
)
def test_creation_item_invalide_renvoie_422(
    client: TestClient, payload: dict, champ_en_erreur: str
) -> None:
    response = client.post("/items", json=payload)

    assert response.status_code == 422
    champs = [erreur["loc"][-1] for erreur in response.json()["detail"]]
    assert champ_en_erreur in champs


# ---------- PUT / PATCH / DELETE ----------

def test_put_remplace_l_item(client: TestClient, item_velo: dict[str, Any]) -> None:
    # When : PUT sans description — elle doit devenir None (remplacement complet)
    response = client.put(f"/items/{item_velo['id']}",
                          json={"titre": "Vélo pliant", "tarif_jour": 10.0})

    assert response.status_code == 200
    corps = response.json()
    assert corps["titre"] == "Vélo pliant"
    assert corps["description"] is None


def test_put_item_absent_renvoie_404(client: TestClient) -> None:
    response = client.put("/items/999", json={"titre": "Vélo", "tarif_jour": 8.5})

    assert response.status_code == 404


def test_patch_modifie_un_seul_champ_sans_ecraser_le_reste(
    client: TestClient, item_velo: dict[str, Any]
) -> None:
    # When : on ne change que le titre.
    response = client.patch(f"/items/{item_velo['id']}", json={"titre": "Vélo pliant"})

    # Then : le titre a changé, la description n'a PAS été écrasée par None.
    assert response.status_code == 200
    assert response.json()["titre"] == "Vélo pliant"
    assert response.json()["description"] == "Trois vitesses"


def test_patch_vide_ne_change_rien(client: TestClient, item_velo: dict[str, Any]) -> None:
    response = client.patch(f"/items/{item_velo['id']}", json={})

    assert response.status_code == 200
    assert response.json() == item_velo


def test_patch_item_absent_renvoie_404(client: TestClient) -> None:
    response = client.patch("/items/999", json={"titre": "Vélo pliant"})

    assert response.status_code == 404


def test_delete_renvoie_204_puis_404(client: TestClient, item_velo: dict[str, Any]) -> None:
    suppression = client.delete(f"/items/{item_velo['id']}")
    relecture = client.get(f"/items/{item_velo['id']}")

    assert suppression.status_code == 204
    assert relecture.status_code == 404


def test_delete_item_absent_renvoie_404(client: TestClient) -> None:
    response = client.delete("/items/999")

    assert response.status_code == 404