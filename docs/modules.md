# Modules

[Documentation index](README.md)

Built-in modules are in [src/automato/modules](../src/automato/modules). A module is used in one of two ways:

- **as an entry**: `{ "module": "health" }` in `entries`, with options in `config`;
- **installed on other entries**: after the module entry is loaded, every entry with certain properties gets its definitions (`{ "device": "plug", "shelly_id": "A1B2C3" }`). These modules still need their own entry in `entries`.

Options shown below are the defaults, from the `definition` at the top of each module file: the file is the reference for the complete list. Modules marked with *requirements* need extra Python packages (see [Installation](installation.md)).

| Area | Modules |
|---|---|
| System | [nodes](#nodes), [health](#health), [notifications](#notifications), [scripting](#scripting) |
| Automation | [toggle](#toggle), [scheduler](#scheduler), [clock](#clock), [astral, astral2](#astral-astral2) |
| Devices | [shelly](#shelly), [tasmota](#tasmota), [zigbee2mqtt](#zigbee2mqtt), [nut](#nut), [solaredge_modbus_tcp](#solaredge_modbus_tcp), [rf_listener, rf2mqtt_listener](#rf_listener-rf2mqtt_listener) |
| Presence and location | [presence](#presence), [net_sniffer](#net_sniffer), [net_sniffer_scapy](#net_sniffer_scapy), [owrtwifi2mqtt](#owrtwifi2mqtt), [room_assistant](#room_assistant), [location_owntracks](#location_owntracks) |
| Network | [net](#net), [net_ping](#net_ping), [speedtest](#speedtest), [http-request](#http-request) |
| Messaging | [telegram](#telegram), [notifications-webpush](#notifications-webpush) |
| Data | [history](#history), [influxdb](#influxdb) |

---

## System

### nodes

Shares entries among nodes and with clients (see the [MQTT protocol](https://github.com/eric-void/automato-core-py/blob/master/docs/mqtt-protocol.md)). Every node should have it.

```json
{ "module": "nodes", "config": { "master": true } }
```

| Option | Default | Description |
|---|---|---|
| `master` | `false` | Answer `automato/data/get` with all definitions and events. One node per installation |
| `compress` | `true` | Compress metadata and data payloads |
| `local` | `false` | Publish own entries but do not load the other nodes' ones (saves resources, but events and actions of remote entries are not available) |
| `dead_time` | `90m` | A node whose metadata is older than this is considered dead |

Topics: `automato/metadata` (every 30 minutes and on `automato/metadata/get`), `automato/dead-node`, and for the master `automato/data` (on `automato/data/get`).

### health

Tracks the health of every local entry and publishes it on `<entry_topic>/health`, with the `alive` and `failure` events. An entry is:

- `alive` when it sends messages (or its `connected` event is 1),
- `idle` after a long time without health events,
- `failure` when a publish rule with `run_interval`/`check_interval` is not published in time, a request gets no response, or a required entry fails,
- `dead` when it is disconnected for longer than the timeout.

| Option | Default | Description |
|---|---|---|
| `health-dead-disconnected-timeout` | `1m` | Disconnected for this time means dead (`0` disables the check) |
| `health-alive-on-message` | `true` | Any message makes the entry alive |
| `health-dead-message-timeout` | (off) | No messages for this time means dead |
| `health-idle-time` | `6h` | Time after which an alive entry with no news is idle |
| `health-check_interval-multiplier` | `2` | Tolerance on `run_interval`/`check_interval` |

The first three options can also be set in the `config` of a single entry. `health/status` publishes the state of all entries (every 10 minutes and on `health/status/get`).

### notifications

Builds the notification of every published message (see [notifications in the core](https://github.com/eric-void/automato-core-py/blob/master/docs/notifications.md)), keeps a history and forwards notifications to subscribed clients through the modules that send them (`telegram`, `notifications-webpush`).

| Option | Default | Description |
|---|---|---|
| `history_length` | `21600` | Seconds of history kept |
| `history_max_items` | `2000` | Maximum notifications kept |
| `history_filter` | `info` | Minimum level stored in the history |
| `history_compress` | `true` | Compress the `notifications/history` payload |
| `notify_send` | `false` | Republish notifications on `notify/<level>/<topic>` |
| `notify_send_level` | `info` | Minimum level for `notify_send` |
| `storage` | `notifications-subscribptions.db` | File (in the storage directory) with the subscriptions |

Topics: `notifications/history/get` → `notifications/history`; `notifications/subscribe/<level>/<topic>` and `notifications/unsubscribe/...` with payload `<driver>:<data>`.

### scripting

Enables Python code in definitions: `script` in topic and `on` rules, `methods`, and `data`. See [Entries](entries.md#python-scripts).

---

## Automation

### toggle

Turns an item into a switch with a uniform interface and timers, on top of one or more devices. Installed on entries with `toggle_*` properties:

```json
{ "item": "garden_light", "caption": "Garden", "toggle_devices": "garden_relay(js:params['port'] == '1')",
  "config": { "toggle_defaults": { "timer-to-1": "2h" } } }
```

| Property | Description |
|---|---|
| `toggle_devices` | Event references of the devices to follow and command. The event defaults to `output`, the action to the event name plus `-set` with the condition turned into init code |
| `toggle_events` | Events to follow, when they differ from the commanded devices |
| `toggle_actions` | Actions to call when the state changes, when they differ |
| `toggle_detached` | `true` (or a list of entry ids) for devices whose input is detached from the output: their events change the state, but no command is sent back |

The item publishes `<entry_topic>` (`state`, `timer-to`, retained, with the `output` event) and accepts `@/set` (`output-set`, with `timer_to`), `@/get` (`output-get`), `@/toggle` (`output-invert`) and `@/set-defaults`. `toggle_defaults` in `config` sets default timers: `timer-to-1` turns the item off after that time when it is turned on, `timer-to-0` turns it on again after it is turned off.

Module option: `toggle_debounce_time` (`2` seconds) ignores the echo of a command coming back from the device, to avoid on/off loops.

### scheduler

Runs actions at given times. Jobs are defined in the module entry (`jobs`, `groups`) or in other entries (`schedule`, `schedule_groups`, installed on them):

```json
{ "module": "scheduler", "config": { "scheduler_enabled": true } },
{
  "item": "irrigation",
  "schedule": [
    { "id": "morning", "run_cron": "0 6 * * *", "do": "irrigation_valve.output-set(js:params['value'] = 1; params['timer_to'] = 900)" }
  ]
}
```

| Job key | Description |
|---|---|
| `run_interval` / `run_cron` | When to run |
| `do` | One or more action references |
| `do_if_event_not_match` | Skip the action if the target is already in that state |
| `if` | A `js:` condition |
| `group` | Group name; groups can be enabled and disabled together |
| `id` | Job id |
| `entry_id` | Entry for `do` references without an entry (default: the entry declaring the job) |

The scheduler, a group (`port`) or a job can be enabled or disabled, also with a timer, through `scheduler/set` (action `output-set`, with `port` set to `*`, a job id, a group name or `@entry_id`). `scheduler/status` reports the state. `scheduler_enabled` is the initial state, used only when no saved state exists.

### clock

Publishes the current timestamp on `home/time` every 30 seconds (retained), with the `clock` event. `home/time/get` asks for it.

### astral, astral2

*Requirements.* Times of dawn, sunrise, noon, sunset and dusk. `astral2` (for astral 2.x) publishes them on `astral/data` with `clock` events whose `port` is `astral/dawn`, `astral/sunrise`, `astral/noon`, `astral/sunset`, `astral/dusk`: use them in `on` rules. Options: `city` (an [astral city](https://astral.readthedocs.io/)) or `latitude`, `longitude`, `timezone`. `astral` is the version for astral 1.x.

---

## Devices

### shelly

Shelly devices through their MQTT interface. Installed on entries with `shelly_id` (the device id, as in `shellies/<type>-<id>/`) and `device_type`:

```json
{ "device": "boiler_relay", "caption": "Boiler", "device_type": "shelly1pm", "shelly_id": "A1B2C3" }
```

Gen 1 types: `shelly1`, `shelly1pm`, `shellyswitch`/`shelly2`, `shellyswitch25`, `shellydimmer`, `shellydimmer2`, `shellyem`, `shellyem3` (and generic `shelly`). Gen 2+ types (RPC over MQTT): `shellyplus1`, `shellypro2`, `shelly2pmg3`. Events: `output` (per `port`), `input`, `energy`, `temperature`, `connected`...; actions `output-set`, `output-get`, `output-invert`. The full list of types and what they define is in [shelly.py](../src/automato/modules/shelly.py).

### tasmota

Devices with Tasmota firmware. Installed on entries with `tasmota_id` (the Tasmota `%topic%`) and optional `device_type` (`tasmota`, `tasmota_dual`, `tasmota_sonoff`, `tasmota_sonoff_basic`, `tasmota_sonoff_dual`, `tasmota_sonoff_dualr2`, `tasmota_sonoff_pow`, `tasmota_sonoff_powr2`). Options: `tasmota-fulltopic` (`%prefix%/%topic%/`) and the three prefixes (`cmnd`, `stat`, `tele`), as configured on the devices.

### zigbee2mqtt

Zigbee devices through [Zigbee2MQTT](https://www.zigbee2mqtt.io/). Installed on entries with `zigbee_id` (the friendly name, as in `zigbee2mqtt/<id>`) and `device_type`: `zigbee`, `zigbee_switch`, `zigbee_plug`, `zigbee_button`, `zigbee_temperature`, `zigbee_motion`, `zigbee_presence`, `zigbee_contact`, `zigbee_vibration`, `zigbee_waterleak`, `zigbee_waterlevel`. Each type maps the Zigbee2MQTT payload to standard events (`output`, `input`, `temperature`, `humidity`, `occupancy`, `contact`, `battery`...).

### nut

*Requirements.* UPS through [NUT](https://networkupstools.org/). Polls the UPS every minute and publishes its variables on `nut/var/<name>`, with events: `connected`, `output` with ports `online`, `on_battery`, `charging`, `low_battery`..., `battery`, `load`, `energy`, `temperature`, `autonomy`. Options: `nut_upsname`, `nut_host`, `nut_port`, `nut_username`, `nut_password`, `nut_full_vars_interval`.

### solaredge_modbus_tcp

*Requirements.* SolarEdge inverters through modbus TCP. Publishes `solaredge/inverter`, `solaredge/meter/<n>`, `solaredge/battery/<n>`, with `energy` events. Options: `solaredge_modbus_tcp_host`, `solaredge_modbus_tcp_port` (`1502`), `solaredge_modbus_tcp_unit`, and `solaredge_modbus_tcp_data_filter` (which values to publish).

### rf_listener, rf2mqtt_listener

RF 433 MHz codes (remotes, sensors). Entries declare `"rf_code": "1234567"` (or `{ "code": "port" }` for more buttons) and get a temporary `input` event (with the `port` of the code, if given) when the code is received. `rf2mqtt_listener` reads codes published on the `rf2mqtt` topic by an external receiver; `rf_listener` can also read a receiver on a Raspberry Pi GPIO (`rf_listener_gpio`, *requirements*; not suitable for small boards).

---

## Presence and location

### presence

Knows who is at home. Installed on entries with `presence_detect` (the name of the person): their `connected` events (a phone on the wifi) and `location` events (OwnTracks) are combined.

```json
{ "module": "presence" },
{ "device": "phone_anna", "mac_address": "AA:BB:CC:DD:EE:FF", "presence_detect": "Anna" }
```

Publishes `home/presence` (occupants, every 15 seconds), `home/presence/in` and `home/presence/out` with the `presence-in` and `presence-out` events. Options: `presence_home_location` (`{ latitude, longitude, radius }`), `presence_home_regions` (OwnTracks region names), `presence_connection_duration`, `presence_connection_after_disconnect`, `presence_location_session_duration`.

### net_sniffer

Detects devices on the local network by MAC address, and emits their `connected` event. Installed on entries with `mac_address` (and `net_connection_momentary` for devices that connect only briefly). Designed for routers: it uses `iw event` and `iw station dump` (wifi), `ip neigh` and `/proc/net/arp`, optionally `ping`.

| Option | Default | Description |
|---|---|---|
| `connection_time` | `15m` | A device not seen for this time is disconnected |
| `send_connect_message_every` | `10m` | Repeat the connect message while connected |
| `disconnect_grace_time` | `1m` | After a disconnection reported by wifi events, ignore other sources for this time |
| `event_monitor_handler`, `polling_handler`, `ip_get_handler` | `iw`, `iw`, `arp` | Detection methods (`+ping` to confirm uncertain ones) |
| `use_ping_command`, `use_ping_module` | `false` | Ping devices when in doubt (the command needs root; the module needs `net_ping`) |

### net_sniffer_scapy

*Requirements.* Same purpose, with [scapy](https://scapy.net/): sniffs packets and scans the network (`interface`, `ips`). Needs root privileges.

### owrtwifi2mqtt

Same purpose, reading the topics published by an OpenWrt wifi-to-MQTT script (`owrtwifi/status/mac-<mac>/...`).

### room_assistant

Bluetooth Low Energy presence through [room-assistant](https://www.room-assistant.io/). Installed on entries with `room_assistant_instance` and `ble_id`: emits `connected` from the device state (`connected_states`, `disconnected_states`).

### location_owntracks

Phone location through [OwnTracks](https://owntracks.org/). Installed on entries with `owntracks_id` (the last part of the topic `owntracks/device/<id>`, as configured in the app): emits `location` (latitude, longitude, radius, regions) and `clock`.

---

## Network

### net

WAN connection monitoring for a router: WAN IP (`net/wan-ip`), external IP (`net/external-ip`), connectivity check (`net/wan-connected`, with method `http` or `ping`), optional bandwidth usage (`net/bandwidth`, from `/proc/net/dev`) and WAN reconnection. Commands are configurable (`wan-ip-ifstatus-command`, `wan-ip-ifrenew-command`...): on OpenWrt they may need `sudo` rules, as described in the module.

### net_ping

*Requirements.* Ping through [icmplib](https://github.com/ValentinBELYN/icmplib), used by other modules. Options: `ping_timeout`, `ping_retry`, `ping_privileged`.

### speedtest

*Requirements.* Internet speed test through speedtest.net, on request (`net/speedtest/run`), published on `net/speedtest` with the `netspeed` event. Option: `server`.

### http-request

*Requirements.* Publishes values read from web pages: publish rules with `url` and an expression of what to extract, run with `run_interval` or `run_cron`. See the module file for the expression syntax.

---

## Messaging

### telegram

*Requirements.* A Telegram bot: sends notifications to subscribed chats and answers commands.

| Option | Description |
|---|---|
| `token` | Bot token (from BotFather) |
| `notifications_client_id` | Driver name for notification subscriptions (`telegram`) |
| `quick_commands` | Let chats query topics with short commands |
| `threshold_level`, `threshold_max`, `threshold_duration`, `threshold_duration_max` | Anti-flood: above `threshold_max` messages of at least `threshold_level` in `threshold_duration`, messages are collapsed |

In a chat, `/help` lists the commands and `/notify_sub <level>/<topic>` subscribes the chat to notifications: `/notify_sub warn_` sends warnings and higher levels, `_` stands for any.

### notifications-webpush

*Requirements.* Sends notifications as web push messages to subscribed browsers (driver `webpush`). Options: `private_key` (VAPID) and `mailto`.

---

## Data

### history

Writes every event to daily TSV files, one per entry (`<entry>-<date>.tsv`), in `path` (`./history`, relative to the configuration directory; it must exist). Needs `listen_all_events`. Option: `ignore_events` (`["clock", "stats"]`).

### influxdb

*Requirements.* Writes events to InfluxDB 2 (`influxdb_url`, `influxdb_org`, `influxdb_bucket`, `influxdb_token`; a second destination with the `influxdb2_*` options). Needs `listen_all_events`. Option: `ignore_events`.
