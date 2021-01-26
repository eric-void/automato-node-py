# require python3
# -*- coding: utf-8 -*-

import logging
#import regex
import re

from automato.core import system
from automato.core import utils
from automato.node import node_system as node

"""
DEF LETTE DA ENTRY:
entry = {
  # If not specified, it looks for a "output" event
  "toggle_events": "entry_id" | "entry_id.event(js: params['port'] == 1)" | [ "entry_id", ...],
  # It not specified, it looks for a "output-set" action. The module will call the action with "{value: X}" when the toggle state changes
  # (WARN: even if you specify an action name different from "output-set", the module sees if the entry has an "output-get" to obtain a better initialization. It's not mandatory to have it.)
  "toggle_actions": "entry_id" | [ "entry_id", "entry_id.action_name", "entry_id.action_name(js: params['x'] = 1; params['y'] = 2)", ...],
  # A short to set toggle_events and toggle_actions altogether. Specify an event reference. If you omit the eventname, "output" is used. The action is created by adding "-set" to eventname, and by converting condition to init code (replaces only "==" > "=" and "&&" > ";")
  "toggle_devices": "entry_id" | "entry_id(js: params['x'] == value && params['y'] == value)" | "entry_id.event" | [ "entry_id", ..."]
  # TRUE o array di device che hanno input e output detached (se ci arriva un evento partiamo dal presupposto che non serva mandargli la action)
  "toggle_detached": false|true|[ "entry_id" ]
  
  "config": {
    "timer-to": 30, "timer-to-1": 60
  }
}

MQTT:
> home/light 1,0
> home/light/info { state: 1|0|-1, health: ok|error|detached, timer-to: -, timer-state: 1,0, time: time }
< home/light/set 1,0 oppure { state: 1,0, timer-to: 0|time|timestamp, [timer-state: 1|0, defaults: ...] }
< home/light/toggle null | { timer-to: 0|time|timestamp}
< home/light/set-defaults { timer-to: XXX }
  timer-to-1 means "timer-to" used when you set value 1, to return to 0.


TODO:
- action per chiedere lo stato attuale? (lo status/get che potrebbe avere un device, è previsto?)
- evento toggle > state?. action: toggle-set > state_set? + state_get? - oppure "value" - ma funziona anche per detached?

------------

FOCUS-ON: toggle_debounce_time e toggle_output_queue

In caso di cambio veloce di output ON-OFF-ON (o viceversa), se ci sono dei rallentamenti nei relativi feedback dal device, può avvenire un loop infinito.

In pratica:
1. action "output-set: 1", imposta lo stato interno a 1 e manda al device "output-set: 1"
2. action "output-set: 0", imposta lo stato interno a 0 e manda al device "output-set: 0"
3. gli arriva dal device il feedback del primo comando, come evento "output: 1". Questo evento viene preso da event_listener, e provoca un on_set, che imposta lo stato interno a 0 e manda al device "output-set: 0"
=> LOOP INFINITO!

Questa sitazione viene testata in shelly_test (debounce*)

Per evitare questa situazione viene gestita una coda di output mandati (toggle_output_queue) con memorizzati [expiry, source_entry_id, value]. Expiry è impostato a time + 2 secondi (non vogliamo che duri per sempre)
Se lo stesso entry a cui è stato mandato l'output ci manda un evento, e questo evento è già presente in coda (entro l'expiry), invece di innescare un on_set toglie l'elemento della coda e ignora.

POSSIBILI PROBLEMI DI QUESTA SITUAZIONE:
- se il loop è diverso, dovuto a strane dipendenze tra entry diversi, e quindi il feedback mi arriva da un altro device, allora non viene risolto. Bisogna operare un anti-loop generico esterno.
- lui cosi' lega tutto l'entry. Se l'entry ha port diversi, o channel diversi, o eventi diversi, lui comunque lo ha legato, e quindi potrebbe ignorare input che invece andrebbero ascoltati 
  (caso pratico: è giusto che per ogni action "output-set" che faccio su shelly riceva un evento "output", ma se ricevo un evento "input" significa che si è fisicamente schiacciato il pulsante, e quindi andrebbe considerato).
  Questo problema è mitigato dal fatto che comunque c'è un timeout basso in mezzo, e che se il device fa tutto come deve (per ogni output-set manda un output), alla fine non dovrebbe saltare nulla.

"""

definition = {
  'install_on': { '/^toggle_(.*)$/': () },
  'config': {
    'toggle_debounce_time': 2, # Vedi nota sopra. Con 0 disabilita la gestione.
  }
}

def entry_install(self_entry, entry, conf):
  """
  Installs toggle specifications in passed entry
  """
  
  default_event = "output"
  default_action = "output-set"
  detached = False if 'detached' not in conf else conf['detached']
  required = entry.definition['required'] if 'required' in entry.definition else []
  
  entry.toggle_action_agents = []
  entry.toggle_detached = conf['detached'] if 'detached' in conf else False
  entry.toggle_timer = False
  
  if 'events' in conf:
    if isinstance(conf['events'], str):
      conf['events'] = [ conf['events'] ]
  else:
    conf['events'] = []
  
  if 'actions' in conf:
    if isinstance(conf['actions'], str):
      conf['actions'] = [ conf['actions'] ]
  else:
    conf['actions'] = []

  if 'devices' in conf:
    if isinstance(conf['devices'], str):
      conf['devices'] = [ conf['devices'] ]
    for d in conf['devices']:
      conf['events'].append(d)
      conf['actions'].append(system.transform_event_reference_to_action_reference(d))
  
  # events: Elenco di device sui quali ascoltare gli eventi
  for e in conf['events']:
    m = system.decode_event_reference(e, default_event = default_event)
    if m:
      mentry = system.entry_get(m['entry'])
      if mentry:
        if not m['entry'] in required:
          required.append(m['entry'])
        mentry.on(m['event'], event_listener_lambda(entry), m['condition'], self_entry)
      else:
        logging.error("{id}> invalid entry name in event listener definition: {definition}".format(id = entry.id, definition = e))
    else:
      logging.error("{id}> invalid event listener definition: {definition}".format(id = entry.id, definition = e))

  # actions: Elenco di device ai quali mandare le azioni
  for a in conf['actions']:
    m = system.decode_action_reference(a, default_action = default_action)
    if m:
      mentry = system.entry_get(m['entry'])
      if mentry:
        if not m['entry'] in required:
          required.append(m['entry'])
        entry.toggle_action_agents.append([m['entry'], m['action'], m['init']])
      else:
        logging.error("{id}> invalid entry name in action agent definition: {definition}".format(id = entry.id, definition = a))
    else:
      logging.error("{id}> invalid action agent definition: {definition}".format(id = entry.id, definition = a))

  # Add publish and subscribe definitions
  system.entry_definition_add_default(entry, {
    'required': required,
    'config': {
      'toggle_debounce_time': self_entry.config['toggle_debounce_time'],
    },
    'publish': {
      '@': {
        'description': _('Show current extended toggle status of {caption} entry').format(caption = entry.definition['caption']),
        'type': 'object',
        'payload': {
          'state': {
            '0': { 'caption': 'off' },
            '1': { 'caption': 'ON' },
          }
        },
        'notify': _('Current status of {caption} is: {{payload[state!caption]}}').format(caption = entry.definition['caption']),
        'notify_level': 'debug',
        'notify_if': {
          "js:payload['timer-to'] > 0": {
            'notify': _('Current status of {caption} is: {{payload[state!caption]}}, timer: {{payload[timer-to!strftime]}}').format(caption = entry.definition['caption']),
          }
        },
        'run_interval': self_entry.config['publish-interval'] if 'publish-interval' in self_entry.config else 30,
        'handler': publish,
        'events': {
          'output': 'js:({value: 0 + payload["state"], timer_to: 0 + payload["timer-to"]})'
        }
      },
    },
    'subscribe': {
      '@/set' : {
        'description': _('Set toggle status of {caption} entry').format(caption = entry.definition['caption']),
        'type': 'object',
        'response': [ '@' ],
        'handler': on_set,
        'actions': {
          'output-set': "js:('timer_to' in params ? { state: params['value'], 'timer-to': params['timer_to'] } : { state: params['value'] })",
        }
      },
      '@/get' : {
        'description': _('Get current toggle status of {caption} entry').format(caption = entry.definition['caption']),
        'type': 'none',
        'response': [ '@' ],
        'handler': on_get,
        'actions': {
          'output-get': '',
        }
      },
      '@/toggle' : {
        'description': _('Invert toggle status of {caption} entry').format(caption = entry.definition['caption']),
        'type': 'none',
        'response': [ '@' ],
        'handler': on_toggle,
        'actions': {
          'output-invert': "js:('timer_to' in params ? { 'timer-to': params['timer_to'] } : {})",
        }
      },
      '@/set-defaults' : {
        'description': _('Set default values for {caption} entry').format(caption = entry.definition['caption']),
        'type': 'object',
        'response': [ '@' ],
        'handler': on_set_defaults,
      },
    },
  })
  entry.handlers_add('init', 'toggle', _entry_init)
  
def _entry_init(entry):
  entry.data['toggle_boot_time'] = system.time()
  entry.data['toggle_output_queue'] = []
  entry.data['toggle_debounce_time'] = utils.read_duration(entry.definition['config']['toggle_debounce_time'])
  if not 'toggle_output_value' in entry.data:
    entry.data['toggle_output_value'] = 0
  if not 'toggle_output_value_time' in entry.data:
    entry.data['toggle_output_value_time'] = 0
  if not 'toggle_output_values' in entry.data:
    entry.data['toggle_output_values'] = {}
  if not 'toggle_input_values' in entry.data:
    entry.data['toggle_input_values'] = {}
  # Check if there was a previous timer running. If so, init the timer again (if not passed)
  if 'toggle_timer_to' in entry.data:
    if entry.data['toggle_timer_to'] >= system.time():
      toggle_init_timer(entry, entry.data['toggle_timer_to'], entry.data['toggle_timer_to_state'])
    else:
      _on_set(entry, { 'state': entry.data['toggle_timer_to_state'], 'timer-to': 0 })

  # TODO If we can ask for device status, we'll do it now, so i have a correct internal status
  for action_entry_id, action_name, action_init in entry.toggle_action_agents:
    action_entry = system.entry_get(action_entry_id)
    if action_entry and system.entry_support_action(action_entry, "output-get"):
      action_entry.do("output-get", {})
  
def event_listener_lambda(entry):
  return lambda source_entry, eventname, eventdata, caller, published_message: event_listener(entry, source_entry, eventname, eventdata, caller, published_message)

def event_listener(entry, source_entry, eventname, eventdata, caller, published_message):
  value = 1 if eventdata['params']['value'] > 0 else 0

  # If i've not received events from this entry before, or long time ago, i consider this as an initialization, so i don't call on_set (no output change, no timers... i don't consider this as a button press)
  if source_entry.id not in entry.data['toggle_input_values'] or system.time() - entry.data['toggle_input_values'][source_entry.id][1] > 3600:
    entry.data['toggle_input_values'][source_entry.id] = [value, system.time()]
    entry.data['toggle_output_value'] = value
    entry.data['toggle_output_value_time'] = system.time()
    entry.data['toggle_changed'] = False
  # I consider this input event only if different from previous detection
  elif value != entry.data['toggle_input_values'][source_entry.id][0]:
    _on_set(entry, { 'state': value }, source_entry)

def on_set(entry, subscribed_message):
  source_entry = subscribed_message.message.firstPublishedMessage().entry if subscribed_message.message.firstPublishedMessage() else None
  _on_set(entry, subscribed_message.payload, source_entry)

def _on_set(entry, payload, source_entry = None):
  if not isinstance(payload, dict):
    payload = { 'state': payload };
  if 'state' in payload:  
    if payload['state'] != 0 and payload['state'] != 1:
      payload['state'] = 0 if payload['state'] == '0' or payload['state'] == '' or payload['state'] == 'off' or payload['state'] == 'OFF' or payload['state'] == 'Off' or payload['state'] == 'false' or payload['state'] == 'FALSE' or payload['state'] == 'False' else 1
      
    # if "timer-to" is present in direct payload, it has priority over "timer-to-X" in defaults
    if "timer-to" in payload and "timer-to-" + str(payload['state']) not in payload:
      payload["timer-to-" + str(payload['state'])] = payload["timer-to"]
    # Apply defaults (runtime level + definition level)
    if 'toggle_defaults' in entry.data:
      payload = { ** entry.data['toggle_defaults'], ** payload }
    if 'toggle_defaults' in entry.config:
      payload = { ** entry.config['toggle_defaults'], ** payload }
      
    entry.data['toggle_input_values']['_mqtt' if source_entry is None else source_entry.id] = [payload['state'], system.time()]
    set_output(entry, payload['state'], source_entry)
    
    # Manage timers
    if 'timer-to-' + str(payload['state']) in payload and utils.read_duration(payload['timer-to-' + str(payload['state'])]) > 0:
      payload['timer-to'] = payload['timer-to-' + str(payload['state'])]
    if 'timer-to' in payload:
      payload['timer-to'] = utils.read_duration(payload['timer-to'])
      if payload['timer-to'] > 0:
        if payload['timer-to'] < 1000000000:
          payload['timer-to'] = system.time() + payload['timer-to']
        toggle_init_timer(entry, payload['timer-to'], 1 - payload['state'])    
    
  entry.run_publish('@')

def set_output(entry, value, source_entry = None):
  if source_entry and entry.data['toggle_output_queue']:
    entry.data['toggle_output_queue'] = [ q for q in entry.data['toggle_output_queue'] if q[0] >= system.time() ]
    for q in entry.data['toggle_output_queue']:
      if q[1] == source_entry.id and value == q[2]:
        entry.data['toggle_output_queue'].remove(q)
        return

  if value != entry.data['toggle_output_value'] or entry.data['toggle_output_value_time'] == 0:
    toggle_cancel_timer(entry)
    for action_entry_id, action_name, action_init in entry.toggle_action_agents:
      if not source_entry or (action_entry_id != source_entry.id) or entry.toggle_detached == True or (isinstance(entry.toggle_detached, list) and source_entry.id in entry.toggle_detached):
        action_entry = system.entry_get(action_entry_id)
        if action_entry:
          action_entry.do(action_name, {'value': value}, action_init, if_event_not_match = True)
          entry.data['toggle_output_values'][action_entry.id] = value
          if entry.data['toggle_debounce_time'] > 0:
            entry.data['toggle_output_queue'].append([system.time() + entry.data['toggle_debounce_time'], action_entry.id, value])
    entry.data['toggle_output_value'] = value
    entry.data['toggle_output_value_time'] = system.time()
    entry.data['toggle_changed'] = True
  else:
    entry.data['toggle_changed'] = False

def on_toggle(entry, subscribed_message):
  payload2 = { 'state': 1 - entry.data['toggle_output_value']}
  if 'timer-to' in subscribed_message.payload:
    payload2['timer-to'] = subscribed_message.payload['timer-to']
  source_entry = subscribed_message.message.firstPublishedMessage().entry if subscribed_message.message.firstPublishedMessage() else None
  _on_set(entry, payload2, source_entry)

def on_get(entry, subscribed_message):
  entry.run_publish('@')

def publish(entry, topic, definition):
  defaults = entry.data['toggle_defaults'] if 'toggle_defaults' in entry.data else {}
  if 'toggle_defaults' in entry.config:
    defaults = { ** entry.config['toggle_defaults'], ** defaults }  

  res = {
    'state': entry.data['toggle_output_value'],
    'type': 'toggle',
    'changed': entry.data['toggle_changed'] if 'toggle_changed' in entry.data else False,
    'last_changed': entry.data['toggle_output_value_time'],
    'timer-state': 1 if 'toggle_timer_to' in entry.data and entry.data['toggle_timer_to'] > 0 else 0,
    'timer-to': entry.data['toggle_timer_to'] if 'toggle_timer_to' in entry.data and entry.data['toggle_timer_to'] > 0 else 0,
    'defaults': defaults,
    'time': system.time(),
    'output_values': entry.data['toggle_output_values'],
    'input_values': entry.data['toggle_input_values'],
  }
  entry.publish('', res)
  entry.data['toggle_changed'] = False

def on_set_defaults(entry, subscribed_message):
  if isinstance(subscribed_message.payload, dict):
    entry.data['toggle_defaults'] = {}
    for k in ['timer-to', 'timer-to-0', 'timer-to-1']:
      if k in subscribed_message.payload and utils.read_duration(subscribed_message.payload[k]) > 0:
        entry.data['toggle_defaults'][k] = utils.read_duration(subscribed_message.payload[k])

def toggle_init_timer(entry, timer_to, timer_to_state):
  entry.data['toggle_timer_to'] = timer_to
  entry.data['toggle_timer_to_state'] = timer_to_state
  node.entry_invoke_delayed(entry, 'toggle', timer_to - system.time(), _toggle_end_timer, entry.data['toggle_timer_to_state'])
  
def _toggle_end_timer(entry, new_state):
  entry.data['toggle_timer_to'] = 0
  entry.data['toggle_timer_to_state'] = 0
  _on_set(entry, { 'state': new_state, 'timer-to': 0 })

def toggle_cancel_timer(entry):
  if 'toggle_timer_to' in entry.data and entry.data['toggle_timer_to'] > 0:
    entry.data['toggle_timer_to'] = 0
    entry.data['toggle_timer_to_state'] = 0
    node.cancel_entry_invoke_delayed(entry, 'toggle')
