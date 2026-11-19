# automato-node-py

The node of **Automato**, a home automation framework built on MQTT.

A node is a Python service connected to an MQTT broker. It reads a configuration with a list of **entries** (devices, services, automations), loads the **modules** they need, turns MQTT messages into events, runs handlers, schedules periodic tasks and shares the definitions of its entries with the other nodes and the clients. It runs on small systems too: it is used on an OpenWrt router as well as on a server or in Docker.

It is built on [automato-core-py](https://github.com/eric-void/automato-core-py), which defines the entry/event/action model.

## Features

- Devices described in JSON: any MQTT device can be read and commanded, with JavaScript expressions that map payloads to standard events (`output`, `temperature`, `energy`...) and actions (`output-set`).
- Ready made integrations: Shelly (gen 1 and gen 2+), Tasmota, Zigbee2MQTT, OwnTracks, NUT (UPS), SolarEdge (modbus TCP), room-assistant, RF 433 MHz.
- Automations: event listeners in the configuration (`"on": {"door.contact": {"do": "siren.output-set"}}`), a scheduler with cron rules, toggles with timers, Python scripts.
- Health monitoring of every entry, presence detection (wifi, network sniffing, location), notifications with history, Telegram bot and web push.
- More nodes on the same broker share their entries: an automation on one node can use devices handled by another.
- Persistent state, cron and interval scheduling with load-based throttling, data export to InfluxDB.

## The Automato projects

| Repository | What it is |
|---|---|
| [automato-core-py](https://github.com/eric-void/automato-core-py) | Python core, and the reference documentation of definitions and protocol |
| [automato-core-js](https://github.com/eric-void/automato-core-js) | The same core in JavaScript, for browser clients |
| **automato-node-py** (this one) | The node |
| [automato-http-client](https://github.com/eric-void/automato-http-client) | A static web client (in progress) |

## Quick start

The node needs an MQTT broker (for example [Mosquitto](https://mosquitto.org/)) and the core checked out next to it:

```sh
git clone https://github.com/eric-void/automato-core-py.git
git clone https://github.com/eric-void/automato-node-py.git
pip install -r automato-core-py/requirements.txt -r automato-node-py/requirements.txt
```

A minimal configuration, `automato.conf` (JSON, comments allowed):

```json
{
  "name": "home",
  "mqtt": { "broker_host": "127.0.0.1", "broker_port": 1883 },
  "entries": [
    { "module": "nodes", "config": { "master": true } },
    { "module": "health" },
    { "module": "clock" },
    {
      "device": "kitchen_light",
      "caption": "Kitchen light",
      "publish": {
        "kitchen/light/status": { "type": "object", "events": { "output": "js:({value: payload['state'] == 'on' ? 1 : 0})" } }
      },
      "subscribe": {
        "kitchen/light/cmd": { "actions": { "output-set": "js:params['value'] ? 'on' : 'off'" } }
      }
    }
  ]
}
```

Run it:

```sh
automato-node-py/bin/automato-node.sh -c automato.conf
```

With Docker, see [docker/README.md](docker/README.md).

## Documentation

- [Installation](docs/installation.md): from source, as a service (systemd, OpenWrt), with Docker
- [Node configuration](docs/configuration.md): the configuration file, includes, logging, command line
- [Entries](docs/entries.md): devices and items in the configuration, automations, scheduling, scripts
- [Modules](docs/modules.md): the built-in modules and their options
- [Writing modules](docs/writing-modules.md): the module API and the entry lifecycle
- [Tests](docs/testing.md): unit tests and live tests

The format of definitions (topic rules, events, actions, expressions, notifications) is documented in the core: [entry definitions](https://github.com/eric-void/automato-core-py/blob/master/docs/entry-definition.md), [events and actions](https://github.com/eric-void/automato-core-py/blob/master/docs/events-and-actions.md), [scripting](https://github.com/eric-void/automato-core-py/blob/master/docs/scripting.md), [MQTT protocol](https://github.com/eric-void/automato-core-py/blob/master/docs/mqtt-protocol.md).

## Repository layout

| Path | Content |
|---|---|
| `src/automato/node/launcher.py` | Command line, configuration loading, process lifecycle |
| `src/automato/node/node_system.py` | Modules and handlers, entry lifecycle, scheduling |
| `src/automato/node/storage.py` | Persistent entry data |
| `src/automato/modules` | Built-in modules, their tests (`*_test.py`) and optional requirements (`*-requirements.txt`) |
| `bin` | Launcher, service files, test runners |
| `docker` | Compose files, test configuration, notes |
| `tests` | Unit tests |
| `docs` | Documentation, and an annotated example module (`example-module.py`, in Italian) |

## License

[MIT](LICENSE)
