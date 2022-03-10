# require python3
# -*- coding: utf-8 -*-

# TODO
# - Gen2: switch energy stats (apower, voltage, current...) https://shelly-api-docs.shelly.cloud/gen2/Components/FunctionalComponents/Switch
# - Gen2: toggle timer_to via Switch.Set(toggle_after) https://shelly-api-docs.shelly.cloud/gen2/Components/FunctionalComponents/Switch#switchset
# - Gen2: error management (overtemp, overpower, overvoltage)

"""
{
  "device": "name",
  "device_type": "shelly1",
  "shelly_id": "xxxxxx",
}

NOTE: For generation 2 devices mqtt settings must enable RPC style messages (status messages can be turned off)
"""

from automato.core import system

default_def = { 'relay_name': 'relay', 'output_port:def': ['0'], 'input_port:def': ['0'], 'relay:def': [0, 1], 'input:def': [0, 1] }
device_types = {
  # Gen1 devices https://shelly-api-docs.shelly.cloud/gen1/
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
  
  # Gen2 devices https://shelly-api-docs.shelly.cloud/gen2/
  'shellyplus1': { 'gen': 2, 'components': { 'input:0': 'input', 'switch:0': 'switch' } },
  'shellypro2': { 'gen': 2, 'components': { 'input:0': 'input', 'input:1': 'input', 'switch:0': 'switch', 'switch:1': 'switch' } },
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
  
  gen = device_types[device_type]['gen'] if 'gen' in device_types[device_type] else 1
  
  if gen == 2:
    return entry_install_gen2(installer_entry, entry, conf, device_type, device_types[device_type])
  
  t = {x: y for x, y in { **default_def, **device_types[device_type] }.items() if y is not None}
  base_topic = 'shellies/' + device_type + '-' + conf['id'] + '/'
  # @see https://shelly-api-docs.shelly.cloud/#mqtt-support http://shelly-api-docs.shelly.cloud/#shelly1-mqtt http://shelly-api-docs.shelly.cloud/#shelly2-mqtt
  definition_extra = { 'publish': {}, 'subscribe': {}, 'events': {}, "actions": {}}
  
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
    },
    'check_interval': '1m',
  }
  definition_extra['events']['output:init'] = {'port:def': t['output_port:def'], 'value:def': t['relay:def']}
  if t['relay_name'] == 'light': # Used by dinner
    definition_extra['publish']['output-status'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/status$/',
      'description': _('Current full output status of the relay'),
      'type': 'object',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} full state is: {payload}"),
      'events': {
        'output': 'js:({value: payload["ison"] ? 1 : 0, intensity: payload["brightness"], port: matches[1]})',
      },
    }
    definition_extra['events']['output:init'] = {'port:def': t['output_port:def'], 'value:def': t['relay:def'], 'intensity:def': 'int', 'intensity:def:limits': [1, 100] }

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
      }
    }
    definition_extra['events']['input:init'] = {'port:def': t['input_port:def'], 'value:def': t['input:def'], 'channel:def': ['singlepush', 'longpush']}

  if not 'emeter_port:def' in t:
    definition_extra['publish']['power'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/(([0-9]+)/)?power$/', # shellyswitch usare "relay/power" e non "relay/X/power". In questo caso lo assegno alla porta "0"
      'description': _('Power consumption of the device in watts'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} power consumption is: {_[payload]}W"),
      'events': {
        'energy': 'js:({power: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
      }
    }
    definition_extra['publish']['energy'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/(([0-9]+)/)?energy$/',
      'description': _('Energy consumed by the device in watt*min'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} energy consumed is: {_[payload]}Wmin"),
      'events': {
        'energy': 'js:({energy: parseFloat(payload) / 60000, energy_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
      }
    }
    definition_extra['events']['energy:init'] = {'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wmin', 'power:def': 'float', 'power:unit': 'W', 'port:def': t['output_port:def']}
    definition_extra['events']['energy:group'] = 1
  else:
    definition_extra['publish']['power'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?power$/', # shellyswitch usare "relay/power" e non "relay/X/power". In questo caso lo assegno alla porta "0"
      'description': _('Instantaneous active power in Watts'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' emeter #{matches[1]} power detected is: {_[payload]}W"),
      'events': {
        'energy': 'js:({power: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
      }
    }
    definition_extra['publish']['total'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?total$/',
      'description': _('Total energy in Wh'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' emeter #{matches[1]} energy detected is: {_[payload]}Wh"),
      'events': {
        'energy': 'js:({energy: parseFloat(payload) / 1000, energy_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
      }
    }
    definition_extra['publish']['total_returned'] = {
      'topic': '/^' + base_topic + 'emeter/(([0-9]+)/)?total_returned$/',
      'description': _('Total energy returned to the grid in Wh'),
      'type': 'float',
      'notify_level': 'debug', 'notify': _("Shelly device '{caption}' relay #{matches[1]} returned energy detected is: {_[payload]}Wh"),
      'events': {
        'energy': 'js:({energy_returned: parseFloat(payload) / 1000, energy_returned_reported: parseFloat(payload), port: matches[1] ? matches[2] : "0"})',
      }
    }
    definition_extra['events']['energy:init'] = {'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wh', 'energy_returned:def': 'float', 'energy_returned:unit': 'kWh', 'energy_returned_reported:def': 'float', 'energy_returned_reported:unit': 'Wh', 'power:def': 'float', 'power:unit': 'W', 'port:def': t['output_port:def']}
    definition_extra['events']['energy:group'] = 1

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
    'notify_level': 'debug', 'notify': _("Shelly device '{caption}' is: {_[payload|caption]}"),
    'events': {
      'connected': 'js:({value: payload == "true"})',
    }
  }
  
  if t['relay_name'] != 'light':
    definition_extra['subscribe']['output-set'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/command$/',
      'type': ['on', 'off'],
      'response': [ base_topic + t['relay_name'] + '/{matches[1]}' ],
      'actions': {
        'output-set': { 'topic': 'js:"' + base_topic + 'relay/" + ("port" in params ? params["port"] : "0") + "/command"', 'payload': 'js:params["value"] ? "on" : "off"' },
      }
    }
    definition_extra['actions']['output-set:init'] = { 'port:def': t['output_port:def'], 'value:def': t['relay:def'] }
  else:
    definition_extra['subscribe']['output-set'] = {
      'topic': '/^' + base_topic + t['relay_name'] + '/([0-9]+)/set$/',
      'type': 'object',
      'response': [ base_topic + t['relay_name'] + '/{matches[1]}/status' ],
      'actions': {
        'output-set': { 
          'topic': 'js:"' + base_topic + t['relay_name'] + '/" + ("port" in params ? params["port"] : "0") + "/set"', 
          'payload': 'jsf:let payload = {}; if ("value" in params) payload.turn = params["value"] ? "on" : "off"; if ("intensity" in params) payload.brightness = params["intensity"]; return payload'
        },
      }
    }
    definition_extra['actions']['output-set:init'] = { 'port:def': t['output_port:def'], 'value:def': t['relay:def'], 'intensity:def': 'int', 'intensity:def:limits': [1, 100] }

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

def entry_install_gen2(installer_entry, entry, conf, device_type, device_conf):
  
  #t = {x: y for x, y in { **default_def, **device_types[device_type] }.items() if y is not None}
  base_topic = device_type + '-' + conf['id']

  definition_extra = { 'publish': {}, 'subscribe': {}, 'events': {}, "actions": {}}
  ports = {'output': [], 'input': []}
  
  definition_extra['publish']['lwt'] = {
    'topic': base_topic + '/online',
    'description': _('Connection status of the device (LWT)'),
    'type': ['true', 'false'],
    'payload': {
      'payload': {
        'true': { 'caption': 'online' },
        'false': { 'caption': 'OFFLINE' },
      },
    },
    'notify_level': 'debug', 'notify': _("Shelly device '{caption}' is: {_[payload|caption]}"),
    'events': {
      'connected': 'js:({value: payload == "true"})',
    }
  }
  
  for component in device_conf['components']:
    d = component.find(":")
    component_id = int(component[d + 1:]) if d > 0 else 0
    
    # https://shelly-api-docs.shelly.cloud/gen2/Components/FunctionalComponents/Switch
    if device_conf['components'][component] == 'switch':
      ports['output'].append(component_id)

      # method Switch.Set, ex: shellyplus1-a8032abc7158/rpc = {"id": "test1", "src":"shellyplus1-a8032abc7158/response", "method":"Switch.Set", "params":{"id":0,"on":true}}
      definition_extra['subscribe']['switch_' + str(component_id) + '_set'] = {
        'topic': base_topic + "/rpc[js:payload['method'] == 'Switch.Set' && payload['params']['id'] == " + str(component_id) + "]",
        'description': _('Switch set'),
        'type': 'object',
        'response': [
          # ex: shellyplus1-a8032abc7158/response/rpc = {"id":"test1","src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/response","result":{"was_on":false}}
          # TODO i should check payload[id]
          base_topic + '/response/rpc[js:payload["result"]["id"] == ' + str(component_id) + ' && "was_on" in payload["result"]]',
          # ex: shellyplus1-a8032abc7158/events/rpc = {"src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/events","method":"NotifyStatus","params":{"ts":1646738883.91,"switch:0":{"id":0,"output":true,"source":"MQTT"}}}
          base_topic + "/events/rpc[js:payload['method'] == 'NotifyStatus' && '" + component + "' in payload['params'] && 'output' in payload['params']['" + component + "'] ]",
        ],
        'actions': {
          'output-set': {
            'topic': base_topic + '/rpc',
            'payload': 'js:params["port"] == ' + str(component_id) + ' ? ({"id": uniqid(), "src":"' + base_topic + '/response", "method":"Switch.Set", "params":{"id": ' + str(component_id) + ',"on": params["value"] ? true : false } }) : null',
          }
        }
      }
      
      # Notification of switch status: usually sent after a Switch.Set method, or via external sources ("source": "MQTT" | "WS_in" (web interface) | "switch" (physical switch))
      # ex: shellyplus1-a8032abc7158/events/rpc = {"src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/events","method":"NotifyStatus","params":{"ts":1646738883.91,"switch:0":{"id":0,"output":true,"source":"MQTT"}}}
      definition_extra['publish']['switch_' + str(component_id) + '_status'] = {
        'topic': base_topic + "/events/rpc[js:payload['method'] == 'NotifyStatus' && '" + component + "' in payload['params'] && 'output' in payload['params']['" + component + "'] ]",
        'description': _('Switch status notification'),
        'type': 'object',
        'notify_level': 'debug', 'notify': _("Shelly device '{caption}' " + component + " state is: {payload[params][" + component + "][output]}"),
        'events': {
          'output': 'js:({ value: payload["params"]["' + component + '"]["output"] ? 1 : 0, port: ' + str(component_id) + '})',
          'clock': 'js:({ value: parseInt(payload["params"]["ts"]) })',
        },
      }

      # method Switch.GetStatus, ex: shellyplus1-a8032abc7158/rpc = {"id": "test1", "src":"shellyplus1-a8032abc7158/response", "method":"Switch.GetStatus", "params":{"id":0,"on":true}}
      definition_extra['subscribe']['switch_' + str(component_id) + '_get'] = {
        'topic': base_topic + "/rpc[js:payload['method'] == 'Switch.GetStatus' && payload['params']['id'] == " + str(component_id) + "]",
        'description': _('Switch get status'),
        'type': 'object',
        'response': [
          # ex: shellyplus1-a8032abc7158/response/rpc = b'{"id":"test1","src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/response","result":{"id":0, "source":"MQTT", "output":true,"temperature":{"tC":56.5, "tF":133.8}}}
          # TODO i should check payload[id]
          base_topic + '/response/rpc[js:payload["result"]["id"] == ' + str(component_id) + ' && "output" in payload["result"]]',
        ],
        'actions': {
          'output-get': {
            'topic': base_topic + '/rpc',
            'payload': 'js:params["port"] == ' + str(component_id) + ' ? ({"id": uniqid(), "src":"' + base_topic + '/response", "method":"Switch.GetStatus", "params":{"id": ' + str(component_id) + '} }) : null',
          }
        }
      }

      # Response with switch status: usually sent after a Switch.GetStatus method
      # ex: shellyplus1-a8032abc7158/response/rpc = b'{"id":"test1","src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/response","result":{"id":0, "source":"MQTT", "output":true,"temperature":{"tC":56.5, "tF":133.8}}}
      definition_extra['publish']['switch_' + str(component_id) + '_status_response'] = {
        'topic': base_topic + '/response/rpc[js:payload["result"]["id"] == ' + str(component_id) + ' && "output" in payload["result"]]',
        'description': _('Switch status response'),
        'type': 'object',
        'notify_level': 'debug', 'notify': _("Shelly device '{caption}' " + component + " state is: {payload[result][output]}"),
        'events': {
          'output': 'js:({ value: payload["result"]["output"] ? 1 : 0, port: ' + str(component_id) + '})',
          'temperature': 'js:("temperature" in payload["result"] ? { value: payload["result"]["temperature"]["tC"] } : null)',
        },
      }
      
    elif device_conf['components'][component] == 'input':
      ports['input'].append(component_id)
      
      # Notification of input status: used when input type = 'switch'
      # ex: shellyplus1-a8032abc7158/events/rpc = b'{"src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/events","method":"NotifyStatus","params":{"ts":1646946181.62,"input:0":{"id":0,"state":false}}}'
      definition_extra['publish']['input_' + str(component_id) + '_status'] = {
        'topic': base_topic + "/events/rpc[js:payload['method'] == 'NotifyStatus' && '" + component + "' in payload['params'] && 'state' in payload['params']['" + component + "'] ]",
        'description': _('Input status notification'),
        'type': 'object',
        'notify_level': 'debug', 'notify': _("Shelly device '{caption}' " + component + " state is: {payload[params][" + component + "][state]}"),
        'events': {
          'input': 'js:({ value: payload["params"]["' + component + '"]["state"] ? 1 : 0, port: ' + str(component_id) + '})',
          'clock': 'js:({ value: parseInt(payload["params"]["ts"]) })',
        },
      }
        
      # Notification of input events: used when input type = 'button'. Event can be single_push, long_push, double_push, btn_down (ignored), btn_up (ignored)
      # @see https://shelly-api-docs.shelly.cloud/gen2/Components/FunctionalComponents/Input/#notifications
      # ex: shellyplus1-a8032abc7158/events/rpc = b'{"src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/events","method":"NotifyEvent","params":{"ts":1646945882.47,"events":[{"component":"input:0", "id":0, "event":"double_push", "ts":1646945882.47}]}}'
      definition_extra['publish']['input_' + str(component_id) + '_event'] = {
        'topic': base_topic + "/events/rpc[js:payload['method'] == 'NotifyEvent' && payload['params']['events'][0]['component'] == '" + component + "']",
        'description': _('Input event notification'),
        'type': 'object',
        'notify_level': 'debug', 'notify': _("Shelly device '{caption}' " + component + " event: {payload[params][events][0][event]}"),
        'events': {
          'input': 'js:(["single_push", "double_push", "long_push"].indexOf(payload["params"]["events"][0]["event"]) > -1 ? { value: 1, port: ' + str(component_id) + ', temporary: true, channel: payload["params"]["events"][0]["event"] == "single_push" ? "singlepush" : (payload["params"]["events"][0]["event"] == "double_push" ? "doublepush" : "longpush")} : null)',
          'clock': 'js:({ value: parseInt(payload["params"]["ts"]) })',
        },
      }
        
      # method Input.GetStatus
      # ex: shellyplus1-a8032abc7158/rpc = b'{"id": 0, "src":"shellyplus1-a8032abc7158/response", "method": "Input.GetStatus", "params": {"id": 0}}'
      definition_extra['subscribe']['input_' + str(component_id) + '_get'] = {
        'topic': base_topic + "/rpc[js:payload['method'] == 'Input.GetStatus' && payload['params']['id'] == " + str(component_id) + "]",
        'description': _('Input get status'),
        'type': 'object',
        'response': [
          # TODO i should check payload[id]
          base_topic + '/response/rpc[js:payload["result"]["id"] == ' + str(component_id) + ' && "state" in payload["result"]]',
        ],
        'actions': {
          'input-get': {
            'topic': base_topic + '/rpc',
            'payload': 'js:params["port"] == ' + str(component_id) + ' ? ({"id": uniqid(), "src":"' + base_topic + '/response", "method":"Input.GetStatus", "params":{"id": ' + str(component_id) + '} }) : null',
          }
        }
      }

      # Response with input status (NOTE: for input of type button, state returned is null, we decode it as "value: 0")
      # ex: shellyplus1-a8032abc7158/response/rpc = b'{"id":0,"src":"shellyplus1-a8032abc7158","dst":"shellyplus1-a8032abc7158/response","result":{"id":0,"state":false}}'
      definition_extra['publish']['input_' + str(component_id) + '_status_response'] = {
        'topic': base_topic + '/response/rpc[js:payload["result"]["id"] == ' + str(component_id) + ' && "state" in payload["result"]]',
        'description': _('Input status response'),
        'type': 'object',
        'notify_level': 'debug', 'notify': _("Shelly device '{caption}' " + component + " state is: {payload[result][state]}"),
        'events': {
          'input': 'js:({ value: payload["result"]["state"] ? 1 : 0, port: ' + str(component_id) + '})',
        },
      }
  
  definition_extra['events'] = {}
  definition_extra['actions'] = {}
  if ports['output']:
    definition_extra['events']['output:init'] = {'value:def': [0, 1], 'port:def': ports['output']}
    definition_extra['actions']['output-set:init'] = {'value:def': [0, 1], 'port:def': ports['output']}
    definition_extra['actions']['output-get:init'] = {'port:def': ports['output']}
  if ports['input']:
    definition_extra['events']['input:init'] = {'value:def': [0, 1], 'port:def': ports['input'], 'channel:def': ['singlepush', 'doublepush', 'longpush']}
    definition_extra['actions']['input-get:init'] = {'port:def': ports['input']}
  
  #print(str(definition_extra))
  system.entry_definition_add_default(entry, definition_extra);
