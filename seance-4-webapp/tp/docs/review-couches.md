# Review de la verticale `reservations`

Relue à froid (7.4). Chaque point a été vérifié par inspection du code
(`grep`) et/ou par test (`/docs`, `SQL_ECHO=true`, cas de chevauchement).
   Point de contrôle | OK / KO | Ce que j'ai corrigé / Notes |
 |---|---|---|
 | Aucun SQL ni requête SQLAlchemy dans le router | OK | `routers/reservations.py` ne contient ni `select`, ni `Session`, ni `execute` : le router ne fait qu'orchestrer (schémas HTTP -> service). |
 | Aucune `HTTPException` dans le service | OK | Aucune occurrence d'`HTTPException` dans `services/*`. Le service lève des exceptions métier pures. La traduction vers HTTP se fait dans le gestionnaire global (`@app.exception_handler`), un seul endroit pour tout le backend. |
 | Aucun `commit()` dans le repository | OK | Aucun `commit` dans `repositories/*` : le repository se limite à `add/flush/refresh`. Le `commit()` vit uniquement dans `app/api/deps.py` (`get_db`), une seule transaction par requête. |
 | `response_model` sur les 4 routes | OK | 4 occurrences de `response_model=` dans `routers/reservations.py` (POST, GET liste, GET détail, PATCH). Chaque route affiche son schéma de réponse dans `/docs`. |
 | Schéma de lecture sans champ interne | OK | `ReservationRead` a `from_attributes=True` ; champs exposés : `id, item_id, borrower_id, date_debut, date_fin, statut`. Vérifié sur `/reservations` : aucun champ interne ne fuit. |
 | Chevauchement : les cinq cas couverts | OK | `find_chevauchements` teste `date_debut < fin AND date_fin > début` (inégalités strictes) : le cas englobant est bien couvert, contrairement à un test du seul "début dans un créneau". Tests : 409 pour partiel début, partiel fin, englobant, contenu ; 201 pour avant, après, jointifs (créneaux qui se touchent sans se chevaucher). |
 | Pas de f-string dans une requête SQL | OK | Seul `ilike(f"%{search}%")` reste dans `ItemRepository.list` : la f-string construit la valeur du motif, pas du SQL. QLAlchemy la transmet en paramètre lié. Aucune concaténation de SQL. |
 | Pas de N+1 sur `GET /reservations` | OK | `ReservationRead` n'embarque aucune relation imbriquée (`item`, `borrower`) : la réponse ne déclenche aucun accès paresseux. Vérifié avec `SQL_ECHO=true` : le nombre de SELECT reste constant quel que soit le nombre de réservations. |
 | Migration relue, `downgrade()` testé | OK | Voir `review-migrations.md` (3bis) : le renommage autogénéré a été corrigé en `alter_column`, et le retour arrière a été vérifié par `SELECT`. |
 | Aucune dépendance injustifiée | KO -> corrigé | `alembic` était listé en doublon dans `requirements.txt`. Le doublon a été supprimé. |