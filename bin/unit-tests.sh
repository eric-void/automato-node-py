#!/bin/sh
# Code-oriented unit tests: no broker, no network, a few seconds. They complement the "live" module tests (docker-tests.sh).
# Suites: automato-core-py/tests and automato-node-py/tests (each one in its own python process).
#
# By default they run in the automato-node-tests image (built by docker-tests.sh), with the sources of this checkout mounted:
#   bin/unit-tests.sh                      # python 3.13
#   PYTHON_VERSION=3.11 bin/unit-tests.sh  # python 3.11 (golconda version)
#   bin/unit-tests.sh --local              # local python (dependencies must be installed)
# Other arguments are passed to "python -m unittest discover" (e.g. -v, -k pattern).

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

if [ "$1" = "--inside" ] || [ "$1" = "--local" ]; then
  shift
  export PYTHONPATH="$ROOT/automato-node-py/src:$ROOT/automato-core-py/src"
  export PYTHONDONTWRITEBYTECODE=1
  failed=0
  for suite in automato-core-py/tests automato-node-py/tests; do
    printf '\n===== Unit tests: %s =====\n' "$suite"
    python -m unittest discover -s "$ROOT/$suite" -t "$ROOT/$suite" -p 'test_*.py' "$@" || failed=1
  done
  exit "$failed"
fi

IMAGE="automato-node-tests:py${PYTHON_VERSION:-3.13}"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image $IMAGE not found: build it with PYTHON_VERSION=${PYTHON_VERSION:-3.13} bin/docker-tests.sh (or use --local)" >&2
  exit 2
fi
exec docker run --rm -e TZ=Europe/Rome -v "$ROOT/automato-core-py:/w/automato-core-py:ro" -v "$ROOT/automato-node-py:/w/automato-node-py:ro" \
  --entrypoint /w/automato-node-py/bin/unit-tests.sh "$IMAGE" --inside "$@"
