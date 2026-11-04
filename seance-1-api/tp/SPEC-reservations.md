# Ressource : reservations

Fichiers : `app/schemas/reservation.py`, `app/routers/reservations.py`
Stockage : dictionnaire en mémoire dans le router (comme `items`)

## Schémas
- `ReservationCreate` :
  - `item_id` : `int` (>= 1)
  - `date_debut` : `date`
  - `date_fin` : `date`

- `ReservationRead` :
  - `id` : `int`
  - `item_id` : `int`
  - `date_debut` : `date`
  - `date_fin` : `date`
  - `statut` : `Literal["active", "annulee"]` (par défaut : `"active"`).

## Routes (préfixe /reservations, tag "reservations")
- POST ""              → 201, ReservationRead. 422 si date_fin <= date_debut.
- GET  ""              → 200, list[ReservationRead]. Query : item_id optionnel, limit (défaut 20, max 100).
- GET  "/{reservation_id}" → 200, ReservationRead. 404 si absente.
- POST "/{reservation_id}/annuler" → 200, ReservationRead avec statut "annulee".
                                     404 si absente, 409 si déjà annulée.

## Contraintes
1. Aucun accès à `FAKE_DB` de `items`.
2. `response_model` doit être présent sur toutes les routes.
3. Pas de logique de validation en `if` dans le router : tout doit être géré par Pydantic (y compris `date_fin > date_debut`).
4. Pas de dépendances supplémentaires** dans `requirements.txt` (sauf justification).
5. Ordre des routes : Les routes littérales (ex: `/annuler`) doivent être déclarées avant les routes paramétrées (ex: `/{reservation_id}`).
6. Pas de `async def` sans `await`.