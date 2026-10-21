import unicodedata

from fastapi import APIRouter, HTTPException, Path, Query, Response
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])

FAKE_DB: dict[int, dict] = {}


def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1

def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")

# Route pour lister les items (filtrés et paginés)
@router.get("", response_model=list[ItemRead])
def list_items(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    disponible: bool | None = None,
):
    items = list(FAKE_DB.values())

    # Filtrer par titre (q)
    if q:
        qn = _sans_accent(q.lower())
        items = [item for item in items if qn in _sans_accent(item["titre"].lower())]

    # Filtrer par disponibilité
    if disponible is not None:
        items = [item for item in items if item["disponible"] == disponible]

    # Pagination
    return items[skip : skip + limit]


# Route pour obtenir un item spécifique (GET)
@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int = Path(ge=1)):
    item = FAKE_DB.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    return item


# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    new_id = _next_id()
    item = {"id": new_id, **payload.model_dump()}
    FAKE_DB[new_id] = item
    return item


# Route pour remplacer un item (PUT)
@router.put("/{item_id}", response_model=ItemRead)
def update_item(payload: ItemCreate, item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    FAKE_DB[item_id] = {"id": item_id, **payload.model_dump()}
    return FAKE_DB[item_id]


# Route pour mettre à jour partiellement un item (PATCH)
@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(payload: ItemUpdate, item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    data = payload.model_dump(exclude_unset=True)
    FAKE_DB[item_id].update(data)
    return FAKE_DB[item_id]


# Route pour supprimer un item (DELETE)
@router.delete("/{item_id}", status_code=204, response_class=Response)
def delete_item(item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    del FAKE_DB[item_id]
