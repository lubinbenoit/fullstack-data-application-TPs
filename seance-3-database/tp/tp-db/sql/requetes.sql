-- 1. Items disponibles < 10 €/jour, tarif croissant
SELECT titre, tarif_jour FROM items
WHERE disponible AND tarif_jour < 10
ORDER BY tarif_jour;

--      titre     | tarif_jour
-- ---------------+------------
--  Perceuse      |       5.00
--  Vélo de ville |       8.50
-- (2 rows)


-- 2. Titre contenant "velo"
SELECT * FROM items WHERE titre ILIKE '%velo%';

--  id | owner_id | titre | description | tarif_jour | disponible | created_at
-- ----+----------+-------+-------------+------------+------------+------------
-- (0 rows) vélo != velo


-- 3. Chaque item avec le nom de son propriétaire
SELECT i.id, i.titre, u.display_name AS proprietaire
FROM items i
JOIN users u ON u.id = i.owner_id
ORDER BY i.id;

--  id |     titre      | proprietaire
-- ----+----------------+--------------
--   1 | Vélo de ville  | Alice
--   2 | Perceuse       | Alice
--   3 | Tente 2 places | Bob
--   4 | Appareil photo | Bob
-- (4 rows)

-- 4. Nombre de réservations par item y compris les jamais réservés
-- (note : LEFT JOIN + COUNT(colonne de la table de droite), sinon le INNER JOIN
--  élimine la Perceuse et COUNT(*) afficherait 1 au lieu de 0)
SELECT i.titre, COUNT(r.id) AS nb_reservations
FROM items i
LEFT JOIN reservations r ON r.item_id = i.id
GROUP BY i.id, i.titre
ORDER BY i.id;

--      titre      | nb_reservations
-- ----------------+-----------------
--  Vélo de ville  |               1
--  Perceuse       |               0
--  Tente 2 places |               1
--  Appareil photo |               1
-- (4 rows)

-- 5. Utilisateurs ayant publié au moins un item : nb + tarif moyen
SELECT u.display_name, COUNT(i.id) AS nb_items, AVG(i.tarif_jour) AS tarif_moyen
FROM users u
JOIN items i ON i.owner_id = u.id
GROUP BY u.id, u.display_name
ORDER BY u.id;

--  display_name | nb_items |     tarif_moyen
-- --------------+----------+---------------------
--  Alice        |        2 |  6.7500000000000000
--  Bob          |        2 | 16.0000000000000000
-- (2 rows)

-- 6. Réservations actives commençant après le 01/09/2026
SELECT r.id, i.titre, u.display_name AS emprunteur, r.date_debut, r.date_fin
FROM reservations r
JOIN items i ON i.id = r.item_id
JOIN users u ON u.id = r.borrower_id
WHERE r.statut = 'active' AND r.date_debut > DATE '2026-09-01'
ORDER BY r.id;

--  id |     titre      | emprunteur | date_debut |  date_fin
-- ----+----------------+------------+------------+------------
--   2 | Tente 2 places | Alice      | 2026-09-10 | 2026-09-12
--   3 | Appareil photo | Chloe      | 2026-09-15 | 2026-09-20
-- (2 rows)

-- 7. Les 2 items les plus chers, en sautant le premier (pagination)
SELECT titre, tarif_jour FROM items
ORDER BY tarif_jour DESC
LIMIT 2 OFFSET 1;

--      titre      | tarif_jour
-- ----------------+------------
--  Tente 2 places |      12.00
--  Vélo de ville  |       8.50
-- (2 rows)

-- 8. Chiffre d'affaires potentiel des réservations actives
SELECT i.titre, r.date_debut, r.date_fin,
       i.tarif_jour * (r.date_fin - r.date_debut) AS ca_potentiel
FROM reservations r
JOIN items i ON i.id = r.item_id
WHERE r.statut = 'active'
ORDER BY r.id;

--      titre      | date_debut |  date_fin  | ca_potentiel
-- ----------------+------------+------------+--------------
--  Tente 2 places | 2026-09-10 | 2026-09-12 |        24.00
--  Appareil photo | 2026-09-15 | 2026-09-20 |       100.00
-- (2 rows)