from pydantic import BaseModel, Field, model_validator
from datetime import date
from typing import Literal

class ReservationCreate(BaseModel):
    item_id: int = Field(ge=1)
    date_debut: date
    date_fin: date

    @model_validator(mode="after")
    def check_dates(self) -> "ReservationCreate":
        if self.date_fin <= self.date_debut:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return self

class ReservationRead(BaseModel):
    id: int
    item_id: int
    date_debut: date
    date_fin: date
    statut: Literal["active", "annulee"] = "active"
