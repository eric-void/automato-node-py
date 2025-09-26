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

ikea button: click: on|off | brightness_up|brightness_down (when pressed) | brightness_stop (when released) <-- LEGACY MODE
  When legacy mode is off, you should check the "action" payload: brightness_move_up|brightness_move_down (when pressed) | brightness_stop (when released)
  

received message zigbee2mqtt/xiaomi_aqara_water_1 = b'{"battery":100,"voltage":3055,"linkquality":94,"last_seen":1588074240833,"water_leak":false,"elapsed":3006136}'
"""

from automato.core import system

default_def = { 'output_port:def': ['0'], 'input_port:def': ['0'], 'relay:def': [0, 1], 'input:def': [0, 1] }
device_types = {
  'zigbee': { },
  'zigbee_switch': { },
  'zigbee_temperature': { },
  'zigbee_button': { },
  'zigbee_plug': { },
  'zigbee_vibration': { },
  'zigbee_motion': { },
  'zigbee_presence': { }, # "occupancy": true, "illuminance": 95,
  'zigbee_waterleak': { },
  'zigbee_contact': { }, # "contact": true,
  'zigbee_waterlevel': { }, # "liquid_level_percent", "liquid_depth", "liquid_state" (@see https://www.zigbee2mqtt.io/devices/ME201WZ.html)
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
          # channel: single | double | triple | quadruple | many | long | long_release | hold | hold_release [+ x_duration in ms] - For ikea button brightness_up | brightness_down | brightness_stop
          #   (channel is the 'action' payload, if available. If not it uses the 'click' payload)
          #
          'input': [
            'js:( (typeof payload == "object") && "action" in payload ? { value: 1, temporary: true, channel: payload["action"], "x_duration": "duration" in payload ? payload["duration"] : -1} : ' +
              '( (typeof payload == "object") && "click" in payload ? { value: 1, temporary: true, channel: payload["click"], "x_duration": "duration" in payload ? payload["duration"] : -1} : ' +
              '( (typeof payload == "object") && "water_leak" in payload ? { value: payload["water_leak"] ? 1 : 0, channel: "water-leak" } : ' +
              '( (typeof payload == "occupancy") && "occupancy" in payload ? { value: payload["occupancy"] ? 1 : 0, channel: "occupancy" } : ' +
              '( (typeof payload == "contact") && "contact" in payload ? { value: payload["contact"] ? 1 : 0, channel: "contact" } : ' +
              'null)))))',
            'js:( (typeof payload == "contact") && "contact" in payload ? { value: payload["contact"] ? 0 : 1, channel: "contact-open" } : null)',
          ],
          'input:init': { 'value:def': [0, 1], 'channel:def': ['single', 'double', 'triple', 'quadruple', 'many', 'long', 'water-leak', 'hold', 'release' ], 'duration:def': 'int' },
          'temperature': 'js:((typeof payload == "object") && "temperature" in payload ? { value: payload["temperature"] } : null)',
          'temperature:init': { 'value:unit': '°C' },
          'humidity': 'js:((typeof payload == "object") && "humidity" in payload ? { value: payload["humidity"] } : null)',
          'battery': 'js:((typeof payload == "object") && "battery" in payload ? { value: payload["battery"] } : null)',
          'output': 'js:((typeof payload == "object") && "state" in payload && (payload["state"] == "ON" || payload["state"] == "OFF") ? { value: payload["state"] == "ON" ? 1 : 0 } : null)',
          'water-leak': 'js:((typeof payload == "object") && "water_leak" in payload ? { value: payload["water_leak"] ? 1 : 0 } : null)',
          'vibration': 'js:((typeof payload == "object") && "vibration" in payload ? (payload["vibration"] ? { value: payload["vibration"] ? 1 : 0, temporary: true } : { value: payload["vibration"] ? 1 : 0}) : null)',
          # TODO 'tilt' (x,y,z) {"battery":100,"elapsed":561,"last_seen":1750067147496,"linkquality":32,"sensitivity":"middle","tilt":false,"vibration":true,"x":251,"y":249,"z":199}
          'occupancy': 'js:((typeof payload == "object") && "occupancy" in payload ? { value: payload["occupancy"] ? 1 : 0, temporary: true } : null)',
          'tamper': 'js:((typeof payload == "object") && "tamper" in payload ? { value: payload["tamper"] ? 1 : 0 } : null)',
          'illuminance': 'js:((typeof payload == "object") && "illuminance" in payload ? { value: payload["illuminance"] } : null)',
          'contact': 'js:((typeof payload == "object") && "contact" in payload ? { value: payload["contact"] ? 1 : 0 } : null)',
          'liquid_level_percent': 'js:((typeof payload == "object") && "liquid_level_percent" in payload ? { value: payload["liquid_level_percent"] } : null)',
          'liquid_level_percent:init': { 'value:unit': '%' },
          'liquid_depth': 'js:((typeof payload == "object") && "liquid_depth" in payload ? { value: payload["liquid_depth"] } : null)',
          'liquid_depth:init': { 'value:unit': 'm' },
          'liquid_distance': 'js:((typeof payload == "object") && "liquid_depth" in payload && "installation_height" in payload ? { value:payload["installation_height"] - payload["liquid_depth"] } : null)',
          'liquid_distance:init': { 'value:unit': 'm' },
          'liquid_state': 'js:((typeof payload == "object") && "liquid_state" in payload ? { value: payload["liquid_state"] } : null)',
          'liquid_state:init': { 'value:def': ['low', 'normal', 'high'] },
          'installation_height': 'js:((typeof payload == "object") && "installation_height" in payload ? { value: payload["installation_height"] } : null)',
          'installation_height:init': { 'value:unit': 'm' },
        },
        'check_interval': '6h', # In genere tutti i device che ho mandano almeno 1 notifica all'ora (circa, anche extender e pulsanti), però mi tengo largo e considero 6h [NOTA: In realtà il pulsante ikea manda 1 notifica ogni 24h]
      }
    },
    'subscribe': {
      'command': {
        'topic': 'zigbee2mqtt/' + str(conf["zigbee_id"]) + '/set',
        'response': [ 'zigbee2mqtt/' + str(conf["zigbee_id"]) ],
        'actions': {
          #'output-set': "js:params['value'] ? 'ON' : 'OFF'",
          'output-set': "js:({'state': params['value'] ? 'ON': 'OFF'})",
          'output-set:init': { 'value:def': [0, 1] },
        }
      },
      'state-get': {
        'topic': 'zigbee2mqtt/' + str(conf["zigbee_id"]) + '/get',
        'response': [ 'zigbee2mqtt/' + str(conf["zigbee_id"]) ],
        'actions': {
          'output-get': "js:({'state': ''})",
          'output-get:init': { 'value:def': [0, 1] },
        }
      },
    }
  })
