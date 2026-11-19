# Tests

[Documentation index](README.md)

There are two kinds of tests, both run from the directory that contains the checkouts (`automato-core-py` and `automato-node-py` side by side).

## Unit tests

Code-oriented tests of the core and the node: no broker, no network, a few seconds. The node runs with a fake broker (see [tests/node_helpers.py](../tests/node_helpers.py)).

```sh
automato-node-py/bin/unit-tests.sh                      # Python 3.13, in the test image
PYTHON_VERSION=3.11 automato-node-py/bin/unit-tests.sh  # Python 3.11
automato-node-py/bin/unit-tests.sh --local              # local Python, with the dependencies installed
automato-node-py/bin/unit-tests.sh -k scheduler         # options of "python -m unittest discover"
```

They run the suites in `automato-core-py/tests` and `automato-node-py/tests`. The test image (`automato-node-tests:py<version>`) is built by the live test runner below; build it once before using the docker mode.

Every bug fix in the core or the node should come with a unit test.

## Live tests

Module tests that go through a real broker: each `*_test.py` (in `src/automato/modules`, plus `system_test.py` in the core and `node_system_test.py`) starts the node with a test configuration, sends messages and checks the events, the published messages and the notifications.

With Docker, a temporary Mosquitto broker is started on an isolated network:

```sh
automato-node-py/bin/docker-tests.sh                     # all test units
automato-node-py/bin/docker-tests.sh shelly_test net_test
PYTHON_VERSION=3.11 automato-node-py/bin/docker-tests.sh
```

Against a broker of your choice, with a configuration that points to it (see [docker/test-config.json](../docker/test-config.json)):

```sh
AUTOMATO_TEST_CONFIG=my-test-config.json automato-node-py/bin/all-tests.sh
automato-node-py/bin/automato-node.sh -c my-test-config.json --test toggle_test
```

Do not run live tests on a production broker: they publish test topics and retained messages.

[docker/KNOWN-ISSUES.md](../docker/KNOWN-ISSUES.md) tracks the state of the suite.

## Core parity

Changes to the core must also be checked against the JavaScript core: see [automato-core-js](https://github.com/eric-void/automato-core-js#tests) (`node automato-core-js/test/run.js` and `node automato-core-js/test/parity/run.js`, which uses the `automato-node:local` image).
