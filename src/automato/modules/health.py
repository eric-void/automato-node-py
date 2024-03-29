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
    # Consider an entry dead if disconnected and not reconnected within this time. Use "0" to disable check
    # [Available also in specific entry config]
    'health-dead-disconnected-timeout': '1m',
    # If setted, every entry is considered alive when it sends a message
    # [Available also in specific entry config]
    'health-alive-on-message': True,
    # If setted, every entry is considered dead when no messages are sent in X time (messages emitting these events are ignored: connected, alive, failure)
    # [Available also in specific entry config]
    #'health-dead-message-timeout': '10m',

    # After this time in "alive" state, if no "health event" occours the status goes to "idle"
    'health-idle-time': '6h', 
    # Every "run_interval" or "check_interval" timeout check will consider original property multiplied by this factor (e.g. if "run_interval" is 10, the checker will consider timeout if not published in 15 seconds)
    'health-check_interval-multiplier': 2,
    # Internal
    'health-checker-secs': 5,
    # If an entry fails only for required entries, do not publish its status change
    'health-do-not-publish-require-failures': True,
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
  
"""
entry.definition.config = {
  'health-publish' = 'always|never|major', # default: major
}
"""

def load(entry):
  return {
    'subscribe': {
      '#': {
        'handler': on_subscribe_all_messages
      }
    }
  }

# entry_load handler should be executed as the last one
SYSTEM_HANDLER_ORDER_entry_load = 10

def entry_load(self_entry, entry):
  if entry.is_local:
    entry.health_entry = self_entry
    entry.health_status = { 'value': '', 'reason': '', 'flags': [] }
    entry.health_dead = '' # Reason the entry should be considered dead
    entry.health_response = '' # A failure in response to subscribed topic
    entry.health_required = {} # The status of required entries (only for entries in status "dead" or "failure")
    entry.health_publish = {} # Failure in run_interval/check_interval (not published as often as expected)
    entry.health_time = 0 # Last access to an health_* variable
    entry.health_changed = 0 # Last MAJOR change (from alive|idle to dead|failure or back) to an health_* variable
    entry.health_config_dead_disconnected_timeout = utils.read_duration(entry.config['health-dead-disconnected-timeout'] if 'health-dead-disconnected-timeout' in entry.config else (self_entry.config['health-dead-disconnected-timeout'] if 'health-dead-disconnected-timeout' in self_entry.config else 0))
    entry.health_config_alive_on_message = utils.read_duration(entry.config['health-alive-on-message'] if 'health-alive-on-message' in entry.config else (self_entry.config['health-alive-on-message'] if 'health-alive-on-message' in self_entry.config else False))
    entry.health_config_dead_message_timeout = utils.read_duration(entry.config['health-dead-message-timeout'] if 'health-dead-message-timeout' in entry.config else (self_entry.config['health-dead-message-timeout'] if 'health-dead-message-timeout' in self_entry.config else 0))
    
    system.entry_definition_add_default(entry, {
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
        },
      },
      "events_listen": [".connected", ".alive", ".failure"]
    });

def entry_init(self_entry, entry):
  if entry.is_local:
    if entry.health_config_dead_disconnected_timeout > 0 and system.entry_support_event(entry, 'connected'):
      entry.on('connected', lambda source_entry, eventname, eventdata, caller, published_message: event_connected(self_entry, source_entry, eventname, eventdata, caller, published_message), None, self_entry)
    
    if 'required' in entry.definition and entry.definition['required']:
      for req_entry_id in entry.definition['required']:
        rentry = system.entry_get(req_entry_id)
        if rentry:
          _system_loaded_add_required_listeners(self_entry, rentry, entry)

    for t in entry.definition['publish']:
      # TODO run_cron support
      if ('run_interval' in entry.definition['publish'][t] and entry.definition['publish'][t]['run_interval'] != 0) or ('check_interval' in entry.definition['publish'][t] and entry.definition['publish'][t]['check_interval'] != 0):
        interval = utils.read_duration(entry.definition['publish'][t]['check_interval'] if 'check_interval' in entry.definition['publish'][t] else entry.definition['publish'][t]['run_interval']) * self_entry.config['health-check_interval-multiplier']
        if not t in self_entry.health_publish_checker:
          self_entry.health_publish_checker[t] = {}
        self_entry.health_publish_checker[t][entry.id] = { 'interval': interval, 'last_published': 0 }

def entry_unload(self_entry, entry):
  pass

def _system_loaded_add_required_listeners(self_entry, required_entry, required_by_entry):
  required_entry.on('alive', lambda source_entry, eventname, eventdata, caller, published_message: event_health_for_requirement(self_entry, source_entry, eventname, eventdata, caller, published_message, required_by_entry), None, self_entry)
  required_entry.on('failure', lambda source_entry, eventname, eventdata, caller, published_message: event_health_for_requirement(self_entry, source_entry, eventname, eventdata, caller, published_message, required_by_entry), None, self_entry)

def init(entry):
  entry.health_dead_checker = {}
  entry.health_publish_checker = {}

  entry.health_checker_thread = threading.Thread(target = _health_checker_timer, args = [entry], daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
  entry.health_checker_thread._destroyed = False
  entry.health_checker_thread.start()
  
def destroy(entry):
  entry.health_checker_thread._destroyed = True
  entry.health_checker_thread.join()

def entry_health_status(entry):
  if not entry.is_local or not hasattr(entry, 'health_entry'):
    return None
  
  res = {'value': 'idle', 'reason': '', 'flags': []}
  
  if entry.health_dead:
    res['flags'].append('dead')
  if entry.health_response:
    res['flags'].append('response')
  if entry.health_required:
    res['flags'].append('required')
  if entry.health_publish:
    res['flags'].append('publish')
  
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
        res['reason'] = res['reason'] + (', ' if res['reason'] else '') + _('{topic} not published as expected (last published: {last}, check: {now}, diff: {diff}, interval: {interval}, delay: {delay})').format(topic = t, now = entry.health_publish[t][0], last = entry.health_publish[t][1], diff = entry.health_publish[t][0] - entry.health_publish[t][1], interval = entry.health_publish[t][2], delay = entry.health_publish[t][3])
    if res['reason']:
      res['value'] = 'failure'

  if res['value'] == 'idle' and system.time() - entry.health_time < utils.read_duration(entry.health_entry.config['health-idle-time']):
    res['value'] = 'alive'

  return res

def check_health_status(installer_entry, entry):
  entry.health_time = system.time()
  publish_health_status(installer_entry, entry)

def publish_health_status(installer_entry, entry):
  status = entry_health_status(entry)
  if status:
    has_problems = status['value'] == 'dead' or status['value'] == 'failure'
    had_problems = entry.health_status['value'] == 'dead' or entry.health_status['value'] == 'failure'
    changed = status['value'] != entry.health_status['value'] or status['reason'] != entry.health_status['reason']
    changed_major = has_problems != had_problems
    
    to_publish = entry.config['health-publish'] if 'health-publish' in entry.config else 'major'
    if installer_entry.config['health-do-not-publish-require-failures'] and ((status['flags'] == ['required'] and entry.health_status['flags'] == []) or (status['flags'] == [] and entry.health_status['flags'] == ['required'])):
      to_publish = False
    if changed_major:
      entry.health_changed = entry.health_time
    if changed:
      entry.health_status = status
    
    if to_publish == 'always' or (to_publish == 'major' and changed_major):
      status['changed'] = entry.health_changed
      status['schanged'] = utils.strftime(status['changed']) if status['changed'] > 0 else '-'
      #status['entry'] = entry.id
      status['time'] = system.time()
      entry.publish('health', status)
    
def publish_all_entries_status(entry, topic_rule, topic_definition):
  status = {}
  for entry_id in system.entries():
    oentry = system.entry_get(entry_id)
    if oentry.is_local and entry_id != entry.id:
      status[entry_id] = entry_health_status(oentry)
      if status[entry_id]:
        status[entry_id]['changed'] = oentry.health_changed
        status[entry_id]['schanged'] = utils.strftime(status[entry_id]['changed']) if status[entry_id]['changed'] > 0 else '-'
  entry.publish('', status)

def _health_checker_timer(entry):
  # if system load_level is high i disable health_publish_checker and health_dead_checker. When the load returns low, i'll reset health checker data (to avoid fake health problems)
  health_disable_load_level = 0
  
  while not threading.currentThread()._destroyed:
    now = system.time()
    
    if node.load_level() > 0:
      health_disable_load_level = now
    elif health_disable_load_level > 0 and node.load_level() == 0 and now - health_disable_load_level > 60:
      health_disable_load_level = 0
      # if a moment ago the system was too load, and now is ok, i must consider health_dead_checker and health_publish_checker data as invalid and reset them (or i'll report a lot of fake health problems)
    
    if health_disable_load_level > 0:
      # health_dead_checker
      for entry_id in entry.health_dead_checker:
        source_entry = system.entry_get(entry_id)
        if source_entry:
          entry.health_dead_checker[entry_id] = (system.time() + entry.health_dead_checker[entry_id][1], entry.health_dead_checker[entry_id][1], entry.health_dead_checker[entry_id][2])

      # health_publish_checker
      for t in entry.health_publish_checker:
        for e in entry.health_publish_checker[t]:
          if entry.health_publish_checker[t][e]['last_published'] > 0:
            entry.health_publish_checker[t][e]['last_published'] = system.time()
    
    else:
      # health_dead_checker
      timeouts = [ entry_id for entry_id in entry.health_dead_checker if now > entry.health_dead_checker[entry_id][0] ]
      if timeouts:
        for entry_id in timeouts:
          source_entry = system.entry_get(entry_id)
          if source_entry:
            source_entry.health_dead = entry.health_dead_checker[entry_id][2]
            check_health_status(entry, source_entry)
        entry.health_dead_checker = { entry_id: entry.health_dead_checker[entry_id] for entry_id in entry.health_dead_checker if entry_id not in timeouts }
      
      # health_publish_checker
      delay = system.broker().queueDelay() * 2 if not system.test_mode else 0
      for t in entry.health_publish_checker:
        for e in entry.health_publish_checker[t]:
          if entry.health_publish_checker[t][e]['last_published'] > 0 and now - entry.health_publish_checker[t][e]['last_published'] > entry.health_publish_checker[t][e]['interval'] + delay:
            target_entry = system.entry_get(e)
            if target_entry and t not in target_entry.health_publish:
              target_entry.health_publish[t] = [now, entry.health_publish_checker[t][e]['last_published'], entry.health_publish_checker[t][e]['interval'], delay]
              check_health_status(entry, target_entry)

    system.sleep(entry.config['health-checker-secs'])

def event_connected(self_entry, source_entry, eventname, eventdata, caller, published_message, from_generic_message = False):
  if eventdata['params']['value']:
    source_entry.health_dead = ''
    # A connection resets response failure
    source_entry.health_response = ''
    if source_entry.id in self_entry.health_dead_checker:
      del self_entry.health_dead_checker[source_entry.id]
    check_health_status(self_entry, source_entry)
  else:
    self_entry.health_dead_checker[source_entry.id] = (system.time() + source_entry.health_config_dead_disconnected_timeout, source_entry.health_config_dead_disconnected_timeout, 'disconnected for too long')

def on_subscribe_all_messages(entry, subscribed_message):
  """
  Monitor every mqtt message
  """
  message = subscribed_message.message
  if (message.retain): # Retained messages should be skipped
    return

  firstpm = subscribed_message.message.firstPublishedMessage()
  listened_events = [e for e in subscribed_message.message.events() if e['name'] == 'connected' or e['name'] == 'alive' or e['name'] == 'failure']
  if firstpm and firstpm.entry.is_local and len(listened_events) == 0:
    if not hasattr(firstpm.entry, 'health_config_alive_on_message'):
      if firstpm.entry.id != entry.id:
        logging.error("HEALTH> entry {id} has NO health_config_alive_on_message".format(id = firstpm.entry.id))
    elif firstpm.entry.health_config_alive_on_message:
      event_connected(entry, firstpm.entry, 'connected', { 'params': { 'value': True } }, '', None, from_generic_message = True)
    if not hasattr(firstpm.entry, 'health_config_dead_message_timeout'):
      if firstpm.entry.id != entry.id:
        logging.error("HEALTH> entry {id} has NO health_config_dead_message_timeout".format(id = firstpm.entry.id))
    elif firstpm.entry.health_config_dead_message_timeout:
      entry.health_dead_checker[firstpm.entry.id] = (system.time() + firstpm.entry.health_config_dead_message_timeout, firstpm.entry.health_config_dead_message_timeout, 'silent for too long')
  
  # Look for entries subscribed to this topic. If a "response" is defined, we will wait for the response to come (or not)
  for sm in message.subscribedMessages():
    if 'response' in sm.definition:
      system.subscribe_response(sm.entry, subscribed_message.message, callback = lambda _entry, _id, _message, _final, _response_to_message: on_response_to_subscribed_message(entry, _entry, _id, _message, _final, _response_to_message), no_response_callback = lambda _entry, _id, _response_to_message: on_no_response_to_subscribed_message(entry, _entry, _id, _response_to_message))
  
  # Update publish checker
  for pm in subscribed_message.message.publishedMessages():
    if pm.topic_rule in entry.health_publish_checker and pm.entry.id in entry.health_publish_checker[pm.topic_rule]:
      entry.health_publish_checker[pm.topic_rule][pm.entry.id]['last_published'] = system.time()
      if pm.entry and pm.topic_rule in pm.entry.health_publish:
        del pm.entry.health_publish[pm.topic_rule]
        check_health_status(entry, pm.entry)
  """
  if subscribed_message.topic in entry.health_publish_checker:
    for e in entry.health_publish_checker[subscribed_message.topic]:
      entry.health_publish_checker[subscribed_message.topic][e]['last_published'] = system.time()
      target_entry = system.entry_get(e)
      if target_entry and subscribed_message.topic in target_entry.health_publish:
        del target_entry.health_publish[subscribed_message.topic]
        check_health_status(entry, target_entry)
  """

def on_response_to_subscribed_message(installer_entry, entry, id, message, final, response_to_message):
  entry.health_response = ''
  check_health_status(installer_entry, entry)

def on_no_response_to_subscribed_message(installer_entry, entry, id, response_to_message):
  entry.health_response = _('no response to {topic} = {payload} request').format(topic = response_to_message.topic, payload = str(response_to_message.payload)[0:20])
  check_health_status(installer_entry, entry)

def event_health_for_requirement(self_entry, source_entry, eventname, eventdata, caller, published_message, required_by_entry):
  m = system.current_received_message()
  if m.retain: # health events from retained messages should be skipped
    return
  
  """
  Called when an entry, required by another entry, changes its health status
  """
  if eventname == 'alive':
    if not eventdata['params']['value']:
      required_by_entry.health_required[source_entry.id] = 'dead'
      check_health_status(self_entry, required_by_entry)
    elif source_entry.id in required_by_entry.health_required and required_by_entry.health_required[source_entry.id] == 'dead':
      del required_by_entry.health_required[source_entry.id]
      check_health_status(self_entry, required_by_entry)
  elif eventname == 'failure':
    if eventdata['params']['value']:
      required_by_entry.health_required[source_entry.id] = 'failure'
      check_health_status(self_entry, required_by_entry)
    elif source_entry.id in required_by_entry.health_required and required_by_entry.health_required[source_entry.id] == 'failure':
      del required_by_entry.health_required[source_entry.id]
      check_health_status(self_entry, required_by_entry)
