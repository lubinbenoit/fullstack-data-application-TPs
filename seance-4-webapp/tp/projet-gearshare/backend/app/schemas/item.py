from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Schéma pour la création d'un item
class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titre: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tarif_jour: float = Field(gt=0)
    disponible: bool = True

# Schéma pour la lecture d'un item
class ItemRead(BaseModel):
    id: int
    titre: str
    description: str | None
    tarif_jour: float
    disponible: bool

# Schéma pour la mise à jour partielle (PATCH)
class ItemUpdate(BaseModel):
    titre: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    tarif_jour: Optional[float] = Field(default=None, gt=0)
    disponible: Optional[bool] = None