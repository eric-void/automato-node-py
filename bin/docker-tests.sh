#!/bin/sh
# Set PYTHON_VERSION (e.g. 3.11, the golconda version) to build and run the
# tests on another Python; the default is 3.13.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/../docker/compose.tests.yaml"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --remove-orphans
}

trap cleanup EXIT
docker compose -f "$COMPOSE_FILE" run --build --rm test-runner "$@"
exit $?
