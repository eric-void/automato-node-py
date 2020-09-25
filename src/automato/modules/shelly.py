# require python3
# -*- coding: utf-8 -*-

# TODO
# - Roller mode
# - overpower


"""
{
  "device": "name",
  "device_type": "shelly1",
  "shelly_id": "xxxxxx",
}
"""

from automato.core import system

definition = {
  "install_on": {
    "device_type": ('in', ['shelly1', 'shelly1pm', 'shelly2', 'shellyswitch', 'shellyswitch25', 'shellydimmer', 'shellydimmer2' ]),
    "/^shelly_(.*)$/": (),
  }
}

def entry_install(installer_entry, entry, conf):
  device_type = conf['device_type'] if 'device_type' in conf else 'shelly'
  if device_type == 'shelly2':
    device_type = 'shellyswitch'
  base_topic = 'shellies/' + device_type + '-' + conf['id'] + '/'
  # @see http://shelly-api-docs.shelly.cloud/#mqtt-support http://shelly-api-docs.shelly.cloud/#shelly1-mqtt http://shelly-api-docs.shelly.cloud/#shelly2-mqtt
  system.entry_definition_add_default(entry, {
    'publish': {
      'default': { 'topic': base_topic + '#' },
      
      'output': {
        'topic': '/^' + base_topic + 'relay/([0-9]+)$/',
        'description': _('Current output status of the relay'),
        'type': [ 'on', 'off', 'overpower' ],
        'payload': {
          'payload': {
            'off': { 'caption': 'off' },
            'on': { 'caption': 'ON' },
            'overpower': { 'caption': 'OVER POWER' }, # TODO Gestire
          },
        },
        'notify': _("Shelly device '{caption}' relay #{matches[1]} state is: {_[payload!caption]}"),
        'notify_level': 'debug',
        'events': {
          'output': 'js:payload == "on" ? ({value: 1, port: matches[1]}) : (payload == "off" ? ({value: 0, port: matches[1]}) : false)',
        },
        'check_interval': '1m',
      },
      'input': {
        'topic': '/^' + base_topic + 'input/([0-9]+)$/',
        'description': _('Status of the input pin of the device'),
        'type': 'int',
        'payload': {
          'payload': {
            0: { 'caption': 'off' },
            1: { 'caption': 'ON' },
          },
        },
        'notify': _("Shelly device '{caption}' input #{matches[1]} state is: {_[payload!caption]}"),
        'notify_level': 'debug',
        'events': {
          'input': 'js:({value: parseInt(payload), port: matches[1], channel: "singlepush"})',
        }
      },
      'longpush': {
        'topic': '/^' + base_topic + 'longpush/([0-9]+)$/',
        'description': _('Detects if input pin of the device is in longpush state'),
        'type': 'int',
        'payload': {
          'payload': {
            0: { 'caption': 'off' },
            1: { 'caption': 'ON' },
          },
        },
        'notify': _("Shelly device '{caption}' input #{matches[1]} longpush state is: {_[payload!caption]}"),
        'notify_level': 'debug',
        'events': {
          'input': 'js:({value: parseInt(payload), port: matches[1], channel: "longpush"})',
        }
      },
      'power': {
        'topic': '/^' + base_topic + 'relay/([0-9]+)/power$/',
        'description': _('Power consumption of the device in watts'),
        'type': 'float',
        'notify': _("Shelly device '{caption}' relay #{matches[1]} power consumption is: {_[payload]}W"),
        'notify_level': 'debug',
        'events': {
          'energy': 'js:({power: parseFloat(payload), power_unit: "W", port: matches[1]})',
        }
      },
      'energy': {
        'topic': '/^' + base_topic + 'relay/([0-9]+)/energy$/',
        'description': _('Energy consumed by the device in watt*min'),
        'type': 'float',
        'notify': _("Shelly device '{caption}' relay #{matches[1]} energy consumed is: {_[payload]}Wmin"),
        'notify_level': 'debug',
        'events': {
          'energy': 'js:({energy: parseFloat(payload) / 60000, energy_unit: "kWh", energy_reported: parseFloat(payload), energy_reported_unit: "Wmin", port: matches[1]})',
        }
      },
      'lwt': {
        'topic': '/^' + base_topic + 'online$/',
        'description': _('Connection status of the device (LWT)'),
        'type': ['true', 'false'],
        'payload': {
          'payload': {
            'true': { 'caption': 'online' },
            'false': { 'caption': 'OFFLINE' },
          },
        },
        'notify': _("Shelly device '{caption}' is: {_[payload|caption]}W"),
        'notify_level': 'debug',
        'events': {
          'connected': 'js:({value: payload == "true"})',
        }
      }
    },
    'subscribe': {
      'output-set': {
        'topic': '/^' + base_topic + 'relay/([0-9]+)/command$/',
        'type': ['on', 'off'],
        'response': [ base_topic + 'relay/{matches[1]}' ],
        'actions': {
          'output-set': { 'topic': 'js:"' + base_topic + 'relay/" + ("port" in params ? params["port"] : "0") + "/command"', 'payload': 'js:params["value"] ? "on" : "off"' },
        }
      }
    }
  })
  """
  *2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/input_event/1 {"event":"","event_cnt":0}
  2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/loaderror 0
  2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/overload  0
  *2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/overtemperature 0
  *2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/temperature_f 111.83
  *2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/temperature 44.35
  2020-08-20 15:16:34 shellies/shellydimmer2-E09806966EFB/light/0/status  {"ison":false,"has_timer":false,"timer_started":0,"timer_duration":0,"timer_remaining":0,"mode":"white","brightness":5}
  2020-08-20 15:16:33 shellies/shellydimmer2-E09806966EFB/light/0 off
  2020-08-20 15:16:33 shellies/shellydimmer2-E09806966EFB/announce  {"id":"shellydimmer2-E09806966EFB","model":"SHDM-2","mac":"E09806966EFB","ip":"192.168.2.229","new_fw":false,"fw_ver":"20200818-121046/v1.8.2@36539b0b"}
  *2020-08-20 15:16:33 shellies/announce {"id":"shellydimmer2-E09806966EFB","model":"SHDM-2","mac":"E09806966EFB","ip":"192.168.2.229","new_fw":false,"fw_ver":"20200818-121046/v1.8.2@36539b0b"}
  """

