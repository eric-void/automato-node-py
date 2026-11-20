# Installation

[Documentation index](README.md)

## Requirements

- Python 3.11 or newer.
- An MQTT broker reachable by the node, for example [Mosquitto](https://mosquitto.org/) 2. Browser clients need a websocket listener on it.
- The two repositories side by side: the launcher looks for the core in `../automato-core-py`.

```
automato-core-py/
automato-node-py/
```

## From source

```sh
git clone https://github.com/eric-void/automato-core-py.git
git clone https://github.com/eric-void/automato-node-py.git
```

Install the dependencies (in a virtual environment, or with the system package manager where available):

```sh
pip install -r automato-core-py/requirements.txt
pip install -r automato-node-py/requirements.txt
```

The core evaluates the expressions of definitions with Js2Py. The PyPI release does not work after Python 3.11: on newer versions install a patched fork **before** the requirements, otherwise pip keeps the PyPI one (same version number):

```sh
pip install 'Js2Py @ git+https://github.com/a-j-albert/Js2Py.git@cc64a715727f110b79310b8031e0ade9c501d5d3'
```

### QuickJS scripting engine

Js2Py is the default engine; QuickJS is faster and works on every Python version (`"scripting-engine": "quickjs"` in the configuration, see [Node configuration](configuration.md#keys)). It needs the `quickjs-ng` package:

```sh
pip install -r automato-core-py/requirements-quickjs.txt
```

PyPI has wheels for Linux x86_64/aarch64, Windows and macOS, not for OpenWrt armv7, which has no compiler: build the wheel on a PC and copy it to the node (see [On OpenWrt](#quickjs-on-openwrt)).

At startup the node logs `scripting_js> scripting engine: quickjs` (or `js2py`). If the configured engine cannot be loaded (for example `quickjs-ng` is not installed) it logs an error and uses the other one, so the node starts anyway. To switch back, set `"scripting-engine": "js2py"` and restart: keep Js2Py installed as long as you want to be able to do it.

Modules with external dependencies have their own requirements file, next to the module: `src/automato/modules/<module>-requirements.txt`. Install only the ones you use, or all of them with:

```sh
pip install -r automato-node-py/requirements-all.txt
```

| Module | Needs |
|---|---|
| `astral`, `astral2` | astral |
| `net` (some checks), `http-request` | requests |
| `net_ping`, `net_sniffer` (ping) | icmplib |
| `net_sniffer_scapy` | scapy |
| `nut` | pynutclient |
| `solaredge_modbus_tcp` | solaredge-modbus, pymodbus < 3.7 |
| `speedtest` | speedtest-cli |
| `telegram` | python-telegram-bot 22 |
| `notifications-webpush` | pywebpush |
| `influxdb` | influxdb-client |
| `rf_listener` | RPi.GPIO (on a Raspberry Pi) |

Some modules call system commands (`ip`, `iw`, `ping`, `ifstatus`...): see their options in [Modules](modules.md).

## Running

```sh
automato-node-py/bin/automato-node.sh -c /etc/automato/automato.conf
```

`bin/automato-node.sh` sets `PYTHONPATH` to the sources of the node and the core and starts `src/automato/node/launcher.py`. See [Node configuration](configuration.md) for the file and the command line options.

The node stops cleanly on `Ctrl+C` or `SIGTERM`, saving the data of its entries.

## As a systemd service

[bin/automato.service](../bin/automato.service) is a unit file that runs the node as an `automato` user:

```sh
useradd -r -s /usr/bin/nologin automato
cp automato-node-py/bin/automato.service /etc/systemd/system/
# edit ExecStart with the path of the checkout and the -c option
systemctl enable --now automato
```

The user must be able to write the storage and log paths of the configuration.

## On OpenWrt

[bin/automato-init-procd-script](../bin/automato-init-procd-script) is a procd init script. Copy (or link) it in `/etc/init.d/`, set `SCRIPT` and `CONFIGFILE` at its top, create the `automato` user and group as described in its comments, then:

```sh
/etc/init.d/automato enable
/etc/init.d/automato start
```

On a router CPU and memory are limited: keep `listen_all_events` off, prefer `log-level: info`, use the [QuickJS engine](#quickjs-scripting-engine) (about 3 times faster than Js2Py on an armv7 router), and run heavy modules (history, InfluxDB, Telegram) on another node.

### QuickJS on OpenWrt

PyPI has no `quickjs-ng` wheel for armv7 and the router has no compiler. [bin/build-quickjs-wheel.sh](../bin/build-quickjs-wheel.sh) builds it on a PC with Docker, in an Alpine container (musl, as OpenWrt). For a foreign architecture the PC needs qemu user emulation (Arch Linux: `pacman -S qemu-user-static qemu-user-static-binfmt`, then `systemctl restart systemd-binfmt`). The wheel is abi3: one file for every Python >= 3.10.

```sh
# on the PC (a few minutes under emulation; PLATFORM=linux/arm64 for an aarch64 router)
automato-node-py/bin/build-quickjs-wheel.sh dist
scp dist/quickjs_ng-*-linux_armv7l.whl root@router:/tmp/

# on the router (about 750 KB in the overlay; --no-cache-dir keeps pip's cache out of the flash)
pip3 install --no-deps --no-cache-dir /tmp/quickjs_ng-*-linux_armv7l.whl
python3 -c "import quickjs; print(quickjs.Context().eval('[1, 2].map(x => x * 2)').json())"
rm /tmp/quickjs_ng-*.whl
```

Then set `"scripting-engine": "quickjs"` in the configuration and restart the node (`/etc/init.d/automato restart`); the log must show `scripting_js> scripting engine: quickjs`. Add the wheel to the list of packages to reinstall after a firmware upgrade.

## With Docker

The [Dockerfile](../Dockerfile) builds an image with the node, the core and all the module dependencies (Python 3.13, both scripting engines: Js2Py fork and QuickJS). It is built from the directory that contains both checkouts:

```sh
docker build -f automato-node-py/Dockerfile -t automato-node:local .
```

The image reads `/etc/automato/automato.conf` and keeps data in `/var/lib/automato` and logs in `/var/log/automato`. It needs BuildKit (`docker buildx`) for the dedicated ignore file. [docker/README.md](../docker/README.md) has a Compose setup and the details.

## Several nodes

Every node connects to the same broker and has the `nodes` module. Exactly one of them should be the **master** (`"config": { "master": true }`): it answers the clients' `automato/data/get` requests. Give each node a different `name`. See the `nodes` module in [Modules](modules.md#nodes).
