# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # teste la connexion avant de la réutiliser
    echo=settings.sql_echo,  # affiche le SQL généré : très utile en développement
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
