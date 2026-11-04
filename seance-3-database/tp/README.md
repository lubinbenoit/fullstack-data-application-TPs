# TP — Séance 3 : PostgreSQL en pratique

## Objectifs du TP

À la fin de ce TP, vous devez savoir :

- lancer PostgreSQL avec Docker Compose et vous y connecter en `psql` ;
- écrire le DDL d'un schéma relationnel avec ses contraintes ;
- constater qu'une contrainte vous protège réellement d'une donnée incohérente ;
- écrire des requêtes avec jointures, agrégats et pagination ;
- mesurer l'effet d'un index avec `EXPLAIN ANALYZE` ;

Tout se fait en SQL, **écrit par vous** : vous devez connaître cette syntaxe pour pouvoir relire
et corriger un schéma, et tout ce qui suivra. Le cours et la
[documentation PostgreSQL](https://www.postgresql.org/docs/16/) sont vos références. Pas encore de
Python : la liaison avec FastAPI est le sujet de la séance 4.

## Prérequis

- Docker Desktop lancé.

---

## Étape 0 — Lancer PostgreSQL

Créez un dossier `tp-db/` et écrivez-y un `docker-compose.yml` avec un seul service `db` :

- image `postgres:16` ;
- utilisateur, mot de passe et base : `gearshare` (variables d'environnement de l'image officielle) ;
- port `5432` exposé sur la machine ;
- un **volume nommé** pour les données ;
- le dossier local `sql/init/` monté en lecture seule sur `/docker-entrypoint-initdb.d` (les
  scripts qui s'y trouvent sont joués au premier démarrage, sur une base vide) ;
- un **healthcheck** basé sur `pg_isready`.

Le §9 du cours vous donne la structure. Créez le dossier `sql/init/` (vide pour l'instant), puis
démarrez la base et connectez-vous :

```bash
docker compose up -d
docker compose ps          # le service db doit être "healthy"
docker compose exec db psql -U gearshare -d gearshare
```

Dans `psql`, affichez la version du serveur, listez les tables (`\dt`, aucune pour l'instant) et
quittez (`\q`).

On a :
```bash
psql (16.15 (Debian 16.15-1.pgdg13+2)),
\dt
Did not find any relations.
```
> 💡 Si vous préférez un client graphique, DBeaver ou l'extension PostgreSQL de VS Code se
> connectent sur `localhost:5432`. Mais **sachez vous servir de `psql`** : sur un serveur distant,
> c'est souvent tout ce que vous aurez.

---

## Étape 1 — Créer le schéma

Créez `sql/init/01-schema.sql` avec les tables `users`, `items` et `reservations`. Le cahier des
charges :

**`users`**
- `id` : clé primaire auto-incrémentée
- `email` : obligatoire, unique, max 255 caractères
- `password_hash` : obligatoire
- `display_name` : obligatoire, max 80 caractères
- `created_at` : horodatage avec fuseau, valeur par défaut = maintenant

**`items`**
- `id` : clé primaire auto-incrémentée
- `owner_id` : obligatoire, référence `users(id)`, suppression en cascade
- `titre` : obligatoire, max 120 caractères
- `description` : optionnelle, texte libre
- `tarif_jour` : obligatoire, montant exact, strictement positif
- `disponible` : booléen, obligatoire, défaut vrai
- `created_at` : comme pour `users`

**`reservations`**
- `id` : clé primaire auto-incrémentée
- `item_id` : obligatoire, référence `items(id)`, suppression en cascade
- `borrower_id` : obligatoire, référence `users(id)` — aucun comportement de suppression
  n'est précisé : n'en ajoutez pas
- `date_debut`, `date_fin` : dates obligatoires
- `statut` : obligatoire, défaut `'active'`, uniquement parmi `active`, `annulee`, `terminee`
- une contrainte **nommée** garantissant `date_fin > date_debut`

Appliquez-le. Comme le volume existe déjà (l'étape 0 a démarré la base à vide), le script d'init
**ne se rejouera pas tout seul**. Deux options :

```bash
# Option A : repartir de zéro (le script d'init se joue)
docker compose down -v && docker compose up -d

# Option B : appliquer le fichier à chaud
docker compose exec -T db psql -U gearshare -d gearshare < sql/init/01-schema.sql
```

Faites l'option A au moins une fois : c'est le mécanisme que vous utiliserez pour le script de
seed du projet.

**Vérifiez** avec `\dt`, puis `\d items` et `\d reservations` : vous devez voir les colonnes, la
clé primaire, les contraintes `CHECK` et les clés étrangères. Si une contrainte manque, corrigez
maintenant.

```bash
gearshare=# \dt
             List of relations
 Schema |     Name     | Type  |   Owner   
--------+--------------+-------+-----------
 public | items        | table | gearshare
 public | reservations | table | gearshare
 public | users        | table | gearshare
(3 rows)

gearshare=# \d items
                                       Table "public.items"
   Column    |           Type           | Collation | Nullable |              Default              
-------------+--------------------------+-----------+----------+-----------------------------------
 id          | bigint                   |           | not null | nextval('items_id_seq'::regclass)
 owner_id    | bigint                   |           | not null | 
 titre       | character varying(120)   |           | not null | 
 description | text                     |           |          | 
 tarif_jour  | numeric(8,2)             |           | not null | 
 disponible  | boolean                  |           | not null | true
 created_at  | timestamp with time zone |           | not null | now()
Indexes:
    "items_pkey" PRIMARY KEY, btree (id)
Check constraints:
    "items_tarif_jour_check" CHECK (tarif_jour > 0::numeric)
Foreign-key constraints:
    "items_owner_id_fkey" FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
Referenced by:
    TABLE "reservations" CONSTRAINT "reservations_item_id_fkey" FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE

gearshare=# \d reservations
                                      Table "public.reservations"
   Column    |         Type          | Collation | Nullable |                 Default                  
-------------+-----------------------+-----------+----------+------------------------------------------
 id          | bigint                |           | not null | nextval('reservations_id_seq'::regclass)
 item_id     | bigint                |           | not null | 
 borrower_id | bigint                |           | not null | 
 date_debut  | date                  |           | not null | 
 date_fin    | date                  |           | not null | 
 statut      | character varying(20) |           | not null | 'active'::character varying
Indexes:
    "reservations_pkey" PRIMARY KEY, btree (id)
Check constraints:
    "dates_coherentes" CHECK (date_fin > date_debut)
    "statut_valide" CHECK (statut::text = ANY (ARRAY['active'::character varying, 'annulee'::character varying, 'terminee'::character varying]::text[]))
Foreign-key constraints:
    "reservations_borrower_id_fkey" FOREIGN KEY (borrower_id) REFERENCES users(id) ON DELETE CASCADE
    "reservations_item_id_fkey" FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
```

---

## Étape 2 — Insérer des données, et se faire refuser

Créez `sql/init/02-seed.sql`, qui insère exactement les données suivantes (les résultats attendus
aux étapes suivantes en dépendent). Les `id` sont ceux que la base doit générer, dans cet ordre.

**Utilisateurs** — mots de passe : n'importe quelle chaîne factice, ce ne sont pas encore de vrais
hashs.

| id | email | display_name |
|---|---|---|
| 1 | alice@esiee.fr | Alice |
| 2 | bob@esiee.fr | Bob |
| 3 | chloe@esiee.fr | Chloé |

**Items**

| id | propriétaire | titre | description | tarif_jour |
|---|---|---|---|---|
| 1 | Alice | Vélo de ville | Cadre alu, panier avant | 8.50 |
| 2 | Alice | Perceuse | Avec jeu de mèches | 5.00 |
| 3 | Bob | Tente 2 places | *(aucune)* | 12.00 |
| 4 | Bob | Appareil photo | Reflex + objectif 50mm | 20.00 |

**Réservations**

| id | item | emprunteur | date_debut | date_fin | statut |
|---|---|---|---|---|---|
| 1 | Vélo de ville | Bob | 2026-09-01 | 2026-09-05 | terminee |
| 2 | Tente 2 places | Alice | 2026-09-10 | 2026-09-12 | active |
| 3 | Appareil photo | Chloé | 2026-09-15 | 2026-09-20 | active |


```bash
PS C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db> docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM users;"
 id |     email      |   password_hash    | display_name |          created_at           
----+----------------+--------------------+--------------+-------------------------------
  1 | alice@esiee.fr | $pbkdf2-sha256$... | Alice        | 2026-10-07 07:54:34.199684+00
  2 | bob@esiee.fr   | $pbkdf2-sha256$... | Bob          | 2026-10-07 07:54:34.199684+00
  3 | chloe@esiee.fr | $pbkdf2-sha256$... | Chloe        | 2026-10-07 07:54:34.199684+00
(3 rows)

PS C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db> docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items;"
 id | owner_id |     titre      |       description       | tarif_jour | disponible |          created_at           
----+----------+----------------+-------------------------+------------+------------+-------------------------------
  1 |        1 | Vélo de ville  | Cadre alu, panier avant |       8.50 | t          | 2026-10-07 07:54:34.204022+00
  2 |        1 | Perceuse       | Avec jeu de mèches      |       5.00 | t          | 2026-10-07 07:54:34.204022+00
  3 |        2 | Tente 2 places |                         |      12.00 | t          | 2026-10-07 07:54:34.204022+00
  4 |        2 | Appareil photo | Reflex + objectif 50mm  |      20.00 | t          | 2026-10-07 07:54:34.204022+00
(4 rows)

PS C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db> docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM reservations;"
 id | item_id | borrower_id | date_debut |  date_fin  |  statut  
----+---------+-------------+------------+------------+----------
  1 |       1 |           2 | 2026-09-01 | 2026-09-05 | terminee
  2 |       3 |           1 | 2026-09-10 | 2026-09-12 | active
  3 |       4 |           3 | 2026-09-15 | 2026-09-20 | active
(3 rows)
```

Appliquez-le, puis **essayez délibérément de casser la base**. Écrivez une instruction pour
chacun des cas suivants, et notez le message d'erreur exact et le nom de la contrainte violée :

1. un deuxième utilisateur avec l'email `alice@esiee.fr` ;

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose down -v
[+] Running 3/3
 ✔ Container tp-db-db-1   Removed                                                                                                                      0.5s
 ✔ Network tp-db_default  Removed                                                                                                                      0.4s
 ✔ Volume tp-db_pgdata    Removed                                                                                                                      0.0s

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose up -d
[+] Running 3/3
 ✔ Network tp-db_default  Created                                                                                                                      0.1s
 ✔ Volume tp-db_pgdata    Created                                                                                                                      0.0s
 ✔ Container tp-db-db-1   Started                                                                                                                      0.9s

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM users;"
service "db" is not running

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose logs db

db-1  | 2026-10-08 14:11:17.938 UTC [63] ERROR:  duplicate key value violates unique constraint "users_email_key"
db-1  | 2026-10-08 14:11:17.938 UTC [63] DETAIL:  Key (email)=(alice@esiee.fr) already exists.
db-1  | 2026-10-08 14:11:17.938 UTC [63] STATEMENT:  INSERT INTO users (email, password_hash, display_name)
db-1  |         VALUES
db-1  |             ('alice@esiee.fr', '$pbkdf2-sha256$...', 'Alice2');
db-1  | psql:/docker-entrypoint-initdb.d/02-seed.sql:24: ERROR:  duplicate key value violates unique constraint "users_email_key"
db-1  | DETAIL:  Key (email)=(alice@esiee.fr) already exists.
```

2. un item dont le propriétaire n'existe pas (`owner_id = 999`) ;

```bash
db-1  | 2026-10-08 14:14:43.714 UTC [63] ERROR:  insert or update on table "items" violates foreign key constraint "items_owner_id_fkey"
db-1  | psql:/docker-entrypoint-initdb.d/02-seed.sql:24: ERROR:  insert or update on table "items" violates foreign key constraint "items_owner_id_fkey"
db-1  | 2026-10-08 14:14:43.714 UTC [63] DETAIL:  Key (owner_id)=(999) is not present in table "users".
db-1  | DETAIL:  Key (owner_id)=(999) is not present in table "users".
db-1  | 2026-10-08 14:14:43.714 UTC [63] STATEMENT:  INSERT INTO items (owner_id, titre, description, tarif_jour)
db-1  |         VALUES
db-1  |             (999, 'Item de 999', '', 10.00)
```

3. un item à tarif négatif ;

```bash
db-1  | psql:/docker-entrypoint-initdb.d/02-seed.sql:24: ERROR:  new row for relation "items" violates check constraint "items_tarif_jour_check"
db-1  | DETAIL:  Failing row contains (5, 1, Item a tarif négatif, , -10.00, t, 2026-10-08 14:16:01.625239+00).
db-1  | 2026-10-08 14:16:01.625 UTC [63] ERROR:  new row for relation "items" violates check constraint "items_tarif_jour_check"
db-1  | 2026-10-08 14:16:01.625 UTC [63] DETAIL:  Failing row contains (5, 1, Item a tarif négatif, , -10.00, t, 2026-10-08 14:16:01.625239+00).
db-1  | 2026-10-08 14:16:01.625 UTC [63] STATEMENT:  INSERT INTO items (owner_id, titre, description, tarif_jour)
db-1  |         VALUES
db-1  |             (1, 'Item a tarif négatif', '', -10.00)
```

4. une réservation qui se termine avant de commencer ;

```bash
db-1  | 2026-10-08 14:18:17.229 UTC [63] ERROR:  new row for relation "reservations" violates check constraint "dates_coherentes"
db-1  | 2026-10-08 14:18:17.229 UTC [63] DETAIL:  Failing row contains (4, 1, 2, 2026-09-10, 2026-09-09, terminee).
db-1  | 2026-10-08 14:18:17.229 UTC [63] STATEMENT:  INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
db-1  |         VALUES
db-1  |             (1, 2, '2026-09-10', '2026-09-09', 'terminee');
db-1  | psql:/docker-entrypoint-initdb.d/02-seed.sql:23: ERROR:  new row for relation "reservations" violates check constraint "dates_coherentes"
db-1  | DETAIL:  Failing row contains (4, 1, 2, 2026-09-10, 2026-09-09, terminee).
```

5. une réservation au statut `en_attente_peut_etre`.

```bash
db-1  | psql:/docker-entrypoint-initdb.d/02-seed.sql:23: ERROR:  new row for relation "reservations" violates check constraint "statut_valide"
db-1  | 2026-10-08 14:19:15.439 UTC [63] ERROR:  new row for relation "reservations" violates check constraint "statut_valide"
db-1  | 2026-10-08 14:19:15.439 UTC [63] DETAIL:  Failing row contains (4, 2, 2, 2026-09-01, 2026-09-05, en_attente_peut_etre).
db-1  | 2026-10-08 14:19:15.439 UTC [63] STATEMENT:  INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
db-1  |         VALUES
db-1  |             (2, 2, '2026-09-01', '2026-09-05', 'en_attente_peut_etre');
db-1  | DETAIL:  Failing row contains (4, 2, 2, 2026-09-01, 2026-09-05, en_attente_peut_etre).
```

Les cinq doivent échouer. Consignez les noms de contraintes : c'est ce que vous intercepterez en
Python (séance 4) pour renvoyer un `409` propre au lieu d'un `500`.

Puis testez la suppression d'un utilisateur : comptez les items de Bob, puis supprimez Bob. La
base refuse. Lisez attentivement le message : il vous dit pourquoi et nomme la contrainte qui
bloque. Vérifiez que rien n'a été supprimé, pas même ses items.

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items WHERE owner_id = 2;"
 id | owner_id |     titre      |      description       | tarif_jour | disponible |          created_at
----+----------+----------------+------------------------+------------+------------+-------------------------------
  3 |        2 | Tente 2 places |                        |      12.00 | t          | 2026-10-08 14:23:54.086826+00
  4 |        2 | Appareil photo | Reflex + objectif 50mm |      20.00 | t          | 2026-10-08 14:23:54.086826+00
(2 rows)
```

Avec :
```python
CREATE TABLE items (
    id          BIGSERIAL PRIMARY KEY,
    owner_id    BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
```
dans la base, les items sont supprimés en cascade avec la suppression de Bob :

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items WHERE owner_id = 2;"
 id | owner_id |     titre      |      description       | tarif_jour | disponible |          created_at
----+----------+----------------+------------------------+------------+------------+-------------------------------
  3 |        2 | Tente 2 places |                        |      12.00 | t          | 2026-10-08 14:23:54.086826+00
  4 |        2 | Appareil photo | Reflex + objectif 50mm |      20.00 | t          | 2026-10-08 14:23:54.086826+00
(2 rows)


C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "DELETE FROM users WHERE id = 2;"
DELETE 1

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items WHERE owner_id = 2;"
 id | owner_id | titre | description | tarif_jour | disponible | created_at
----+----------+-------+-------------+------------+------------+------------
(0 rows)
```

Sans `ON DELETE CASCADE` sur `owner_id` :

```bash
docker compose exec db psql -U gearshare -d gearshare -c "DELETE FROM users WHERE id = 2;"
ERROR:  update or delete on table "users" violates foreign key constraint "items_owner_id_fkey" on table "items"
DETAIL:  Key (id)=(2) is still referenced from table "items".
```

Voyons maintenant ce qui se passerait sans ce garde-fou. Écrivez les deux instructions
`ALTER TABLE` qui suppriment la clé étrangère de `borrower_id`, puis la recréent, sous le même nom,
avec `ON DELETE CASCADE`. Supprimez à nouveau Bob, recomptez ses items et regardez ce que contient
la table `reservations`. Pour chaque ligne disparue, notez qui l'a perdue et pourquoi : par quelle
clé étrangère la cascade est passée.

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "ALTER TABLE items DROP CONSTRAINT items_owner_id_fkey;" && docker compose exec db psql -U gearshare -d gearshare -c "ALTER TABLE items ADD CONSTRAINT items_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE;"
ALTER TABLE
ALTER TABLE

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "DELETE FROM users WHERE id = 2;"
DELETE 1

C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare -c "SELECT * FROM items WHERE owner_id = 2;"
 id | owner_id | titre | description | tarif_jour | disponible | created_at
----+----------+-------+-------------+------------+------------+------------
(0 rows)
```

**Question à laquelle vous devez répondre par écrit** : quel comportement voulez-vous pour
GearShare ? Supprimer un compte doit-il effacer l'historique des prêts que d'autres utilisateurs
ont faits sur son matériel ? Et ses propres emprunts ? Notez votre décision — c'est un choix de
conception, pas un détail.


Réponse : On supprime les `ON DELETE CASCADE` pour le projet GearShare, car : l'historique des prêts des autres sur son matériel ne doit pas disparaître lorsqu'on supprime un utilisateur. La réservation d'Alice sur la tente de Bob est l'historique d'Alice pas celui de Bob, si on garde le `CASCADE` et qu'on supprime Bob ça effacerait la résrvation quand même.
Les emprunts de Bob doivent être conservés pour servir en cas de litige. (traçabilité)


Rechargez ensuite les données (`docker compose down -v && docker compose up -d`).

---

## Étape 3 — Interroger

Écrivez les requêtes suivantes dans un fichier `sql/requetes.sql`, avec leur résultat en
commentaire. Toutes doivent être testées.

1. Les items disponibles à moins de 10 €/jour, triés par tarif croissant.
2. Les items dont le titre contient « velo », insensible à la casse. Regardez le résultat de près.
3. Chaque item avec le nom de son propriétaire (jointure).
4. Le nombre de réservations par item, **y compris les items jamais réservés** (le piège du cours).
5. Pour chaque utilisateur : son nom, son nombre d'items publiés, le tarif moyen de ses items.
   Uniquement ceux qui ont publié au moins un item.
6. Les réservations actives dont la date de début est postérieure au 1er septembre 2026, avec le
   titre du matériel et le nom de l'emprunteur.
7. Les 2 items les plus chers, en sautant le premier (pagination).
8. Le chiffre d'affaires potentiel de chaque réservation active : tarif journalier × nombre de
   jours. (Indice : la différence de deux `DATE` donne un entier en PostgreSQL.)

La requête 4 est celle sur laquelle je vous attends. Si votre résultat ne contient que les items
réservés, ou si la Perceuse apparaît avec 1 réservation, corrigez.

```bash
docker compose exec -T db psql -U gearshare -d gearshare -f - < sql/requetes.sql
```

---

## Étape 4 — Transactions

Ouvrez **deux** sessions `psql` en parallèle (deux terminaux), A et B.

**Isolation.** Dans A, ouvrez une transaction, passez le tarif du Vélo de ville à 99.00 et
relisez-le. Sans valider, relisez-le depuis B. Puis annulez dans A et relisez des deux côtés.
Recommencez en validant au lieu d'annuler. Notez à chaque fois ce que voit B.

**Atomicité.** Dans une seule transaction, écrivez :

1. une réservation valide du Vélo de ville par Chloé du 1er au 4 novembre 2026 ;
2. le passage du Vélo de ville à `disponible = FALSE` ;
3. une réservation qui échoue volontairement (emprunteur inexistant) ;
4. une validation de la transaction.

Vérifiez ensuite : la réservation de novembre existe-t-elle ? Le vélo est-il indisponible ?
Notez aussi ce que répond `psql` à la validation, et ce qu'il répond si vous tapez une autre
commande entre l'erreur et la validation. C'est exactement ce que vous devrez gérer côté
SQLAlchemy en séance 4.

```bash
A)
gearshare=# BEGIN;
UPDATE items SET tarif_jour = 99.00 WHERE titre = 'Vélo de ville';
SELECT tarif_jour FROM items WHERE titre = 'Vélo de ville';
BEGIN
UPDATE 1
 tarif_jour
------------
      99.00
(1 row)

B)
gearshare=# SELECT tarif_jour FROM items WHERE titre = 'Vélo de ville';
 tarif_jour
------------
       8.50
(1 row)
Modification non validée est invisible pour les autres sessions

A)
ROLLBACK;
gearshare=# BEGIN;
BEGIN
gearshare=*# UPDATE items SET tarif_jour = 99.00 WHERE titre = 'Vélo de ville';
UPDATE 1
gearshare=*# SELECT tarif_jour FROM items WHERE titre = 'Vélo de ville';
 tarif_jour
------------
      99.00
(1 row)

B)
gearshare=# SELECT tarif_jour FROM items WHERE titre = 'Vélo de ville';
 tarif_jour
------------
       8.50
(1 row)

A)
gearshare=*# COMMIT;
COMMIT

B)
gearshare=# SELECT tarif_jour FROM items WHERE titre = 'Vélo de ville';
 tarif_jour
------------
      99.00
(1 row)

A)
gearshare=# ROLLBACK;
WARNING:  there is no transaction in progress
ROLLBACK
```
>> une fois qu'on a commit on ne peut pas revenir en arrière


#### Atomicité

```bash
gearshare=# BEGIN;
BEGIN
gearshare=*# INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
VALUES (1, 3, DATE '2026-11-01', DATE '2026-11-04', 'active');
INSERT 0 1
gearshare=*# UPDATE items SET disponible = FALSE WHERE id = 1;
UPDATE 1
gearshare=*# INSERT INTO reservations (item_id, borrower_id, date_debut, date_fin, statut)
VALUES (1, 999, DATE '2026-11-01', DATE '2026-11-04', 'active');
ERROR:  insert or update on table "reservations" violates foreign key constraint "reservations_borrower_id_fkey"
DETAIL:  Key (borrower_id)=(999) is not present in table "users".
```
(`borrower_id = 999` n'existe pas)

```bash
gearshare=!# SELECT 1;
ERROR:  current transaction is aborted, commands ignored until end of transaction block
```

Transaction en état d'échec, toutes commande est refusée jusqu'à la fin.
Il faut `ROLLBACK` ou `COMMIT`

```bash
gearshare=!# COMMIT;
ROLLBACK

gearshare=# SELECT * FROM reservations WHERE item_id = 1;
SELECT disponible FROM items WHERE id = 1;
 id | item_id | borrower_id | date_debut |  date_fin  |  statut
----+---------+-------------+------------+------------+----------
  1 |       1 |           2 | 2026-09-01 | 2026-09-05 | terminee
  8 |       1 |           3 | 2026-11-01 | 2026-11-04 | active
(2 rows)

 disponible
------------
 f
(1 row)
```

La réservation de novembre n'existe pas, le vélo est toujours disponible : 
l'erreur survenue après les deux instructions valides les a effacées rétroactivement. Tout ou rien = atomicité.

---

## Étape 5 — Index et `EXPLAIN ANALYZE`

**Générez du volume** : insérez 200 000 items appartenant à Alice, de titre `Item de test 1`,
`Item de test 2`, …, `Item de test 200000`, avec un tarif aléatoire entre 1 et 51 €. Une seule
instruction suffit : cherchez `generate_series` et `random()` dans la documentation. Lancez
ensuite `ANALYZE items;` pour mettre à jour les statistiques du planificateur.

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-3-database\tp\tp-db>docker compose exec db psql -U gearshare -d gearshare
psql (16.15 (Debian 16.15-1.pgdg13+2))
Type "help" for help.

gearshare=# INSERT INTO items (owner_id, titre, tarif_jour)
SELECT 1,
       'Item de test ' || n,
       (random() * 50 + 1)::numeric(8,2)
FROM generate_series(1, 200000) AS n;
INSERT 0 200000
gearshare=# ANALYZE items;
ANALYZE
```

**Mesurez** avec `EXPLAIN ANALYZE` la recherche de l'item de titre exact `Item de test 123456`.
Relevez le type de nœud et le temps d'exécution.

```bash
gearshare=# EXPLAIN ANALYZE SELECT * FROM items WHERE titre = 'Item de test 123456';
                                            QUERY PLAN
---------------------------------------------------------------------------------------------------
 Seq Scan on items  (cost=0.00..4562.05 rows=1 width=82) (actual time=5.640..9.570 rows=1 loops=1)
   Filter: ((titre)::text = 'Item de test 123456'::text)
   Rows Removed by Filter: 200003
 Planning Time: 0.229 ms
 Execution Time: 9.613 ms
(5 rows)

9,6 ms à parcourir les 200 003 lignes du volume
```

Créez un index sur `titre`, relancez `ANALYZE`, remesurez. Consignez les deux chiffres dans
`MESURES.md` avec le facteur d'accélération.

```bash
gearshare=# CREATE INDEX idx_items_titre ON items (titre);
ANALYZE items;
EXPLAIN ANALYZE SELECT * FROM items WHERE titre = 'Item de test 123456';
CREATE INDEX
ANALYZE
                                                       QUERY PLAN
------------------------------------------------------------------------------------------------------------------------
 Index Scan using idx_items_titre on items  (cost=0.42..8.44 rows=1 width=82) (actual time=0.140..0.141 rows=1 loops=1)
   Index Cond: ((titre)::text = 'Item de test 123456'::text)
 Planning Time: 0.368 ms
 Execution Time: 0.154 ms
(4 rows)
```

En créant un index sur titre, on stock dans un B-tree les titres triés. Ca permet d'aller rechercher une ligne en complexité logarithmique plutôt que linéaire.
Temps d'exécution = 0,154 ms 
C'est 62 fois plus rapide par rapport aux 9,6 ms sans l'index


Mesurez ensuite deux cas plus subtils :

- (a) la recherche des titres qui **se terminent** par `123456` (joker en tête avec `LIKE`) ;

```bash
gearshare=# EXPLAIN ANALYZE SELECT * FROM items WHERE titre LIKE '%123456';
                                              QUERY PLAN
------------------------------------------------------------------------------------------------------
 Seq Scan on items  (cost=0.00..4562.05 rows=20 width=82) (actual time=10.786..16.851 rows=1 loops=1)
   Filter: ((titre)::text ~~ '%123456'::text)
   Rows Removed by Filter: 200003
 Planning Time: 1.735 ms
 Execution Time: 16.875 ms
(5 rows)
```

16.875 ms est attendu 
Mettre un joker en tête (%) rend impossible de descendre l'arbre de façon ordonné car un B-tree est trié en commençant par le début de la chaîne de caractères, donc dans ce cas l'index est inutilisable et la complexité est linéaire.


- (b) le filtre `disponible = TRUE`, **après** avoir créé un index sur `disponible` et relancé
  `ANALYZE`. Mesurez ensuite `disponible = FALSE`, avec le même index.

```bash
gearshare=# EXPLAIN ANALYZE SELECT count(*) FROM items WHERE disponible = TRUE;
                                                    QUERY PLAN
-------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=4562.05..4562.06 rows=1 width=8) (actual time=34.818..34.820 rows=1 loops=1)
   ->  Seq Scan on items  (cost=0.00..4062.04 rows=200004 width=0) (actual time=0.045..27.386 rows=200003 loops=1)
         Filter: disponible
         Rows Removed by Filter: 1
 Planning Time: 0.469 ms
 Execution Time: 34.924 ms
(6 rows)

gearshare=# EXPLAIN ANALYZE SELECT count(*) FROM items WHERE disponible = FALSE;
 Aggregate  (cost=4.32..4.33 rows=1 width=8) (actual time=0.153..0.154 rows=1 loops=1)
   ->  Index Only Scan using idx_items_disponible on items  (cost=0.29..4.31 rows=1 width=0) (actual time=0.144..0.145 rows=1 loops=1)
         Index Cond: (disponible = false)
         Heap Fetches: 0
 Planning Time: 0.908 ms
 Execution Time: 0.403 ms
(6 rows)
Résultat : on voit que une seule ligne sur 200 004 est à FALSE, les autres sont à TRUE. 
Pour disponible = TRUE, Seq scan est utilisé et donne 34 ms
Pour disponible = FALSE index scan est utilisé, ce qui est beaucoup plus rapide. Un index n'est utilisé que si la condition est sélective (peu de ligne matchées). Sur une colonne booléenne quasi uniforme, l'index ne sert que pour la valeur rare. 
```

Expliquez en une phrase chacun des résultats dans `MESURES.md`. (Indice pour (a) : un B-tree
est trié par le début de la chaîne. Indice pour (b) : comptez combien de lignes vérifient chacune
des deux conditions. Question bonus : l'index sur `titre` sert-il pour un `LIKE` avec le joker
**en fin** de chaîne ? Mesurez avant de répondre.)

```bash
gearshare=# EXPLAIN ANALYZE SELECT * FROM items WHERE titre LIKE 'Item de test 123%';
                                                QUERY PLAN
----------------------------------------------------------------------------------------------------------
 Seq Scan on items  (cost=0.00..4562.05 rows=2020 width=82) (actual time=0.029..13.525 rows=1111 loops=1)
   Filter: ((titre)::text ~~ 'Item de test 123%'::text)
   Rows Removed by Filter: 198893
 Planning Time: 0.087 ms
 Execution Time: 13.572 ms
(5 rows)


gearshare=# CREATE INDEX idx_items_disponible ON items (disponible);
ANALYZE items;

EXPLAIN ANALYZE SELECT count(*) FROM items WHERE disponible = TRUE;
EXPLAIN ANALYZE SELECT count(*) FROM items WHERE disponible = FALSE;
CREATE INDEX
ANALYZE
                                                    QUERY PLAN
-------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=4562.05..4562.06 rows=1 width=8) (actual time=20.947..20.949 rows=1 loops=1)
   ->  Seq Scan on items  (cost=0.00..4062.04 rows=200004 width=0) (actual time=0.006..13.894 rows=200003 loops=1)
         Filter: disponible
         Rows Removed by Filter: 1
 Planning Time: 0.219 ms
 Execution Time: 21.042 ms
(6 rows)

gearshare=# SELECT disponible, count(*) FROM items GROUP BY disponible;
 disponible | count
------------+--------
 f          |      1
 t          | 200003
(2 rows)
```

L'index B-tree standard ne sert pas pour un LIKE, même avec le joker en fin.

---

## Étape 6 — Étendre le schéma, et le reviewer

Le schéma actuel ne couvre pas tout GearShare : il manque les **avis** (note + commentaire après
un prêt terminé) et les **tags** de matériel.

### 6.1. Les règles métier

Voici les règles à ajouter au schéma existant (`users`, `items`, `reservations`) :

1. Après une réservation au statut `terminee`, l'emprunteur peut laisser un avis :
   une note entière de 1 à 5 et un commentaire libre optionnel.
2. Un avis est lié à exactement une réservation, et une réservation ne peut avoir
   qu'un seul avis.
3. Un matériel peut porter plusieurs tags (ex. `velo`, `sport`) ; un tag peut être
   porté par plusieurs matériels. Un tag a un libellé unique en minuscules.
4. Un même matériel ne peut pas avoir deux réservations actives qui se chevauchent.

Contraintes techniques : PostgreSQL 16, contraintes nommées, `TIMESTAMPTZ` pour les horodatages,
index sur les clés étrangères.

### 6.2. Écrivez le DDL

Dans `sql/init/03-schema-v2.sql`, écrivez le DDL qui traduit ces règles (`CREATE TABLE`,
`ALTER TABLE`, `CREATE INDEX`). Avant d'écrire, identifiez pour chaque règle le mécanisme qui la
garantit : type, `NOT NULL`, `UNIQUE`, `CHECK`, clé étrangère, table de liaison… ou rien, si la
base ne peut pas la garantir seule.

### 6.3. Reviewez

Relisez votre DDL avec la grille suivante, corrigez ce qui doit l'être et consignez le résultat
dans `REVIEW-schema.md` :

| Point de contrôle | OK / KO | Ce que j'ai corrigé |
|---|---|---|
| Chaque table a une clé primaire | OK | |
| Les clés étrangères sont déclarées avec `REFERENCES` | OK | |
| Les `ON DELETE` sont explicites et cohérents avec le métier | KO | Il y avait des ON DELETE implicites (NO ACTION par défaut). Corrigé en CASCADE sur les trois FK : supprimer une réservation purge son avis, supprimer un item ou un tag purge ses liens dans item_tags. |
| La règle « un seul avis par réservation » est garantie par une contrainte `UNIQUE` | OK | |
| La note est bornée par un `CHECK (note BETWEEN 1 AND 5)` | OK | |
| La table de liaison item/tag a une clé primaire composite | OK | |
| Le libellé de tag est `UNIQUE` | OK | |
| Les contraintes sont nommées | OK | |
| Des index existent sur les clés étrangères | KO | Correction principale : PostgreSQL ne crée pas d'index sur les FK. Ajout explicite de idx_avis_reservation_id, idx_item_tags_item_id, idx_item_tags_tag_id, plus les FK du schéma v1 (items.owner_id, reservations.item_id, reservations.borrower_id) qui n'en avaient aucun. |
| Le non-chevauchement est réellement garanti (contrainte) ou explicitement laissé à l'applicatif | OK | |
| Aucun type flottant pour un montant, aucun `TIMESTAMP` sans fuseau | OK | |

Puis **prouvez que ça marche** : écrivez dans `sql/tests-contraintes.sql` au moins quatre
`INSERT` qui doivent échouer (note à 6, deux avis sur la même réservation, deux tags de même
libellé, un avis sur une réservation inexistante) et vérifiez qu'ils échouent tous — et pour la
bonne raison : lisez le nom de la contrainte dans chaque message.

Sur le non-chevauchement : garantissez-le par une contrainte d'exclusion (`EXCLUDE`, voir la
documentation PostgreSQL), ou documentez explicitement dans `REVIEW-schema.md` que vous le gérerez
en applicatif et pourquoi. Ce que je ne veux pas, c'est que la question soit passée sous silence.

```bash
docker compose exec -T db psql -U gearshare -d gearshare -f - < sql/requetes.sql
```

---

## Ce que vous devez me rendre à la fin de la séance 3

Dans votre dépôt de groupe, un dossier `tp-db/` contenant :

1. **`docker-compose.yml`** avec volume nommé, healthcheck et init.
2. **`sql/init/01-schema.sql`** et **`sql/init/02-seed.sql`** : `docker compose down -v && up -d`
   doit reconstruire une base complète et peuplée.
3. **`sql/requetes.sql`** : les 8 requêtes de l'étape 3, testées, avec leur résultat en commentaire.
4. **`MESURES.md`** : les mesures `EXPLAIN ANALYZE` avant/après index et vos deux explications.
5. **`sql/init/03-schema-v2.sql`** (version corrigée) et **`REVIEW-schema.md`**.
6. **`sql/tests-contraintes.sql`** : les insertions qui doivent échouer.
7. Votre réponse écrite à la question de l'étape 2 sur la suppression d'un utilisateur (2–3 lignes
   dans `REVIEW-schema.md` suffisent).

## Pour aller plus loin

- Créez une vue qui expose le catalogue enrichi (item + propriétaire + note moyenne) et
  interrogez-la comme une table.
- Écrivez un trigger qui bascule automatiquement une réservation en `terminee` quand `date_fin`
  est dépassée, et discutez : est-ce une bonne idée de mettre cette logique en base plutôt que
  dans l'application ?
- Comparez `EXPLAIN ANALYZE` d'une jointure sur `owner_id` avec et sans index sur cette clé
  étrangère, sur les 200 000 lignes générées.
