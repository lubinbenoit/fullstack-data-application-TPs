CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(80)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE items (
    id          BIGSERIAL PRIMARY KEY,
    owner_id    BIGINT       NOT NULL REFERENCES users(id),
    titre       VARCHAR(120) NOT NULL,
    description TEXT,
    tarif_jour  NUMERIC(8, 2) NOT NULL CHECK (tarif_jour > 0),
    disponible  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE reservations (
    id          BIGSERIAL PRIMARY KEY,
    item_id     BIGINT NOT NULL REFERENCES items(id),
    borrower_id BIGINT NOT NULL REFERENCES users(id),
    date_debut  DATE   NOT NULL,
    date_fin    DATE   NOT NULL,
    statut      VARCHAR(20) NOT NULL DEFAULT 'active',
    CONSTRAINT dates_coherentes CHECK (date_fin > date_debut),
    CONSTRAINT statut_valide    CHECK (statut IN ('active', 'annulee', 'terminee'))
);