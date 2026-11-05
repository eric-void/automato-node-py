# Known issues (Docker test run)

Issues found running `bin/docker-tests.sh` (Python 3.13, 2026-10-28). Last run:
15/17 test units pass; `shelly_test` and `net_test` fail.

## Open

### shelly_test: gen2 switch status emits an empty `energy` event

Failing asserts: `g2_get_on`, `g2_get_off`, `g2_get_response` (27/30 OK).

Since commit `f8c72a3` ("Shelly: support for gen2+ energy events and
shelly2pmg3"), the gen2 `switch_N_status` and `switch_N_get` handlers in
`src/automato/modules/shelly.py` always produce an `energy` event. When the
payload has no `apower`/`aenergy`/`voltage`/... fields the `jsf:` script returns
`{}`, so the event carries only the `energy:init` definitions (`power:def`,
`power:unit`, ...) and no values. The tests in `shelly_test.py` were not updated
and do not expect it.

Likely fix: return `null` from the `energy` script when no field is present (as
the `temperature` event already does), instead of changing the tests. Should add
a test with a payload that does contain energy fields.

### net_test: `t2-ping` gets no `connected` event

Failing assert: `t2-ping.events` (3/4 OK). `ping` works in the container and
`net/wan-connected = 1` is published and received (`subscribe_payload` OK), but
no `connected` event is generated. Probably because `t1-http` already
produced the same value (`connected = 1`, port `wan`) and the event is not
re-emitted for an unchanged value. Not yet investigated: check event
deduplication/`changed` handling in `net.py`, or reset state between t1 and t2
in `net_test.py`.

Neither failure has been checked outside Docker: the host has no Python
environment for automato (Python 3.14, no `js2py`).

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
