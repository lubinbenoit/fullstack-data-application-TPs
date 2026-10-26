# app/routers/items.py
from fastapi import APIRouter, Path, Query, Response

from app.api.deps import DbSession
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services.item import ItemService

router = APIRouter(prefix="/items", tags=["items"])


# Route pour lister les items (filtrés et paginés)
@router.get("", response_model=list[ItemRead])
def list_items(
    db: DbSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    disponible: bool | None = None,
):
    return ItemService(db).list(skip=skip, limit=limit, search=q, available_only=disponible)


# Route pour obtenir un item spécifique (GET)
@router.get("/{item_id}", response_model=ItemRead)
def get_item(db: DbSession, item_id: int = Path(ge=1)):
    return ItemService(db).get_or_404(item_id)


# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, db: DbSession = None):
    return ItemService(db).create(payload)


# Route pour remplacer un item (PUT)
@router.put("/{item_id}", response_model=ItemRead)
def update_item(payload: ItemCreate, item_id: int = Path(ge=1), db: DbSession = None):
    return ItemService(db).replace(item_id, payload)


# Route pour mettre à jour partiellement (PATCH)
@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(payload: ItemUpdate, item_id: int = Path(ge=1), db: DbSession = None):
    return ItemService(db).update(item_id, payload)


# Route pour supprimer un item (DELETE)
@router.delete("/{item_id}", status_code=204, response_class=Response)
def delete_item(item_id: int = Path(ge=1), db: DbSession = None):
    ItemService(db).delete(item_id)
    return Response(status_code=204)