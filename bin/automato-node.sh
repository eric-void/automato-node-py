#!/bin/sh

export SELENIUM_MANAGER_DISABLED=true
export PYTHONPATH="$(dirname "$0")/../src:$(dirname "$0")/../../automato-core-py/src"
$(dirname "$0")/../src/automato/node/launcher.py $*
