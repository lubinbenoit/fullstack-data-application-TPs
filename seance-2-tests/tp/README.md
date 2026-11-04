# TP — Séance 2 : tester l'API de la séance 1 (2h)

## Ce que vous allez faire

Ce TP consiste à écrire les tests de l'API que vous avez developpé en séance 1 : le CRUD `items` et
la ressource `reservations`.

## Objectifs du TP

À la fin de ce TP, vous devez savoir :

- installer et lancer pytest dans le projet de la séance 1, dans son conteneur ;
- tester une API FastAPI avec `TestClient`, sans démarrer de serveur ;
- écrire des fixtures : un client partagé, un stockage remis à zéro, un item déjà créé ;
- automatiser, en tests de contrat, toutes les vérifications faites à la main en séance 1 ;


## Ce que j'ai fait

J'ai copié collé le projet de la séance 1 dans la séance 2, sans écraser les fichiers déjà présents.

Ajouter pytest dans le conteneur en mettant dans requirements.txt
pytest
pytest-cov
httpx

(il y avait déjà :
```
pytest==8.3.3
pytest-cov==5.0.0
httpx==0.27.2
```
)
Puis `docker compose up --build`



### Etape 1 : premier test + grosse fixture


#### 2.1

Ajouter les fichiers dans `projet-demo/tests/`

Et `test_health.py`, `conftest.py`


Et `pytest.ini` dans `projet-demo/`

Il y a déjà `pytest.ini` avec
```python
[pytest]
pythonpath = .
testpaths = tests
```

#### brancher les tests dans Docker
Dans Dockerfile il faut que le `COPY` inclue `tests/` et `pytest.ini`

J'ai ajouté 
```bash
COPY pytest.ini .
COPY tests/ ./tests/
```

Dans `test health` (normalement ça y est déjà) :
```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_retourne_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Attention il faut éteindre l'appli puis relancer pour prendre en compre les modifs du Dockerfile
```bash
docker compose up --build

docker compose run --rm api pytest
```

Ensuite on ajoute dans `conftest`
```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```
(contenu du cours)








### Fixture


3.3 et 3.4
3.4 -> côté tests : une classe Storage qui tient tous les dictionnaires de l'API et sait les remettre à zéro, et une fixture qui l'expose.

`conftest` :

```python
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
```






### 3.4 Isoler l'état en mémoire : la fixture storage

Il faut remplacer l'id global dans les routers `items` et `reservations`

Dans `items`
```python
def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1
```

remplace :
```python
_next_id = 1
```

Et 
```python
# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    global _next_id
    item = {"id": _next_id, **payload.model_dump()}
    FAKE_DB[_next_id] = item
    _next_id += 1
    return item
```

devient
```python
# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    new_id = _next_id()
    item = {"id": new_id, **payload.model_dump()}
    FAKE_DB[new_id] = item
    return item
```

Même chose dans `reservations`
```python
_next_id = 1
```

devient
```python
def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1
```

et 
```python
@router.post("", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate):
    global _next_id
    reservation = {
        "id": _next_id,
        "statut": "active",
        **payload.model_dump()
    }
    FAKE_DB[_next_id] = reservation
    _next_id += 1
    return reservation
```

devient
```python
@router.post("", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate):
    new_id = _next_id()
    reservation = {
        "id": new_id,
        "statut": "active",
        **payload.model_dump(),
    }
    FAKE_DB[new_id] = reservation
    return reservation
```

(vérifier que docker desktop est ouvert)
aller dans le répertoire `projet-demo/`
relancer `docker compose up --build`
vérifier que le test reste valide dans un autre terminal dans` projet-demo/` :
```bash
docker compose run --rm api pytest
```




Réaliser des tests : les fichiers test_items.py et test_reservations.py


3->4.4

`test_items.py`

```python
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Storage # à suppr si pb d'import


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
```




`test_reservations.py`

```python
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
```



4.2

`test_schemas.py`


```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.reservation import ReservationCreate


def test_dates_inversees_sont_refusees_par_le_schema() -> None:
    with pytest.raises(ValidationError, match="date_fin"):
        ReservationCreate(item_id=1, date_debut=date(2026, 9, 5), date_fin=date(2026, 9, 1))


def test_dates_egales_sont_refusees_par_le_schema() -> None:
    # Cas limite : date_fin == date_debut doit aussi être refusé (votre `<=`)
    with pytest.raises(ValidationError):
        ReservationCreate(item_id=1, date_debut=date(2026, 9, 5), date_fin=date(2026, 9, 5))


def test_reservation_valide_est_acceptee() -> None:
    r = ReservationCreate(item_id=1, date_debut=date(2026, 9, 1), date_fin=date(2026, 9, 5))
    assert r.date_fin > r.date_debut
```




Ajouter au `conftest`
```python
@pytest.fixture
def reservation_active(client: TestClient, item_velo: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/reservations", json={
        "item_id": item_velo["id"],
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-05",
    })
    assert response.status_code == 201
    return response.json()
```

Dans `projet-demo` :
```bash
docker compose up --build
docker compose run --rm api pytest
```

Corriger le problème Pydantic v1/v2
Dans `ReservationCreate` (`reservation.py`) remplacer le `field validator`

```python
    @field_validator("date_fin")
    def check_date_fin_after_date_debut(cls, v, values):
        if "date_debut" in values and v <= values["date_debut"]:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return v
```

par
```python
    @model_validator(mode="after")
    def check_dates(self) -> "ReservationCreate":
        if self.date_fin <= self.date_debut:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return self
```

Importer
```python
from pydantic import BaseModel, Field, model_validator
```

Gérer les accents (`test_lister_filtre_q_ignorant_la_casse`)

Dans le filtre (`items.py`)

```python
    if q:
        items = [item for item in items if q.lower() in item["titre"].lower()]
```

est remplacé par :

```python
if q:
    qn = _sans_accent(q.lower())
    items = [item for item in items if qn in _sans_accent(item["titre"].lower())]
```

On ajoute la fonction à côté de _next_id :
```python
def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")
```

Relancer les tests.

plus aucun problème.




7.
```bash
docker compose run --rm api pytest --cov=app --cov-report=term-missing
```

8.

Si on casse dans `ItemCreate`
```python
    #model_config = ConfigDict(extra="forbid")
    model_config = ConfigDict()
```
```bash
FAILED tests/test_items.py::test_creation_item_invalide_renvoie_422[payload5-couleur] - assert 201 == 422
================================================================= 1 failed,
```


Si on supprime dans `reservations.py` le raise de l'annulation double
```python
    # if FAKE_DB[reservation_id]["statut"] == "annulee":
    #     raise HTTPException(status_code=409, detail="Réservation déjà annulée")
```
```bash
FAILED tests/test_reservations.py::test_annuler_deux_fois_renvoie_409 - assert 200 == 409
================================================================= 1 failed, 34 passed, 1 warning in 0.50s =================================================================
```

Si on change le model validator des date dans reservation.py
```python
        #if self.date_fin <= self.date_debut:
        if self.date_fin <self.date_debut:
```
```bash
FAILED tests/test_schemas.py::test_dates_egales_sont_refusees_par_le_schema - Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
============================================================== 1 failed, 34 passed, 1 warning in 0.54s
```

Casser excluse unset true du patch (items.py)
```python
    #data = payload.model_dump(exclude_unset=True)
    data = payload.model_dump()
```
```bash
FAILED tests/test_items.py::test_patch_modifie_un_seul_champ_sans_ecraser_le_reste - fastapi.exceptions.ResponseValidationError: 2 validation errors:
FAILED tests/test_items.py::test_patch_vide_ne_change_rien - fastapi.exceptions.ResponseValidationError: 3 validation errors:
======================================================== 2 failed, 33 passed, 1 warning in 1.20s
```