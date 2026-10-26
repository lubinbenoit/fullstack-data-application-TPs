# app/repositories/item.py
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.item import Item


class ItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def list(self, *, skip: int = 0, limit: int = 20,
             search: str | None = None, available_only: bool = False) -> list[Item]:
        # stmt = select(Item).offset(skip).limit(limit)
        stmt = select(Item).options(joinedload(Item.owner)).offset(skip).limit(limit)
        if search:
            stmt = stmt.where(Item.titre.ilike(f"%{search}%"))
        if available_only:
            stmt = stmt.where(Item.disponible.is_(True))
        return list(self.db.scalars(stmt))

    def add(self, item: Item) -> Item:
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item: Item) -> None:
        self.db.delete(item)