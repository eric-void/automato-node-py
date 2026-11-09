# Known issues (Docker test run)

Issues found running `bin/docker-tests.sh` (Python 3.13, 2026-10-28). Last run
(2026-11-09): 17/17 test units pass, also `shelly_test` and `net_test` on
Python 3.11.

## Open

### `nut-requirements.txt` lists the wrong package

`src/automato/modules/nut-requirements.txt` requires `nut2`, but `nut.py`
imports `PyNUT` (NUT's own client module, not on PyPI; see the module
docstring). `nut2` provides a `nut2` module instead, and fails to build on
Python 3.13 (`telnetlib` was removed). The Dockerfile no longer uses this file
and downloads `PyNUT.py` from NUT v2.8.4 (socket based, no `telnetlib`).
`requirements-all.txt` does not include it either.

### `nut_test` is not in `bin/all-tests.sh`

`launcher.py` runs `nut_test` with `--test '*'`, but `bin/all-tests.sh` (and so
the Docker runner) does not include it in the default list.

### Production `compose.yaml` has no time zone

The test runner sets `TZ: Europe/Rome`, required by tasmota and scheduler
fixtures. `compose.yaml` does not set `TZ`, so a containerized node runs in UTC:
cron schedules and local-time conversions would differ from a host install.

## Fixed in the Docker setup

- `shelly_test`: gen2 switch status always emitted an `energy` event, empty
  (only the `energy:init` definitions) when the payload had no energy fields.
  The `energy` script now returns `null` in that case; added `g2_energy` with
  a payload that has them. The test also expected `temperature` without
  `port`, added on purpose in `30611f8`.
- `net_test`: `t2-ping` failed because of the broker healthcheck, not the
  `net` module. A check without `assertEventsTopic` matches any message, and
  the `healthcheck` message published every 2s by `mosquitto_pub` (no events)
  arrived first. The asserts now name the `net/wan-connected` topic.
- Js2Py fork not installed: PyPI's `Js2Py 0.74` (from core requirements) has
  the same version as the fork, so pip kept it and `import js2py` failed on
  Python 3.13 ("Your python version made changes to the bytecode"). The fork is
  now installed first.
- `nut2` failed the build on Python 3.13 (see above).
- `ping` missing from the image (`net` module, `wan-connected-check-method:
  ping`): added `iputils-ping`.
- Test container ran in UTC, failing tasmota (clock off by 1/2 hours) and
  scheduler asserts: `TZ: Europe/Rome` in `compose.tests.yaml`.
- `Dockerfile.dockerignore` is honored only by BuildKit; with the legacy builder
  the whole workspace (including `config`) was sent as build context and
  `.git`/`__pycache__` ended up in the image. BuildKit (`docker-buildx`) is now
  required; `__pycache__`/`*.pyc` are also excluded.
