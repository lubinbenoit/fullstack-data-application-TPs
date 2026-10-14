-- =============================================================
-- Tests : chaque INSERT doit échouer, pour la bonne raison.
-- Lire le nom de la contrainte dans le message d'erreur.
-- Pré-requis : 01-schema.sql, 02-seed.sql, 03-schema-v2.sql joués.
-- =============================================================

-- 1. Note à 6 -> doit échouer sur ck_avis_note
INSERT INTO avis (reservation_id, note, commentaire)
VALUES (1, 6, 'Trop bien, ça dépasse la note max !');
-- ERREUR: new row ... violates check constraint « ck_avis_note »

-- 2. Deux avis sur la même réservation -> doit échouer sur uq_avis_reservation
INSERT INTO avis (reservation_id, note, commentaire)
VALUES (1, 4, 'Premier avis');                    -- réussit (une seule fois !)
INSERT INTO avis (reservation_id, note)
VALUES (1, 3);                                    -- échoue
-- ERREUR: duplicate key value violates unique constraint « uq_avis_reservation »

-- 3. Deux tags de même libellé -> doit échouer sur uq_tags_libelle
INSERT INTO tags (libelle) VALUES ('velo');       -- réussit
INSERT INTO tags (libelle) VALUES ('velo');       -- échoue
-- ERREUR: duplicate key value violates unique constraint « uq_tags_libelle »

-- 3b. Bonus : un tag avec majuscules -> doit échouer sur ck_tags_minuscules
INSERT INTO tags (libelle) VALUES ('Velo');
-- ERREUR: ... violates check constraint « ck_tags_minuscules »

-- 4. Avis sur une réservation inexistante -> doit échouer sur fk_avis_reservation
INSERT INTO avis (reservation_id, note)
VALUES (9999, 5);
-- ERREUR: insert or update on table « avis » violates foreign key
--         constraint « fk_avis_reservation »

-- 5. Chevauchement de réservations actives -> doit échouer sur
--    excl_reservations_item_periode
--    La réservation 2 (item 3) occupe du 10 au 12 septembre.
INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
VALUES (3, 3, '2026-09-11', '2026-09-13', 'active');
-- ERREUR: conflicting key value violates exclusion constraint
--         « excl_reservations_item_periode »

-- 5b. Contre-preuve : le même chevauchement en statut 'annulee' passe.
INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
VALUES (3, 3, '2026-09-11', '2026-09-13', 'annulee');
-- INSERT 0 1 : OK, le filtre WHERE (statut = 'active') exclut les annulées.