# require python3
# -*- coding: utf-8 -*-

import logging
import random
import re
import os
import json

from automato.core import system
from automato.core import utils
from automato.node import node_system as node
from automato.core.notifications import notifications_levels

definition = {
  'config': {
    "storage": "notifications-subscribptions.db",
    "history_length": 21600,
    "history_gc_prob": 5, # OBSOLETE: history is trimmed at every append
    "history_max_items": 2000, # Max number of notifications in history (they are stored in entry data: a big history is expensive to check and store)
    "history_filter": "info",
    "notify_send": False,
    "notify_send_level": "info",
    "history_compress": True,
  },
  
  "subscribe": {
    "notifications/history/get": {
      "description": _("Last notifications published on network"),
      "response": [ "notifications/history" ],
      "publish": [ "notifications/history" ],
    },
    "notifications/subscribe/#": {
      "description": _("Subscribe client to a notification pattern"),
      "topic_syntax": "notifications/subscribe/[LEVEL]/[TYPE]/[TOPIC]",
      "topic_syntax_description": "LEVEL = _|string|string_, TYPE=_|string, TOPIC=_|string",
      "payload_syntax": "[CLIENT_TYPE]:[CLIENT_DATA]",
      "handler": 'on_notifications_subscribe',
      "response": [ "notifications/response" ]
    },
    "notifications/unsubscribe/#": {
      "description": _("Unsubscribe client to a previously subscribed notification pattern"),
      "topic_syntax": "notifications/unsubscribe/[LEVEL]/[TYPE]/[TOPIC]",
      "topic_syntax_description": "LEVEL = _|string|string_, TYPE=_|string, TOPIC=_|string",
      "payload_syntax": "[CLIENT_TYPE]:[CLIENT_DATA]",
      "type": "string",
      "handler": 'on_notifications_unsubscribe',
      "response": [ "notifications/response" ]
    },
    '#': {
      "handler": 'on_all_messages'
    }
  },
  "publish": {
    "notify/#": {
      "type": "string",
    },
    "notifications/response": {
      "type": "string",
    },
    "notifications/history": {
      "description": _("Last notifications published on network"),
      "type": "object",
      "handler": 'publish',
    }
  }
}

def init(entry):
  entry.notification_subscriptions = []
  if entry.storage.fileExists(entry.config['storage']):
    with entry.storage.fileOpen(entry.config['storage'], 'r') as f:
      for line in f:
        if line.strip():
          subscription = utils.json_import(line)
          entry.notification_subscriptions.append(subscription)
  
  if 'history' not in entry.data:
    entry.data['history'] = []
    

def on_all_messages(entry, subscribed_message):
  message = subscribed_message.message
  if (message.retain): # Non devo considerare i messaggi retained
    return
  
  min_level = None
  for pm in message.publishedMessages():
    # Skip building the notification (string formatting, notify_if scripts) if it can't reach any destination (history, notify_send, subscriptions)
    max_level = _definition_max_level(pm.definition)
    if max_level is None:
      continue
    if min_level is None:
      min_level = _min_useful_level(entry)
    if max_level < min_level:
      continue
    if pm.notificationString():
      notification_receive(entry, pm.topic, pm.notificationString(), pm.notificationLevelString())

def _level_value(level, unknown):
  return notifications_levels[level] if isinstance(level, str) and level in notifications_levels else unknown

def _definition_max_level(definition):
  """
  Max level a notification of this topic definition can have (considering notify_level, notify_change_level, and the ones in notify_if)
  @return None if the definition has no notification at all
  """
  has_notify = 'notify' in definition or 'notify_handler' in definition
  levels = [definition['notify_level'] if 'notify_level' in definition else 'info']
  if 'notify_change_level' in definition:
    levels.append(definition['notify_change_level'])
  if 'notify_if' in definition and isinstance(definition['notify_if'], dict):
    for v in definition['notify_if'].values():
      if isinstance(v, dict):
        has_notify = has_notify or 'notify' in v or 'notify_handler' in v
        for k in ['notify_level', 'notify_change_level', 'notify_next_level']:
          if k in v and v[k]:
            levels.append(v[k])
  if not has_notify:
    return None
  # Unknown levels are considered as the highest ones (the notification is not skipped)
  return max(_level_value(l, 1000) for l in levels)

def _min_useful_level(entry):
  """
  Min level of a notification that is used by someone (history, notify_send, a subscription)
  """
  levels = [_level_value(entry.config['history_filter'], 0)]
  if entry.config['notify_send']:
    levels.append(_level_value(entry.config['notify_send_level'], 0))
  for s in entry.notification_subscriptions:
    p = _re_topic_matches.match(s["pattern"])
    level = p.group(1) if p else '_'
    levels.append(0 if level == '_' else _level_value(level[0:-1] if level.endswith('_') else level, 0))
  return min(levels)

#def on_notify(entry, topic = None, payload = None, matches = None, source_entry = None, listened_events = {}):
#  notification_receive(entry, matches[2], payload, matches[1])

def notification_receive(entry, topic, string, notify_level):
  for s in entry.notification_subscriptions:
    if topic_matches(topic, notify_level, s["pattern"], entry):
      for target_entry in node.entries_implements('notifications_send'):
        node.entry_invoke(target_entry, 'notifications_send', s["driver"], s["data"], s["pattern"], topic, string, notify_level)

  if entry.config['notify_send'] and notifications_levels[notify_level] >= notifications_levels[entry.config['notify_send_level']]:
    entry.publish("notify/" + notify_level + "/" + topic, string)
  
  # Salvataggio history
  if notify_level in notifications_levels and notifications_levels[notify_level] < notifications_levels[entry.config["history_filter"]]:
    return
  
  t = system.time()
  history = entry.data['history']
  history.append({'time': t, 'level': notify_level, 'topic': topic, 'message': str(string)})
  # History is ordered by time: old items are at the beginning
  old = 0
  while old < len(history) and t - history[old]['time'] > entry.config["history_length"]:
    old += 1
  if len(history) - old > entry.config["history_max_items"]:
    old = len(history) - entry.config["history_max_items"]
  if old > 0:
    del history[:old]

_re_topic_matches = re.compile('^([^/]+)(?:/([^/]+))?$')

def topic_matches(topic, level, pattern, entry):
  p = _re_topic_matches.match(pattern)
  if p:
    if (p.group(1) == '_' or level == p.group(1) or (p.group(1)[-1] == '_' and level in notifications_levels and p.group(1)[0:-1] in notifications_levels and notifications_levels[level] >= notifications_levels[p.group(1)[0:-1]])) and (p.group(2) is None or p.group(2) == '_' or topic == p.group(2)):
      return True

# Pubblica "notifications/history" quando richiesto da "notifications/history/get"
def publish(entry, topic, definition):
  if entry.config['history_compress']:
    entry.publish('', { "time": system.time(), "+history": utils.b64_compress_data(entry.data['history'])})
  else:
    entry.publish('', { "time": system.time(), "history": entry.data['history']})

def on_notifications_subscribe(entry, subscribed_message):
  if type(subscribed_message.payload) != str:
    return
  
  matches = re.search('/subscribe/(([^/]+)(?:/([^/]+))?)$', subscribed_message.topic)
  data = re.search('^([^:]+):(.*)$', subscribed_message.payload)
  
  if matches and data:
    save = False
    for target_entry in node.entries_implements('notifications_subscribe'):
      save = node.entry_invoke(target_entry, 'notifications_subscribe', data.group(1), data.group(2), matches.group(1))
      if save:
        line = { "driver": data.group(1), "pattern": matches.group(1), "data": save, "time": system.time()}
        entry.notification_subscriptions.append(line)
        with entry.storage.fileOpen(entry.config['storage'], 'a') as f:
          f.write(utils.json_export(line) + '\n')
        entry.publish('notifications/response', _("Client subscribed to notification pattern {pattern}: {driver}:{data}").format(pattern = line["pattern"], driver = line["driver"], data = line["data"]))
        logging.debug('#{id}> Client subscribed to notification pattern {pattern}: {driver}:{data}'.format(id = entry.id, pattern = line["pattern"], driver = line["driver"], data = line["data"]))

def on_notifications_unsubscribe(entry, subscribed_message):
  if type(subscribed_message.payload) != str:
    return
  
  matches = re.search('/unsubscribe/(([^/]+)(?:/([^/]+))?)$', subscribed_message.topic)
  data = re.search('^([^:]+):(.*)$', subscribed_message.payload)
  
  if matches and data:
    found = False
    for i, s in enumerate(entry.notification_subscriptions):
      if s["pattern"] == matches.group(1) and s["driver"] == data.group(1):
        for target_entry in node.entries_implements('notifications_matches'):
          if node.entry_invoke(target_entry, 'notifications_matches', data.group(1), data.group(2), s["data"], matches.group(1)):
            found = s
            break
        if found:
          entry.notification_subscriptions.pop(i)
          entry.publish('notifications/response', _("Client unsubscribed from notification pattern {pattern}: {driver}:{data}").format(pattern = s["pattern"], driver = s["driver"], data = s["data"]))
          logging.debug('#{id}> Client unsubscribed from notification pattern {pattern}: {driver}:{data}'.format(id = entry.id, pattern = s["pattern"], driver = s["driver"], data = s["data"]))
          break
    if found:
      with entry.storage.fileOpen(entry.config['storage'], 'r') as old_file:
        with entry.storage.fileOpen(entry.config['storage'] + '.new', 'w') as new_file:
          for line in old_file:
            if line.strip():
              s = utils.json_import(line)
              if not (s["driver"] == found["driver"] and s["pattern"] == found["pattern"] and s["data"] == found["data"] and s["time"] == found["time"]):
                new_file.write(line.rstrip('\n') + '\n')
      if entry.storage.fileExists(entry.config['storage'] + '.new'):
        entry.storage.fileRemove(entry.config['storage'])
        entry.storage.fileRename(entry.config['storage'] + '.new', entry.config['storage'])
