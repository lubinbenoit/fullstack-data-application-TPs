# app/services/item.py
from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable
from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate
from app.models.user import User

class ItemService:
    def __init__(self, db: Session):
        self.repo = ItemRepository(db)

    def get_or_404(self, item_id: int) -> Item:
        item = self.repo.get(item_id)
        if item is None:
            raise RessourceIntrouvable(f"Item {item_id} introuvable")
        return item

    def create(self, data: ItemCreate) -> Item:
        if self.repo.db.get(User, data.owner_id) is None:
            raise RessourceIntrouvable(f"Utilisateur {data.owner_id} introuvable")
        item = Item(**data.model_dump())
        return self.repo.add(item)

    def list(self, *, skip=0, limit=20, search=None, available_only=False):
        return self.repo.list(skip=skip, limit=limit, search=search,
                              available_only=available_only)

    def update(self, item_id: int, data: ItemUpdate) -> Item:
        item = self.get_or_404(item_id)
        for champ, valeur in data.model_dump(exclude_unset=True).items():
            setattr(item, champ, valeur)
        return item

    def delete(self, item_id: int) -> None:
        self.repo.delete(self.get_or_404(item_id))

    def replace(self, item_id: int, data: ItemCreate) -> Item:
        item = self.get_or_404(item_id)
        for champ, valeur in data.model_dump().items():
            setattr(item, champ, valeur)
        return item