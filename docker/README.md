# Automato Node in Docker

The image runs the node on Python 3.13 and uses the Js2Py fork/patch currently
needed by Automato on Python versions after 3.11. It connects to the MQTT
broker configured in `automato.conf`; it does not start a broker.

## Build and run with Compose

From this directory, create `automato-config/automato.conf` and set its MQTT
connection details. The file is read-only inside the container. For example:

```json
{
  "name": "my-node",
  "mqtt": {
    "broker_host": "mqtt.example.net",
    "broker_port": 1883
  },
  "storage": "/var/lib/automato",
  "log": "/var/log/automato/automato.log",
  "error-log": "/var/log/automato/automato-errors.log"
}
```

Add the node's normal `entries` and other settings to this configuration, or
include configuration fragments from `/etc/automato`. Relative include paths
and local module paths continue to resolve from the configuration directory.

Create the mounted directories and allow the container's default UID/GID
`1000:1000` to write to the data and log directories. Then run:

```sh
mkdir -p automato-config automato-data automato-logs
docker compose up -d --build
docker compose logs -f
```

The config directory is mounted read-only at `/etc/automato`, persistent node
storage at `/var/lib/automato`, and logs at `/var/log/automato`. Compose can
also use alternate host paths through `AUTOMATO_CONFIG_DIR`,
`AUTOMATO_DATA_DIR`, and `AUTOMATO_LOG_HOST_DIR` environment variables.

`AUTOMATO_STORAGE_DIR` and `AUTOMATO_LOG_DIR` can be set to change the
container-side storage and log directories. When `AUTOMATO_LOG_DIR` is set,
configured `log`, `error-log`, `messages-log`, and `debug-log` files are placed
there using their configured filenames. Any other configured writable paths
(for example, a module history directory) should use an absolute path under a
mounted writable directory such as `/var/lib/automato`.

To build manually from the workspace root:

```sh
docker build -f automato-node-py/Dockerfile -t automato-node:local .
```

The Dockerfile-specific ignore file limits the build context to the node and
core source trees. It is honored only by BuildKit (`docker-buildx`): the
legacy builder ignores it, sends the whole workspace (including `config`) to
the Docker daemon and copies `.git`/`__pycache__` into the image. To run directly, mount the three directories above and use
the same container paths; the default command reads
`/etc/automato/automato.conf`.

## Run the test suite with a temporary Mosquitto broker

From the workspace root, run:

```sh
automato-node-py/bin/docker-tests.sh
```

This starts an isolated Mosquitto 2 broker on the Compose network, waits for
its health check, runs the same test units listed in `bin/all-tests.sh`, and
stops the test containers when finished. The broker is not published on the
host and has anonymous access enabled only for this throwaway test network.
The runner returns a nonzero exit code if a test unit or one of its assertions
fails. Pass test unit names to run only a subset, for example:

```sh
automato-node-py/bin/docker-tests.sh shelly_test net_test
```

`AUTOMATO_TEST_CONFIG` can point `bin/all-tests.sh` at a different config
when running the suite directly. The Docker runner uses the bundled
`docker/test-config.json`, which connects to the Compose service named
`mosquitto`.

Current test failures and other known problems are tracked in
[KNOWN-ISSUES.md](KNOWN-ISSUES.md).
