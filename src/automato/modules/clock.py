# require python3
# -*- coding: utf-8 -*-

import logging

from automato.core import system

definition = {
  'description': _('Send current time in unix timestamp'),
  'notify_level': 'debug',
  'topic_root': 'home',
  'publish': {
    './time': {
      'type': 'int',
      'description': _('Current time in unix timestamp'),
      'notify': _('Current time is {_[payload!strftime(%Y-%m-%d %H:%M:%S)]}'),
      'run_interval': 30,
      'qos': 0,
      'retain': True,
      'handler': 'publish',
      'events': { 'clock': '({value: payload})' }
    }
  },
  'subscribe': {
    './time/get': {
      'description': _('Send current time in unix timestamp'),
      'publish': [ './time' ],
    },
    'status': {
      # 'description': _('Send current time in unix timestamp'),
      'publish': [ './time' ],
    }
  }
}

def publish(entry, topic_rule, topic_definition):
  logging.debug('#{id}> clock {topic_rule}: {value}'.format(id = entry.id, topic_rule = topic_rule, value = system.time()))
  entry.publish('', system.time())
