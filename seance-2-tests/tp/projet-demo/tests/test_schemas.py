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