# app/repositories/reservation.py
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reservation import Reservation


class ReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, reservation_id: int) -> Reservation | None:
        return self.db.get(Reservation, reservation_id)

    def find_chevauchements(self, item_id: int, debut: date, fin: date) -> list[Reservation]:
        stmt = select(Reservation).where(
            Reservation.item_id == item_id,
            Reservation.statut == "active",
            Reservation.date_debut < fin,
            Reservation.date_fin > debut,
        )
        return list(self.db.scalars(stmt))

    def add(self, reservation: Reservation) -> Reservation:
        self.db.add(reservation)
        self.db.flush()
        self.db.refresh(reservation)
        return reservation
    
    def list(self, *, skip: int = 0, limit: int = 20,
             item_id: int | None = None) -> list[Reservation]:
        stmt = select(Reservation).order_by(Reservation.id).offset(skip).limit(limit)
        if item_id is not None:
            stmt = stmt.where(Reservation.item_id == item_id)
        return list(self.db.scalars(stmt))