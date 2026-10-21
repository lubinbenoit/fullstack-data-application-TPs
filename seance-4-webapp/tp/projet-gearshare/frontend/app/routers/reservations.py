from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api_client import ApiError, api_client
from app.routers.items import render_item_detail

router = APIRouter()


@router.post("/items/{item_id}/reservations", response_class=HTMLResponse)
def create_reservation_page(
    request: Request,
    item_id: int,
    date_debut: Annotated[date, Form()],
    date_fin: Annotated[date, Form()],
):
    try:
        api_client.create_reservation(item_id, date_debut, date_fin)
    except ApiError as exc:
        if exc.status_code != 422:
            raise
        return render_item_detail(
            request,
            item_id,
            erreurs=exc.messages(),
            valeurs={"date_debut": date_debut, "date_fin": date_fin},
            status_code=422,
        )
    return RedirectResponse(f"/items/{item_id}?message=reservee", status_code=303)


@router.post("/reservations/{reservation_id}")
def update_reservation_page(
    reservation_id: int,
    item_id: Annotated[int, Form()],
    statut: Annotated[str, Form()],
):
    try:
        api_client.update_reservation_status(reservation_id, statut)
    except ApiError as exc:
        if exc.status_code == 409:
            return RedirectResponse(f"/items/{item_id}?message=deja_annulee", status_code=303)
        raise
    return RedirectResponse(f"/items/{item_id}?message=annulee", status_code=303)