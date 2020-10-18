# require python3
# -*- coding: utf-8 -*-

"""
Messaggi zigbee:
https://www.zigbee2mqtt.io/information/mqtt_topics_and_message_structure.html
2019-10-22 12:03:39 - received message zigbee2mqtt/bridge/state = b'online'
2019-10-22 12:03:39 - received message zigbee2mqtt/bridge/config = b'{"version":"1.6.0","commit":"e26ad2a","coordinator":20190608,"log_level":"debug","permit_join":true}'

2019-10-22 00:07:09 - received message zigbee2mqtt/0x00158d00039200a1 = b'{"temperature":20.01,"linkquality":86,"humidity":78.12,"battery":80,"voltage":2965}'

2019-09-11 20:52:09 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":0,"click":"single"}'
2019-09-11 23:53:24 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":115,"click":"double"}'
2019-09-11 23:53:11 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":134,"click":"triple"}'
2019-09-11 23:53:22 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":102,"click":"many"}'
2019-09-11 23:53:15 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":94,"click":"quadruple"}'
2019-09-11 20:52:05 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":0,"click":"long"}'
2019-09-11 20:52:05 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":0,"click":"long_release","duration":279}'
2019-09-17 00:59:20 - received message zigbee2mqtt/0x00158d00035cf702 = b'{"linkquality":134,"battery":100,"voltage":3202,"click":"single"}'

Pulsante ikea: click: on|off | brightness_up|brightness_down (quando si tiene premuto) | brightness_stop (quando viene rilasciato)

received message zigbee2mqtt/xiaomi_aqara_water_1 = b'{"battery":100,"voltage":3055,"linkquality":94,"last_seen":1588074240833,"water_leak":false,"elapsed":3006136}'
"""

from automato.core import system

default_def = { 'output_port:def': ['0'], 'input_port:def': ['0'], 'relay:def': [0, 1], 'input:def': [0, 1] }
device_types = {
  'zigbee': { },
  'zigbee_temperature': { },
  'zigbee_button': { },
  'zigbee_plug': { },
}

definition = {
  "install_on": {
    "device_type": ('in', list(device_types.keys())),
    "zigbee_id": (),
  },
  'config': {
  }
}
  
def entry_install(installer_entry, entry, conf):
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      'status': {
        'topic': 'zigbee2mqtt/' + str(conf["zigbee_id"]),
        'description': _('Data received by zigbee device {caption}'),
        'notify': _('Data received by zigbee device {caption} is: {{payload}}').format(caption = entry.definition['caption']),
        #'notify_level': 'debug',
        'events': {
          # channel: single | double | triple | quadruple | many | long | long_release [+ x_duration in ms]
          'input': 'js:((typeof payload == "object") && "click" in payload ? { value: 1, temporary: true, channel: payload["click"], "x_duration": "duration" in payload ? payload["duration"] : -1} : ' +
            '((typeof payload == "object") && "water_leak" in payload ? { value: payload["water_leak"] ? 1 : 0, channel: "water-leak" } : null))',
          'input:init': { 'value:def': [0, 1], 'channel:def': ['single', 'double', 'triple', 'quadruple', 'many', 'long', 'water-leak' ], 'duration:def': 'int' },
          'temperature': 'js:((typeof payload == "object") && "temperature" in payload ? { value: payload["temperature"] } : null)',
          'temperature:init': { 'value:unit': '°C' },
          'humidity': 'js:((typeof payload == "object") && "humidity" in payload ? { value: payload["humidity"] } : null)',
          'battery': 'js:((typeof payload == "object") && "battery" in payload ? { value: payload["battery"] } : null)',
          'output': 'js:((typeof payload == "object") && "state" in payload && (payload["state"] == "ON" || payload["state"] == "OFF") ? { value: payload["state"] == "ON" ? 1 : 0 } : null)',
          'water-leak': 'js:((typeof payload == "object") && "water_leak" in payload ? { value: payload["water_leak"] ? 1 : 0 } : null)',
        },
        'check_interval': '6h', # In genere tutti i device che ho ora mandano almeno 1 notifica all'ora (circa, anche extender e pulsanti), però mi tengo largo e considero 6h [NOTA: In realtà il pulsante ikea manda 1 notifica ogni 24h]
      }
    },
    'subscribe': {
      'command': {
        'topic': 'zigbee2mqtt/' + str(conf["zigbee_id"]) + '/set',
        'response': [ 'zigbee2mqtt/' + str(conf["zigbee_id"]) ],
        'actions': {
          'output-set': "js:params['value'] ? 'ON' : 'OFF'",
          'output-set:init': { 'value:def': [0, 1] },
        }
      }
    }
  })
