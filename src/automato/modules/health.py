# require python3
# -*- coding: utf-8 -*-

import logging
import threading

from automato.core import system
from automato.core import utils
from automato.node import node_system as node

"""
Events read:
- connected
Events generated:
- alive
- failure
"""

definition = {
  'config': {
    # Consider an entry dead if disconnected and not reconnected within this time
    # [Available also in specific entry config]
    'health-dead-disconnected-timeout': '1m',
    # If setted, every entry is considered alive when it sends a message
    # [Available also in specific entry config]
    'health-alive-on-message': True,
    # If setted, every entry is considered dead when no messages are sent in X time
    # [Available also in specific entry config]
    #'health-dead-message-timeout': '10m',

    # After this time in "alive" state, if no "health event" occours the status goes to "idle"
    'health-idle-time': '6h', 
    # Every "run_interval" or "check_interval" timeout check will consider original property multiplied by this factor (e.g. if "run_interval" il 10, the checker will consider timeout if not published in 15 seconds)
    'health-check_interval-multiplier': 1.5,
    # Internal
    'health-checker-secs': 5,
  },
  'publish': {
    'health/status': {
      'type': 'object',
      'description': _('All entries health status'),
      'handler': 'publish_all_entries_status',
      'run_interval': '10m',
    }
  },
  'subscribe': {
    'health/status/get': {
      'type': '',
      'description': _('Get all entries health status'),
      'publish': [ 'health/status' ],
    }
  },
  # I must listen for ALL health events, so i can skip them in "on_subscribe_all_messages()"
  "events_listen": [
    '*.alive',
    '*.failure',
  ]
}

def load(entry):
  return {
    'subscribe': {
      '#': {
        'handler': on_subscribe_all_messages
      }
    }
  }

# system_loaded handler should be executed as the last one
SYSTEM_HANDLER_ORDER_system_loaded = 10

def system_loaded(entry, entries):
  for e in entries:
    if entries[e].is_local:
      entries[e].health_entry = entry
      entries[e].health_published_status = { 'value': '', 'reason': '' }
      entries[e].health_dead = '' # Reason the entry should be considered dead
      entries[e].health_response = '' # A failure in response to subscribed topic
      entries[e].health_required = {} # The status of required entries (only for entries in status "dead" or "failure")
      entries[e].health_publish = {} # Failure in run_interval/check_interval (not published as often as expected)
      entries[e].health_time = 0 # Last access to an health_* variable
      entries[e].health_changed = 0 # Last change to an health_* variable
      entries[e].health_config_dead_disconnected_timeout = utils.read_duration(entries[e].config['health-dead-disconnected-timeout'] if 'health-dead-disconnected-timeout' in entries[e].config else (entry.config['health-dead-disconnected-timeout'] if 'health-dead-disconnected-timeout' in entry.config else 0))
      entries[e].health_config_alive_on_message = utils.read_duration(entries[e].config['health-alive-on-message'] if 'health-alive-on-message' in entries[e].config else (entry.config['health-alive-on-message'] if 'health-alive-on-message' in entry.config else False))
      entries[e].health_config_dead_message_timeout = utils.read_duration(entries[e].config['health-dead-message-timeout'] if 'health-dead-message-timeout' in entries[e].config else (entry.config['health-dead-message-timeout'] if 'health-dead-message-timeout' in entry.config else 0))
      
      system.entry_definition_add_default(entries[e], {
        'publish': {
          'health': {
            'description': _('Health of the entry'),
            'topic': '@/health',
            'type': 'object',
            'retain': 1,
            'notify': _("{caption} health is changed to: {payload[value]}"),
            'notify_if': {
              'js:payload["value"] == "failure" || payload["value"] == "dead"': { 'notify_level': 'warn', 'notify': _("{caption} health is changed to: {payload[value]} ({payload[reason]})"), 'notify_next_level': 'warn'},
            },
            'events': {
              'alive': "js:('value' in payload && payload['value'] in {'alive':0, 'dead':0, 'idle':0} ? { value: payload['value'] != 'dead'} : null)",
              'failure': "js:('value' in payload && payload['value'] in {'alive':0, 'failure':0, 'idle':0} ? { value: payload['value'] == 'failure', reason: payload['value'] == 'failure' && 'reason' in payload ? payload['reason'] : ''} : null)",
              'clock': "js:({ value: payload['time'] })"
            },
            "events_listen": [".connected", ".alive", ".failure"]
          },
        }
      });

      if system.entry_support_event(entries[e], 'connected'):
        entries[e].on('connected', lambda source_entry, eventname, eventdata: event_connected(entry, source_entry, eventname, eventdata))
      
      if 'required' in entries[e].definition and entries[e].definition['required']:
        for req_entry_id in entries[e].definition['required']:
          rentry = system.entry_get(req_entry_id)
          if rentry:
            _system_loaded_add_required_listeners(entry, rentry, entries[e])

def _system_loaded_add_required_listeners(installer_entry, required_entry, required_by_entry):
  required_entry.on('alive', lambda source_entry, eventname, eventdata: event_health_for_requirement(installer_entry, source_entry, eventname, eventdata, required_by_entry))
  required_entry.on('failure', lambda source_entry, eventname, eventdata: event_health_for_requirement(installer_entry, source_entry, eventname, eventdata, required_by_entry))

def init(entry):
  entry.health_dead_checker = {}
  entry.health_publish_checker = {}

  entry.health_checker_thread = threading.Thread(target = _health_checker_timer, args = [entry], daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
  entry.health_checker_thread._destroyed = False
  entry.health_checker_thread.start()
  
def destroy(entry):
  entry.health_checker_thread._destroyed = True
  entry.health_checker_thread.join()
  
def system_initialized(entry, entries):
  for e in entries:
    if entries[e].is_local:
      for t in entries[e].definition['publish']:
        # TODO run_cron support
        if 'run_interval' in entries[e].definition['publish'][t] or 'check_interval' in entries[e].definition['publish'][t]:
          interval = utils.read_duration(entries[e].definition['publish'][t]['check_interval'] if 'check_interval' in entries[e].definition['publish'][t] else entries[e].definition['publish'][t]['run_interval']) * entry.config['health-check_interval-multiplier']
          if not t in entry.health_publish_checker:
            entry.health_publish_checker[t] = {}
          entry.health_publish_checker[t][e] = { 'interval': interval, 'last_published': 0 }

def entry_health_status(entry):
  if not entry.is_local:
    return None
  
  res = {'value': 'idle', 'reason': ''}
  
  if entry.health_dead:
    res['value'] = 'dead'
    res['reason'] = entry.health_dead
  else:
    res['reason'] = entry.health_response
    if entry.health_required:
      for e in entry.health_required:
        if entry.health_required[e] == 'dead' or entry.health_required[e] == 'failure':
          res['reason'] = res['reason'] + (', ' if res['reason'] else '') + _('{entry} is in state: ' + entry.health_required[e]).format(entry = e)
    if entry.health_publish:
      for t in entry.health_publish:
        res['reason'] = res['reason'] + (', ' if res['reason'] else '') + _('{topic} not published as expected').format(topic = t)
    if res['reason']:
      res['value'] = 'failure'

  if res['value'] == 'idle' and system.time() - entry.health_time < utils.read_duration(entry.health_entry.config['health-idle-time']):
    res['value'] = 'alive'

  return res

def check_health_status(entry):
  entry.health_time = system.time()
  publish_health_status(entry)

def publish_health_status(entry, force = False):
  status = entry_health_status(entry)
  if status:
    changed = status['value'] != entry.health_published_status['value'] or status['reason'] != entry.health_published_status['reason']
    if changed:
      entry.health_changed = entry.health_time
    if force or changed:
      entry.health_published_status = status
      status['changed'] = entry.health_changed
      status['schanged'] = utils.strftime(status['changed']) if status['changed'] > 0 else '-'
      #status['entry'] = entry.id
      status['time'] = system.time()
      entry.publish('health', status)
    
def publish_all_entries_status(entry, topic_rule, topic_definition):
  status = {}
  for entry_id in system.entries():
    oentry = system.entry_get(entry_id)
    if oentry.is_local:
      status[entry_id] = entry_health_status(oentry)
      if status[entry_id]:
        status[entry_id]['changed'] = oentry.health_changed
        status[entry_id]['schanged'] = utils.strftime(status[entry_id]['changed']) if status[entry_id]['changed'] > 0 else '-'
  entry.publish('', status)

def _health_checker_timer(entry):
  while not threading.currentThread()._destroyed:
    now = system.time()
    
    timeouts = [ entry_id for entry_id in entry.health_dead_checker if now > entry.health_dead_checker[entry_id][0] ]
    if timeouts:
      for entry_id in timeouts:
        source_entry = system.entry_get(entry_id)
        if source_entry:
          source_entry.health_dead = entry.health_dead_checker[entry_id][1]
          check_health_status(source_entry)
      entry.health_dead_checker = { entry_id: entry.health_dead_checker[entry_id] for entry_id in entry.health_dead_checker if entry_id not in timeouts }
    
    for t in entry.health_publish_checker:
      for e in entry.health_publish_checker[t]:
        if entry.health_publish_checker[t][e]['last_published'] > 0 and now - entry.health_publish_checker[t][e]['last_published'] > entry.health_publish_checker[t][e]['interval']:
          target_entry = system.entry_get(e)
          if target_entry and t not in target_entry.health_publish:
            target_entry.health_publish[t] = now
            check_health_status(target_entry)

    system.sleep(entry.config['health-checker-secs'])

def event_connected(installer_entry, source_entry, eventname, eventdata, from_generic_message = False):
  if eventdata['params']['value']:
    source_entry.health_dead = ''
    # A connection resets response failure
    source_entry.health_response = ''
    if source_entry.id in installer_entry.health_dead_checker:
      del installer_entry.health_dead_checker[source_entry.id]
    check_health_status(source_entry)
  else:
    installer_entry.health_dead_checker[source_entry.id] = (system.time() + source_entry.health_config_dead_disconnected_timeout, 'disconnected for too long')

def on_subscribe_all_messages(entry, subscribed_message):
  """
  Monitor every mqtt message
  """
  message = subscribed_message.message
  if (message.retain): # Retained messages should be skipped
    return

  firstpm = subscribed_message.message.firstPublishedMessage()
  listened_events = subscribed_message.message.events()
  if firstpm and firstpm.entry.is_local and 'connected' not in listened_events and 'alive' not in listened_events and 'failure' not in listened_events:
    if firstpm.entry.health_config_alive_on_message:
      event_connected(entry, firstpm.entry, 'connected', { 'params': { 'value': True } }, from_generic_message = True)
    if firstpm.entry.health_config_dead_message_timeout:
      entry.health_dead_checker[firstpm.entry.id] = (system.time() + firstpm.entry.health_config_dead_message_timeout, 'silent for too long')
  
  # Look for entries subscribed to this topic. If a "response" is defined, we will wait for the response to come (or not)
  for sm in message.subscribedMessages():
    if 'response' in sm.definition:
      system.subscribe_response(sm.entry, subscribed_message.message, callback = on_response_to_subscribed_message, no_response_callback = on_no_response_to_subscribed_message)
  
  # Update publish checker
  if subscribed_message.topic in entry.health_publish_checker:
    for e in entry.health_publish_checker[subscribed_message.topic]:
      entry.health_publish_checker[subscribed_message.topic][e]['last_published'] = system.time()
      target_entry = system.entry_get(e)
      if target_entry and subscribed_message.topic in target_entry.health_publish:
        del target_entry.health_publish[subscribed_message.topic]
        check_health_status(target_entry)

def on_response_to_subscribed_message(entry, id, message, final, response_to_message):
  entry.health_response = ''
  check_health_status(entry)

def on_no_response_to_subscribed_message(entry, id, response_to_message):
  entry.health_response = _('no response to {topic} = {payload} request').format(topic = response_to_message.topic, payload = str(response_to_message.payload)[0:20])
  check_health_status(entry)

def event_health_for_requirement(installer_entry, source_entry, eventname, eventdata, required_by_entry):
  m = system.current_received_message()
  if m.retain: # health events from retained messages should be skipped
    return
  
  """
  Called when an entry, required by another entry, changes its health status
  """
  if eventname == 'alive':
    if not eventdata['params']['value']:
      required_by_entry.health_required[source_entry.id] = 'dead'
      check_health_status(required_by_entry)
    elif source_entry.id in required_by_entry.health_required and required_by_entry.health_required[source_entry.id] == 'dead':
      del required_by_entry.health_required[source_entry.id]
      check_health_status(required_by_entry)
  elif eventname == 'failure':
    if eventdata['params']['value']:
      required_by_entry.health_required[source_entry.id] = 'failure'
      check_health_status(required_by_entry)
    elif source_entry.id in required_by_entry.health_required and required_by_entry.health_required[source_entry.id] == 'failure':
      del required_by_entry.health_required[source_entry.id]
      check_health_status(required_by_entry)
