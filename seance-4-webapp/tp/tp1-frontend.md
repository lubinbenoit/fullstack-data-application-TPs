# TP 1 — Séance 4 : brancher un frontend sur l'API de la séance 1 (1h30)

## Ce que vous allez faire

Votre API des séances 1 et 2 fonctionne, mais seul un développeur peut s'en servir, avec `/docs`
ou `curl`. Dans ce TP, vous lui ajoutez un **frontend** : une seconde application FastAPI qui sert
des pages HTML et qui ne communique avec le backend **que par son API REST**.

On ne touche pas encore à la base de données : le backend garde son stockage en mémoire. C'est
volontaire. Vous mettez d'abord en place la frontière frontend / backend, puis, dans le
[TP 2](tp2-backend-db.md), vous changez tout ce qu'il y a derrière l'API… sans que le frontend s'en
aperçoive.

Le cours de référence est la [section 2 du cours 1](../cours/cours1-frontend.md#2-le-frontend--une-application-fastapi-qui-sert-du-html).
Gardez-le ouvert : je ne recopie pas ici toutes ses explications.

## Objectifs du TP

À la fin de ce TP, vous devez savoir :

- organiser un dépôt en deux applications séparées, `backend/` et `frontend/`, lancées par un
  seul `docker compose up` ;
- configurer l'adresse du backend dans le frontend par une variable d'environnement ;
- isoler tous les appels au backend dans un client unique, la classe `ApiClient` ;
- écrire des pages HTML avec des templates Jinja2 et un template de base commun ;
- traiter un formulaire avec le schéma Post/Redirect/Get ;
- traduire les erreurs de l'API en messages lisibles.

## Prérequis

- Le TP de la séance 1 terminé : CRUD `items` et ressource `reservations`, en mémoire.
- Le TP de la séance 2 terminé : la suite de tests de l'API passe.
- Docker Desktop lancé.

---

## Étape 0 — Réorganiser le dépôt

Jusqu'ici, votre dépôt ne contenait qu'une application. Il va en contenir deux. Déplacez tout ce
qui concerne l'API dans un dossier `backend/` :

```text
votre-depot/
├── backend/
│   ├── app/              # main.py, routers/, schemas/ (inchangés)
│   ├── tests/            # vos tests de la séance 2 (inchangés)
│   ├── pytest.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             # vide pour l'instant
├── .gitignore
└── docker-compose.yml    # reste à la racine
```

Utilisez `git mv` plutôt qu'un simple déplacement de fichiers : Git conserve ainsi l'historique de
chaque fichier.

```bash
mkdir backend frontend
git mv app tests pytest.ini requirements.txt Dockerfile backend/
```

Puis adaptez `docker-compose.yml` :

- renommez le service `api` en `backend` ;
- le contexte de construction (`build`) devient le dossier `backend/` ;
- les volumes montent désormais `backend/app` et `backend/tests` dans le conteneur.

Dans `docker-compose.yml` :

```python
"api" -> "backend"
"build: ." -> "build: ./backend"
"volumes:
  - ./app:/code/app"
->
"volumes:
  - ./backend/app:/code/app
  - ./backend/tests:/code/tests"


services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app
      - ./backend/tests:/code/tests
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Vérifiez :**

```bash
docker compose up --build -d
curl http://localhost:8000/health
docker compose exec backend pytest
```

```bash
{"status":"ok"}
====================== 35 passed, 1 warning in 1.52s =======================
```

L'API répond et **tous vos tests de la séance 2 passent sans modification**. Si un test casse, le
déplacement a changé quelque chose : corrigez avant d'aller plus loin. Committez.

---

## Étape 1 — Le squelette du frontend

Créez l'arborescence du frontend (la [section 2.2 du cours 1](../cours/cours1-frontend.md#22-la-structure-du-projet-frontend)
l'explique) :

```text
frontend/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py
    ├── api_client.py
    ├── templating.py
    ├── routers/
    │   ├── __init__.py
    │   └── items.py
    ├── templates/
    │   ├── base.html
    │   ├── erreur.html
    │   └── items/
    └── static/
        └── style.css
```

Écrivez `frontend/requirements.txt`. Le frontend a besoin de cinq dépendances : `fastapi`,
`uvicorn`, `jinja2`, `httpx` et `python-multipart` (relisez la section 2.2 du cours 1 pour le rôle
de chacune). Fixez leurs versions, comme dans le backend.


`requirements.txt` :

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2
httpx==0.27.2
python-multipart
```

Pas de SQLAlchemy, pas de driver PostgreSQL : le frontend n'en aura **jamais** besoin.

`frontend/Dockerfile` : reprenez celui du backend, en changeant uniquement le port (`8080`).

Ajoutez un service `frontend` dans `docker-compose.yml`. Il doit :

- être construit à partir du dossier `frontend/` ;
- recevoir la variable `API_BASE_URL`, qui vaut `http://backend:8000` ;
- démarrer après le backend ;
- publier le port `8080` ;
- monter `frontend/app` dans le conteneur et lancer `uvicorn` avec `--reload`, comme le backend,
  pour que vos modifications soient prises en compte sans reconstruire l'image.

```bash
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app
      - ./backend/tests:/code/tests
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  frontend:
    build: ./frontend
    environment:
      - API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    ports:
      - "8080:8080"
    volumes:
      - ./frontend/app:/code/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Pour l'instant, le frontend n'a besoin que d'une seule variable, `API_BASE_URL`, et elle n'est pas
secrète : elle va directement dans `environment:` (relisez la partie sur les variables
d'environnement de la [section 1.2 du cours 1](../cours/cours1-frontend.md#12-configurer-chaque-service--les-variables-denvironnement)).

Écrivez `app/templating.py`, `app/main.py` et `templates/base.html` à partir de la
[section 2.6](../cours/cours1-frontend.md#26-les-routes-de-pages) et de la
[section 2.4](../cours/cours1-frontend.md#24-les-templates-jinja2) du cours 1. Dans `main.py`, ajoutez une
route d'accueil `GET /` qui redirige vers la liste du matériel, `/items`.

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api_client import ApiError
from app.routers import items
from app.templating import BASE_DIR, templates


app = FastAPI(title="GearShare — frontend")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(items.router)


@app.exception_handler(ApiError)
def api_error_page(request: Request, exc: ApiError) -> HTMLResponse:
    messages = {
        404: "Cette page n'existe pas ou plus.",
        503: "Le service est momentanément indisponible. Réessayez dans un instant.",
    }
    message = messages.get(exc.status_code, "Une erreur est survenue.")
    return templates.TemplateResponse(
        request, "erreur.html", {"message": message}, status_code=exc.status_code
    )

# redirection de / vers /items
@app.get("/", response_class=RedirectResponse)
def home() -> RedirectResponse:
    return RedirectResponse(url="/items", status_code=307)
```

Écrivez aussi `templates/erreur.html` : il étend `base.html` et affiche simplement
`{{ message }}` dans un paragraphe, avec un lien de retour vers `/items`.

```python
{# app/templates/erreur.html #}
{% extends "base.html" %}


{% block title %}Erreur — GearShare{% endblock %}

{% block content %}
  <p>{{ message }}</p>
  <p><a href="/items">Retour à la liste du matériel</a></p>
{% endblock %}
```

Copiez enfin la feuille de style de la [section 2.8](../cours/cours1-frontend.md#28-un-peu-de-css) dans
`static/style.css`.

**Vérifiez :**

```bash
docker compose up --build -d
docker compose ps
```

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose ps
NAME                          IMAGE                       COMMAND                  SERVICE    CREATED          STATUS          PORTS
projet-gearshare-backend-1    projet-gearshare-backend    "uvicorn app.main:ap…"   backend    18 seconds ago   Up 16 seconds   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
projet-gearshare-frontend-1   projet-gearshare-frontend   "uvicorn app.main:ap…"   frontend   17 seconds ago   Up 16 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
```

Ne pas oublier de compléter `app/api_client.py`
Et `frontend/app/router/items.py`.


Les deux services sont `running`. `http://localhost:8080/static/style.css` affiche votre feuille de
style. La page d'accueil renvoie encore une erreur : la route `/items` n'existe pas, c'est l'étape
suivante.

---

## Étape 2 — Le client d'API

Écrivez `app/api_client.py` en partant de la [section 2.5 du cours 1](../cours/cours1-frontend.md#25-le-client-dapi),
avec la classe `ApiClient`, ses trois premières méthodes (`list_items`, `get_item`,
`create_item`) et l'instance unique `api_client` créée en fin de module.

Ajoutez à `ApiError` une méthode `messages()` qui transforme le `detail` d'une erreur en liste
de messages affichables. Attention : quand FastAPI rejette une requête (`422`), `detail` n'est pas
une chaîne mais une **liste d'erreurs**, une par champ invalide. Chacune contient notamment `loc`
(l'emplacement du champ, dont le dernier élément est son nom) et `msg` (le message). Votre méthode
doit gérer les deux cas : une chaîne simple, ou une liste. Appelez une route en erreur depuis
`/docs` pour observer le format exact.

```python
ApiError de app/api_client.py
class ApiError(Exception):
    """Erreur renvoyée par le backend, ou backend injoignable."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail

    def messages(self) -> list[str]:
        if isinstance(self.detail, str):
            return [self.detail]
        if isinstance(self.detail, list):
            return [f"{err['loc'][-1]} : {err['msg']}" for err in self.detail]
        return [str(self.detail)]
```

Dans `ApiClient`, ajouter la fonction :

```python
def create_item(self, data: dict[str, Any]) -> dict[str, Any]:
    return self._send("POST", "/items", json=data)
```
Créer les items depuis : `http://localhost:8000/docs`


**Vérifiez depuis le conteneur du frontend**, avant d'écrire la moindre page. Créez d'abord deux
ou trois items depuis `http://localhost:8000/docs`, puis :

```bash
docker compose exec frontend python -c "from app.api_client import api_client; print(api_client.list_items())"
```

```bash
C:\Users\lubin\Documents\Git\fullstack-data-application-2026\seances\seance-4-webapp\tp\projet-gearshare>docker compose exec frontend python -c "from app.api_client import api_client; print(api_client.list_items())"
[{'id': 1, 'titre': 'TurboVelo', 'description': 'En promo 600% de réduction!!!', 'tarif_jour': 1.0, 'disponible': True}, {'id': 2, 'titre': '2 Mo de RAM', 'description': "899 999 € l'unité", 'tarif_jour': 1.0, 'disponible': True}]
```

Vous devez voir vos items. Faites ensuite une expérience : dans `docker-compose.yml`, remplacez
temporairement `http://backend:8000` par `http://localhost:8000`, relancez
(`docker compose up -d`) et rejouez la commande. Vous obtenez une `ApiError` `503`, parce que dans
le conteneur du frontend, `localhost` désigne le frontend lui-même. Remettez `backend`.

```bash
  File "/code/app/api_client.py", line 35, in _send
    raise ApiError(503, "Le service est momentanément indisponible.") from exc
app.api_client.ApiError: 503: Le service est momentanément indisponible.
```

---

## Étape 3 — La page « liste du matériel »

Écrivez `app/routers/items.py` avec la route `GET /items`, et le template
`templates/items/list.html`. Les deux sont dans le cours ([section 2.6](../cours/cours1-frontend.md#26-les-routes-de-pages)
et [section 2.4](../cours/cours1-frontend.md#24-les-templates-jinja2)). Ajoutez au-dessus du tableau un lien
« Proposer un objet » vers `/items/new`, la page du formulaire de création.

Écrivez ensuite la route `GET /items/{item_id}` et son template `templates/items/detail.html` :
titre, description, tarif, statut, et un lien de retour vers la liste.

**Vérifiez :**

1. `http://localhost:8080` redirige vers la liste et affiche vos items ;
2. un clic sur un item affiche sa page de détail ;
3. `http://localhost:8080/items/9999` affiche votre page d'erreur « introuvable », avec un code
   `404` (vérifiez-le dans l'onglet Réseau des outils de développement du navigateur) ;
4. créez depuis `/docs` un item dont le titre est `<b>Test XSS</b>` : la liste doit afficher les
   balises telles quelles, en texte, et non un titre en gras. Si le titre apparaît en gras,
   l'échappement automatique est désactivé quelque part : trouvez où.



Remplir `items.py` et `list.html`.

`list.html` :
```html
{# app/templates/items/list.html #}
{% extends "base.html" %}

{% block title %}Objets — GearShare{% endblock %}

{% block content %}
<h1>Objets disponibles</h1>

<p><a href="/items/new">Proposer un objet</a></p>
{% if items %}
  <table>
    <thead>
      <tr><th>Objet</th><th>Tarif / jour</th><th>Statut</th></tr>
    </thead>
    <tbody>
      {% for item in items %}
        <tr>
          <td><a href="/items/{{ item.id }}">{{ item.titre }}</a></td>
          <td>{{ item.tarif_jour }} €</td>
          <td>{{ "Disponible" if item.disponible else "Indisponible" }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% else %}
  <p>Aucun objet pour le moment.</p>
{% endif %}
{% endblock %}
```

`detail.html` :
```html
{# app/templates/items/detail.html #}
{% extends "base.html" %}

{% block title %}{{ item.titre }} — GearShare{% endblock %}

{% block content %}
<p><a href="/items">← Retour à la liste</a></p>

<h1>{{ item.titre }}</h1>
<p>{{ item.description }}</p>
<p>Tarif : {{ item.tarif_jour }} € / jour</p>
<p>Statut : {{ "Disponible" if item.disponible else "Indisponible" }}</p>
{% endblock %}
```

```bash
>curl http://localhost:8080/items/9999
[...]
  <p>Cette page n&#39;existe pas ou plus.</p>
  <p><a href="/items">Retour à la liste du matériel</a></p>
```

La balise n'est pas interprété donc tout est correct.

---

## Étape 4 — Le formulaire de création d'un item

Deux routes sont nécessaires :

- `GET /items/new` affiche le formulaire (template `templates/items/form.html`) ;
- `POST /items` reçoit le formulaire (`<form method="post" action="/items">`), appelle
  `api_client.create_item`, puis redirige.

On crée un item en postant sur la collection `/items`, comme sur l'API. Seule la page qui affiche
le formulaire a besoin de sa propre URL, `/items/new` : c'est une page, pas une ressource.

Le formulaire contient quatre champs, qui correspondent à `ItemCreate` côté backend : `titre`
(texte, `required minlength="3"`), `description` (`<textarea>`), `tarif_jour` (nombre,
`required min="0.01" step="0.01"`), `disponible` (case à cocher).

La route `POST` lit les quatre champs avec `Form()`, construit les données à envoyer à l'API,
puis :

- en cas de succès, redirige en `303` vers la page de détail du nouvel item ;
- en cas d'erreur `422` du backend, réaffiche le formulaire avec la liste des messages d'erreur
  et les valeurs saisies, avec le code `422` ;
- pour toute autre erreur, laisse remonter l'`ApiError` jusqu'au gestionnaire global.

Le cours 1 (section 2.7) montre ce schéma sur la réservation : appliquez-le à la création d'un
item.

Trois points à comprendre :

- **La case à cocher.** Une case cochée envoie `disponible=on` ; une case **non cochée n'envoie
  rien du tout**. Le paramètre correspondant doit donc avoir une valeur par défaut `False` : sans
  elle, FastAPI exigerait le champ, et décocher la case provoquerait une erreur `422`.
- **L'ordre des routes.** Déclarez `/items/new` **avant** `/items/{item_id}`. Dans l'autre
  ordre, FastAPI essaie de lire `new` comme un `item_id` entier et répond `422`. C'est le
  même piège que dans le TP de la séance 1.
- **La redirection `303`** : rechargez la page après une création réussie, aucun doublon ne doit
  apparaître (relisez la section 2.7 du cours 1 si vous ne voyez pas pourquoi).

Dans le template, affichez les messages d'erreur au-dessus du formulaire, et préremplissez chaque
champ avec la saisie précédente pour que l'utilisateur ne perde pas ce qu'il a tapé. Pensez aussi
à la description vide : un champ de formulaire vide arrive comme une chaîne vide, que vous
transmettrez au backend comme une absence de description.

**Vérifiez :**

1. une création valide redirige vers la page de détail du nouvel item ;
2. rechargez cette page : un seul item a été créé ;
3. retirez temporairement l'attribut `min` du champ `tarif_jour` dans le HTML, saisissez `0` :
   l'erreur `422` vient du **backend**, et le frontend l'affiche proprement, avec les autres
   champs préremplis ;
4. même chose avec un titre de deux caractères.

```bash
3. tarif_jour : Input should be greater than 0

4. titre : String should have at least 3 characters
```

Le point 3 est la démonstration de la section 1.1 du cours 1 : la validation du navigateur est du
confort. Retirez-la, et c'est le backend qui protège les données.

```python
# app/routers/items.py
from typing import Annotated
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api_client import ApiError, api_client
from app.templating import templates

router = APIRouter()


@router.get("/items", response_class=HTMLResponse)
def list_items_page(request: Request) -> HTMLResponse:
    items = api_client.list_items()
    return templates.TemplateResponse(request, "items/list.html", {"items": items})

@router.get("/items/new", response_class=HTMLResponse)   # AVANT /items/{item_id}
def new_item_page(request: Request):
    return templates.TemplateResponse(
        request, "items/form.html", {"erreurs": [], "valeurs": {}}
    )


@router.post("/items", response_class=HTMLResponse)
def create_item_page(
    request: Request,
    titre: Annotated[str, Form()],
    tarif_jour: Annotated[float, Form()],
    description: Annotated[str, Form()] = "",
    disponible: Annotated[bool, Form()] = False,
):
    valeurs = {
        "titre": titre,
        "description": description,
        "tarif_jour": tarif_jour,
        "disponible": disponible,
    }
    data = {**valeurs, "description": description or None}  # "" -> absence de description
    try:
        item = api_client.create_item(data)
    except ApiError as exc:
        if exc.status_code != 422:
            raise                       # les autres erreurs vont au gestionnaire global
        return templates.TemplateResponse(
            request,
            "items/form.html",
            {"erreurs": exc.messages(), "valeurs": valeurs},
            status_code=422,
        )
    return RedirectResponse(f"/items/{item['id']}", status_code=303)


@router.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail_page(request: Request, item_id: int) -> HTMLResponse:
    item = api_client.get_item(item_id)
    return templates.TemplateResponse(request, "items/detail.html", {"item": item})
```

```html
frontend/app/templates/items/form.html

{% extends "base.html" %}

{% block title %}Proposer un objet — GearShare{% endblock %}

{% block content %}
<h1>Proposer un objet</h1>

{% if erreurs %}
  <div class="alerte alerte-erreur">
    <ul>
      {% for message in erreurs %}<li>{{ message }}</li>{% endfor %}
    </ul>
  </div>
{% endif %}

<form method="post" action="/items">
  <label>Titre
    <input type="text" name="titre" required minlength="3"
           value="{{ valeurs.get('titre', '') }}">
  </label>

  <label>Description
    <textarea name="description">{{ valeurs.get('description', '') }}</textarea>
  </label>

  <label>Tarif / jour (€)
    <input type="number" name="tarif_jour" required min="0.01" step="0.01"
           value="{{ valeurs.get('tarif_jour', '') }}">
  </label>

  <label>
    <input type="checkbox" name="disponible"
           {% if valeurs.get('disponible', true) %}checked{% endif %}>
    Disponible
  </label>

  <button type="submit">Enregistrer</button>
</form>
{% endblock %}
```
---

## Étape 5 — Réserver et annuler depuis la page de détail

Complétez la page de détail d'un item pour gérer ses réservations.

**Client d'API.** Ajoutez trois méthodes à `ApiClient` :

- lister les réservations d'un item (`GET /reservations` avec le paramètre `item_id`) ;
- créer une réservation (`POST /reservations`) ;
- annuler une réservation (`PATCH /reservations/{id}` avec le corps `{"statut": "annulee"}`).

**Page de détail.** Elle affiche, sous les informations de l'item :

- la liste de ses réservations, avec leurs dates et leur statut ;
- pour chaque réservation active, un bouton « Annuler » : un formulaire `POST` (pas un lien) vers
  `/reservations/{reservation_id}`, avec deux champs cachés : `statut` (valeur `annulee`) et
  l'identifiant de l'item, pour savoir où rediriger ;
- un formulaire « Réserver » avec deux champs de type `date`, obligatoires.

**Routes du frontend.**

- `POST /items/{item_id}/reservations` crée la réservation. En cas de succès, elle redirige en
  `303` vers la page de l'item avec un message de confirmation. En cas d'erreur `422`, elle
  réaffiche la page de détail avec les messages et les dates saisies.
- `POST /reservations/{reservation_id}` transmet le changement de statut au backend (un formulaire
  HTML ne sait pas envoyer de `PATCH` : le frontend reçoit un `POST` et appelle `PATCH` sur
  l'API), puis redirige en `303` vers la page de l'item. Si le backend répond `409` (réservation déjà annulée), la page de l'item
  affiche « Cette réservation est déjà annulée. » au lieu d'une page d'erreur.

Placez ces routes dans un nouveau router, `app/routers/reservations.py`.

**Contraintes**, que je vérifierai :

- aucun appel `httpx` en dehors de `api_client.py` ;
- aucune règle métier dans le frontend : ne vérifiez pas les dates en Python, c'est le travail du
  backend ;
- pas de JavaScript ;
- aucun `|safe` dans les templates ;
- aucune adresse de backend en dur.

**Vérifiez :** réservez un item, rechargez la page (une seule réservation), tentez une date de fin
antérieure à la date de début (message d'erreur lisible), annulez, puis tentez d'annuler deux fois
la même réservation en renvoyant le formulaire (bouton Précédent du navigateur) : vous devez voir
le message « déjà annulée », pas une page d'erreur.


Ajout dans l'API Client :
```python
    def list_reservations(self, item_id: int) -> list[dict[str, Any]]:
        return self._send("GET", "/reservations", params={"item_id": item_id})

    def update_reservation_status(self, reservation_id: int, statut: str) -> dict[str, Any]:
        return self._send("PATCH", f"/reservations/{reservation_id}", json={"statut": statut})
```

Dans `router/items.py`, remplacer l'ancienne route :

```python
@router.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail_page(request: Request, item_id: int) -> HTMLResponse:
    item = api_client.get_item(item_id)
    return templates.TemplateResponse(request, "items/detail.html", {"item": item})

Par la nouvelle route avec fonction de rendue partagé dans router/items.py

MESSAGES = {
    "reservee": ("succes", "Réservation enregistrée."),
    "annulee": ("succes", "Réservation annulée."),
    "deja_annulee": ("erreur", "Cette réservation est déjà annulée."),
}


def render_item_detail(request, item_id, *, erreurs=None, valeurs=None, message=None, status_code=200):
    item = api_client.get_item(item_id)
    reservations = api_client.list_reservations(item_id)
    return templates.TemplateResponse(
        request,
        "items/detail.html",
        {
            "item": item,
            "reservations": reservations,
            "erreurs": erreurs or [],
            "valeurs": valeurs or {},
            "message": MESSAGES.get(message),
        },
        status_code=status_code,
    )


@router.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail_page(request: Request, item_id: int, message: str | None = None):
    return render_item_detail(request, item_id, message=message)
```

Nouveau routeur (`router/reservations.py`)

```python
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api_client import ApiError, api_client
from app.routers.items import render_item_detail

router = APIRouter()


@router.post("/items/{item_id}/reservations", response_class=HTMLResponse)
def create_reservation_page(
    request: Request,
    item_id: int,
    date_debut: Annotated[date, Form()],
    date_fin: Annotated[date, Form()],
):
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


@router.post("/reservations/{reservation_id}")
def update_reservation_page(
    reservation_id: int,
    item_id: Annotated[int, Form()],
    statut: Annotated[str, Form()],
):
    try:
        api_client.update_reservation_status(reservation_id, statut)
    except ApiError as exc:
        if exc.status_code == 409:
            return RedirectResponse(f"/items/{item_id}?message=deja_annulee", status_code=303)
        raise
    return RedirectResponse(f"/items/{item_id}?message=annulee", status_code=303)
```

Enregistrer le nouveau routeur dans `main.py`
`app.include_router(reservations.router)`


template `items/detail.py` à compléter par :

```python
{% if message %}
  <div class="alerte alerte-{{ message[0] }}">{{ message[1] }}</div>
{% endif %}

<h2>Réservations</h2>
{% if reservations %}
  <table>
    <thead>
      <tr><th>Du</th><th>Au</th><th>Statut</th><th></th></tr>
    </thead>
    <tbody>
      {% for r in reservations %}
        <tr>
          <td>{{ r.date_debut }}</td>
          <td>{{ r.date_fin }}</td>
          <td>{{ r.statut }}</td>
          <td>
            {% if r.statut != "annulee" %}
              <form method="post" action="/reservations/{{ r.id }}">
                <input type="hidden" name="statut" value="annulee">
                <input type="hidden" name="item_id" value="{{ item.id }}">
                <button type="submit">Annuler</button>
              </form>
            {% endif %}
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% else %}
  <p>Aucune réservation pour le moment.</p>
{% endif %}

<h2>Réserver</h2>
{% if erreurs %}
  <div class="alerte alerte-erreur">
    <ul>{% for m in erreurs %}<li>{{ m }}</li>{% endfor %}</ul>
  </div>
{% endif %}
<form method="post" action="/items/{{ item.id }}/reservations">
  <label>Du
    <input type="date" name="date_debut" required value="{{ valeurs.get('date_debut', '') }}">
  </label>
  <label>Au
    <input type="date" name="date_fin" required value="{{ valeurs.get('date_fin', '') }}">
  </label>
  <button type="submit">Réserver</button>
</form>
{% endblock %}
```

réservez un item, rechargez la page (une seule réservation), tentez une date de fin :

```bash
body : Value error, date_fin doit être postérieure à date_debut
```

---

## Étape 6 — Observer les limites

Deux expériences, qui préparent la suite :

1. **Arrêtez le backend** : `docker compose stop backend`, puis rechargez la liste dans le
   navigateur. Vous devez voir votre page « service indisponible », avec un code `503`, et non une
   stack trace. Relancez-le : `docker compose start backend`.

```bash
Le service est momentanément indisponible. Réessayez dans un instant.

Retour à la liste du matériel
```

2. **Revenez sur la liste.** Vos items ont disparu : le stockage du backend est en mémoire, et il
   a été vidé au redémarrage. Le frontend, lui, n'a rien perdu, puisqu'il ne stocke rien.

C'est précisément ce que règle le TP 2 : vous branchez le backend sur PostgreSQL, et vous
vérifierez que **le frontend continue de fonctionner sans modification**, tant que le contrat de
l'API reste le même.

---

## Ce que vous devez me rendre à la fin du TP 1

Sur le dépôt Git de votre groupe :

1. **Le dépôt réorganisé** : `backend/` et `frontend/`, un `docker-compose.yml` à deux services ;
   `docker compose up --build` suffit à tout démarrer.
2. **Les tests de la séance 2 qui passent** dans `backend/`, sans modification.
3. **Le frontend** : liste, détail, création d'un item, réservation et annulation depuis la page
   de détail, en respectant les contraintes de l'étape 5.

```bash
docker compose run --rm backend pytest
============================================================== 35 passed, 1 warning in 0.51s ===============================================================
```

## Pour aller plus loin

- **Testez le frontend sans backend.** Avec le `TestClient` de FastAPI et `monkeypatch`,
  remplacez les méthodes de l'instance `api_client` par de fausses méthodes qui renvoient des
  données fixes ou lèvent une `ApiError`. Vérifiez qu'un `404` du backend donne une page `404`, et qu'une
  création réussie répond `303`.
- Ajoutez des filtres à la liste du matériel (recherche par titre, « disponibles uniquement ») :
  un formulaire en `GET` dont les champs deviennent les query parameters `q` et `disponible` de
  l'API.
- Ajoutez la modification d'un item (`PATCH` côté API) : remarquez que le formulaire HTML est
  en `POST`, et que c'est le client d'API qui appelle `PATCH`.
