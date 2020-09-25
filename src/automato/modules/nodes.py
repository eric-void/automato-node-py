# require python3
# -*- coding: utf-8 -*-

import logging
import zlib
import base64
import json

from automato.core import system
from automato.core import utils

definition = {
  'config': {
    'master': False, # At least a node should have "master: True". That node will respond to automato/data requests
    'compress': True,
    'local': False, # If set to TRUE, this node will send its entries to other nodes, but it will not read other node's entries. Use this to reduce system load on big networks, and ONLY if this node don't need to look for remote entries (you can't use events or actions from remote nodes if turned on!)
    'dead_time': '45m', # If a node don't send its metadata at least every X seconds, consider it as dead. It should be > than max(definition['publish']['./metadata']['run_interval'])
  },
  
  'description': _('Automato remote nodes manager'),
  'notify_level': 'debug',
  'topic_root': 'automato',
  'run_interval': '10m', # Check for dead nodes every 10 minutes
  'publish': {
    './metadata': {
      'description': _('System metadata built by an automato node (by merging local metadata with other nodes metadata)'),
      'type': 'object',
      'run_interval': '30m', # Sends metadata every 30 minutes. So other nodes, if don't see this node metadata after 30 minutes, could consider this as a dead node
      'handler': 'publish_metadata',
    },
    './dead-node': {
      'description': _('Detected a non-responding node, it will be considered as dead for next metadata broadcast'),
      'type': 'object',
      'notify_level': 'info',
      'notify': _('Automato node "{payload[name]}" is dead, last seen at {payload[last_seen!strftime(%Y-%m-%d %H:%M:%S)]}'),
    }
  },
  'subscribe': {
    './metadata' : {
      #'description': _('Listen to other automato nodes metadata'),
      'handler': 'on_metadata'
    },
    './metadata/get': {
      'description': _('Request the publishing on the broker of system metadata'),
      'publish' : [ './metadata' ]
    }
  }
}

def load(entry):
  if entry.definition['config']['master']:
    return {
      'publish': {
        './data': {
          'description': _('System data collected (metadata + all events)'),
          'type': 'object',
          'notify_level': 'info',
          'handler': 'publish_data',
        }
      },
      'subscribe': {
        './data/get': {
          'description': _('Request the publishing on the broker of system data'),
          'publish' : [ './data' ]
        }
      }
    };

def start(entry):
  #OBSOLETE: if 'nodes' not in entry.data:
  entry.data['nodes'] = {
    system.default_node_name: {
      'description': system.config['description'] if 'description' in system.config else '',
      'time': system.time(),
    }
  }
  #OBSOLETE: if 'seen' not in entry.data:
  entry.data['seen'] = {}

  publish_metadata(entry, entry.topic('./metadata'))

def on_metadata(entry, subscribed_message):
  payload = subscribed_message.payload
  if payload and 'from_node' in payload and payload['from_node'] != system.default_node_name and 'time' in payload and system.time() - payload['time'] < utils.read_duration(entry.config['dead_time']):
    entry.data['seen'][payload['from_node']] = { 'my_time': system.time(), 'his_time': payload['time'] }
    
    todo = []
    for node in payload['nodes']:
      if node not in entry.data['nodes'] or entry.data['nodes'][node]['time'] < payload['nodes'][node]['time']:
        entry.data['nodes'][node] = payload['nodes'][node]
        todo.append(node)
    if not entry.config['local']:
      for node in todo:
        #entry.data[node] = payload['nodes'][node]
        payload_entries = utils.b64_decompress_data(payload['entries'])
        node_entries = {}
        for entry_id in payload_entries:
          if entry_id.endswith('@' + node):
            node_entries[entry_id] = payload_entries[entry_id]
        system.entry_load_definitions(node_entries, node_name = node, unload_other_from_node = True, id_from_definition = False)
    
    if todo:
      publish_metadata(entry, entry.topic('./metadata'))
      logging.debug('#{id}> Loaded new metadata by: {todo}, current entries: {entries}'.format(id = entry.id, todo = todo, entries = ", ".join(system.entries().keys())))
    # DEBUG
    #logging.debug('#{id}> Loaded new metadata: {todo}, mynodes: {nodes}, extnodes: {nodes}, current entries: {entries}'.format(id = entry.id, todo = todo, mynodes = entry.data['nodes'], nodes = payload['nodes'], entries = ", ".join(system.entries.keys())))

def publish_metadata(entry, topic, local_metadata = None):
  entry.publish(topic, {
    'from_node': system.default_node_name,
    'time': system.time(),
    'nodes': entry.data['nodes'],
    'entries': utils.b64_compress_data(system.entries_definition_exportable()) if entry.config['compress'] else system.entries_definition_exportable(),
  })

def publish_data(entry, topic, local_metadata = None):
  if not entry.config['compress']:
    entry.publish(topic, {
      'from_node': system.default_node_name,
      'time': system.time(),
      'entries': system.entries_definition_exportable(),
      'events': system.events_export(),
    });
  else:
    entry.publish(topic, {
      'from_node': system.default_node_name,
      'time': system.time(),
      '+': utils.b64_compress_data({
        'entries': system.entries_definition_exportable(),
        'events': system.events_export(),
      })
    });

def run(entry):
  t = system.time()

  if 'seen' in entry.data and t - entry.created > 60:
    dead = [node for node in entry.data['seen'] if node != system.default_node_name and t - entry.data['seen'][node]['his_time'] > utils.read_duration(entry.config['dead_time'])]
    if dead:
      for node in dead:
        system.entry_unload_node_entries(node)
        entry.publish('./dead-node', { 'name': node, 'last_seen': entry.data['seen'][node]['his_time'], 'time': t })
      entry.data['seen'] = {node:v for node,v in entry.data['seen'].items() if t - entry.data['seen'][node]['his_time'] <= utils.read_duration(entry.config['dead_time'])}
      publish_metadata(entry, entry.topic('./metadata'))
        
    # Can't kill myself
    #if [node for node in entry.data['seen'] if node == system.default_node_name and t - entry.data['seen'][node]['his_time'] > utils.read_duration(entry.config['dead_time'])]:
    #  ###SEND_MESSAGE###('./metadata', _('Hi, i\'m automato node "{name}", and i don\'t receive my own metadata since {time}, problems on MQTT broker? Or am i dead?').format(name = system.default_node_name, time = utils.strftime(entry.data['seen'][system.default_node_name]['his_time'])), 'critical')
