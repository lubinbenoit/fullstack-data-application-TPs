-- =============================================================
-- GearShare — Schéma v2 : avis, tags, non-chevauchement
-- PostgreSQL 16. Joué après 01-schema.sql et 02-seed.sql.
-- =============================================================

-- Extension requise pour la contrainte d'exclusion :
-- l'opérateur = sur BIGINT n'existe pas dans GiST, btree_gist l'ajoute.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- -------------------------------------------------------------
-- 1. AVIS (note + commentaire, un seul avis par réservation)
-- -------------------------------------------------------------
CREATE TABLE avis (
    id             BIGSERIAL PRIMARY KEY,
    reservation_id BIGINT       NOT NULL,
    note           SMALLINT     NOT NULL,
    commentaire    TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_avis_reservation
        FOREIGN KEY (reservation_id) REFERENCES reservations (id)
        ON DELETE CASCADE,                       -- plus de réservation -> plus d'avis
    CONSTRAINT ck_avis_note
        CHECK (note BETWEEN 1 AND 5),
    -- La règle « un seul avis par réservation » :
    CONSTRAINT uq_avis_reservation UNIQUE (reservation_id)
);

-- Index sur la clé étrangère (PostgreSQL ne le fait pas automatiquement)
CREATE INDEX idx_avis_reservation_id ON avis (reservation_id);

-- -------------------------------------------------------------
-- 2. TAGS (libellé unique, en minuscules)
-- -------------------------------------------------------------
CREATE TABLE tags (
    id        BIGSERIAL PRIMARY KEY,
    libelle   VARCHAR(50) NOT NULL,

    CONSTRAINT uq_tags_libelle   UNIQUE (libelle),
    CONSTRAINT ck_tags_minuscules CHECK (libelle = lower(libelle))
);

-- -------------------------------------------------------------
-- 3. LIAISON item <-> tag (N-N)
-- -------------------------------------------------------------
CREATE TABLE item_tags (
    item_id BIGINT NOT NULL,
    tag_id  BIGINT NOT NULL,

    CONSTRAINT pk_item_tags PRIMARY KEY (item_id, tag_id),

    CONSTRAINT fk_item_tags_item
        FOREIGN KEY (item_id) REFERENCES items (id)
        ON DELETE CASCADE,                      -- item supprimé -> liens supprimés
    CONSTRAINT fk_item_tags_tag
        FOREIGN KEY (tag_id) REFERENCES tags (id)
        ON DELETE CASCADE                       -- tag supprimé -> liens supprimés
);

CREATE INDEX idx_item_tags_item_id ON item_tags (item_id);
CREATE INDEX idx_item_tags_tag_id  ON item_tags (tag_id);

-- -------------------------------------------------------------
-- 4. Non-chevauchement des réservations actives d'un même item
--    Garanti par la base via contrainte d'exclusion :
--    deux réservations actives du même item ne peuvent pas avoir
--    des intervalles qui se chevauchent.
--    (Uniquement les statuts 'active', via un prédicat partiel.)
-- -------------------------------------------------------------
ALTER TABLE reservations
    ADD CONSTRAINT excl_reservations_item_periode
    EXCLUDE USING gist (
        item_id WITH =,
        daterange(date_debut, date_fin) WITH &&
    ) WHERE (statut = 'active');

-- Index sur les clés étrangères manquantes du schéma v1
CREATE INDEX IF NOT EXISTS idx_items_owner_id      ON items (owner_id);
CREATE INDEX IF NOT EXISTS idx_reservations_item_id     ON reservations (item_id);
CREATE INDEX IF NOT EXISTS idx_reservations_borrower_id ON reservations (borrower_id);