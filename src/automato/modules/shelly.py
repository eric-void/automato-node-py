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

default_def = { 'relay_name': 'relay', 'output_port:def': ['0'], 'input_port:def': ['0'], 'relay:def': [0, 1], 'input:def': [0, 1] }
device_types = {
  'shelly': { },
  'shelly1': { },
  'shelly1pm': { },
  'shelly2': { 'output_port:def': ['0', '1'], 'input_port:def': ['0', '1'] },
  'shellyswitch': { 'output_port:def': ['0', '1'], 'input_port:def': ['0', '1'] },
  'shellyswitch25': { 'output_port:def': ['0', '1'], 'input_port:def': ['0', '1'] },
  'shellydimmer': { 'relay_name': 'light' }, # TODO Non ha relay, ma per ora mi serve perchè anche lui definisce publish['output'] - che si potrebbe togliere
  'shellydimmer2': { 'relay_name': 'light' },
  'shellyem': { 'emeter_port:def': ['0', '1'], 'input:def': None },
  'shellyem3': { 'emeter_port:def': ['0', '1', '2'], 'input:def': None },
  #TODO shellies/shellydimmer2-E09806966EFB/light/0/status	{"ison":true,"has_timer":false,"timer_started":0,"timer_duration":0,"timer_remaining":0,"mode":"white","brightness":41}
}

definition = {
  "install_on": {
    "device_type": ('in', list(device_types.keys())),
    "/^shelly_(.*)$/": (),
  }
}

def entry_install(installer_entry, entry, conf):
  device_type = conf['device_type'] if 'device_type' in conf else 'shelly'
  if device_type == 'shelly2':
    device_type = 'shellyswitch'
  t = {x: y for x, y in { **default_def, **device_types[device_type] }.items() if y is not None}
  base_topic = 'shellies/' + device_type + '-' + conf['id'] + '/'
  # @see https://shelly-api-docs.shelly.cloud/#mqtt-support http://shelly-api-docs.shelly.cloud/#shelly1-mqtt http://shelly-api-docs.shelly.cloud/#shelly2-mqtt
  definition_extra = { 'publish': {}, 'subscribe': {}}
  
  definition_extra['publish']['default'] = { 'topic': base_topic + '#' }
  definition_extra['publish']['output'] = {
    'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)$/',
    'description': _('Current output status of the relay'),
    'type': [ 'on', 'off', 'overpower' ],
    'payload': {
      'payload': {
        'off': { 'caption': 'off' },
        'on': { 'caption': 'ON' },
        'overpower': { 'caption': 'off (OVERPOWER)' }, # TODO Gestire
      },
    },
    'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} state is: {_[payload!caption]}"),
    'events': {
      'output': 'js:payload == "on" ? ({value: 1, port: matches[1]}) : (payload == "off" || payload == "overpower" ? ({value: 0, port: matches[1]}) : false)',
      'output:init': {'port:def': t['output_port:def'], 'value:def': t['relay:def']},
    },
    'check_interval': '1m',
  }
  if t['relay_name'] == 'light': # Used by dinner
    definition_extra['publish']['output-status'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/status$/',
      'description': _('Current full output status of the relay'),
      'type': 'object',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} full state is: {payload}"),
      'events': {
        'output': 'js:({value: payload["ison"] ? 1 : 0, intensity: payload["brightness"], port: matches[1]})',
        'output:init': {'port:def': t['output_port:def'], 'value:def': t['relay:def'], 'intensity:def': 'int', 'intensity:def:limits': [1, 100] },
      },
    }
  if 'input:def' in t:
    definition_extra['publish']['input'] = {
      'topic': '/^' + base_topic + 'input/([0-9]+)$/',
      'description': _('Status of the input pin of the device'),
      'type': 'int',
      'payload': {
        'payload': {
          0: { 'caption': 'off' },
          1: { 'caption': 'ON' },
        },
      },
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' input #{matches[1]} state is: {_[payload!caption]}"),
      'events': {
        'input': 'js:({value: parseInt(payload), port: matches[1], channel: "singlepush"})',
        'input:init': {'port:def': t['input_port:def'], 'value:def': t['input:def'], 'channel:def': ['singlepush', 'longpush']},
      }
    }
    definition_extra['publish']['longpush'] = {
      'topic': '/^' + base_topic + 'longpush/([0-9]+)$/',
      'description': _('Detects if input pin of the device is in longpush state'),
      'type': 'int',
      'payload': {
        'payload': {
          0: { 'caption': 'off' },
          1: { 'caption': 'ON' },
        },
      },
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' input #{matches[1]} longpush state is: {_[payload!caption]}"),
      'events': {
        'input': 'js:({value: parseInt(payload), port: matches[1], channel: "longpush"})',
        'input:init': {'port:def': t['input_port:def'], 'value:def': t['input:def'], 'channel:def': ['singlepush', 'longpush']},
      }
    }
  if not 'emeter_port:def' in t:
    definition_extra['publish']['power'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/(([0-9]+)/)?power$/', # shellyswitch usare "relay/power" e non "relay/X/power". In questo caso lo assegno alla porta "0"
      'description': _('Power consumption of the device in watts'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} power consumption is: {_[payload]}W"),
      'events': {
        'energy': 'js:({power: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
        'energy:init': {'power:def': 'float', 'power:unit': 'W', 'port:def': t['output_port:def']},
      }
    }
    definition_extra['publish']['energy'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/(([0-9]+)/)?energy$/',
      'description': _('Energy consumed by the device in watt*min'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} energy consumed is: {_[payload]}Wmin"),
      'events': {
        'energy': 'js:({energy: parseFloat(payload) / 60000, energy_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
        'energy:init': {'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wmin'},
      }
    }
  else:
    definition_extra['publish']['power'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?power$/', # shellyswitch usare "relay/power" e non "relay/X/power". In questo caso lo assegno alla porta "0"
      'description': _('Instantaneous active power in Watts'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' emeter #{matches[1]} power detected is: {_[payload]}W"),
      'events': {
        'energy': 'js:({power: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
        'energy:init': {'power:def': 'float', 'power:unit': 'W', 'port:def': t['output_port:def']},
      }
    }
    definition_extra['publish']['total'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?total/',
      'description': _('Total energy in Wh'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' emeter #{matches[1]} energy detected is: {_[payload]}Wh"),
      'events': {
        'energy': 'js:({energy: parseFloat(payload) / 1000, energy_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
        'energy:init': {'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wh'},
      }
    }
    definition_extra['publish']['total_returned'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?total_returned/',
      'description': _('Total energy returned to the grid in Wh'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} returned energy detected is: {_[payload]}Wh"),
      'events': {
        'energy': 'js:({energy_returned: parseFloat(payload) / 1000, energy_returned_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
        'energy:init': {'energy_returned:def': 'float', 'energy_returned:unit': 'kWh', 'energy_returned_reported:def': 'float', 'energy_returned_reported:unit': 'Wh'},
      }
    }

  definition_extra['publish']['lwt'] = {
    'topic': '/^' + base_topic + 'online$/',
    'description': _('Connection status of the device (LWT)'),
    'type': ['true', 'false'],
    'payload': {
      'payload': {
        'true': { 'caption': 'online' },
        'false': { 'caption': 'OFFLINE' },
      },
    },
    'notify_level': 'debug', 'notify': _("Shelly device '{caption}' is: {_[payload|caption]}W"),
    'events': {
      'connected': 'js:({value: payload == "true"})',
    }
  }
  
  definition_extra['subscribe']['output-set'] = {
    'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/command$/',
    'type': ['on', 'off'],
    'response': [ base_topic + t['relay_name'] + '/{matches[1]}' ],
    'actions': {
      'output-set': { 'topic': 'js:"' + base_topic + 'relay/" + ("port" in params ? params["port"] : "0") + "/command"', 'payload': 'js:params["value"] ? "on" : "off"' },
      'output-set:init': { 'port:def': t['output_port:def'], 'value:def': t['relay:def'] },
    }
  } if t['relay_name'] != 'light' else {
    'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/set$/',
    'type': 'object',
    'response': [ base_topic + t['relay_name'] + '/{matches[1]}/status' ],
    'actions': {
      'output-set': { 
        'topic': 'js:"' + base_topic + t['relay_name'] + '/" + ("port" in params ? params["port"] : "0") + "/set"', 
        'payload': 'js:let payload = {}; if ("value" in params) payload.turn = params["value"] ? "on" : "off"; if ("intensity" in params) payload.brightness = params["intensity"]; payload'
      },
      'output-set:init': { 'port:def': t['output_port:def'], 'value:def': t['relay:def'], 'intensity:def': 'int', 'intensity:def:limits': [1, 100] },
    }
  }

  system.entry_definition_add_default(entry, definition_extra);

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

