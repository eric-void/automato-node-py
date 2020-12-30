# require python3
# -*- coding: utf-8 -*-

import logging
import os
import datetime

from automato.core import system
from automato.core import utils
from automato.node import node_system as node

# TODO Al momento funziona solo con listen_all_events = TRUE
# TODO Path deve già esistere (non lo crea se non c'è)

definition = {
  'config': {
    'path': './history',
    'ignore_events': ['clock', 'stats'],
  },
  'run_interval': 60,
}

def load(entry):
  entry.history_path = os.path.realpath(os.path.join(entry.node_config['base_path'], entry.definition['config']['path']))
  entry.history_last_file_suffix = ''
  entry.history_event_buffer = {}
  system.on_all_events(lambda _entry, eventname, eventdata, caller, published_message: on_all_events(entry, _entry, eventname, eventdata, caller, published_message))

def on_all_events(installer_entry, entry, eventname, eventdata, caller, published_message):
  if eventname not in installer_entry.config['ignore_events']:
    if entry.id not in installer_entry.history_event_buffer:
      installer_entry.history_event_buffer[entry.id] = {}
    if eventname not in installer_entry.history_event_buffer[entry.id]:
      installer_entry.history_event_buffer[entry.id][eventname] = {}
    k = system.entry_event_keys_index(eventdata['keys'])
    if k not in installer_entry.history_event_buffer[entry.id][eventname]:
      installer_entry.history_event_buffer[entry.id][eventname][k] = [ ['#', eventdata] ]
    else:
      installer_entry.history_event_buffer[entry.id][eventname][k].append(['', eventdata])

def run(entry):
  file_suffix = datetime.datetime.now().strftime('%Y-%m-%d')
  for entry_id in entry.history_event_buffer:
    lines = []
    filepath = entry.history_path + '/' + entry_id + '-' + file_suffix + '.tsv'

    for eventname in entry.history_event_buffer[entry_id]:
      for k in entry.history_event_buffer[entry_id][eventname]:
        t = '#'
        for d in entry.history_event_buffer[entry_id][eventname][k]:
          if file_suffix == entry.history_last_file_suffix:
            t = d[0]
          if t == '#' or d[1]['changed_params']:
            lines.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f') + '\t' + eventname + '\t' + utils.json_export(d[1]['keys']) + '\t' + t + utils.json_export({x: d[1]['params'][x] for x in d[1]['params'] if x not in d[1]['keys']} if t == '#' else d[1]['changed_params']))
          t = ''
        entry.history_event_buffer[entry_id][eventname][k] = []
    
    if len(lines):
      lines.sort()
      with open(filepath, 'a') as the_file:
        for l in lines:
          the_file.write(l + '\n')

  entry.history_last_file_suffix = file_suffix
