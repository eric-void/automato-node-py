# Known issues (Docker test run)

Issues found running `bin/docker-tests.sh` (Python 3.13, 2026-10-28). Last run
(2026-11-11, Python 3.13 and 3.11): 20/20 test units pass (`nut_test` and
`telegram_test` included).

## Open

None.

## Fixed in the Docker setup

- `nut_test` was not in `bin/all-tests.sh`, and once added it failed
  `t4-changes`: `./var/ups_status` generates one `output` event per port, and
  `assertSomeEvents` in core `test.py` saw only the last one (events were
  indexed by name). It now matches any event with that name. The test is in
  the default list.
- `nut-requirements.txt` required `nut2`, a different client (module `nut2`,
  does not build on Python 3.13), while `nut.py` imports `PyNUT`, which has no
  pip package. The file now only documents the manual install (NUT v2.8.4+ on
  Python 3.13, as the Dockerfile does). Update (2026-11-11): NUT now publishes
  the official `pynutclient` pip package (module `PyNUTClient.PyNUT`), used by
  `nut.py` and installed from `nut-requirements.txt`.
- Production `compose.yaml` had no time zone, so a containerized node ran in
  UTC: it now sets `TZ: ${TZ:-Europe/Rome}`, as `config/sauron-docker` does.
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
