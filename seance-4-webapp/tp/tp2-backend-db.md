# TP 2 — Séance 4 : brancher le backend sur PostgreSQL

## Ce que vous allez faire

À la fin du [TP 1](tp1-frontend.md), votre application a deux services : un frontend qui sert des
pages HTML et un backend qui garde tout en mémoire. Dans ce TP, vous ajoutez le troisième service,
**PostgreSQL**, et vous restructurez le backend en couches pour qu'il y lise et écrive ses
données.

Le frontend, lui, ne doit presque pas changer : il ne connaît que l'API. Chaque modification que
vous serez obligés d'y faire révélera un changement du contrat de l'API ; vous les noterez.

Ce TP est **guidé, pas dicté** : je vous dis quoi construire, dans quel ordre, et comment vérifier
que ça marche. Le code, c'est vous qui l'écrivez, en vous appuyant sur le
[cours 2](../cours/cours2-backend-db.md), qui vous donne tous les éléments nécessaires. Les seules commandes données telles quelles sont celles à lancer
dans le terminal.

## Objectifs du TP

À la fin de ce TP, vous devez savoir :

- structurer un backend FastAPI en couches (routers / services / repositories / models / schemas) ;
- configurer SQLAlchemy et injecter une session par requête ;
- créer, relire et corriger une migration Alembic ;
- externaliser toute la configuration en variables d'environnement ;
- orchestrer backend + frontend + base dans un seul `docker compose up`, et choisir comment les
  migrations s'y appliquent ;
- repérer un N+1 dans les logs SQL et le corriger ;
- écrire une verticale complète avec ses règles métier, et la relire avec une grille de review.

C'est le TP le plus long du module. **Ce que vous produisez ici est le socle de votre projet** :
soignez-le, vous allez vivre dedans pendant trois séances.

## Prérequis

- Les TP des séances 1 et 2 terminés.
- Le TP 1 de cette séance terminé : dépôt organisé en `backend/` et `frontend/`.
- Docker Desktop lancé.

---

## Étape 0 — L'arborescence cible

Repartez du dépôt du TP 1. Le dossier `frontend/` ne bouge pas ; c'est le dossier `backend/` qui
se restructure en couches. Voici la cible :

```text
gearshare/
├── backend/
│   ├── alembic/
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   └── session.py
│   │   ├── api/
│   │   │   └── deps.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── routers/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/          # celui du TP 1, inchangé
├── .env.example
├── .env               # ← dans le .gitignore
├── .gitignore
└── docker-compose.yml
```

```text
gearshare/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   └── session.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── tests/
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/          # celui du TP 1, inchangé
├── .env               # ← dans le .gitignore
├── .env.example
├── .gitignore
└── docker-compose.yml
```
Créez les dossiers vides, puis :

1. **Dépendances.** Ajoutez à `backend/requirements.txt` les quatre bibliothèques dont le backend
   a désormais besoin : SQLAlchemy 2.0, le driver PostgreSQL `psycopg` (version 3, avec son
   extra `binary`), Alembic et `pydantic-settings`. Fixez les versions majeures, comme pour
   FastAPI. Gardez `pytest` et `httpx`, ajoutés en séance 2.
2. **`.gitignore`.** Il doit au minimum exclure le `.env`, les caches Python et pytest, et votre
   environnement virtuel.

**Faites ce `.gitignore` maintenant.** Un `.env` commité en séance 4, c'est un secret exposé dans
l'historique Git jusqu'au rendu. Vérifiez-le :

```bash
echo "TEST=1" > .env
git status          # le .env ne doit PAS apparaître
```

---

## Étape 1 — Configuration et session

Trois fichiers à écrire :

- **`app/core/config.py`** : une classe de configuration `pydantic-settings` qui lit au moins
  l'URL de la base et un booléen d'affichage du SQL (désactivé par défaut). Elle est instanciée
  une seule fois, au niveau du module.

```
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str                 # séance 5
    jwt_expire_minutes: int = 60
    sql_echo: bool = False


settings = Settings()

```


- **`app/db/session.py`** : l'engine SQLAlchemy et la fabrique de sessions, construits à partir de
  cette configuration. Activez la vérification des connexions mortes (`pool_pre_ping`).

```
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

```
- **`app/api/deps.py`** : la dépendance `get_db`, qui ouvre une session par requête, la valide si
  tout s'est bien passé, l'annule en cas d'exception, et la ferme **dans tous les cas**. Exposez
  aussi l'alias `DbSession` pour ne pas répéter `Depends(get_db)` partout.
```
# app/api/deps.py
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

```

Puis le fichier **`.env.example`**, commité, qui liste toutes les variables nécessaires avec des
valeurs de développement : les trois variables attendues par l'image `postgres`
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`), `DATABASE_URL` au format
`postgresql+psycopg://utilisateur:motdepasse@hote:port/base`, et `SQL_ECHO`. Copiez-le :

```
# Service db (lues aussi par Compose pour la substitution ${...})
POSTGRES_USER=gearshare
POSTGRES_PASSWORD=gearshare
POSTGRES_DB=gearshare

# Service backend
DATABASE_URL=postgresql+psycopg://gearshare:gearshare@db:5432/gearshare
JWT_SECRET=changez-moi-en-production
JWT_EXPIRE_MINUTES=60
SQL_ECHO=false
```

```bash
cp .env.example .env
```

**Vérifiez votre compréhension** : quel hôte mettez-vous dans `DATABASE_URL`, `db` ou `localhost` ?
Pourquoi ? Si vous hésitez, relisez le cours de la séance 0 sur le réseau Docker.

```text
L’hôte est db, le nom du service Postgres dans docker-compose.yml. Cela dépend de l’endroit d’où part la connexion : elle part du conteneur backend, pas de notre PC. Dans ce conteneur, localhost désigne le conteneur backend lui-même, où rien n’écoute sur le port 5432. Docker Compose résout le nom du service db vers l’adresse du conteneur Postgres. C’est le même piège que API_BASE_URL=http://backend:8000 côté frontend dans le TP précédent.

localhost ne serait correct que pour un programme lancé directement sur ton PC (hors Docker) et qui passerait par le port publié du conteneur, par exemple avec un ports: "5432:5432" sur le service db.
```


**Point de contrôle** : dans `get_db`, que se passe-t-il si une route lève une exception après
avoir ajouté un objet à la session ? L'objet est-il en base ? Notez votre réponse, vous la
vérifierez à l'étape 4.

```
Le add() ne fait que placer l’objet dans la session (en mémoire). Selon les options (autoflush, flush() explicite), un INSERT peut avoir été envoyé, mais il reste dans la transaction en cours, qui n’est pas validée.
Quand la route lève une exception, le except de get_db exécute rollback() : la transaction est annulée, et le commit() n’est jamais atteint.
Donc l’objet n’est pas en base, même si un flush a eu lieu avant l’exception.
```


---

## Étape 2 — Les modèles

Écrivez `app/models/base.py`, puis `user.py`, `item.py` et `reservation.py`, en traduisant
**exactement** le schéma SQL de la séance 3. Le modèle `Item` du cours vous sert de référence pour
la syntaxe ; les deux autres sont à écrire entièrement.

Points à ne pas rater :

- `index=True` sur toutes les clés étrangères ;
- `Numeric(8, 2)` pour `tarif_jour` (jamais `Float` pour de l'argent) ;
- `DateTime(timezone=True)` avec une valeur par défaut côté serveur pour `created_at` ;
- l'unicité de `User.email` ;
- les contraintes `CHECK` de la séance 3 dans `__table_args__` (tarif positif, dates cohérentes,
  statut valide), **nommées** ;
- les `relationship(back_populates=...)` des deux côtés de chaque lien.

Enfin, faites en sorte que `app/models/__init__.py` importe `Base` et les trois modèles. Ce
fichier n'est pas cosmétique : relisez dans le cours la partie sur Alembic pour comprendre ce qui
se passe sans lui.

```
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```
```
Pour les fichiers app/models/user.py item.py et reservation.py, on traduit le SQL du schema.sql de la séance 3 en SQLAlchemy.
Les fichiers app/models/ sont basés sur SQLalchemy (ORM), ils parlent à la base de données, ils décrivent les tables SQL et les colonnse, ils contiennent les relations, clés étrangères, contraintes (CHEK, Numeric(8,2)...). Une instance est un objet branché sur la base. Equivalent aux entités en PHP.

Ne pas confondre avec app/schemas/ qui utilisent la bibliothèque Pydantic, ils parlent à l'API (requêtes et réponses HTTP, décrivent le format des JSON échangés, contiennent quels champs sont visibles, optionnels, en lecture ou écriture. Une instance est un objet neutre, juste des données validées)
```
```
# app/models/item.py
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("tarif_jour > 0", name="tarif_jour_positif"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    titre: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tarif_jour: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="items")
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
```
```
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
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
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
```
```
# app/models/user.py
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Contreparties des relationship() de Item et Reservation
    items: Mapped[list["Item"]] = relationship(back_populates="owner")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="borrower")
```
```
# app/models/__init__.py
from app.models.base import Base
from app.models.user import User
from app.models.item import Item
from app.models.reservation import Reservation
```

---

## Étape 3 — Alembic

Initialisez Alembic depuis `backend/` :

```bash
alembic init alembic
```

Puis branchez-le sur votre application, dans `alembic/env.py` :

- l'URL de connexion doit venir de votre configuration, **pas** de `alembic.ini` ;
- `target_metadata` doit pointer sur les métadonnées de votre `Base`, avec les modèles importés.

Dans `alembic.ini`, laissez `sqlalchemy.url` vide : ce fichier est commité, votre mot de passe n'a
rien à y faire.

```
# alembic/env.py
from app.core.config import settings
from app.models.base import Base
from app.models import item, reservation, user

    # url = config.get_main_option("sqlalchemy.url")
    url = config.set_main_option("sqlalchemy.url", settings.database_url)

# target_metadata = None
target_metadata = Base.metadata

ajouter après cette ligne :
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

rétablir la lecture normale :
# url = config.get_main_option("sqlalchemy.url")
    # url = config.set_main_option("sqlalchemy.url", settings.database_url)
    url = config.get_main_option("sqlalchemy.url")

```


Pour lancer Alembic dans un conteneur, ajoutez temporairement le service `db` à votre
`docker-compose.yml` (vous le compléterez à l'étape 6 ; le cours en donne un modèle).
Démarrez la base seule, puis générez la migration :

```bash
docker compose up -d db
docker compose run --rm backend alembic revision --autogenerate -m "schema initial"
```

> 💡 Si vous exécutez Alembic depuis votre machine plutôt que dans le conteneur, `DATABASE_URL`
> doit pointer sur `localhost` et non `db`, et le port de la base doit être publié. Le plus simple
> est de tout faire dans le conteneur.

```
docker-compose.yml

# services:
#   backend:
#     build: ./backend
#     ports:
#       - "8000:8000"
#     volumes:
#       - ./backend/app:/code/app
#       - ./backend/tests:/code/tests
#     command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#   frontend:
#     build: ./frontend
#     environment:
#       - API_BASE_URL=http://backend:8000
#     depends_on:
#       - backend
#     ports:
#       - "8080:8080"
#     volumes:
#       - ./frontend/app:/code/app
#     command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gearshare -d gearshare"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app
      - ./backend/tests:/code/tests
      - ./backend/alembic:/code/alembic
      - ./backend/alembic.ini:/code/alembic.ini
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    environment:
      - API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    ports:
      - "8080:8080"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

volumes:
  pgdata:
```
```
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pytest==8.3.3
pytest-cov==5.0.0
httpx==0.27.2
SQLAlchemy~=2.0
psycopg[binary]~=3.0
alembic~=1.0
pydantic-settings~=2.0
alembic
```
```
# backend/.dockerignore

__pycache__/
*.pyc
.pytest_cache/
.coverage
.venv/
.env
```

```
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose up -d db
time="2026-10-25T12:31:26+01:00" level=warning msg="The \"POSTGRES_USER\" variable is not set. Defaulting to a blank string."
time="2026-10-25T12:31:26+01:00" level=warning msg="The \"POSTGRES_PASSWORD\" variable is not set. Defaulting to a blank string."
time="2026-10-25T12:31:26+01:00" level=warning msg="The \"POSTGRES_DB\" variable is not set. Defaulting to a blank string."
[+] Running 3/3
 ✔ Network projet-gearshare_default  Created                                                                       0.1s
 ✔ Volume projet-gearshare_pgdata    Created                                                                       0.0s
 ✔ Container projet-gearshare-db-1   Started                                                                       0.6s


```

```
dossier corrompu... (antivirus ?)
Je change de dossier
C'est pénible
```
```
faire les modifs précédentes sur alembic/env et les autres fichiers
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose run --rm backend alembic revision --autogenerate -m "schema initial"
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                                                                                                                                                                                                                                                                                                           0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.tables
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
INFO  [alembic.autogenerate.compare.tables] Detected added table 'users'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'items'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_items_owner_id' on '('owner_id',)'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'reservations'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_reservations_borrower_id' on '('borrower_id',)'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_reservations_item_id' on '('item_id',)'
  Generating /code/alembic/versions/809e331e258e_schema_initial.py ...  done
```


**Ouvrez le fichier généré dans `alembic/versions/` et lisez-le en entier.** Vérifiez :

- [✔] les trois tables sont créées dans le bon ordre (`users` avant `items`) ;
- [x] les clés étrangères sont présentes, avec le bon `ondelete` ;
- [✔] les contraintes `CHECK` sont là, avec leurs noms ;
- [✔] les index sur les clés étrangères sont créés ;
- [✔] le `downgrade()` supprime bien tout, dans l'ordre inverse.

```
Suppression de ON DELETE CASCADE sur les réservations models/reservation.py
et cascade="all, delete-orphan" dans models/item.py
```

S'il manque quelque chose, ne corrigez pas la migration : corrigez le **modèle**, supprimez le
fichier, régénérez.


```
del alembic\versions\809e331e258e_schema_initial.py
rmdir /s /q alembic\versions\__pycache__
docker compose run --rm backend alembic heads
docker compose run --rm backend alembic current
docker compose run --rm backend alembic revision --autogenerate -m "schema initial"
```

Appliquez, inspectez, puis testez l'aller-retour :

```bash
docker compose run --rm backend alembic upgrade head
docker compose exec db psql -U gearshare -d gearshare -c "\dt"
docker compose exec db psql -U gearshare -d gearshare -c "\d items"
docker compose run --rm backend alembic downgrade base
docker compose run --rm backend alembic upgrade head
```

```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose run --rm backend alembic upgrade head
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 5e526ec40fdd, schema initial

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose exec db psql -U gearshare -d gearshare -c "\d reservations"
                                      Table "public.reservations"
   Column    |         Type          | Collation | Nullable |                 Default
-------------+-----------------------+-----------+----------+------------------------------------------
 id          | bigint                |           | not null | nextval('reservations_id_seq'::regclass)
 item_id     | bigint                |           | not null |
 borrower_id | bigint                |           | not null |
 date_debut  | date                  |           | not null |
 date_fin    | date                  |           | not null |
 statut      | character varying(20) |           | not null |
Indexes:
    "reservations_pkey" PRIMARY KEY, btree (id)
    "ix_reservations_borrower_id" btree (borrower_id)
    "ix_reservations_item_id" btree (item_id)
Check constraints:
    "dates_coherentes" CHECK (date_fin > date_debut)
    "statut_valide" CHECK (statut::text = ANY (ARRAY['active'::character varying, 'annulee'::character varying, 'terminee'::character varying]::text[]))
Foreign-key constraints:
    "reservations_borrower_id_fkey" FOREIGN KEY (borrower_id) REFERENCES users(id)
    "reservations_item_id_fkey" FOREIGN KEY (item_id) REFERENCES items(id)


C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose run --rm backend alembic downgrade base
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 5e526ec40fdd -> , schema initial

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose run --rm backend alembic upgrade head
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 5e526ec40fdd, schema initial
```

Le cycle complet doit passer sans erreur. Si `downgrade` échoue, corrigez la migration maintenant :
une migration non réversible est un problème que vous traînerez tout le projet.

### 3bis — Le piège du renommage

Exercice court mais important. Insérez d'abord deux items en base avec `psql` (il vous faudra un
utilisateur pour la clé étrangère). 

```

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO users (email, password_hash, display_name) VALUES ('bob@example.com', 'x', 'Bob') RETURNING id;"
 id
----
  1
(1 row)

INSERT 0 1
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO items (owner_id, titre, tarif_jour, disponible) VALUES (1, 'Tente 3 places', 12.50, true), (1, 'Réchaud', 4.00, true);"
INSERT 0 2
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare\backend>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre, tarif_jour FROM items;"
 id |     titre      | tarif_jour
----+----------------+------------
  1 | Tente 3 places |      12.50
  2 | Réchaud        |       4.00
(2 rows)
```

Puis renommez, dans le modèle `Item`, la colonne `tarif_jour`
en `prix_jour`, et générez :

```
models/item.py :

    # tarif_jour: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    prix_jour: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

        # CheckConstraint("tarif_jour > 0", name="tarif_jour_positif"),
        CheckConstraint("prix_jour > 0", name="tarif_jour_positif"),
```

```bash
docker compose run --rm backend alembic revision --autogenerate -m "renommage tarif_jour"
```
```
docker compose run --rm backend alembic revision --autogenerate -m "renommage tarif_jour"
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.tables
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
INFO  [alembic.ddl.postgresql] Detected sequence named 'reservations_id_seq' as owned by integer column 'reservations(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'users_id_seq' as owned by integer column 'users(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'items_id_seq' as owned by integer column 'items(id)', assuming SERIAL and omitting
INFO  [alembic.autogenerate.compare.tables] Detected added column 'items.prix_jour'
INFO  [alembic.autogenerate.compare.tables] Detected removed column 'items.tarif_jour'
  Generating /code/alembic/versions/610f8d868f9b_renommage_tarif_jour.py ...  done
```

Lisez la migration générée. Que fait-elle exactement ? Que deviendraient vos deux items si vous
l'appliquiez ? Notez votre prédiction, puis **corrigez la migration à la main** pour qu'elle
renomme la colonne sans perte (le cours vous donne l'opération Alembic à utiliser).
N'oubliez pas le `downgrade()`.

```
Prédiction : 
Avec deux lignes déjà en base, l’add_column ... NOT NULL sans valeur par défaut échoue sur PostgreSQL (column contains null values). Et si on contournait ça avec un défaut, le drop_column détruirait les tarifs : les deux items resteraient mais sans leur prix. Les contraintes CHECK nommées (tarif_jour_positif) risquent aussi d’apparaître dans la migration, car la condition change.
```
```
correction du fichier de migration :

# def upgrade() -> None:
#     """Upgrade schema."""
#     # ### commands auto generated by Alembic - please adjust! ###
#     op.add_column('items', sa.Column('prix_jour', sa.Numeric(precision=8, scale=2), nullable=False))
#     op.drop_column('items', 'tarif_jour')
#     # ### end Alembic commands ###


# def downgrade() -> None:
#     """Downgrade schema."""
#     # ### commands auto generated by Alembic - please adjust! ###
#     op.add_column('items', sa.Column('tarif_jour', sa.NUMERIC(precision=8, scale=2), autoincrement=False, nullable=False))
#     op.drop_column('items', 'prix_jour')
#     # ### end Alembic commands ###

def upgrade() -> None:
    op.alter_column('items', 'tarif_jour', new_column_name='prix_jour')


def downgrade() -> None:
    op.alter_column('items', 'prix_jour', new_column_name='tarif_jour')
```


Appliquez, et vérifiez que les tarifs sont toujours là :

```bash
docker compose run --rm backend alembic upgrade head
docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre, prix_jour FROM items;"
```

```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose run --rm backend alembic upgrade head
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 5e526ec40fdd -> 610f8d868f9b, renommage tarif_jour

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre, prix_jour FROM items;"
 id |     titre      | prix_jour
----+----------------+-----------
  1 | Tente 3 places |     12.50
  2 | Réchaud        |      4.00
(2 rows)
```
```
Les deux articles sont toujours là et le nom de la colonne tarif_jour a été renommée correctement.
```


Puis **revenez en arrière** (`downgrade -1`, supprimez le fichier de migration, remettez
`tarif_jour` dans le modèle) : c'était un exercice, on garde le nom initial.
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose run --rm backend alembic downgrade -1
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                                    0.0s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 610f8d868f9b -> 5e526ec40fdd, renommage tarif_jour
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre, prix_jour FROM items;"
ERROR:  column "prix_jour" does not exist
LINE 1: SELECT id, titre, prix_jour FROM items;
                          ^
HINT:  Perhaps you meant to reference the column "items.tarif_jour".

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre, tarif_jour FROM items;"
 id |     titre      | tarif_jour
----+----------------+------------
  1 | Tente 3 places |      12.50
  2 | Réchaud        |       4.00
(2 rows)
```
```
Supprimer aussi __pycache__ de alembic/versions/
```



Consignez dans `docs/review-migrations.md` ce que vous avez observé : la migration générée, votre
prédiction, la correction. C'est un livrable.

---

## Étape 4 — Une verticale complète : `items`

Écrivez la ressource `items` couche par couche, **dans cet ordre**, en vérifiant chaque fichier
avant de passer au suivant :

1. **`app/core/exceptions.py`** : une exception métier de base, et une sous-classe par famille
   d'erreur — ressource introuvable, conflit métier, accès refusé. Elles transportent un message
   lisible. Aucune ne connaît HTTP.
```
Le vocabulaire des erreurs
```
```
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

```
2. **`app/schemas/item.py`** : un schéma de création, un schéma de modification (tous les champs
   optionnels) et un schéma de lecture, construit depuis un objet SQLAlchemy.
```
Le contrat de l'API
ItemRead doit maintenant pouvoir être construit depuis un objet SQLAlchemy (le modèle, pas un dict)
```
```
class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True) # construit depuis un objet ORM
    id: int
    titre: str
    description: str | None
    tarif_jour: float
    disponible: bool
```
```
+ ajouter :
class ItemCreate(BaseModel):
    owner_id: int = Field(ge=1)
```


3. **`app/repositories/item.py`** : une classe `ItemRepository` qui sait récupérer un item,
   lister (avec pagination, recherche texte et filtre sur la disponibilité), ajouter et supprimer.
   **Aucun `commit()`** : relisez pourquoi dans le cours.
```
seul qui touche la base
classe qui reçoit la session et encapsule toutes les requêtes SQL pour les items
```
```
# app/repositories/item.py
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item


class ItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def list(self, *, skip: int = 0, limit: int = 20,
             search: str | None = None, available_only: bool = False) -> list[Item]:
        stmt = select(Item).offset(skip).limit(limit)
        if search:
            stmt = stmt.where(Item.titre.ilike(f"%{search}%"))
        if available_only:
            stmt = stmt.where(Item.disponible.is_(True))
        return list(self.db.scalars(stmt))

    def add(self, item: Item) -> Item:
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item: Item) -> None:
        self.db.delete(item)
```

4. **`app/services/item.py`** : une classe `ItemService` qui s'appuie sur le repository et lève
   l'exception « introuvable » quand l'item n'existe pas. Pas d'autre règle pour l'instant
   (l'ownership viendra en séance 5).

```
# app/services/item.py
from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable
from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, db: Session):
        self.repo = ItemRepository(db)

    def get_or_404(self, item_id: int) -> Item:
        item = self.repo.get(item_id)
        if item is None:
            raise RessourceIntrouvable(f"Item {item_id} introuvable")
        return item

    def create(self, data: ItemCreate) -> Item:
        item = Item(**data.model_dump())
        return self.repo.add(item)

    def list(self, *, skip=0, limit=20, search=None, available_only=False):
        return self.repo.list(skip=skip, limit=limit, search=search,
                              available_only=available_only)

    def update(self, item_id: int, data: ItemUpdate) -> Item:
        item = self.get_or_404(item_id)
        for champ, valeur in data.model_dump(exclude_unset=True).items():
            setattr(item, champ, valeur)
        return item

    def delete(self, item_id: int) -> None:
        self.repo.delete(self.get_or_404(item_id))

    def replace(self, item_id: int, data: ItemCreate) -> Item:
        item = self.get_or_404(item_id)
        for champ, valeur in data.model_dump().items():
            setattr(item, champ, valeur)
        return item
```

5. **`app/routers/items.py`** : les cinq routes du CRUD, avec `response_model` et les codes de
   statut de la séance 1. Le router ne fait que traduire : schéma en entrée, appel au service,
   schéma en sortie.
```
app/routers/items.py avant :
```
```
# app/routers/items.py
import unicodedata

from fastapi import APIRouter, HTTPException, Path, Query, Response
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])

FAKE_DB: dict[int, dict] = {}


def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1

def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")

# Route pour lister les items (filtrés et paginés)
@router.get("", response_model=list[ItemRead])
def list_items(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    disponible: bool | None = None,
):
    items = list(FAKE_DB.values())

    # Filtrer par titre (q)
    if q:
        qn = _sans_accent(q.lower())
        items = [item for item in items if qn in _sans_accent(item["titre"].lower())]

    # Filtrer par disponibilité
    if disponible is not None:
        items = [item for item in items if item["disponible"] == disponible]

    # Pagination
    return items[skip : skip + limit]


# Route pour obtenir un item spécifique (GET)
@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int = Path(ge=1)):
    item = FAKE_DB.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    return item


# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    new_id = _next_id()
    item = {"id": new_id, **payload.model_dump()}
    FAKE_DB[new_id] = item
    return item


# Route pour remplacer un item (PUT)
@router.put("/{item_id}", response_model=ItemRead)
def update_item(payload: ItemCreate, item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    FAKE_DB[item_id] = {"id": item_id, **payload.model_dump()}
    return FAKE_DB[item_id]


# Route pour mettre à jour partiellement un item (PATCH)
@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(payload: ItemUpdate, item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    data = payload.model_dump(exclude_unset=True)
    FAKE_DB[item_id].update(data)
    return FAKE_DB[item_id]


# Route pour supprimer un item (DELETE)
@router.delete("/{item_id}", status_code=204, response_class=Response)
def delete_item(item_id: int = Path(ge=1)):
    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} introuvable")
    del FAKE_DB[item_id]

```
```
app/routers/items.py mis à jour :
```
```
# app/routers/items.py
from fastapi import APIRouter, Path, Query, Response

from app.api.deps import DbSession
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services.item import ItemService

router = APIRouter(prefix="/items", tags=["items"])


# Route pour lister les items (filtrés et paginés)
@router.get("", response_model=list[ItemRead])
def list_items(
    db: DbSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    disponible: bool | None = None,
):
    return ItemService(db).list(skip=skip, limit=limit, search=q, available_only=disponible)


# Route pour obtenir un item spécifique (GET)
@router.get("/{item_id}", response_model=ItemRead)
def get_item(db: DbSession, item_id: int = Path(ge=1)):
    return ItemService(db).get_or_404(item_id)


# Route pour créer un item (POST)
@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, db: DbSession = None):
    return ItemService(db).create(payload)


# Route pour remplacer un item (PUT)
@router.put("/{item_id}", response_model=ItemRead)
def update_item(payload: ItemCreate, item_id: int = Path(ge=1), db: DbSession = None):
    return ItemService(db).replace(item_id, payload)


# Route pour mettre à jour partiellement (PATCH)
@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(payload: ItemUpdate, item_id: int = Path(ge=1), db: DbSession = None):
    return ItemService(db).update(item_id, payload)


# Route pour supprimer un item (DELETE)
@router.delete("/{item_id}", status_code=204, response_class=Response)
def delete_item(item_id: int = Path(ge=1), db: DbSession = None):
    ItemService(db).delete(item_id)
    return Response(status_code=204)
```

Dans `app/main.py`, incluez le router, gardez la route `/health`, et branchez la traduction des
exceptions métier en codes HTTP. À vous de choisir entre un `try`/`except` dans chaque
route et un gestionnaire d'exceptions global. Justifiez ce choix en une
phrase dans `docs/review-migrations.md`.
```
app/main.py avant :
# app/main.py
from fastapi import FastAPI
from app.routers import items, reservations

app = FastAPI(title="GearShare API", version="0.1.0")
app.include_router(items.router)
app.include_router(reservations.router)

@app.get("/health", tags=["monitoring"])
def health() -> dict[str, str]:
    return {"status": "ok"}
```
```
app/main.py après :
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
```

```
ajustement de deps.py

# app/api/deps.py
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

DbSession = Annotated[Session, Depends(get_db)]
```


**Vérifiez** :

```bash
docker compose up -d --build
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{"owner_id": 1, "titre": "Vélo de ville", "tarif_jour": 8.5}'

curl http://localhost:8000/items
curl -i http://localhost:8000/items/9999          # attendu : 404 avec {"detail": "..."}
docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items;"
```

```
docker compose up -d --build
docker compose restart backend
curl -X POST http://localhost:8000/items -H "Content-Type: application/json" -d "{\"owner_id\": 1, \"titre\": \"Velo de ville\", \"tarif_jour\": 8.5}"
{"id":3,"titre":"Velo de ville","description":null,"tarif_jour":8.5,"disponible":true}

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl http://localhost:8000/items
[{"id":1,"titre":"Tente 3 places","description":null,"tarif_jour":12.5,"disponible":true},{"id":2,"titre":"Réchaud","description":null,"tarif_jour":4.0,"disponible":true},{"id":3,"titre":"Velo de ville","description":null,"tarif_jour":8.5,"disponible":true}]

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i http://localhost:8000/items/9999
HTTP/1.1 404 Not Found
date: Sun, 25 Oct 2026 16:14:56 GMT
server: uvicorn
content-length: 34
content-type: application/json

{"detail":"Item 9999 introuvable"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items;"
 id | owner_id |     titre      | description | tarif_jour | disponible |          created_at
----+----------+----------------+-------------+------------+------------+-------------------------------
  1 |        1 | Tente 3 places |             |      12.50 | t          | 2026-10-25 13:21:36.869958+00
  2 |        1 | Réchaud        |             |       4.00 | t          | 2026-10-25 13:21:36.869958+00
  3 |        1 | Velo de ville  |             |       8.50 | t          | 2026-10-25 16:13:40.62159+00
(3 rows)
```

La dernière commande est celle qui compte : **la donnée est-elle réellement en base ?
```
Oui car le SELECT le montre. On a bien les objets. le backend ne fait plus que lire/écrire dans PostgreSQL, il n'est plus le détenteur des données.
```

** Redémarrez
ensuite tout et refaites un `GET /items` : les données doivent survivre.

```bash
docker compose restart
curl http://localhost:8000/items
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose restart
[+] Restarting 3/3
 ✔ Container projet-gearshare-backend-1   Started                                                                                          1.1s
 ✔ Container projet-gearshare-db-1        Started                                                                                          1.0s
 ✔ Container projet-gearshare-frontend-1  Started                                                                                          1.2s

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl http://localhost:8000/items
[{"id":1,"titre":"Tente 3 places","description":null,"tarif_jour":12.5,"disponible":true},{"id":2,"titre":"Réchaud","description":null,"tarif_jour":4.0,"disponible":true},{"id":3,"titre":"Velo de ville","description":null,"tarif_jour":8.5,"disponible":true}]
```
```
Les données survivent au redémarrage complet des services. La mémoire du conteneur backend est jetable et recréée ; l'état de l'application vit dans le volume de PostgreSQL, qui n'est pas affecté par un restart. C'est le changement d'architecture du TP : le backend est devenu sans état (stateless), la base est la seule source de vérité.
```
Revenez enfin sur le point de contrôle de l'étape 1 : provoquez une erreur après un ajout (par
exemple un `POST` avec un `owner_id` qui n'existe pas) et vérifiez en base que rien n'a été écrit.
Quel code HTTP obtenez-vous ? Est-ce le bon ? Si c'est une `500`, demandez-vous quelle couche
devrait détecter ce cas.
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/items -H "Content-Type: application/json" -d "{\"owner_id\": 999, \"titre\": \"Item fantome\", \"tarif_jour\": 5}"
HTTP/1.1 500 Internal Server Error
date: Sun, 25 Oct 2026 16:23:36 GMT
server: uvicorn
content-length: 21
content-type: text/plain; charset=utf-8

Internal Server Error

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, titre FROM items;"
 id |     titre
----+----------------
  1 | Tente 3 places
  2 | Réchaud
  3 | Velo de ville
(3 rows)

```
services/item.py

    # def create(self, data: ItemCreate) -> Item:
    #     item = Item(**data.model_dump())
    #     return self.repo.add(item)
    def create(self, data: ItemCreate) -> Item:
        if self.repo.db.get(User, data.owner_id) is None:
            raise RessourceIntrouvable(f"Utilisateur {data.owner_id} introuvable")
        item = Item(**data.model_dump())
        return self.repo.add(item)
```
Ce n'est pas le bon code. Une 500 signifie "le serveur a un bug", alors que le client a envoyé une référence invalide. Le rollback protège les données, mais le code de retour est faux.

Quelle couche doit détecter ce cas ?

Le service : c’est lui qui porte les règles métier ("le propriétaire doit exister"). Le repository ne fait que de l’accès aux données, et le router ne doit pas connaître SQLAlchemy.
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/items -H "Content-Type: application/json" -d "{\"owner_id\": 999, \"titre\": \"Item fantome\", \"tarif_jour\": 5}"
HTTP/1.1 404 Not Found
date: Sun, 25 Oct 2026 16:28:35 GMT
server: uvicorn
content-length: 40
content-type: application/json

{"detail":"Utilisateur 999 introuvable"}
```
---

## Étape 5 — Débusquer un N+1

Mettez `SQL_ECHO=true` dans votre `.env` et redémarrez le backend.

```
docker compose up -d backend
```

Faites évoluer la représentation d'un item pour qu'elle inclue son propriétaire (la page liste du
frontend pourra l'afficher). Pas de nouvelle route : c'est la ressource `items` qui s'enrichit, et
`GET /items` renvoie désormais un champ `owner` en plus.

Pour cela, créez un petit schéma de lecture du propriétaire, limité à son identifiant et à son nom
affiché, et ajoutez-le comme champ du schéma de lecture d'un item. Ce schéma ne doit contenir **ni
`email` ni `password_hash`** : n'exposez jamais un utilisateur complet dans la représentation
d'une autre ressource.

```
# app/schemas/user.py

from pydantic import BaseModel, ConfigDict


class OwnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str
```
```
Dans app/schemas/item.py, ajoutez le champ à ItemRead

from app.schemas.user import OwnerRead

class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    titre: str
    description: str | None
    tarif_jour: float
    disponible: bool
    owner: OwnerRead
```


Insérez une vingtaine d'items en une seule commande SQL (indice : `INSERT ... SELECT` avec
`generate_series`), appelez `GET /items?limit=50`, et **comptez les requêtes SQL dans les logs** :

```
docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO users (email, password_hash, display_name) SELECT 'user' || g || '@example.com', 'x', 'User ' || g FROM generate_series(1, 20) AS g;"
docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO items (owner_id, titre, tarif_jour, disponible) SELECT id, 'Objet ' || id, 5 + id, true FROM users WHERE email LIKE 'user%@example.com';"
```

```bash
curl -s "http://localhost:8000/items?limit=50" > /dev/null
docker compose logs --since 30s backend | grep -c "SELECT"
```

```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -s "http://localhost:8000/items?limit=50" > NUL

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose logs --since 5s backend | find /c "SELECT"
22
```


Combien de requêtes pour une seule page ? D'où viennent-elles ? Le N+1 est ici caché dans la
sérialisation : trouvez quelle ligne de votre code le déclenche, sans que vous ayez écrit de
boucle. Corrigez-le dans la méthode de liste de `ItemRepository` (le cours vous donne l'option de
chargement à utiliser), puis recomptez.

```
23 items pour 21 propriétaires distincts (Bob en a 3, partagés par la mémoïsation de l’identity map), 
-> 1 requête sur items (la liste)
+ 21 requêtes SELECT FROM users WHERE users.id = ...
(une par propriétaire distinct) 
= 22 requêtes
```
```
Où est le N+1 ? Dans la sérialisation, pas dans une boucle : FastAPI valide chaque Item avec ItemRead, et pour remplir le champ owner, Pydantic lit item.owner. Cet accès déclenche un chargement paresseux (lazy="select", valeur par défaut) : un SELECT users.* WHERE users.id = ? par propriétaire. La ligne coupable est donc owner: OwnerRead dans ItemRead. Dans les logs, on reconnaît le motif : une requête sur items, puis une série de SELECT ... FROM users WHERE users.id = %(pk_1)s.
```

```
correction : dans ItemRepository.list

    def list(self, *, skip: int = 0, limit: int = 20,
             search: str | None = None, available_only: bool = False) -> list[Item]:
        # stmt = select(Item).offset(skip).limit(limit)
        stmt = select(Item).options(joinedload(Item.owner)).offset(skip).limit(limit)
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -s "http://localhost:8000/items?limit=50" > NUL

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose logs --since 5s backend | find /c "SELECT"
1
```
```
vec joinedload(Item.owner), on dit à SQLAlchemy "charge les propriétaires dès la requête initiale". 
Il émet un seul SELECT avec un JOIN entre items et users. Quand Pydantic lit item.owner, l’objet est déjà là donc pas besoin de requête.
Donc il émet une seule requête.
```
```
On remet SQL_ECHO=false dans .env
docker compose up -d backend
```

Notez les deux chiffres, avant et après, dans `docs/review-migrations.md` (ou un
`docs/notes-perf.md`).

> N'oubliez pas de remettre `SQL_ECHO=false` avant de rendre : les logs SQL en continu sont
> inexploitables, et en production ils peuvent contenir des données personnelles.

---

## Étape 6 — Compose à trois services et migrations au démarrage

### 6.1. Les trois services

Complétez le `docker-compose.yml` :

- le service `db` reçoit ses identifiants par substitution depuis le `.env`, stocke ses données
  dans un volume nommé, et expose un `healthcheck` ;
- le service `backend` reçoit `env_file: .env` et n'attend pas seulement que la base soit
  démarrée, mais qu'elle soit **prête** ;
- le service `frontend` reste celui du TP 1 : **pas de `env_file`**, il n'a besoin que de
  `API_BASE_URL` (relisez pourquoi dans le [cours 1](../cours/cours1-frontend.md)).

```
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app
      - ./backend/tests:/code/tests
      - ./backend/alembic:/code/alembic
      - ./backend/alembic.ini:/code/alembic.ini
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    environment:
      - API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    ports:
      - "8080:8080"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

volumes:
  pgdata:
```

### 6.2. Votre choix : comment appliquer les migrations ?

Jusqu'ici, vous lanciez `alembic upgrade head` à la main. Sur votre rendu, je ferai `git clone`,
`cp .env.example .env`, `docker compose up`, et rien d'autre : les migrations doivent donc
s'appliquer **toutes seules**, avant que l'API ne reçoive sa première requête.

Le cours présente deux approches. **C'est à votre groupe de choisir**, et de justifier :

| | Option 1 : `entrypoint.sh` | Option 2 : service `migrate` |
|---|---|---|
| Où vit la commande | Dans l'image du backend, exécutée avant `uvicorn` | Dans un service Compose dédié, construit depuis la même image |
| Ce qui attend quoi | Le backend attend la base | `migrate` attend la base, le backend attend la fin de `migrate` |
| Ce que vous devez écrire | Un script shell, et le `Dockerfile` qui l'utilise | Un service de plus, et la bonne `condition` dans `depends_on` |

Avant de trancher, répondez par écrit, dans `docs/choix-migrations.md`, à ces questions :

1. Que se passe-t-il au **deuxième** `docker compose up`, quand la base est déjà à jour ?
2. Si une migration échoue, que voit-on dans `docker compose ps` et dans les logs ? Le backend
   démarre-t-il quand même ?
3. En production, que se passerait-il si trois instances du backend démarraient en même temps
   sur une base pas encore migrée ? (Inutile de le tester en local : le port `8000` publié
   empêche de lancer plusieurs instances.)
4. Votre backend tourne en `--reload` pendant le développement : votre option fonctionne-t-elle
   toujours ?

Puis écrivez votre choix et sa justification en quelques lignes. Il n'y a pas de mauvaise
réponse, il y a des réponses non justifiées.

```
docker-compoes.yml : le service migrate doit avoir depends_on: db: condition: service_healthy (attendre que la base soit prête), et le backend doit avoir depends_on: migrate: condition: service_completed_successfully.
```
```
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
  
  migrate:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend/alembic:/code/alembic
      - ./backend/alembic.ini:/code/alembic.ini
    command: alembic upgrade head
    restart: "no"

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app
      - ./backend/tests:/code/tests
      - ./backend/alembic:/code/alembic
      - ./backend/alembic.ini:/code/alembic.ini
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    environment:
      - API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    ports:
      - "8080:8080"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

volumes:
  pgdata:
```

```
sur le dépôt cloné par le correcteur, l’image doit être autonome, sans dépendre des montages
Dockerfile : ajouter COPY alembic.ini . et COPY alembic ./alembic
```
```
FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
COPY pytest.ini .
COPY tests/ ./tests/

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```


### 6.3. Vérifiez depuis zéro

```bash
docker compose down -v          # ⚠️ supprime aussi le volume : la base repart vide
docker compose up --build
```

```
docker compose down -v
docker compose up --build -d
```

```
db-1  | 2026-10-26 09:22:27.603 UTC [1] LOG:  database system is ready to accept connections
migrate-1  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
migrate-1  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
migrate-1  | INFO  [alembic.runtime.migration] Running upgrade  -> 5e526ec40fdd, schema initial
migrate-1 exited with code 0
backend-1  | INFO:     Will watch for changes in these directories: ['/code']
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
backend-1  | INFO:     Started reloader process [1] using WatchFiles
frontend-1  | INFO:     Will watch for changes in these directories: ['/code']
frontend-1  | INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
frontend-1  | INFO:     Started reloader process [1] using WatchFiles
frontend-1  | INFO:     Started server process [8]
frontend-1  | INFO:     Waiting for application startup.
frontend-1  | INFO:     Application startup complete.
backend-1   | INFO:     Started server process [8]
backend-1   | INFO:     Waiting for application startup.
backend-1   | INFO:     Application startup complete.
```

Un seul `up` doit : démarrer Postgres, attendre qu'il soit prêt, appliquer les migrations, démarrer
l'API, démarrer le frontend. Regardez l'ordre des lignes dans les logs pour le confirmer, puis :

```bash
docker compose ps -a
docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM alembic_version;"
```

```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose ps -a
NAME                          IMAGE                       COMMAND                  SERVICE    CREATED          STATUS                      PORTS
projet-gearshare-backend-1    projet-gearshare-backend    "uvicorn app.main:ap…"   backend    38 seconds ago   Up 30 seconds               0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
projet-gearshare-db-1         postgres:16                 "docker-entrypoint.s…"   db         2 minutes ago    Up 37 seconds (healthy)     5432/tcp
projet-gearshare-frontend-1   projet-gearshare-frontend   "uvicorn app.main:ap…"   frontend   38 seconds ago   Up 30 seconds               0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
projet-gearshare-migrate-1    projet-gearshare-migrate    "alembic upgrade head"   migrate    39 seconds ago   Exited (0) 30 seconds ago
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM alembic_version;"
 version_num
--------------
 5e526ec40fdd
(1 row)
```

Si vous devez lancer plusieurs commandes dans le bon ordre pour que ça marche, ce n'est pas fini.

### 6.4. Le frontend sur la vraie base

Ouvrez le frontend sur `http://localhost:8080` et refaites le parcours du TP 1 : liste, détail,
création d'un item.

- La **liste** et le **détail** fonctionnent sans modification du frontend : le contrat de lecture
  n'a pas changé (ou presque : regardez comment s'affiche `tarif_jour`, devenu un `Numeric`).
- La **création** échoue avec un message « owner_id : Field required ». Le contrat a changé : un
  item a désormais un propriétaire. Votre frontend du TP 1 affiche proprement l'erreur `422` du
  backend, c'est exactement ce qu'on attendait de lui.

Corrigez de façon **provisoire** : insérez un utilisateur de démonstration en base, puis faites
envoyer `owner_id` par le frontend, en le fixant dans la route de création.

```bash
docker compose exec db psql -U gearshare -d gearshare \
  -c "INSERT INTO users (email, display_name, password_hash) VALUES ('demo@esiee.fr', 'Démo', 'x');"
```

```bash
docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO users (email, display_name, password_hash) VALUES ('demo@esiee.fr', 'Démo', 'x');"
docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, email FROM users;"
```
```
Dans le frontend on ajoute owner_id en dur
Dans routers/items.py dans la route POST /items

    data = {
        **valeurs, 
        "description": description or None, # "" -> absence de description
        "owner_id": 1,  # TODO séance 5
    }  
```
```bash
docker compose up -d --build frontend
```


Marquez cette valeur d'un commentaire `# TODO séance 5` : en séance 5, le propriétaire sera
l'utilisateur connecté, déduit du jeton par le backend, et ce champ disparaîtra du formulaire.

Enfin, redémarrez tout (`docker compose restart`) et rechargez la liste : **les items sont toujours
là**. C'est la différence avec l'étape 6 du TP 1.

```bash
docker compose restart
```

Notez dans `docs/review-migrations.md` chaque modification que vous avez dû faire dans
`frontend/`, et le changement de contrat qui l'a provoquée.

---

## Étape 7 — La verticale `reservations`

Vous avez construit `items` couche par couche. Construisez maintenant `reservations` de la même
façon, en suivant **exactement** l'architecture de `items` : mêmes conventions de nommage, même
découpage, mêmes exceptions métier. Le modèle `Reservation` existe déjà (étape 2).

```
remplacer l'ancien schemas/reservation.py

# app/schemas/reservation.py
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

par :
```
```
# app/schemas/reservation.py
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReservationCreate(BaseModel):
    item_id: int = Field(ge=1)
    borrower_id: int = Field(ge=1)
    date_debut: date
    date_fin: date

    @model_validator(mode="after")
    def dates_coherentes(self):
        if self.date_fin <= self.date_debut:
            raise ValueError("date_fin doit être postérieure à date_debut")
        return self


class ReservationUpdate(BaseModel):
    statut: Literal["annulee"]


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: int
    borrower_id: int
    date_debut: date
    date_fin: date
    statut: str
```



```
# app/repositories/user.py
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)
```
```
Ajouter dans # app/repositories/reservation.py
    def list(self, *, skip: int = 0, limit: int = 20,
             item_id: int | None = None) -> list[Reservation]:
        stmt = select(Reservation).order_by(Reservation.id).offset(skip).limit(limit)
        if item_id is not None:
            stmt = stmt.where(Reservation.item_id == item_id)
        return list(self.db.scalars(stmt))
```

```

Remplacer l'ancien services/reservation.py

# app/services/reservation.py
from datetime import date

from app.core.exceptions import ConflitReservation, RessourceIntrouvable
from app.models.reservation import Reservation
from app.repositories.item import ItemRepository
from app.repositories.reservation import ReservationRepository


class ReservationService:
    def __init__(self, reservations: ReservationRepository, items: ItemRepository) -> None:
        self.reservations = reservations
        self.items = items

    def creer(self, *, item_id: int, borrower_id: int, debut: date, fin: date) -> Reservation:
        item = self.items.get(item_id)
        if item is None:
            raise RessourceIntrouvable(f"Item {item_id} introuvable")
        if item.owner_id == borrower_id:
            raise ConflitReservation("Vous ne pouvez pas réserver votre propre matériel")
        if not item.disponible:
            raise ConflitReservation("Ce matériel n'est pas disponible")
        if self.reservations.find_chevauchements(item_id, debut, fin):
            raise ConflitReservation("Ce créneau est déjà réservé")

        return self.reservations.add(
            Reservation(item_id=item_id, borrower_id=borrower_id,
                        date_debut=debut, date_fin=fin, statut="active")
        )

par :
```
```
# app/services/reservation.py
from sqlalchemy.orm import Session

from app.core.exceptions import ConflitReservation, RessourceIntrouvable
from app.models.reservation import Reservation
from app.repositories.item import ItemRepository
from app.repositories.reservation import ReservationRepository
from app.repositories.user import UserRepository
from app.schemas.reservation import ReservationCreate


class ReservationService:
    def __init__(self, db: Session) -> None:
        self.repo = ReservationRepository(db)
        self.items = ItemRepository(db)
        self.users = UserRepository(db)

    def get_or_404(self, reservation_id: int) -> Reservation:
        reservation = self.repo.get(reservation_id)
        if reservation is None:
            raise RessourceIntrouvable(f"Réservation {reservation_id} introuvable")
        return reservation

    def list(self, *, skip: int = 0, limit: int = 20, item_id: int | None = None):
        return self.repo.list(skip=skip, limit=limit, item_id=item_id)

    def create(self, data: ReservationCreate) -> Reservation:
        item = self.items.get(data.item_id)
        if item is None:
            raise RessourceIntrouvable(f"Item {data.item_id} introuvable")
        if self.users.get(data.borrower_id) is None:
            raise RessourceIntrouvable(f"Utilisateur {data.borrower_id} introuvable")
        if not item.disponible:
            raise ConflitReservation("Ce matériel n'est pas disponible")
        if self.repo.find_chevauchements(data.item_id, data.date_debut, data.date_fin):
            raise ConflitReservation("Ce créneau est déjà réservé")
        return self.repo.add(
            Reservation(**data.model_dump(), statut="active")
        )

    def cancel(self, reservation_id: int) -> Reservation:
        reservation = self.get_or_404(reservation_id)
        if reservation.statut != "active":
            raise ConflitReservation("Seule une réservation active peut être annulée")
        reservation.statut = "annulee"
        return reservation
```
```
remplacer l'ancien routers/reservations.py

# app/routers/reservations.py
from fastapi import APIRouter, HTTPException, Path, Query
from datetime import date
from typing import Optional
from app.schemas.reservation import ReservationCreate, ReservationRead

router = APIRouter(prefix="/reservations", tags=["reservations"])

FAKE_DB: dict[int, dict] = {}
def _next_id() -> int:
    return max(FAKE_DB, default=0) + 1

@router.post("", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate):
    new_id = _next_id()
    reservation = {
        "id": new_id,
        "statut": "active",
        **payload.model_dump(),
    }
    FAKE_DB[new_id] = reservation
    return reservation

@router.get("", response_model=list[ReservationRead])
def list_reservations(
    item_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    reservations = list(FAKE_DB.values())
    if item_id:
        reservations = [r for r in reservations if r["item_id"] == item_id]
    return reservations[:limit]

@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: int = Path(ge=1)):
    if reservation_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    return FAKE_DB[reservation_id]

@router.post("/{reservation_id}/annuler", response_model=ReservationRead)
def cancel_reservation(reservation_id: int = Path(ge=1)):
    if reservation_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if FAKE_DB[reservation_id]["statut"] == "annulee":
        raise HTTPException(status_code=409, detail="Réservation déjà annulée")
    FAKE_DB[reservation_id]["statut"] = "annulee"
    return FAKE_DB[reservation_id]

par :
```
```
# app/routers/reservations.py
from fastapi import APIRouter, Path, Query

from app.api.deps import DbSession
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate
from app.services.reservation import ReservationService

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", response_model=ReservationRead, status_code=201)
def create_reservation(payload: ReservationCreate, db: DbSession):
    return ReservationService(db).create(payload)


@router.get("", response_model=list[ReservationRead])
def list_reservations(
    db: DbSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    item_id: int | None = Query(default=None, ge=1),
):
    return ReservationService(db).list(skip=skip, limit=limit, item_id=item_id)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(db: DbSession, reservation_id: int = Path(ge=1)):
    return ReservationService(db).get_or_404(reservation_id)


@router.patch("/{reservation_id}", response_model=ReservationRead)
def patch_reservation(payload: ReservationUpdate, db: DbSession,
                      reservation_id: int = Path(ge=1)):
    # le schéma n'autorise que "annulee" : toute autre valeur donne un 422
    return ReservationService(db).cancel(reservation_id)
```


### 7.1. Le contrat

Routes attendues :

| Méthode et chemin | Rôle | Codes attendus |
|---|---|---|
| `POST /reservations` | Créer une réservation | `201`, `404`, `409`, `422` |
| `GET /reservations` | Lister, filtrable par `item_id`, paginé | `200` |
| `GET /reservations/{id}` | Détail | `200`, `404` |
| `PATCH /reservations/{id}` | Annuler, avec le corps `{"statut": "annulee"}` | `200`, `404`, `409` |

### 7.2. Les règles métier

Elles vivent toutes dans le service, et nulle part ailleurs :

- l'item doit exister, sinon « introuvable » ;
- l'item doit être disponible, sinon « conflit » ;
- aucune réservation **active** de cet item ne doit chevaucher le créneau demandé, sinon
  « conflit » ;
- on ne peut annuler qu'une réservation au statut `active`, sinon « conflit ».

La détection de chevauchement est une requête : elle va donc dans le repository, et le service
l'appelle. Avant de l'écrire, dessinez sur papier les cinq cas de figure entre un créneau existant
et un créneau demandé : **avant**, **après**, **chevauchement partiel au début**, **chevauchement
partiel à la fin**, **englobant**. Puis trouvez la condition la plus simple qui renvoie « vrai »
exactement pour les trois cas de conflit. Indice : elle tient en deux comparaisons, et il est plus
facile de raisonner sur les cas où il n'y a **pas** de conflit.

Décidez aussi, et notez-le : deux réservations jointives (l'une finit le jour où l'autre commence)
sont-elles en conflit ? Votre requête doit refléter cette décision.

```
Les jointives ne sont pas en conflit.
Le CHECK date_fin > date_debut impose au moins un jour d'écart, donc une réservation d'un jour est 2026-11-10 -> 2026-11-11. Cela revient à un un intervalle semi-ouvert [debut, fin[ : date_fin est le jour de restitution, pas un jour d’utilisation. Si date_fin était inclusive, une location d’un jour serait debut == fin, ce que la contrainte interdit. La requête est donc date_debut < fin AND date_fin > debut, avec des inégalités strictes
```


### 7.3. Vérifiez

Écrivez dans `docs/cas-tests-chevauchement.md` les cinq cas de figure (plus le cas jointif), avec
pour chacun le créneau existant, le créneau demandé et le code attendu. Puis rejouez-les un par un
depuis `http://localhost:8000/docs` ou avec `curl`, et notez le résultat obtenu. Ce fichier est
votre plan de tests pour le service : le cours 2 montre comment l'automatiser avec
`parametrize` sur la base de test.

Contrôlez aussi la migration : si votre modèle `Reservation` a évolué depuis le schéma initial,
générez une migration, relisez-la et testez son `downgrade()`.

```
docker compose exec db psql -U gearshare -d gearshare -c "INSERT INTO users (email, password_hash, display_name) VALUES ('alice@example.com', 'x', 'Alice') RETURNING id;"
```
```
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-01\", \"date_fin\": \"2026-11-05\"}"
HTTP/1.1 201 Created
date: Mon, 26 Oct 2026 12:01:22 GMT
server: uvicorn
content-length: 104
content-type: application/json

{"id":3,"item_id":1,"borrower_id":2,"date_debut":"2026-11-01","date_fin":"2026-11-05","statut":"active"}

C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-08\", \"date_fin\": \"2026-11-12\"}"
HTTP/1.1 409 Conflict
date: Mon, 26 Oct 2026 12:02:58 GMT
server: uvicorn
content-length: 45
content-type: application/json

{"detail":"Ce créneau est déjà réservé"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-13\", \"date_fin\": \"2026-11-18\"}"
HTTP/1.1 409 Conflict
date: Mon, 26 Oct 2026 12:03:32 GMT
server: uvicorn
content-length: 45
content-type: application/json

{"detail":"Ce créneau est déjà réservé"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-05\", \"date_fin\": \"2026-11-20\"}"
HTTP/1.1 409 Conflict
date: Mon, 26 Oct 2026 12:04:32 GMT
server: uvicorn
content-length: 45
content-type: application/json

{"detail":"Ce créneau est déjà réservé"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-15\", \"date_fin\": \"2026-11-20\"}"
HTTP/1.1 201 Created
date: Mon, 26 Oct 2026 12:05:16 GMT
server: uvicorn
content-length: 104
content-type: application/json

{"id":5,"item_id":1,"borrower_id":2,"date_debut":"2026-11-15","date_fin":"2026-11-20","statut":"active"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>curl -i -X POST http://localhost:8000/reservations -H "Content-Type: application/json" -d "{\"item_id\": 1, \"borrower_id\": 2, \"date_debut\": \"2026-11-20\", \"date_fin\": \"2026-11-25\"}"
HTTP/1.1 201 Created
date: Mon, 26 Oct 2026 12:05:53 GMT
server: uvicorn
content-length: 104
content-type: application/json

{"id":6,"item_id":1,"borrower_id":2,"date_debut":"2026-11-20","date_fin":"2026-11-25","statut":"active"}
C:\dev\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec db psql -U gearshare -d gearshare -c "SELECT id, item_id, date_debut, date_fin, statut FROM reservations;"
 id | item_id | date_debut |  date_fin  | statut
----+---------+------------+------------+--------
  2 |       1 | 2026-11-10 | 2026-11-15 | active
  3 |       1 | 2026-11-01 | 2026-11-05 | active
  4 |       1 | 2026-11-05 | 2026-11-10 | active
  5 |       1 | 2026-11-15 | 2026-11-20 | active
  6 |       1 | 2026-11-20 | 2026-11-25 | active
(5 rows)
```
```
docker compose run --rm backend alembic revision --autogenerate -m "verif reservations"
[+] Creating 1/1
 ✔ Container projet-gearshare-db-1  Running                                                                                                                   0.0s
[+] Running 2/2
 ✔ Container projet-gearshare-db-1       Healthy                                                                                                              0.5s
 ✔ Container projet-gearshare-migrate-1  Started                                                                                                              0.3s
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.tables
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
INFO  [alembic.ddl.postgresql] Detected sequence named 'items_id_seq' as owned by integer column 'items(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'reservations_id_seq' as owned by integer column 'reservations(id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'users_id_seq' as owned by integer column 'users(id)', assuming SERIAL and omitting
  Generating /code/alembic/versions/a23565de091c_verif_reservations.py ...  done
```
```
pas d'évolution du modèle :
def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
```



### 7.4. Relisez

Échangez votre verticale `reservations` avec un autre binôme de votre groupe (ou relisez-la vous-
même le lendemain, à froid), et remplissez `docs/review-couches.md` :

| Point de contrôle | OK / KO | Ce que j'ai corrigé/Notes perso |
|---|---|---|
| Aucun SQL ni requête SQLAlchemy dans le router | OK | routers/reservations.py ne contient pas "select sqlalchemy Session execute query" |
| Aucune `HTTPException` dans le service (uniquement les exceptions métier) | OK | pas de "HTTPException" dans services/* |
| Aucun `commit()` dans le repository | OK | pas de "commit" dans repositories/*, le commit vit uniquement dans app/api/deps.py (get_db) |
| `response_model` sur les 4 routes | OK | 4 occurrences de "response_model=" dans routers/reservations.py (POST, GET liste, GET détail, PATCH). Dans /docs chaque route affiche un schéma de réponse. |
| Schéma de lecture construit depuis l'objet SQLAlchemy, sans champ interne | OK | ReservationRead a "from_attributes=True" dans schemas/reservation.py. Ses champs sont id, item_id, borrower_id, date_debut, date_fin, statut. http://localhost:8000/reservations n'expose que ces champs. | 
| La requête de chevauchement couvre les cinq cas, y compris l'englobant | OK | find_chevauchements de app/repositories/reservation.py est correct et les cas de tests montrent 409 pour partiel début, partiel fin, englobant (et contenu), 201 pour avant, après, jointifs. | 
| Pas de f-string dans une requête SQL | OK | Seul ilike(f"%{search}%") d’ItemRepository.list reste. La valeur n'est pas du SQL concaténé mais c'est un paramètre lié. |
| Pas de N+1 sur `GET /reservations` (si la relation `item` est chargée) | OK | dans le schéma ReservationRead ne contient aucune relation imbriquée (item, borrower). On a testé lorsqu'on a mis SQL_ECHO=true |
| Migration relue, `downgrade()` testé | OK | |
| Aucune dépendance ajoutée sans justification | KO | j'ai retiré alembic en doublon |

Sur la requête de chevauchement, soyez exigeants : c'est l'erreur la plus fréquente de ce TP. Une
condition qui teste seulement « le début demandé tombe dans un créneau existant » rate le cas où
la nouvelle réservation **englobe** complètement une réservation existante.

### 7.5. Le frontend

La page de détail d'un item, écrite au TP 1, doit toujours permettre de réserver et d'annuler.
Mais le backend renvoie maintenant `409` pour un créneau déjà pris ou un item indisponible, et
votre frontend ne savait gérer que le `422` : ajoutez le `409` aux erreurs affichées sur le
formulaire de réservation (le cours 1 montre comment). Vérifiez dans le navigateur
qu'une réservation en conflit affiche un message clair, et non une page d'erreur.

```
Dans le frontend, le contrat a changé
une réservation est faite par quelqu'un
le backend exige un borrower_id
api_client

def create_reservation(self, item_id: int, date_debut: date, date_fin: date) -> dict[str, Any]:
        return self._send(
            "POST",
            "/reservations",
            json={"item_id": item_id, "date_debut": date_debut.isoformat(), "date_fin": date_fin.isoformat()},
        )

devient :

    def create_reservation(self, item_id: int, date_debut: date, date_fin: date) -> dict[str, Any]:
        return self._send(
            "POST",
            "/reservations",
            json={
                "item_id": item_id,
                "date_debut": date_debut.isoformat(),
                "date_fin": date_fin.isoformat(),
                "borrower_id": 2,  # TODO séance 5 : déduit du jeton
            },
        )


```
```
Ajouter le 409 au formulaire de réservation
create_reservation_page dans le routeur frontend de reservation

try:
        api_client.create_reservation(item_id, date_debut, date_fin)
    except ApiError as exc:
        if exc.status_code != 422:
            raise
        return render_item_detail(
            request,
            item_id,
            erreurs=exc.messages(),
            valeurs={"date_debut": date_debut, "date_fin": date_fin},
            status_code=422,
        )
    return RedirectResponse(f"/items/{item_id}?message=reservee", status_code=303)

devient 

    try:
        api_client.create_reservation(item_id, date_debut, date_fin)
    except ApiError as exc:
        if exc.status_code not in (409, 422):
            raise
        return render_item_detail(
            request,
            item_id,
            erreurs=exc.messages(),
            valeurs={"date_debut": date_debut, "date_fin": date_fin},
            status_code=exc.status_code,
        )
    return RedirectResponse(f"/items/{item_id}?message=reservee", status_code=303)

```
---

## Ce que vous devez me rendre à la fin du TP 2

Sur le dépôt Git de votre projet :

1. **`docker compose up` fonctionne depuis un clone propre** : `git clone`,
   `cp .env.example .env`, `docker compose up` → API sur `:8000`, frontend sur `:8080`, base
   migrée automatiquement et accessible.
2. **Le backend en couches** : `models/`, `schemas/`, `repositories/`, `services/`, `routers/`,
   avec au moins les ressources `items` et `reservations` complètes.
3. **Les migrations Alembic** dans `alembic/versions/`, avec un `downgrade()` testé.
4. **`.env.example` commité, `.env` absent du dépôt.** Je vérifierai l'historique Git.
5. **Le frontend du TP 1 branché sur la base** : liste, détail, création d'un item, réservation et
   annulation, avec des données qui survivent à un redémarrage.
6. **`docs/choix-migrations.md`** : vos réponses aux quatre questions de l'étape 6.2, votre choix
   (`entrypoint.sh` ou service `migrate`) et sa justification.
7. **`docs/review-couches.md`** : la review de la verticale `reservations`, avec les corrections
   apportées.
8. **`docs/review-migrations.md`** : ce que vous avez observé sur le renommage de colonne, votre
   choix de traduction des exceptions, le N+1 (les deux chiffres avant/après), et les
   modifications imposées au frontend par les changements de contrat.
9. **`docs/cas-tests-chevauchement.md`** : les cas de chevauchement, le code attendu et le
   résultat obtenu.

## Pour aller plus loin

- **Branchez votre suite de la séance 2 sur la base de test** : créez `gearshare_test`, ajoutez les
  fixtures `engine`, `db` et `client` du cours 2, remplacez la remise à zéro en
  mémoire par la transaction annulée, et vérifiez que vos tests de contrat de la séance 2 passent
  **sans modification**. Puis automatisez `docs/cas-tests-chevauchement.md` en un test paramétré
  sur `ReservationService`. C'est le premier chantier de la séance 5, autant prendre de l'avance.
- Implémentez **l'autre** option de migration que celle choisie à l'étape 6, sur une branche, et
  comparez le comportement sur les quatre questions.
- Écrivez un script `seed.py` qui peuple la base de données de démonstration, et branchez-le sur
  une commande `docker compose run --rm backend python -m app.seed`.
- Mettez en place un middleware qui logue la durée de chaque requête, et repérez la route la plus
  lente.
