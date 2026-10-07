from fastapi import FastAPI
from app.routers import items, reservations

app = FastAPI(title="GearShare API", version="0.1.0")
app.include_router(items.router)
app.include_router(reservations.router)

@app.get("/health", tags=["monitoring"])
def health() -> dict[str, str]:
    return {"status": "ok"}
