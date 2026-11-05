#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/../docker/compose.tests.yaml"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --remove-orphans
}

trap cleanup EXIT
docker compose -f "$COMPOSE_FILE" run --build --rm test-runner "$@"
exit $?
