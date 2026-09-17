#!/usr/bin/env bash
# Aurea — deploy script for the production VPS.
#
# INSTALLED AT /home/deploy/deploy.sh on the server, deliberately OUTSIDE the git
# tree: the script must not be overwritten by the checkout it is performing.
# This copy is the source of truth — when it changes here, reinstall it there.
#
# It is the forced command of the CI SSH key (command="..." in authorized_keys),
# so that key can run this and nothing else, even though the deploy user has sudo.
set -euo pipefail

REPO=/home/deploy/bot_curriculum
UV=/home/deploy/.local/bin/uv
BRANCH=main

cd "$REPO"

git fetch --prune origin
# -f discards local changes to tracked files; -B moves the local branch onto the
# remote one, which is also what switches this checkout from develop to main.
# Never `git clean` here: .env lives in this directory, untracked.
git checkout -f -B "$BRANCH" "origin/$BRANCH"

echo "[deploy] now at $(git log --oneline -1)"

"$UV" sync --frozen
sudo systemctl restart botcv

echo "[deploy] botcv restarted"
