# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api_client import ApiError
from app.routers import items, reservations
from app.templating import BASE_DIR, templates


app = FastAPI(title="GearShare — frontend")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(items.router)
app.include_router(reservations.router)

@app.exception_handler(ApiError)
def api_error_page(request: Request, exc: ApiError) -> HTMLResponse:
    messages = {
        404: "Cette page n'existe pas ou plus.",
        503: "Le service est momentanément indisponible. Réessayez dans un instant.",
    }
    message = messages.get(exc.status_code, "Une erreur est survenue.")
    return templates.TemplateResponse(
        request, "erreur.html", {"message": message}, status_code=exc.status_code
    )

# redirection de / vers /items
@app.get("/", response_class=RedirectResponse)
def home() -> RedirectResponse:
    return RedirectResponse(url="/items", status_code=307)
