# app/schemas/user.py

from pydantic import BaseModel, ConfigDict


class OwnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str