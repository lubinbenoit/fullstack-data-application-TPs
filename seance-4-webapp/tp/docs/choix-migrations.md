# Choix de migrations

## 6.2. Votre choix : comment appliquer les migrations ?

### 1. Que se passe-t-il au **deuxième** `docker compose up`, quand la base est déjà à jour ?

```
alembic upgrade head compare la révision enregistrée dans alembic_version avec la dernière du dossier versions/. Elles sont identiques, donc il ne fait rien et sort avec le code 0. L’opération est idempotente. Avec l’option 2, le conteneur migrate repasse par Exited (0), et le backend démarre normalement.
```

### 2. Si une migration échoue, que voit-on dans `docker compose ps` et dans les logs ? Le backend démarre-t-il quand même ?

```
Avec l'option 1 : l’erreur survient dans le conteneur backend, qui s’arrête (Exited (1)), ou boucle en redémarrage avec une restart policy. La trace des migrations se mélange aux logs de l’API.

Avec l'option 2 : docker compose ps -a montre migrate en Exited (1), et le backend n’est jamais lancé (il reste Created). docker compose up s’arrête avec un message du type service "migrate" didn't complete successfully: exit 1. La trace est isolée dans docker compose logs migrate. Le frontend, qui dépend du backend, ne démarre pas non plus.

Dans les deux cas le backend ne démarre pas, mais l’option 2 rend l’échec bien plus lisible.
```

### 3. En production, que se passerait-il si trois instances du backend démarraient en même temps sur une base pas encore migrée ? (Inutile de le tester en local : le port `8000` publié empêche de lancer plusieurs instances.)

```
Avec l'option 1 : chacune exécute upgrade head en même temps, et elles se marchent dessus. Deux instances tentent de créer les mêmes tables, et l’une échoue avec relation already exists, ou bien deux écritures simultanées dans alembic_version entrent en conflit. Le résultat dépend du hasard : certaines instances plantent, d’autres démarrent. Alembic ne verrouille pas par défaut.

Avec l'option 2 : les migrations ne sont exécutées qu’une fois, par un seul processus, et les instances ne démarrent qu’ensuite. C’est le schéma des orchestrateurs (job de migration avant le déploiement).
```

### 4. Votre backend tourne en `--reload` pendant le développement : votre option fonctionne-t-elle toujours ?

```
Dans les deux options, la migration ne s’exécute qu’au démarrage du conteneur. --reload ne relance que le processus Python quand un fichier change, pas l’entrypoint ni le service migrate. Si on ajoute une migration pendant le développement, il faut la relancer avec docker compose run --rm migrate (option 2). Avec l’option 1, il faut redémarrer tout le backend. Pour que migrate voie les nouveaux fichiers sans rebuild, il faut lui donner les mêmes montages alembic/ et alembic.ini que le backend.
```

### Choix de l'option et justification

```
L'option 2 est meilleure pour plusieurs raisons :

- Séparation des responsabilités : le backend ne fait que servir l’API, et une panne de migration est visible séparément.
- Pas de course entre instances (question 3).
- Moins de pièges sous Windows : un entrypoint.sh édité sous Windows avec des fins de ligne CRLF produit l’erreur exec ./entrypoint.sh: no such file or directory dans le conteneur. Il faut aussi le rendre exécutable et finir par exec "$@" pour que uvicorn reçoive les signaux d’arrêt. L’option 2 évite tout cela.
- Moins de code : c'est juste un service, il n'y a pas de script.

Le seul avantage de l’option 1 est de tenir en un conteneur, ce qui ne vaut pas ces inconvénients.
```