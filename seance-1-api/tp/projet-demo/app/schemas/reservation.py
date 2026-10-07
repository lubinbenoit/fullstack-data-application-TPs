from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Literal

class ReservationCreate(BaseModel):
    item_id: int = Field(ge=1)
    date_debut: date
    date_fin: date

    @field_validator("date_fin")
    def check_date_fin_after_date_debut(cls, v, values):
        if "date_debut" in values and v <= values["date_debut"]:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return v

class ReservationRead(BaseModel):
    id: int
    item_id: int
    date_debut: date
    date_fin: date
    statut: Literal["active", "annulee"] = "active"
