# automato-node-py

Python server/node runtime built on `../automato-core-py`. Read workspace architecture in `../AGENTS.md` and `../ARCHITECTURE.md`.

## Layout

- `src/automato/node/launcher.py`: CLI/config loading and process lifecycle.
- `node_system.py`: connects core entries to local module handlers, installs/initializes/unloads entries, schedules periodic/cron publishing and coordinates runtime state.
- `storage.py`: persistent entry data.
- `src/automato/modules/`: built-in device and service integrations (Shelly, Tasmota, Zigbee2MQTT, networking, presence, notifications, history, etc.) and adjacent tests.
- `bin/`: service/launcher scripts and test runner.
- `tests/`: code-oriented unit tests (no broker, the node runs with a fake one, see `tests/node_helpers.py`); `bin/unit-tests.sh` runs them with the core ones (`../automato-core-py/tests`) in the test image. The "live" module tests (`*_test.py`, `bin/docker-tests.sh`) need a broker.
- `requirements.txt`: node/core baseline dependencies; `requirements-all.txt` and module-specific files cover optional integrations.

## Guidance

Treat entry lifecycle hooks (`entry_load`, batch load/install, `entry_init`, unload) as a central extension contract. Module definitions are consumed by the shared core and exported to clients, so changes may affect Python/JS core parity and browser interpretation. Before editing a module, find its tests, config references in `../config`, and optional dependency file. Do not assume every module is enabled on every node. Deployment configuration may contain sensitive data.
