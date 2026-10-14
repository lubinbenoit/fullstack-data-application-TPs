# Étape 5 : index et EXPLAIN ANALYZE

## Recherche par titre exact (`titre = 'Item de test 123456'`)
Sans index : Execution Time: 9.613 ms
Avec index : Execution Time: 0.154 ms

Sans index, PostgreSQL n'a d'autre choix que de lire les 200 004 lignes, une par une et d'en éliminer 200 003 (Rows Removed by Filter), alors qu'avec index le B-tree contient les titres triés, la recherche descend l'arbre en quelques sauts et atteint directement la ligne cible.

## (a) `LIKE '%123456'` (joker en tête)

Résultat : Seq Scan, 16,875 ms, l'index n'est pas utilisé.

Un B-tree est trié par le début de la chaîne : avec un joker en tête on ne connaît pas le début de la clé, il est donc impossible de descendre l'arbre de façon ordonnée et PostgreSQL retombe sur un parcours complet de la table.

## (b) Filtre sur `disponible` (avec index `idx_items_disponible`)

| Condition | Lignes matchées | Nœud | Temps |
|---|---|---|---|
| `disponible = TRUE` | 200 003 / 200 004 | Seq Scan | 34,9 ms |
| `disponible = FALSE` | 1 / 200 004 | Index Only Scan | 0,4 ms |

Pour TRUE : la condition matche presque toute la table, elle n'est pas sélective ; passer par l'index puis relire chaque ligne coûterait plus cher qu'un balayage direct, donc le planificateur ignore l'index.
Pour FALSE : une seule ligne matche, la condition est très sélective. L'index mène directement à elle (Index Only Scan : la réponse est entièrement dans l'index, Heap Fetches: 0), ~87 fois plus rapide. Un index n'est utilisé que si la condition est sélective, indexer un booléen quasi uniforme ne sert que pour la valeur rare.
 
## Question bonus : `LIKE 'Item de test 123%'` (joker en fin)

Résultat : Seq Scan, 13,572 ms, l'index sur titre n'est pas utilisé,
alors que le motif est un préfixe (donc compatible a priori avec un tri par le début de la chaîne).

Avec la locale française par défaut, l'ordre du tri linguistique ne
correspond pas à l'ordre des chaînes brutes, donc PostgreSQL ne peut pas
utiliser un B-tree standard pour LIKE ; pour le rendre utilisable il faut un index spécifique : `CREATE INDEX ON items (titre text_pattern_ops);`.