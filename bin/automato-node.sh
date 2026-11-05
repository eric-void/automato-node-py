#!/bin/sh

export SELENIUM_MANAGER_DISABLED=true
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONPATH="$SCRIPT_DIR/../src:$SCRIPT_DIR/../../automato-core-py/src${PYTHONPATH:+:$PYTHONPATH}"
exec python "$SCRIPT_DIR/../src/automato/node/launcher.py" "$@"
