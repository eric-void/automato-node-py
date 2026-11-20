# Node configuration

[Documentation index](README.md)

## The file

The configuration is a JSON file. Comments (`//` and `/* */`) and trailing commas are allowed (it is read with [jstyleson](https://github.com/linjackson78/jstyleson)). The default path is `/etc/automato/automato.conf`; use `-c` for another one.

```json
{
  "name": "home-server",
  "description": "Main node",
  "mqtt": {
    "broker_host": "127.0.0.1",
    "broker_port": 1883,
    "broker_user": "automato",
    "broker_pass": "..."
  },
  "storage": "data",
  "log": "logs/automato.log",
  "error-log": "logs/automato-errors.log",
  "log-level": "info",
  "include": [ "conf.d/*.conf" ],
  "entries": [
    { "module": "nodes", "config": { "master": true } },
    { "module": "health" }
  ]
}
```

### Includes

`include` is a list of glob patterns, relative to the directory of the file that contains them. Matching files are loaded in alphabetical order, and can include other files. A typical layout keeps one file per area:

```
automato.conf
conf.d/10-system.conf
conf.d/20-lights.conf
conf.d/30-heating.conf
```

Merge rule: top level lists are concatenated (so every file can add `entries`), top level objects are merged (one level deep, so a later `mqtt` adds or replaces keys), any other value is replaced by the last file.

## Keys

| Key | Default | Description |
|---|---|---|
| `name` | host name | Node name: entries of this node have ids `<id>@<name>`. Must be unique among the nodes |
| `description` | | Shown in the node metadata |
| `mqtt` | | Broker connection (below) |
| `entries` | | The entries of the node, see [Entries](entries.md) |
| `include` | | Other configuration files (above) |
| `base_path` | directory of the file | Base for relative paths. It is also added to the Python path, so local modules can be put there |
| `storage` | `data` | Directory where entry data are saved (relative to `base_path`) |
| `storage_interval` | `10` | Seconds (or duration) between checks for changed entry data to save. Raise it on slow nodes |
| `listen_all_events` | `false` | Compute every event, not only the listened ones. Needed by `history` and `influxdb`; costs CPU on small nodes |
| `log` | | Log file, rotated every day |
| `error-log` | | Log file with errors only |
| `messages-log` | | Log of all MQTT messages received and sent |
| `debug-log` | | Log of the `debug` logger |
| `console-log` | `true` | Log on the console |
| `color-log` | `false` | Colors on a terminal |
| `log-level` | `debug` | `debug`, `info`, `warning`, `error`. `info` saves CPU on slow nodes |
| `stats-detailed` | `false` | Collect timing statistics per topic (printed at exit) |
| `scripting-engine` | `js2py` | Engine for the JavaScript snippets of definitions: `js2py` or `quickjs` (faster, needs the quickjs-ng package, see [Installation](installation.md#quickjs-scripting-engine)). If it cannot be loaded the node logs an error and uses the other one. Details in [scripting](https://github.com/eric-void/automato-core-py/blob/master/docs/scripting.md#engines-of-the-python-core) |

### MQTT

| Key | Default | Description |
|---|---|---|
| `broker_host` | `127.0.0.1` | |
| `broker_port` | `1883` | |
| `broker_user`, `broker_pass` | | |
| `client_id` | `automato_<name>` | A random suffix is added, unless set from the command line with `--mqtt-client-id` |
| `topic_filter_ignore` | `[]` | Topics never processed (MQTT patterns or `/regexp/`) |
| `check_broken_connection` | `5` | Seconds: a message published by the node must come back within this time, otherwise the connection is restarted |

The node subscribes to `#`: the broker user needs read access to every topic the node handles, and write access to the topics it publishes.

Keep credentials out of shared files: a separate included file (`conf.d/00-secrets.conf` with only the `mqtt` object) is easy to exclude from version control.

## Environment variables

| Variable | Effect |
|---|---|
| `AUTOMATO_STORAGE_DIR` | Overrides `storage` |
| `AUTOMATO_LOG_DIR` | Moves `log`, `error-log`, `messages-log` and `debug-log` into this directory (keeping their file names) |
| `TZ` | Time zone of the node: cron rules and local times use it |
| `AUTOMATO_SCRIPTING_ENGINE` | Default of `scripting-engine`, when the configuration does not set it (used by the tests) |

They are used by the Docker image; include paths and local modules still resolve from the configuration directory.

## Command line

```
automato-node.sh [-c FILE] [-r] [--mqtt-client-id ID | --mqtt-client-id-prefix PREFIX]
automato-node.sh -c FILE -t TOPIC [-p PAYLOAD] [-q QOS] [--mqtt-retain]
automato-node.sh -c FILE --test [TEST_NAME]
```

| Option | Description |
|---|---|
| `-c`, `--config` | Configuration file |
| `-r`, `--reset` | Start without the saved entry data |
| `--mqtt-client-id` | Fixed client id |
| `--mqtt-client-id-prefix` | Client id prefix (a random suffix is added) |
| `-t`, `--mqtt-topic` | Sender mode: connect, publish this topic, exit. With `-p` (payload), `-q` (qos), `--mqtt-retain` |
| `--test` | Run the live test suite, or one test unit (see [Tests](testing.md)) |

The sender mode is handy in shell scripts and cron jobs: it uses the broker settings of the configuration.

## Storage

Entries keep state in `entry.data` (timers, last runs, module state). It is saved as JSON in the storage directory, as `<node>_data_<entry>.json` with a periodic backup copy, and loaded at start (unless `-r` is used). Saving happens when data changes, at most every `storage_interval`, and at exit.
