# Entries

[Documentation index](README.md)

The `entries` list of the configuration contains the definitions of the entries run by the node. The format of a definition (topic rules, events, actions, expressions) is described in the core: [entry definitions](https://github.com/eric-void/automato-core-py/blob/master/docs/entry-definition.md) and [events and actions](https://github.com/eric-void/automato-core-py/blob/master/docs/events-and-actions.md). This page covers what the node adds.

## Kinds of entries

```json
"entries": [
  { "module": "scheduler" },
  { "module": "net", "id": "net_main", "config": { "wan-connected-check-method": "ping" } },
  { "device": "boiler_relay", "shelly_id": "A1B2C3", "device_type": "shelly1pm" },
  { "item": "boiler", "caption": "Boiler", "toggle_devices": "boiler_relay" }
]
```

- **`module`**: loads Python code. The node imports `automato.modules.<name>` (the [built-in modules](modules.md)), or `<name>` from the Python path: the directory of the configuration is in the path, so a local module `my_module.py` next to the configuration is loaded with `"module": "my_module"` (`/` in the name selects a package: `"local/my_module"`). The module's own definition is merged with the one in the configuration, which wins.
- **`device`** and **`item`**: no code. They are described by their definition, and modules can extend them: a module declares `install_on` rules, and installs itself on every entry with matching properties. Above, `shelly_id` makes the `shelly` module add the topics, events and actions of a Shelly device, and `toggle_devices` makes the `toggle` module turn `boiler` into a switch with timers.

So a device is usually one line in the configuration, when a module knows it. A device that no module knows is described by hand, with `publish` and `subscribe`.

The same module can be used by more entries (with different `id`): each one is an instance with its own `config` and `data`.

## Keys added by the node

### Scheduling

| Key | Where | Description |
|---|---|---|
| `run_interval` | entry, publish rule | Seconds (or duration) between runs. On the entry it calls the `run` method; on a publish rule it calls the rule's `handler` |
| `run_cron` | entry, publish rule | A cron rule (`"*/5 * * * *"`), instead of `run_interval`. Uses the node time zone |
| `run_throttle` | entry, publish rule | What to do when the node is overloaded (late in processing MQTT messages): `skip`, `wait` (postpone), `force`, or a number of seconds to wait at most. Can be a list: `["policy on high load", "policy on very high load"]` |
| `check_interval` | publish rule | For the `health` module: the topic should be published at least this often (not needed with `run_interval`) |
| `run_on` | publish rule | Event references: run the rule's handler when one of these events happens |

A run that is late (the node was stopped) is executed at start. Scheduling state is kept in the entry data.

### Handlers

| Key | Where | Description |
|---|---|---|
| `handler` | publish rule | Function that publishes the topic: `handler(entry, topic_rule, topic_definition)`; it usually calls `entry.publish('', payload)` (`''` is the topic of the rule) |
| `handler` | subscribe rule | Function called for a message: `handler(entry, subscribed_message)` |
| `publish` | subscribe rule | Topics (rules of this entry) to publish when a message arrives: `"./status/get": { "publish": ["./status"] }` |
| `handler`, `do` | `on` | Function called for an event, or actions to call (see the core docs) |

In the configuration a handler is the **name** of a method: a function of the module, or a method defined by the `scripting` module (below). Modules can also use functions directly.

### Dependencies

`required` lists entries this entry needs: the `health` module reports a failure when one of them fails.

## Automations without code

Most automations are `on` rules:

```json
{
  "item": "night_light",
  "on": {
    "corridor_motion.occupancy(js:params['value'] == 1)": { "do": "corridor_light.output-set(js:params['value'] = 1; params['timer_to'] = 120)" },
    "astral.clock(js:params['port'] == 'astral/sunrise')": { "do": "garden_light.output-set(js:params['value'] = 0)" }
  }
}
```

The `scheduler` module runs actions at given times, with groups that can be enabled and disabled; the `toggle` module adds timers and a uniform command interface. See [Modules](modules.md).

## Python scripts

With the `scripting` module loaded (`{ "module": "scripting" }`), definitions can contain Python code: `script` in publish rules, subscribe rules and `on` rules, and `methods` at the top level. A script is a string or a list of lines; nested lists are indented blocks:

```json
{
  "item": "boiler_guard",
  "data": { "warned": false },
  "events_listen": [ "boiler.temperature" ],
  "run_interval": "1m",
  "methods": {
    "run": [
      "t = event_get('boiler.temperature')",
      "if t and t['value'] > 80 and not warned:",
      [ "do('siren.output-set', {'value': 1})", "warned = True" ],
      "elif t and t['value'] < 70:",
      [ "warned = False" ]
    ]
  },
  "subscribe": {
    "boiler/guard/reset": {
      "description": "Reset the guard",
      "script": "warned = False"
    }
  }
}
```

- Keys of `data` are local variables of every script of the entry; their changes are saved (in the entry data, persistent across restarts).
- Methods `init`, `start` and `run` are called by the node at the same times as module functions. Other methods are callable by name from scripts, and usable as handlers.
- `return value` ends a script with a result.

Variables available in scripts:

| Name | Description |
|---|---|
| `entry`, `config` | The entry and its `config` |
| `now` | Current timestamp |
| `publish(topic, payload, qos, retain)` | `entry.publish` |
| `do(actionref, params)`, `entry_do(entry, action, params)`, `self_do(action, params)` | Call actions |
| `event_get(eventref)`, `event_get_time(eventref)`, `entry_event_get(entry, event, condition)` | Read events (only listened ones: add them to `events_listen`) |
| `run_publish(topic_rule)` | Run the handler of a publish rule of the entry |
| `entry_invoke(entry, method, ...)` | Call a method of an entry |
| `call_method_delayed(name, delay, ...)`, `cancel_call_method_delayed()` | Call a method of the entry later |
| `broker` | The MQTT layer: `broker.get(topic)` returns the last payload received on a topic |
| `d(duration)`, `array_sum`, `array_avg`, `array_min`, `array_max` | Helpers |
| `utils`, `logging`, `re` | Python modules |
| exports of modules | Values that modules make available to every script |

In a subscribe rule script: `subscribed_message`, `topic`, `payload`, `matches`. In a publish rule script: `topic`, `topic_definition`. In an `on` script: `on_entry` (the entry that emitted the event), `eventname`, `eventdata`, `params`, `caller`, `published_message`.

Scripts run in the node process: they can do anything Python can. Keep them short, and move complex logic to a local module.
