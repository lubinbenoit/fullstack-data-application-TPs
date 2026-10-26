# app/models/reservation.py
from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("date_fin > date_debut", name="dates_coherentes"),
        CheckConstraint("statut IN ('active', 'annulee', 'terminee')", name="statut_valide"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    borrower_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Côté inverse des deux liens
    item: Mapped["Item"] = relationship(back_populates="reservations")
    borrower: Mapped["User"] = relationship(back_populates="reservations")