# app/core/exceptions.py
class DomainError(Exception):
    """Exception métier de base : message lisible, aucune notion d'HTTP."""
    def __init__(self, message: str) -> None:
        self.message = message


class RessourceIntrouvable(DomainError):
    """Ressource introuvable — sera traduite en 404."""

class ConflitReservation(DomainError):
    """Conflit métier — sera traduite en 409."""

class AccesRefuse(DomainError):
    """Accès refusé — sera traduite en 403."""