   Point de contrôle | OK / KO | Ce que j'ai corrigé |
 |---|---|---|
 | Chaque table a une clé primaire | OK | RAS. `avis.id`, `tags.id` en `BIGSERIAL PRIMARY KEY` ; `item_tags` en PK composite `(item_id, tag_id)`. |
 | Les clés étrangères sont déclarées avec `REFERENCES` | OK | RAS. `fk_avis_reservation → reservations(id)`, `fk_item_tags_item → items(id)`, `fk_item_tags_tag → tags(id)`. |
 | Les `ON DELETE` sont explicites et cohérents avec le métier | OK (corrigé) | Premier jet : implicites (`NO ACTION`). Corrigé en `CASCADE` : supprimer une réservation purge son avis ; supprimer un item ou un tag purge ses liens dans `item_tags`. |
 | « Un seul avis par réservation » garanti par `UNIQUE` | OK | RAS. `uq_avis_reservation UNIQUE (reservation_id)`. Preuve : test 2. |
 | La note est bornée par `CHECK (note BETWEEN 1 AND 5)` | OK | RAS. `ck_avis_note` sur `SMALLINT` (entier garanti par le type). Preuve : test 1. |
 | La table de liaison item/tag a une PK composite | OK | RAS. `pk_item_tags (item_id, tag_id)` — garantit aussi l'unicité du lien. |
 | Le libellé de tag est `UNIQUE` | OK | RAS. `uq_tags_libelle` + `ck_tags_minuscules CHECK (libelle = lower(libelle))` pour la casse. Preuves : tests 3 et 3b. |
 | Les contraintes sont nommées | OK | RAS. Toutes nommées (`fk_`, `ck_`, `uq_`, `pk_`, `excl_`) — c'est ce qui permet d'identifier la cause dans chaque message d'erreur ci-dessous. |
 | Des index existent sur les clés étrangères | OK (corrigé) | Correction principale : PostgreSQL **ne crée pas** d'index sur les FK (contrairement aux PK/UNIQUE). Ajout explicite de `idx_avis_reservation_id`, `idx_item_tags_item_id`, `idx_item_tags_tag_id`, plus les FK du schéma v1 : `idx_items_owner_id`, `idx_reservations_item_id`, `idx_reservations_borrower_id`. |
 | Le non-chevauchement garanti (contrainte) ou laissé à l'applicatif | OK | **Garanti en base** par contrainte d'exclusion — voir §3. Preuves : tests 5 et 5b. |
 | Aucun type flottant, aucun `TIMESTAMP` sans fuseau | OK | RAS. `SMALLINT` note, `TIMESTAMPTZ created_at`, `NUMERIC(8,2) tarif_jour`. |

## exécution de sql/tests-contraintes.sql

Base recréée vierge (`docker compose down -v && docker compose up -d`),
puis `psql -U gearshare -d gearshare -f sql/tests-contraintes.sql`.
6 INSERT échouent, chacun pour la bonne contrainte ; 3 INSERT de contrôle réussissent.

```text
psql:<stdin>:9:  ERROR: new row for relation "avis" violates check constraint "ck_avis_note"
psql:<stdin>:14: INSERT 0 1                          <- avis note=4 sur résa 1 : OK
psql:<stdin>:16: ERROR: duplicate key value violates unique constraint "uq_avis_reservation"
psql:<stdin>:20: INSERT 0 1                          <- tag 'velo' : OK
psql:<stdin>:21: ERROR: duplicate key value violates unique constraint "uq_tags_libelle"
psql:<stdin>:25: ERROR: new row for relation "tags" violates check constraint "ck_tags_minuscules"
psql:<stdin>:30: ERROR: insert or update on table "avis" violates foreign key constraint "fk_avis_reservation"
psql:<stdin>:38: ERROR: conflicting key value violates exclusion constraint "excl_reservations_item_periode"
psql:<stdin>:42: INSERT 0 1                          <- résa chevauchante mais 'annulee' : OK