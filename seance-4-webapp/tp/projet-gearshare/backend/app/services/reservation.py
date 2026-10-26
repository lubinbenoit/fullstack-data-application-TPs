# app/services/reservation.py
from sqlalchemy.orm import Session

from app.core.exceptions import ConflitReservation, RessourceIntrouvable
from app.models.reservation import Reservation
from app.repositories.item import ItemRepository
from app.repositories.reservation import ReservationRepository
from app.repositories.user import UserRepository
from app.schemas.reservation import ReservationCreate


class ReservationService:
    def __init__(self, db: Session) -> None:
        self.repo = ReservationRepository(db)
        self.items = ItemRepository(db)
        self.users = UserRepository(db)

    def get_or_404(self, reservation_id: int) -> Reservation:
        reservation = self.repo.get(reservation_id)
        if reservation is None:
            raise RessourceIntrouvable(f"Réservation {reservation_id} introuvable")
        return reservation

    def list(self, *, skip: int = 0, limit: int = 20, item_id: int | None = None):
        return self.repo.list(skip=skip, limit=limit, item_id=item_id)

    def create(self, data: ReservationCreate) -> Reservation:
        item = self.items.get(data.item_id)
        if item is None:
            raise RessourceIntrouvable(f"Item {data.item_id} introuvable")
        if self.users.get(data.borrower_id) is None:
            raise RessourceIntrouvable(f"Utilisateur {data.borrower_id} introuvable")
        if not item.disponible:
            raise ConflitReservation("Ce matériel n'est pas disponible")
        if self.repo.find_chevauchements(data.item_id, data.date_debut, data.date_fin):
            raise ConflitReservation("Ce créneau est déjà réservé")
        return self.repo.add(
            Reservation(**data.model_dump(), statut="active")
        )

    def cancel(self, reservation_id: int) -> Reservation:
        reservation = self.get_or_404(reservation_id)
        if reservation.statut != "active":
            raise ConflitReservation("Seule une réservation active peut être annulée")
        reservation.statut = "annulee"
        return reservation