from fastapi import APIRouter, HTTPException, Path, Query
from datetime import date
from typing import Optional
from app.schemas.reservation import ReservationCreate, ReservationRead

router = APIRouter(prefix="/reservations", tags=["reservations"])

FAKE_DB: dict[int, dict] = {}
def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1

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

@router.get("", response_model=list[ReservationRead])
def list_reservations(
    item_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    reservations = list(FAKE_DB.values())
    if item_id:
        reservations = [r for r in reservations if r["item_id"] == item_id]
    return reservations[:limit]

@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: int = Path(ge=1)):
    if reservation_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    return FAKE_DB[reservation_id]

@router.post("/{reservation_id}/annuler", response_model=ReservationRead)
def cancel_reservation(reservation_id: int = Path(ge=1)):
    if reservation_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if FAKE_DB[reservation_id]["statut"] == "annulee":
        raise HTTPException(status_code=409, detail="Réservation déjà annulée")
    FAKE_DB[reservation_id]["statut"] = "annulee"
    return FAKE_DB[reservation_id]
