#!/bin/bash
# File d'attente de compilations par git: les demandeurs (sessions cloud, Pi) poussent une demande, la buildbox
# compile et repousse le résultat, le demandeur le récupère et vérifie le sha256. Aucun SSH, aucun port entrant.
# Tout vit sur une branche orpheline (jamais main): BUILDQ_BRANCH du dépôt BUILDQ_REPO. Voir docs/buildq.md.
#
#   buildq.sh submit <fichier.patch> [cible]   -> affiche l'id de la demande      (demandeur)
#   buildq.sh wait <id> [timeout_s]            -> attend le résultat, code 0 = ok (demandeur)
#   buildq.sh fetch <id> <dossier>             -> copie les fichiers + vérifie sha256 (demandeur)
#   buildq.sh serve [intervalle_s]             -> boucle: traite les demandes     (buildbox)
#   buildq.sh prune [garder]                   -> garde les N dernières demandes  (buildbox)
set -euo pipefail
REPO="${BUILDQ_REPO:-Ashram56/Tron-Legacy-MPF}"
BRANCH="${BUILDQ_BRANCH:-buildq}"
WORK="${BUILDQ_WORK:-$HOME/.cache/buildq}"
# commande de build de la buildbox; reçoit le patch en $1 et le dossier de sortie en $2
BUILD_CMD="${BUILDQ_BUILD_CMD:-bash $HOME/tron-gozen/fast/gozen_arm64.sh}"
URL="${BUILDQ_URL:-https://github.com/$REPO.git}"
[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] && URL="https://x-access-token:${GH_TOKEN:-$GITHUB_TOKEN}@github.com/$REPO.git"

sync() {  # clone/maj de la branche; la crée (orpheline) si absente
  if [ ! -d "$WORK/.git" ]; then mkdir -p "$WORK"; git init -q "$WORK"; git -C "$WORK" remote add origin "$URL"; fi
  git -C "$WORK" remote set-url origin "$URL"
  git -C "$WORK" config user.name buildq; git -C "$WORK" config user.email buildq@localhost
  if git -C "$WORK" fetch -q origin "$BRANCH" 2>/dev/null; then git -C "$WORK" checkout -q -B "$BRANCH" "origin/$BRANCH"
  else git -C "$WORK" checkout -q --orphan "$BRANCH" 2>/dev/null || git -C "$WORK" checkout -q "$BRANCH"; fi
}
push() {  # $1 message; recommence si quelqu'un a poussé entre-temps
  git -C "$WORK" add -A; git -C "$WORK" commit -q -m "$1" || return 0
  for i in 1 2 3 4; do
    git -C "$WORK" push -q origin "$BRANCH" && return 0
    sleep $((2 << i)); git -C "$WORK" pull -q --rebase origin "$BRANCH" || true
  done; return 1
}
cmd="${1:-}"; shift || true
case "$cmd" in
submit)
  patch="$1"; target="${2:-gozen_arm64}"; sync
  sha=$(sha256sum "$patch" | cut -c1-8); id="$(date -u +%Y%m%dT%H%M%SZ)-$sha"
  d="$WORK/requests/$id"; mkdir -p "$d"; cp "$patch" "$d/patch.diff"
  printf '{"id":"%s","target":"%s","requester":"%s"}\n' "$id" "$target" "${BUILDQ_REQUESTER:-$(hostname)}" > "$d/request.json"
  push "request $id" && echo "$id" ;;
wait)
  id="$1"; t=$(( $(date +%s) + ${2:-900} ))
  while [ "$(date +%s)" -lt "$t" ]; do
    sync; s="$WORK/results/$id/status"
    if [ -f "$s" ]; then cat "$s"; [ "$(cat "$s")" = ok ]; exit $?; fi
    sleep 10
  done; echo timeout; exit 2 ;;
fetch)
  id="$1"; out="$2"; sync; r="$WORK/results/$id"; mkdir -p "$out"
  [ -f "$r/status" ] || { echo "pas de résultat pour $id" >&2; exit 1; }
  cp "$r"/* "$out"/; cd "$out"
  [ -f SHA256SUMS ] && sha256sum -c SHA256SUMS ;;
serve)
  every="${1:-20}"; echo "buildq: écoute de $REPO@$BRANCH toutes les ${every}s"
  while true; do
    sync || { sleep "$every"; continue; }
    for q in "$WORK"/requests/*/; do
      [ -d "$q" ] || continue; id=$(basename "$q"); r="$WORK/results/$id"; [ -f "$r/status" ] && continue
      mkdir -p "$r"; echo "buildq: construit $id"
      if $BUILD_CMD "$q/patch.diff" "$r" > "$r/build.log" 2>&1; then st=ok; else st=failed; fi
      tail -c 20000 "$r/build.log" > "$r/build.log.tmp"; mv "$r/build.log.tmp" "$r/build.log"
      ( cd "$r" && find . -maxdepth 1 -type f ! -name status ! -name SHA256SUMS -printf '%f\n' | xargs -r sha256sum > SHA256SUMS )
      echo "$st" > "$r/status"; push "result $id $st" && echo "buildq: $id $st (publié)"
    done
    sleep "$every"
  done ;;
prune)
  keep="${1:-10}"; sync
  for kind in requests results; do ls -1 "$WORK/$kind" 2>/dev/null | sort | head -n -"$keep" | while read -r i; do git -C "$WORK" rm -rq "$kind/$i"; done; done
  push "prune"
  # l'historique garde les anciens binaires: repartir d'une branche vide
  git -C "$WORK" checkout -q --orphan tmp-squash && git -C "$WORK" add -A && git -C "$WORK" commit -q -m "buildq squash"
  git -C "$WORK" push -q -f origin "tmp-squash:$BRANCH" ;;
*) sed -n '2,12p' "$0"; exit 1 ;;
esac
