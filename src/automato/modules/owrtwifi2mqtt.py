# require python3
# -*- coding: utf-8 -*-

# Based on https://github.com/dersimn/owrtwifi2mqtt
# Subscribe to:
# - owrtwifi/status/mac-00-00-00-00-00-00/lastseen/iso8601 2019-12-12T16:22:53+0100
# - owrtwifi/status/mac-00-00-00-00-00-00/lastseen/epoch 1576164173
# - owrtwifi/status/mac-00-00-00-00-00-00/event new|del

import logging
import threading
from automato.core import system
from automato.core import utils

definition = {
  'description': _('Sniff network searching for devices with mac addresses'),

  'install_on': {
    'mac_address': (),
    'net_connection_momentary': (),
  },

  'config': {
    'momentary_flood_time': 30,
    'connection_time': '15m',
    'disconnect_on_event_del': False,
  },
  
  'subscribe': {
    '/^owrtwifi/status/mac-(.*)/(lastseen/iso8601|lastseen/epoch|event)$/': {
      'handler': 'on_subscribed_message',
    }
    
  }
}

def load(entry):
  if not 'owrtwifi2mqtt_mac_addresses' in entry.data:
    entry.data['owrtwifi2mqtt_mac_addresses'] = {}

def init(entry):
  entry.destroyed = False
  entry.thread_checker = threading.Thread(target = _thread_checker, args = [entry], daemon = True)
  entry.thread_checker._destroyed = False
  entry.thread_checker.start()

def destroy(entry):
  entry.thread_checker._destroyed = True
  entry.thread_checker.join()

def entry_install(installer_entry, entry, conf):
  installer_entry.data['owrtwifi2mqtt_mac_addresses'][conf['mac_address'].upper()] = [entry.id, 'net_connection_momentary' in conf and conf['net_connection_momentary'], False, 0]
  
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      '@/connected': {
        'description': _('Device connected to the network'),
        'type': 'none',
        'notify': _('Device {caption} connected to the local network'),
        'events': {
          'connected': 'js:({ value: true })'
        }
      },
      '@/disconnected': {
        'description': _('Device disconnected from the network'),
        'type': 'none',
        'notify': _('Device {caption} disconnected from the local network'),
        'events': {
          'connected': 'js:({ value: false })'
        }
      },
      '@/detected': {
        'description': _('Device momentarily detected on the network'),
        'type': 'none',
        'notify': _('Device {caption} momentarily detected on local network'),
        'events': {
          'connected': 'js:({ value: true, temporary: true})',
          'input': 'js:({ value: 1, temporary: true})'
        }
      }
    },
  })

def on_subscribed_message(installer_entry, subscribed_message):
  payload = subscribed_message.payload
  matches = subscribed_message.matches
  mac_address = matches[1].upper().replace("-", ":")
  if mac_address in installer_entry.data['owrtwifi2mqtt_mac_addresses']:
    entry = system.entry_get(installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][0])
    if entry:
      momentary = installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][1]
      connected = installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][2]
      last_seen = installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][3]
      installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][3] = system.time()
      if matches[2] == 'lastseen/iso8601' or matches[2] == 'lastseen/epoch' or (matches[2] == 'event' and payload == 'new'):
        if momentary:
          if system.time() - last_seen < utils.read_duration(installer_entry.config['momentary_flood_time']):
            return
          else:
            entry.publish('@/detected')
        elif not connected:
          installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][2] = True
          entry.publish('@/connected')
      elif (matches[2] == 'event' and payload == 'del') and installer_entry.config['disconnect_on_event_del']:
        installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][2] = False
        entry.publish('@/disconnected')

def _thread_checker(installer_entry):
  while not threading.currentThread()._destroyed:
    status_check(installer_entry)
    system.sleep(utils.read_duration(installer_entry.config['connection_time']) / 10)

def status_check(installer_entry):
  config_connection_time = utils.read_duration(installer_entry.config['connection_time'])
  for mac_address in installer_entry.data['owrtwifi2mqtt_mac_addresses']:
    if installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][2] and system.time() - installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][3] > config_connection_time:
      entry = system.entry_get(installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][0])
      if entry:
        installer_entry.data['owrtwifi2mqtt_mac_addresses'][mac_address][2] = False
        entry.publish('@/disconnected')

