# app/routers/reservations.py
from fastapi import APIRouter, Path, Query

from app.api.deps import DbSession
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate
from app.services.reservation import ReservationService

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate, db: DbSession):
    return ReservationService(db).create(payload)


@router.get("", response_model=list[ReservationRead])
def list_reservations(
    db: DbSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    item_id: int | None = Query(default=None, ge=1),
):
    return ReservationService(db).list(skip=skip, limit=limit, item_id=item_id)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(db: DbSession, reservation_id: int = Path(ge=1)):
    return ReservationService(db).get_or_404(reservation_id)


@router.patch("/{reservation_id}", response_model=ReservationRead)
def patch_reservation(payload: ReservationUpdate, db: DbSession,
                      reservation_id: int = Path(ge=1)):
    # le schéma n'autorise que "annulee" : toute autre valeur donne un 422
    return ReservationService(db).cancel(reservation_id)