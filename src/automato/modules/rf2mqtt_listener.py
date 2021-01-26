# require python3
# -*- coding: utf-8 -*-

import logging

from automato.core import system

definition = {
  'subscribe': {
    'rf2mqtt': {
      'handler': 'on_rf2mqtt_message',
    }
  }
}

"""
ENTRY DEFINITIONS:
entry = {
  "rf_code": '1234567' | {'1234567': 'port'},
}
"""

def load(self_entry):
  if not hasattr(self_entry, 'rf_codes'):
    self_entry.rf_codes = {}

def entry_load(self_entry, entry):
  if "rf_code" in entry.definition:
    entry_install(self_entry, entry, entry.definition['rf_code'])

def entry_unload(self_entry, entry):
  if "rf_code" in entry.definition:
    rf_code = entry.definition['rf_code']
    if isinstance(rf_code, dict):
      for c in rf_code:
        del self_entry.rf_codes[c]
    else:
      del self_entry.rf_codes[rf_code]

def entry_install(self_entry, entry, rf_code):
  if isinstance(rf_code, dict):
    for c in rf_code:
      self_entry.rf_codes[c] = (entry.id, rf_code[c])
  else:
    self_entry.rf_codes[rf_code] = (entry.id, '')
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append('rf2mqtt_listener')
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      '@/detected': {
        'description': _('Detects RF signal from {caption} device'),
        'type': 'string',
        'notify': _('Detected RF signal from {caption} device'),
        'notify_if': {
          'js:payload': { 'notify': _('Detected RF signal from {caption} device ({payload})') }
        },
        'events': {
          'connected': 'js:(payload == "" ? { value: true, temporary: true } : { value: true, temporary: true, port: payload })',
          'input': 'js:(payload == "" ? { value: 1, temporary: true } : { value: 1, temporary: true, port: payload })',
        }
      }
    },
  })
  
def rf_rx_callback(self_entry, rfdevice):
  for rf_code in self_entry.rf_codes:
    if str(rfdevice['rx_code']) == str(rf_code):
      entry_id, port = self_entry.rf_codes[rf_code]
      logging.debug("#{id}> found matching code: {rx_code} for {entry_id}/{port} [pulselength {rx_pulselength}, protocol {rx_proto}]".format(id = self_entry.id, entry_id = entry_id, port = port if port != '' else '-', rx_code = str(rfdevice['rx_code']), rx_pulselength = str(rfdevice['rx_pulselength']), rx_proto = str(rfdevice['rx_proto'])))
      entry = system.entry_get(entry_id)
      if entry:
        entry.publish('@/detected', port)
      else:
        logging.error('#{id}> entry {entry_id} not found for rf_code {rf_code}'.format(id = self_entry.id, entry_id = entry_id, rf_code = rf_code))

def on_rf2mqtt_message(entry, subscribed_message):
  rf_rx_callback(entry, subscribed_message.payload)
