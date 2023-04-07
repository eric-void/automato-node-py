# require python3
# -*- coding: utf-8 -*-

"""
NUT Integration

Uses official "PyNUT" module: https://github.com/networkupstools/nut/tree/master/scripts/python/module
- PyNUT code example (test): https://github.com/networkupstools/nut/blob/master/scripts/python/module/test_nutclient.py.in
- PyNUT code example (monitor app): https://github.com/networkupstools/nut/blob/master/scripts/python/app/NUT-Monitor-py3qt5.in

The module has no official pip package.
You need to manual copy the library file in python "site-packages" dir.

EXAMPLE OF MANUAL INSTALLATION:
(this works in Arch Linux, other distrubution paths may vary)

git clone https://github.com/networkupstools/nut.git
for i in /usr/lib/python*/site-packages/; do sudo cp nut/scripts/python/module/PyNUT.py.in ${i}PyNUT.py; done;
rm -rf nut

"""

import logging
import re
import sys
import PyNUT

from automato.core import system
from automato.core import utils
from automato.node import node_system as node

definition = {
  'description': _('NUT (Network UPS Tools) integration'),
  
  'config': {
    'nut_upsname': '',
    'nut_host': '127.0.0.1',
    'nut_port': 3493,
    'nut_username': None, # admin | upsmon
    'nut_password': None, # nutobu | nutnut
    'nut_debug': False,
    'nut_full_vars_interval': '1h',
  },
  
  'run_interval': 60, # = polling interval
  
  'notify_level': 'info',
  'topic_root': 'nut',
  'publish': {
    # Non really used for publishing topics. Load phase propagates 'reatain' and 'qos' key to other ./var/* publish definition 
    'var_template': {
      'topic': './var/#',
      'topic_match_priority': 0,
      'retain': True,
      #'events_debug': 1,
    },
    './var/time': {
      'type': 'int',
      'events': { "clock": "js:({value: parseInt(payload)})" },
      # 'retain': True, > copied from var_template
    },
    # Common variables, @see https://networkupstools.org/docs/developer-guide.chunked/apas02.html or https://www.rfc-editor.org/rfc/rfc9271.html#appendix-A.1
    './var/ups_status': {
      'type': 'string',
      'notify': _('Current UPS status is: {payload}'),
      'events': {
        "connected": "js:({value: payload.indexOf('OL') >= 0 || payload.indexOf('OB') >= 0 ? 1 : 0 })",
        "output": [
          # @see https://www.rfc-editor.org/rfc/rfc9271.html#section-5.1
          "js:({port: 'online', value: payload.indexOf('OL') >= 0 ? 1 : 0})",
          "js:({port: 'on_battery', value: payload.indexOf('OB') >= 0 ? 1 : 0})",
          "js:({port: 'charging', value: payload.indexOf('CHRG') >= 0 && payload.indexOf('DISCHRG') < 0 ? 1 : 0})",
          "js:({port: 'discharging', value: payload.indexOf('DISCHRG') >= 0 ? 1 : 0})",
          "js:({port: 'low_battery', value: payload.indexOf('LB') >= 0 ? 1 : 0})",
          "js:({port: 'replace_battery', value: payload.indexOf('RB') >= 0 ? 1 : 0})",
          "js:({port: 'overload', value: payload.indexOf('OVER') >= 0 ? 1 : 0})",
          "js:({port: 'trimming', value: payload.indexOf('TRIM') >= 0 ? 1 : 0})",
          "js:({port: 'boosting', value: payload.indexOf('BOOST') >= 0 ? 1 : 0})",
          "js:({port: 'bypass', value: payload.indexOf('BYPASS') >= 0 ? 1 : 0})",
        ],
      }
    },
    './var/ups_temperature': {
      'type': 'float',
      'notify': _('Current UPS temperature is: {payload}°C'),
      'events': {
        "temperature": "js:({value: parseFloat(payload)})",
      }
    },
    './var/output_voltage': {
      'type': 'int',
      'notify': _('Current UPS output voltage is: {payload}V'),
      'events': {
        "energy": "js:({port: 'output', voltage: parseInt(payload)})",
      }
    },
    './var/output_voltage_nominal': {
      'type': 'int',
      'notify': _('Current UPS output voltage (nominal) is: {payload}V'),
      'events': {
        "energy": "js:({port: 'output_nominal', voltage: parseInt(payload)})",
      }
    },
    './var/battery_charge': {
      'type': 'int',
      'notify': _('Current UPS battery charge is: {payload}%'),
      'events': {
        "battery": "js:({value: parseInt(payload)})",
      }
    },
    './var/battery_runtime': {
      'type': 'int',
      'notify': _('Current UPS battery runtime is: {payload} seconds'),
      'events': {
        "autonomy": "js:({value: parseInt(payload)})",
      }
    },
    './var/ups_load': {
      'type': 'int',
      'notify': _('Current UPS load is: {payload}%'),
      'events': {
        "load": "js:({value: parseInt(payload)})",
      }
    },
    './var/ups_realpower': {
      'type': 'int',
      'notify': _('Current UPS power is: {payload}W'),
      'events': {
        "energy": "js:({port: 'ups', power: parseInt(payload)})",
      }
    }
    # other publish definitions are added by "load" handler
  },
  
  'subscribe': {
    './refresh': {
      'handler': 'on_refresh',
    }
  }
}

def load(entry):
  definition = {
    'publish': {}
  }
  template = entry.definition['publish']['var_template']
  template = {
    'qos': template['qos'] if 'qos' in template else 0,
    'retain': template['retain'] if 'retain' in template else 0,
    'events_debug': template['events_debug'] if 'events_debug' in template else 0,
  }
  for k in entry.definition['publish']:
    if k != 'var_template':
      definition['publish'][k] = {}
      if 'qos' not in entry.definition['publish'][k]:
        definition['publish'][k]['qos'] = template['qos']
      if 'retain' not in entry.definition['publish'][k]:
        definition['publish'][k]['retain'] = template['retain']
      if 'events_debug' not in entry.definition['publish'][k]:
        definition['publish'][k]['events_debug'] = template['events_debug']
  
  entry.nut_vars = nut_GetUPSVars(entry, entry.definition["config"])
  entry.nut_vars_last_full = 0
  if entry.nut_vars:
    for k in entry.nut_vars:
      if k not in entry.definition['publish']:
        definition['publish']['./var/' + k.replace('.', '_')] = {
          ** template, 
          'type': 'int' if isinstance(entry.nut_vars[k], int) else ('float' if isinstance(entry.nut_vars[k], float) else 'string'),
        }
  return definition

def run(entry):
  publish_all = system.time() - entry.nut_vars_last_full > utils.read_duration(entry.config['nut_full_vars_interval'])
  
  if entry.nut_vars:
    nut_vars = nut_GetUPSVars(entry)
    if nut_vars:
      entry.publish('./var/time', system.time())
      for k in nut_vars:
        if publish_all or k not in entry.nut_vars or nut_vars[k] != entry.nut_vars[k]:
          entry.publish('./var/' + k.replace('.', '_'), nut_vars[k])
          entry.nut_vars[k] = nut_vars[k]
      if publish_all:
        entry.nut_vars_last_full = system.time()

def on_refresh(entry, subscribed_message):
  run(entry)

def nut_connect(entry, config = None):
  if not config:
    config = entry.config
  nut_client = None
  try:
    nut_client = PyNUT.PyNUTClient(host = config['nut_host'], port = config['nut_port'], login = config['nut_username'], password = config['nut_password'], debug = config['nut_debug'])
    if not nut_client.CheckUPSAvailable(config['nut_upsname']):
      logging.error("#{id}> UPS {upsname} is not available".format(id = entry.id, upsname = config['nut_upsname']))
      nut_client = None
  except :
    logging.exception("#{id}> error connecting: {err}".format(id = entry.id, err = sys.exc_info()[1]))
  return nut_client

def nut_GetUPSVars(entry, config = None, nut_client = None):
  if not config:
    config = entry.config
  res = None
  if 'nut_test_result' in config and 'GetUPSVars' in config['nut_test_result'] and config['nut_test_result']['GetUPSVars']:
    res = config['nut_test_result']['GetUPSVars']
  else:
    if not nut_client:
      nut_client = nut_connect(entry, config)
    if nut_client:
      try:
        res = nut_client.GetUPSVars(config['nut_upsname'])
      except :
        logging.exception("#{id}> error getting data (GetUPSVars) from UPS: {err}".format(id = entry.id, err = sys.exc_info()[1]))
  if res:
    res = {k.decode("UTF-8"): float(res[k].decode("UTF-8")) if re.match("^[+-]?[0-9]+\.[0-9]+$", res[k].decode("UTF-8")) else int(res[k].decode("UTF-8")) if re.match("^[+-]?[0-9]+$", res[k].decode("UTF-8")) else res[k].decode("UTF-8") for k in res}
  return res

# vv = nut_client.GetRWVars(entry.config['nut_upsname'])
# entry.nut_rw_vars = {k.decode("UTF-8"): vv[k].decode("UTF-8") for k in r}
# vv = nut_client.GetUPSCommands(entry.config['nut_upsname'])
# entry.nut_commands = {k.decode("UTF-8"): vv[k].decode("UTF-8") for k in r}


