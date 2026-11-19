# Writing modules

[Documentation index](README.md)

A module is a Python file. Built-in modules are in `src/automato/modules`; a local module can be put in the configuration directory (it is in the Python path) and loaded with `"module": "file_name"`. [docs/example-module.py](example-module.py) is an annotated reference of every hook (comments in Italian).

## A minimal module

```python
# my_counter.py
import logging
from automato.core import system

definition = {
  'description': 'Counts button presses',
  'config': { 'button': 'hall_button' },
  'topic_root': 'home/counter',
  'publish': {
    './value': {
      'type': 'int',
      'description': 'Number of presses',
      'retain': True,
      'notify': 'Counter: {_[payload]}',
      'events': { 'counter': "js:({value: parseInt(payload)})" },
      'handler': 'publish',
    }
  },
  'subscribe': {
    './reset': {
      'description': 'Reset the counter',
      'response': [ './value' ],
      'handler': 'on_reset',
    }
  },
}

def init(entry):
  if 'count' not in entry.data:
    entry.data['count'] = 0
  entry.on_button = lambda source, eventname, eventdata, caller, pm: on_button(entry, eventdata)
  system.on_event(entry.config['button'] + '.input', entry.on_button, entry, 'my_counter')

def on_button(entry, eventdata):
  entry.data['count'] += 1
  entry.run_publish('./value')

def publish(entry, topic_rule, topic_definition):
  entry.publish('', entry.data['count'])

def on_reset(entry, subscribed_message):
  entry.data['count'] = 0
  entry.run_publish('./value')
```

```json
{ "module": "my_counter", "config": { "button": "hall_button" } }
```

`definition` is merged with the definition in the configuration (the configuration wins). `entry.data` is saved automatically. Use `_()` around texts to make them translatable (it is installed as a builtin by the core).

## Hooks

Functions with these names are called by the node. All of them receive the module entry first.

| Hook | When |
|---|---|
| `load(entry)` | While the definition is loaded, before it is normalized. May return a dict merged into the definition. `entry.publish` is not usable yet; use `entry.definition['config']` (not `entry.config`) |
| `init(entry)` | The entry is ready. The broker may still be disconnected: publishes are queued |
| `start(entry)` | The node is running and connected (called in a thread) |
| `run(entry)` | Every `run_interval` or `run_cron` of the entry |
| `destroy(entry)` | The entry is unloaded (node stop, reload) |
| `entry_load(entry, other)` | Another entry is loaded: the module can add definitions to it |
| `entry_unload(entry, other)` | Another entry is unloaded |
| `entry_install(entry, other, conf)` | Another entry matches `install_on` (below) |
| `entry_uninstall(entry, other, conf)` | The opposite |
| `entry_init(entry, other)` | Another entry is initialized |
| `system_entries_change(entry, loaded_ids, unloaded_ids)` | Entries changed (a node joined or left) |

Handlers named in the definition (`handler` of topic rules, `on` rules) are looked up by name among the module functions and `entry.methods`.

`SYSTEM_HANDLER_ORDER_<hook> = N` at module level changes the order in which modules receive a hook (negative first, default 0).

## Installing on other entries

`install_on` selects the entries a module extends, by their properties:

```python
definition = {
  'install_on': {
    'my_device_id': (),                       # the property exists
    'device_type': ('in', ['type_a', 'type_b']),  # the property has one of these values
    '/^mydev_(.*)$/': (),                     # properties matching a regexp
  }
}

def entry_install(installer_entry, entry, conf):
  # conf contains the matched properties; for a regexp with a group, the group is the key
  system.entry_definition_add_default(entry, {
    'publish': {
      'mydev/' + conf['my_device_id'] + '/status': {
        'type': 'object',
        'events': { 'output': "js:({value: payload['on'] ? 1 : 0})" },
      }
    },
    'subscribe': {
      'mydev/' + conf['my_device_id'] + '/set': {
        'actions': { 'output-set': "js:({on: params['value'] ? true : false})" },
      }
    },
  })
```

`entry_definition_add_default` adds definitions that the entry's own configuration can still override. This is how `shelly`, `tasmota`, `zigbee2mqtt` and `toggle` work.

An entry that matches more rules gets all of them in `conf`; an entry loaded later is installed when it arrives (and loading a module with `entry_load` or `install_on` reloads the entries already loaded).

## The entry object

| Attribute | Description |
|---|---|
| `id`, `id_local`, `node_name`, `type`, `caption` | Identity |
| `definition`, `config` | Full definition and its `config` |
| `node_config` | The whole node configuration |
| `data` | Persistent dict, saved in the storage directory. Protect concurrent changes with `entry.data_lock` |
| `is_local` | `True` for entries of this node |
| `module` | The imported module (for module entries) |
| `publish(topic, payload, qos, retain, response_callback, no_response_callback)` | Publishes; `topic` can be a rule (`./value`, `@`, an alias) or `''` for the current rule |
| `run_publish(topic_rule)` | Runs the handler of a publish rule |
| `topic(rule)` | Resolves a rule to the real topic |
| `on(event, listener, condition, reference_entry)` | Listens to an event of this entry |
| `do(action, params, init)` | Calls an action of this entry |
| `methods` | Functions callable by name (scripts add theirs here) |
| `exports` | Shared dict: values put here are variables of every script (for example `exports['is_day']`) |
| `handlers_add(hook, key, function)` | Adds a handler for a hook from another module (used in `entry_install`) |
| `request` | Thread-local storage for the current call |

## Helpers in `automato.node.node_system`

| Function | Description |
|---|---|
| `entry_invoke(entry, method, *args)` | Calls a method of an entry |
| `entry_invoke_threaded(entry, method, *args)` | Same, in a thread (one at a time per method) |
| `entry_invoke_delayed(entry, timer_key, delay, method, *args)` / `cancel_entry_invoke_delayed(entry, timer_key)` | Timers |
| `entries_invoke(method, *args)` | Calls a method on every entry that implements it |
| `entries_implements(method)` | Entries implementing a method (a module can offer a service: `notifications_send` is implemented by `telegram` and `notifications-webpush`) |

The core functions (`system.on_event`, `system.do_action`, `system.event_get`...) are described in the [core API](https://github.com/eric-void/automato-core-py/blob/master/docs/python-api.md).

## Good practices

- **Use standard events and actions** (`output`, `output-set`, `temperature`...): clients and other modules work with them without changes. See the [standard events](https://github.com/eric-void/automato-core-py/blob/master/docs/events-and-actions.md#standard-events).
- **Do not block** hooks called by the MQTT thread (subscribe handlers, event listeners): start a thread for slow work.
- **Pass `reference_entry`** to `system.on_event`, so listeners are removed when the entry is unloaded.
- **Declare optional dependencies** in `<module>-requirements.txt` next to the module, and add it to `requirements-all.txt`.
- **Write tests**: unit tests in `tests/` (no broker, see [Tests](testing.md)) and, for behavior through MQTT, a `<module>_test.py` live test.
- Small nodes run on routers: avoid heavy work for every message, and keep `data` small (it is compared and saved periodically).
