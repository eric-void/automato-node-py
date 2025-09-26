# require python3
# -*- coding: utf-8 -*-

"""
Room assistant integration to detect BLE (Bluetooth Low Energy) devices
@see https://www.room-assistant.io

Supported messages:

- room-assistant/entity/[INSTANCE]/device-tracker/ble-[BLE_ID]-tracker = b'{"entity":{"attributes":{},"id":"ble-[BLE_ID]-tracker","name":"[NAME]","distributed":true,"stateLocked":true,"state":"not_home"},"diff":[{"path":"/state","oldValue":"home","newValue":"not_home"}],"hasAuthority":true}'
- room-assistant/entity/[INSTANCE]/bluetooth-low-energy-presence-sensor/ble-[BLE_ID] = b'{"entity":{"attributes":{"lastUpdatedAt":"2025-03-12T17:59:17.823Z"},"id":"ble-[BLE_ID]","name":"[NAME]","distributed":true,"stateLocked":true,"distances":{"zigbee":{"lastUpdatedAt":"2025-03-12T17:57:28.612Z","distance":1.9,"outOfRange":false}},"timeout":60,"measuredValues":{"zigbee":{"rssi":-64.56242362478892,"measuredPower":-59}},"state":"not_home"},"diff":[{"path":"/state","oldValue":"zigbee","newValue":"not_home"},{"path":"/attributes/distance","oldValue":1.9},{"path":"/attributes/lastUpdatedAt","oldValue":"2025-03-12T17:57:28.612Z","newValue":"2025-03-12T17:59:17.823Z"}],"hasAuthority":true}'

Generates "connected[value=1]" event if payload["entity"]["state"] is one of config["connected_state"] and "connected[value=0]"  event if payload["entity"]["state"] is one of config["disconnected_states"]
"""

import logging
import json
from automato.core import system

definition = {
  "install_on": {
    "room_assistant_instance": (),
    "ble_id": (),
  },
  "config": {
    "connected_states": ["home"],
    "disconnected_states": ["not_home"],
  }
}

def entry_install(installer_entry, entry, conf):
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  #logging.debug('#DEBUG> ' + str(installer_entry.config))
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      'status': {
        'topic': '/^room-assistant/entity/' + str(conf["room_assistant_instance"]) + '/(device-tracker|bluetooth-low-energy-presence-sensor)/ble-' + str(conf["ble_id"]) + '(-tracker)?$/',
        'description': _('Data received by BLE/room-assistant device {caption}'),
        'notify': _('Data received by BLE/room-assistant device {caption} is: {{payload}}').format(caption = entry.definition['caption']),
        #'notify_level': 'debug',
        'events': {
          'connected' : 'js:((typeof payload == "object") && "entity" in payload && "state" in payload["entity"] && (' + json.dumps(installer_entry.config["connected_states"]) + '.indexOf(payload["entity"]["state"]) >= 0 || ' + json.dumps(installer_entry.config["disconnected_states"]) + '.indexOf(payload["entity"]["state"]) >= 0) ? {"value": ' + json.dumps(installer_entry.config["connected_states"]) + '.indexOf(payload["entity"]["state"]) >= 0 ? 1 : 0 } : null)',
        },
      }
    },
  })
