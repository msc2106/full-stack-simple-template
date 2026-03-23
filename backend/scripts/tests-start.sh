#! /usr/bin/env bash
set -e
set -x

docker compose down testdb
docker compose up --wait testdb
bash scripts/prestart.sh

bash scripts/test.sh "$@"

docker compose down testdb
