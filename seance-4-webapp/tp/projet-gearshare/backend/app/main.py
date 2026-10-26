# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import RessourceIntrouvable, ConflitReservation, AccesRefuse
from app.routers import items, reservations

app = FastAPI(title="GearShare API", version="0.1.0")


# --- Traduction des exceptions métier en réponses HTTP ---
@app.exception_handler(RessourceIntrouvable)
async def not_found_handler(request: Request, exc: RessourceIntrouvable) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ConflitReservation)
async def conflict_handler(request: Request, exc: ConflitReservation) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(AccesRefuse)
async def forbidden_handler(request: Request, exc: AccesRefuse) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


# --- Routers ---
app.include_router(items.router)
app.include_router(reservations.router)


@app.get("/health", tags=["monitoring"])
def health() -> dict[str, str]:
    return {"status": "ok"}