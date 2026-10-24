# buildq: compilations demandées à la buildbox sans copie manuelle

La buildbox (session Claude sur VINCENT-PC, WSL2) n'a ni port entrant, ni clé SSH vers le Pi, ni dossier partagé
du projet. Elle sait seulement sortir en HTTPS vers GitHub. `scripts/buildq/buildq.sh` en fait une file d'attente
portée par git: une branche orpheline `buildq` (jamais `main`) de `BUILDQ_REPO` (défaut
`Ashram56/Tron-Legacy-MPF`).

```
requests/<id>/{request.json,patch.diff}     poussé par le demandeur
results/<id>/{status,SHA256SUMS,build.log,<artefacts>}   poussé par la buildbox
```

## Demandeur (session cloud, Pi, tout poste avec git et un jeton GitHub `GH_TOKEN`)

```bash
id=$(bash scripts/buildq/buildq.sh submit mon.patch)     # cible par défaut: gozen_arm64
bash scripts/buildq/buildq.sh wait "$id" 900              # 0 = ok, 1 = failed, 2 = timeout
bash scripts/buildq/buildq.sh fetch "$id" ./out           # copie et vérifie le sha256 (échoue si faux)
```

## Buildbox (une fois par session, le patch arrive en $1, la sortie va dans $2)

```bash
export GH_TOKEN=...   # déjà présent s'il pousse sur le dépôt (tmp/gozen-arm64-* a marché)
bash scripts/buildq/buildq.sh serve 20     # à lancer via Monitor / en arrière-plan; traite chaque demande une fois
```

`BUILDQ_BUILD_CMD` (défaut `bash ~/tron-gozen/fast/gozen_arm64.sh`) est appelée `CMD <patch> <dossier_sortie>`: le
script de build doit déposer ses fichiers dans ce dossier (adapter l'appel si `gozen_arm64.sh` prend d'autres
arguments). `prune [N]` garde les N dernières demandes et réécrit la branche sans historique (les binaires ne
s'accumulent pas).

## À savoir

- Dépôt public: les binaires de la branche `buildq` sont visibles. Ici c'est du GoZen/FFmpeg open source plus
  notre patch, déjà commité dans `pup_addons`. Pour du privé: `BUILDQ_REPO=Ashram56/Tron-Legacy-MPF-Private`
  (il faut que les jetons du demandeur et de la buildbox le lisent).
- Limite de GitHub: 100 Mo par fichier. Au-delà, compresser (`xz`) ou passer par une release.
- Latence: intervalle de `serve` (20 s) + temps de build (8 s) + `wait` (10 s).
- Seul le demandeur nommé dans `request.json` est indicatif; l'accès repose sur le jeton GitHub.
