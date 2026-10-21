# app/routers/items.py
from typing import Annotated
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api_client import ApiError, api_client
from app.templating import templates

router = APIRouter()


@router.get("/items", response_class=HTMLResponse)
def list_items_page(request: Request) -> HTMLResponse:
    items = api_client.list_items()
    return templates.TemplateResponse(request, "items/list.html", {"items": items})

@router.get("/items/new", response_class=HTMLResponse)   # AVANT /items/{item_id}
def new_item_page(request: Request):
    return templates.TemplateResponse(
        request, "items/form.html", {"erreurs": [], "valeurs": {}}
    )


@router.post("/items", response_class=HTMLResponse)
def create_item_page(
    request: Request,
    titre: Annotated[str, Form()],
    tarif_jour: Annotated[float, Form()],
    description: Annotated[str, Form()] = "",
    disponible: Annotated[bool, Form()] = False,
):
    valeurs = {
        "titre": titre,
        "description": description,
        "tarif_jour": tarif_jour,
        "disponible": disponible,
    }
    data = {**valeurs, "description": description or None}  # "" -> absence de description
    try:
        item = api_client.create_item(data)
    except ApiError as exc:
        if exc.status_code != 422:
            raise                       # les autres erreurs vont au gestionnaire global
        return templates.TemplateResponse(
            request,
            "items/form.html",
            {"erreurs": exc.messages(), "valeurs": valeurs},
            status_code=422,
        )
    return RedirectResponse(f"/items/{item['id']}", status_code=303)


MESSAGES = {
    "reservee": ("succes", "Réservation enregistrée."),
    "annulee": ("succes", "Réservation annulée."),
    "deja_annulee": ("erreur", "Cette réservation est déjà annulée."),
}


def render_item_detail(request, item_id, *, erreurs=None, valeurs=None, message=None, status_code=200):
    item = api_client.get_item(item_id)
    reservations = api_client.list_reservations(item_id)
    return templates.TemplateResponse(
        request,
        "items/detail.html",
        {
            "item": item,
            "reservations": reservations,
            "erreurs": erreurs or [],
            "valeurs": valeurs or {},
            "message": MESSAGES.get(message),
        },
        status_code=status_code,
    )


@router.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail_page(request: Request, item_id: int, message: str | None = None):
    return render_item_detail(request, item_id, message=message)