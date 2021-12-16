# require python3
# -*- coding: utf-8 -*-

# @see https://github.com/arendst/Sonoff-Tasmota/wiki/JSON-Status-Responses
# @see https://github.com/arendst/Sonoff-Tasmota/wiki/Commands

# TODO
# - longpress

"""
{
  "device": "name",
  "device_type": "tasmota",
  "tasmota_id": "xxxxxx",
}
"""

from automato.core import system

default_def = { 'output_port:def': ['0'], 'input_port:def': ['0'], 'relay:def': [0, 1], 'input:def': [0, 1] }
device_types = {
  'tasmota': { },
  'tasmota_dual': { 'output_port:def': ['0', '1'], 'input_port:def': ['0', '1'] },
  'tasmota_sonoff': { },
  'tasmota_sonoff_basic': { },
  'tasmota_sonoff_dual': { 'output_port:def': ['0', '1', '2'], 'input_port:def': ['0', '1', '2', '3'] },
  'tasmota_sonoff_dualr2': { 'output_port:def': ['0', '1', '2'], 'input_port:def': ['0', '1', '2', '3'] },
  'tasmota_sonoff_pow': { },
  'tasmota_sonoff_powr2': { },
}

definition = {
  "install_on": {
    "device_type": ('in', list(device_types.keys())),
    "/^tasmota_(.*)$/": (),
  },
  
  'config': {
    # @see https://github.com/arendst/Sonoff-Tasmota/wiki/MQTT-Features
    "tasmota-fulltopic": "%prefix%/%topic%/",
    "tasmota-prefix1": 'cmnd',
    "tasmota-prefix2": 'stat',
    "tasmota-prefix3": 'tele',
    "update_period_check": "10m", # TODO di base mandano ogni 5minuti (@see teleperiod)
  }
}

def entry_install(installer_entry, entry, conf):
  device_type = conf['device_type'] if 'device_type' in conf else 'tasmota'
  t = {x: y for x, y in { **default_def, **device_types[device_type] }.items() if y is not None}
  topic_cmd = installer_entry.config['tasmota-fulltopic'].replace('%prefix%', installer_entry.config['tasmota-prefix1']).replace('%topic%', conf['id'])
  topic_stat = installer_entry.config['tasmota-fulltopic'].replace('%prefix%', installer_entry.config['tasmota-prefix2']).replace('%topic%', conf['id'])
  topic_tele = installer_entry.config['tasmota-fulltopic'].replace('%prefix%', installer_entry.config['tasmota-prefix3']).replace('%topic%', conf['id'])
  
  system.entry_definition_add_default(entry, {
    'publish': {
      topic_stat + '/#': {},
      topic_tele + '/#': {},

      'power': {
        'topic': '/^' + topic_stat + 'POWER([0-9]*)$/',
        'description': _("Tasmota device {caption} has changed power toggle state"),
        'type': [ 'ON', 'OFF' ],
        'notify': _("Tasmota device '{caption}' toggle state: {payload}"),
        'notify_level': 'debug',
        'events': {
          'output': 'js:({value: payload == "ON" ? 1 : 0, port: matches[1] ? matches[1] : "0"})',
          'output:init': {'port:def': t['output_port:def'], 'value:def': t['relay:def']},
        }
      },
      'result': {
        'topic': '/^' + topic_stat + "RESULT([0-9]*)$/",
        # Es: stat/sonoff6/RESULT  {"POWER":"ON"}
        'description': _("Tasmota device {caption} command result"),
        'type': 'object',
        'notify': _("Tasmota device '{caption}' result for last command executed: {payload}"),
        'notify_level': 'debug',
      },
      'state': {
        # Es: tele/sonoff3/STATE {"Time":"2018-12-13T18:45:58", "Uptime":220, "Vcc":3.260, "POWER":"OFF", "Wifi":{"AP":1, "SSID":"TANELORN", "RSSI":80, "APMac":"30:B5:C2:4F:D1:16"}}
        # {"Time":"2018-12-13T18:45:13","Uptime":"9T04:16:23","Vcc":3.244,"POWER1":"ON","Wifi":{"AP":1,"SSId":"TANELORN","BSSId":"30:B5:C2:4F:D1:16","Channel":1,"RSSI":62}}
        'topic': topic_tele + "STATE",
        'description': _("Tasmota device {caption} connection status"),
        'type': 'object',
        'notify': _("Tasmota device '{caption}' is connected to: {payload[Wifi][SSID!'']}{payload[Wifi][SSId!'']} ({payload[Wifi][RSSI]}%), uptime: {payload[Uptime]}"),
        'notify_level': 'debug',
        'events': {
          'clock': 'js:({value: t(payload["Time"])})',
          'stats': 'js:(payload)', # TODO Decodificare
          'output': [
            'js: "POWER" in payload ? { value: payload["POWER"] == "ON" ? 1 : 0, port: "0" } : null',
            'js: "POWER1" in payload ? { value: payload["POWER1"] == "ON" ? 1 : 0, port: "1" } : null',
            'js: "POWER2" in payload ? { value: payload["POWER2"] == "ON" ? 1 : 0, port: "2" } : null',
            'js: "POWER3" in payload ? { value: payload["POWER3"] == "ON" ? 1 : 0, port: "3" } : null',
            'js: "POWER4" in payload ? { value: payload["POWER4"] == "ON" ? 1 : 0, port: "4" } : null',
          ],
        },
        'check_interval': '5m',
      },
      'sensor': {
        # Es: stat/sonoff6/STATUS8  {"StatusSNS":{"Time":"2018-12-03T13:48:08","SI7021":{"Temperature":17.7,"Humidity":51.2},"TempUnit":"C"}}
        # Es: tele/sonoff3/SENSOR {"Time":"2019-05-10T12:39:28","SI7021":{"Temperature":17.6,"Humidity":63.7},"TempUnit":"C"}
        # Es: tele/sonoff6/SENSOR {"Time":"2019-05-10T12:37:01","BME280":{"Temperature":16.6,"Humidity":63.9,"Pressure":1001.8},"PressureUnit":"hPa","TempUnit":"C"}
        # Es: tele/sonoffpow/SENSOR {"Time":"2018-12-03T13:45:20","ENERGY":{"TotalStartTime":"2018-11-20T00:00:51","Total":0.10263,"Yesterday":0.00114,"Today":0.00070,"Period":0,"Power":0,"ApparentPower":0,"ReactivePower":0,"Factor":0.00,"Voltage":234,"Current":0.000}}
        # Es: stat/sonoff4/STATUS8  {"StatusSNS":{"Time":"2019-10-22T10:08:16"}} su notify_if
        'topic': '/^(' + topic_tele + '|' + topic_stat + ')(SENSOR|STATUS8)$/',
        'description': _("Tasmota device {caption} temperature measurement"),
        'type': 'object',
        'notify': _("Tasmota device '{caption}' reports sensor {payload[SensorType]} data: {payload[Data]}"),
        'notify_level': 'debug',
        'payload_transform': 'jsf:if ("StatusSNS" in payload) payload = payload["StatusSNS"]; payload["Data"] = {}; for (k in payload) { if (payload[k] && k != "Data" && is_dict(payload[k])) { for (x in payload[k]) payload["Data"][x] = payload[k][x]; payload["SensorType"] = k } }; return payload',
        #'_payload_transform': 'js:payload',
        'events': {
          'temperature': 'js:"Temperature" in payload["Data"] && "TempUnit" in payload ? { "value": parseFloat(payload["Data"]["Temperature"]), "value:unit": "°" + payload["TempUnit"] } : null',
          'humidity': 'js:"Humidity" in payload["Data"] ? { "value": parseFloat(payload["Data"]["Humidity"]) } : null',
          'pressure': 'js:"Pressure" in payload["Data"] && "PressureUnit" in payload ? { "value": parseFloat(payload["Data"]["Pressure"]), "value:unit": payload["PressureUnit"] } : null',
          'energy': 'js:payload["SensorType"] == "ENERGY" ? {"power": payload["Data"]["Power"], "power_reactive": payload["Data"]["ReactivePower"], "power_apparent": payload["Data"]["ApparentPower"], "power_factor": payload["Data"]["Factor"], "energy_today": payload["Data"]["Today"], "energy_yesterday": payload["Data"]["Yesterday"], "energy_total": is_array(payload["Data"]["Total"]) ? payload["Data"]["Total"][0] : payload["Data"]["Total"], "total_starttime": t(payload["Data"]["TotalStartTime"]), "total_duration": t(payload["Time"]) - t(payload["Data"]["TotalStartTime"]), "voltage": payload["Data"]["Voltage"], "current": payload["Data"]["Current"] } : null',
          'energy:init': { "power:unit": "W", "energy:unit": "kWh", "current:unit": "A", "voltage:unit": "V" },
          'clock': 'js:({value: t(payload["Time"])})',
        },
      },
      'lwt': {
        # Es: tele/sonoff6/LWT  Online
        'topic': topic_tele + "LWT",
        'description': _("Tells if the tasmota device {caption} is connected"),
        'type': [ 'Online', 'Offline' ],
        'notify': _("Tasmota device '{caption}' is {payload}"),
        'notify_level': 'debug',
        'events': {
          'connected': 'js:({value: payload == "Online"})',
        }
      },
      # Only for GPIO configured as buttons, with "SetOption73 1" (only for Tasmota v8.3.0+)
      # see https://tasmota.github.io/docs/Buttons-and-Switches/#button and https://tasmota.github.io/docs/Commands/#setoption73
      'button': {
        'topic': "/^" + topic_stat + "BUTTON([0-9]*)$/",
        'description': _("Tasmota device {caption} button status"),
        'type': 'object',
        'notify': _("Tasmota device '{caption}' button status detected: {payload[ACTION]}"),
        'notify_level': 'info',
        'events': {
          'input': 'js:({value: 1, port: matches[1] ? matches[1] : "0", temporary: true, channel: payload["ACTION"]})', # channel = SINGLE|DOUBLE|TRIPLE|QUAD|PENTA|HOLD
          'input:init': {'port:def': t['input_port:def'], 'value:def': t['input:def'], 'channel:def': ['SINGLE', 'DOUBLE', 'TRIPLE', 'QUAD', 'PENTA', 'HOLD']},
        }
      },
      # Not supported by standard tasmota install, but available with this rule:
      # For button: "Rule1 on Button1#state do Publish stat/XXX/INPUT1 %value% endon"
      # For switches: "Rule1 on Switch1#state do Publish stat/XXX/INPUT1 %value% endon"
      # "Rule1 1"
      # See https://tasmota.github.io/docs/Rules/ and https://tasmota.github.io/docs/Buttons-and-Switches/
      # NOTE: You can detach (or "decouple") the button also using SwitchTopic|ButtonTopic xxx, but that way is limited and fallbacks to standard usage (input connected to relay) if broker is not available. So we prefer using the rule method.
      'input': {
        'topic': "/^" + topic_stat + "INPUT([0-9]*)$/",
        'description': _("Tasmota device {caption} input"),
        'type': 'string',
        'notify': _("Tasmota device '{caption}' input detected: {payload}"),
        'notify_level': 'info',
        'events': {
          # For switches values are: OFF|ON|TOGGLE|HOLD|INC_DEC|INV|CLEAR, for buttons: OFF|ON|TOGGLE|HOLD
          'input': 'js:({value: payload == "ON" ? 1 : (payload == "OFF" ? 0 : payload), port: matches[1] ? matches[1] : "0", channel: payload == "ON" || payload == "OFF" ? "" : payload, temporary: payload == "ON" || payload == "OFF"})'
        }
      },
      # TODO
      # Es: stat/sonoff6/STATUS {"Status":{"Module":1,"FriendlyName":"Sonoff6","Topic":"sonoff6","ButtonTopic":"0","Power":1,"PowerOnState":3,"LedState":1,"SaveData":1,"SaveState":1,"ButtonRetain":0,"PowerRetain":0}}
      # Es: stat/sonoffpow/STATUS {"Status":{"Module":6,"FriendlyName":["SonoffPow"],"Topic":"sonoffpow","ButtonTopic":"0","Power":1,"PowerOnState":3,"LedState":1,"SaveData":1,"SaveState":1,"SwitchTopic":"0","SwitchMode":[0,0,0,0,0,0,0,0],"ButtonRetain":0,"SwitchRetain":0,"SensorRetain":0,"PowerRetain":0}}
      # Es: stat/sonoff3/STATUS10 {"StatusSNS":{"Time":"2018-12-03T13:48:09", "Switch1":"ON"}}
    },
    'subscribe': {
      'output-set': {
        'topic': '/^' + topic_cmd + 'POWER([0-9]*)$/[ON|OFF]', # WARN After a reboot the device sends a cmd/XXX/POWER with an empty payload, and NO response is sent. Health module will consider that a failure, and for that reason i must specify [ON|OFF] (to consider only these values)
        'type': ['ON', 'OFF'],
        'response': [ topic_stat + 'RESULT' ],
        # NOTA SU RESPONSE su un sonoff basic e dual (notare lo stat/sonoff3/POWER1 invece di stat/sonoff3/POWER) - Da documentazione "XXX" = "XXX1"
        # > cmnd/sonoff3/POWER	ON
        # < stat/sonoff3/RESULT	{"POWER1":"ON"}
        # < stat/sonoff3/POWER1	ON
        # > cmnd/sonoff8/POWER2	ON
        # < stat/sonoff8/RESULT	{"POWER2":"ON"}
        # < stat/sonoff8/POWER2	ON
        'actions': {
          'output-set': { 'topic': 'js:"' + topic_cmd + 'POWER" + ("port" in params && params["port"] != "0" ? params["port"] : "")', 'payload': 'js:params["value"] ? "ON" : "OFF"' },
          'output-set:init': { 'port:def': t['output_port:def'], 'value:def': t['relay:def'] },
        }
      },
      'output-get': {
        'topic': '/^' + topic_cmd + 'POWER([0-9]*)$/[]', # WARN this describes the request for output status, but for the reason above i specify NO response
        'type': '',
        'actions': {
          'output-get': { 'topic': 'js:"' + topic_cmd + 'POWER" + ("port" in params && params["port"] != "0" ? params["port"] : "")', 'payload': 'js:""' },
          'output-get:init': { 'port:def': t['output_port:def'] },
        }
      }
    }
  })
