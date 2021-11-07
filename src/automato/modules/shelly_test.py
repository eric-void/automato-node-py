# require python3
# -*- coding: utf-8 -*-

from automato.core import test

def test_init():
  test.add_node_config({
    "entries": [
      { "module": "toggle" },
      { "module": "shelly" },
      {
        "device": "shelly-test",
        "device_type": "shelly2",
        "shelly_id": "XXXXXX",

        "events_listen": [".output", ".input", ".connected", ".temperature", ".humidity", ".energy", ".clock"],
        "events": { "energy:group": 0 }, # Disable event grouping for simple testing
      },
      {
        "caption": "Toggle test",
        "item": "toggle-test",
        "entry_topic": "home/toggle-test",
        "toggle_devices": "shelly-test",
      },
      {
        "device": "shellydimmer-test",
        "device_type": "shellydimmer",
        "shelly_id": "YYYYYY",

        "events_listen": [".output", ".input", ".connected", ".temperature", ".humidity", ".energy", ".clock"],
        "events": { "energy:group": 0 }, # Disable event grouping for simple testing
      },
    ],
  })

def test_run(entries):
  test.assertPublish('get_on', 'shellies/shellyswitch-XXXXXX/relay/1', 'on', assertEvents = {'output': {'value': 1, 'port': '1', 'port:def': ['0', '1'], 'value:def': [0, 1]}})
  test.assertPublish('get_off', 'shellies/shellyswitch-XXXXXX/relay/1', 'off', assertEvents = {'output': {'value': 0, 'port': '1', 'port:def': ['0', '1'], 'value:def': [0, 1]}})
  test.assertAction('set_on', 'shelly-test', 'output-set', {'value': 1}, assertSubscribe = {'shellies/shellyswitch-XXXXXX/relay/0/command': 'on'})
  test.assertAction('set_off', 'shelly-test', 'output-set', {'value': 0, 'port': '1'}, assertSubscribe = {'shellies/shellyswitch-XXXXXX/relay/1/command': 'off'})
  test.assertPublish('get_input_on', 'shellies/shellyswitch-XXXXXX/input/0', '1', assertEvents = {'input': {'value': 1, 'port': '0', 'channel': 'singlepush', 'port:def': ['0', '1'], 'value:def': [0, 1], 'channel:def': ['singlepush', 'longpush']}})
  test.assertPublish('get_power', 'shellies/shellyswitch-XXXXXX/relay/1/power', '3.5', assertEvents = {'energy': {'power': 3.5, 'port': '1', 'port:def': ['0', '1'], 'power:def': 'float', 'power:unit': 'W', 'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wmin'}})
  test.assertPublish('get_power2', 'shellies/shellyswitch-XXXXXX/relay/1/energy', '6000', assertEvents = {'energy': {'power': 3.5, 'energy': 0.1, 'energy_reported': 6000, 'port': '1', 'port:def': ['0', '1'], 'power:def': 'float', 'power:unit': 'W', 'energy:def': 'float', 'energy:unit': 'kWh', 'energy_reported:def': 'float', 'energy_reported:unit': 'Wmin'}})
  test.assertPublish('lwt_online', 'shellies/shellyswitch-XXXXXX/online', 'true', assertEvents = {'connected': { 'value': True }})
  test.assertPublish('lwt_offline', 'shellies/shellyswitch-XXXXXX/online', 'false', assertEvents = {'connected': { 'value': False }})
  test.assertPublish('input', 'shellies/shellyswitch-XXXXXX/input/0', '1', 
    assertEvents = {'input': {'value': 1, 'port': '0', 'channel': 'singlepush', 'port:def': ['0', '1'], 'value:def': [0, 1], 'channel:def': ['singlepush', 'longpush']}},
    assertNotification = [ "debug", "Shelly device 'shelly-test' input #0 state is: ON" ],
  )
  
  # Check "debounce" di toggle, faccio un primo set a ON (con relativo feedback da device) di inizializzazione, poi simulo un set veloce OFF/ON, con il primo feedback che arriva dopo
  # NOTA: in caso di problemi va in errore solo "debounce5"
  test.assertAction('debounce1', 'toggle-test', 'output-set', {'value': 1}, assertSubscribe = {'shellies/shellyswitch-XXXXXX/relay/0/command': 'on'})
  test.assertPublish('debounce2', 'shellies/shellyswitch-XXXXXX/relay/0', 'on', assertSubscribeNotReceive = [ 'shellies/shellyswitch-XXXXXX/relay/0/command' ])
  test.assertAction('debounce3', 'toggle-test', 'output-set', {'value': 0}, assertSubscribe = {'shellies/shellyswitch-XXXXXX/relay/0/command': 'off'})
  test.assertAction('debounce4', 'toggle-test', 'output-set', {'value': 1}, assertSubscribe = {'shellies/shellyswitch-XXXXXX/relay/0/command': 'on'})
  test.assertPublish('debounce5', 'shellies/shellyswitch-XXXXXX/relay/0', 'off', assertSubscribeNotReceive = [ 'shellies/shellyswitch-XXXXXX/relay/0/command' ])
  
  # Check shellydimmer
  test.assertPublish('dget_on', 'shellies/shellydimmer-YYYYYY/light/0', 'off', assertEvents = {'output': {'value': 0, 'port': '0', 'port:def': ['0'], 'value:def': [0, 1], 'intensity:def': 'int', 'intensity:def:limits': [1,100]}})
  test.assertPublish('dget_on2', 'shellies/shellydimmer-YYYYYY/light/0/status', {"ison": False, "has_timer": False, "timer_started": 0, "timer_duration": 0, "timer_remaining": 0, "mode": "white", "brightness": 50}, assertEvents = {'output': {'value': 0, 'port': '0', 'intensity': 50, 'port:def': ['0'], 'value:def': [0, 1], 'intensity:def': 'int', 'intensity:def:limits': [1,100] }})
  test.assertAction('dset_on', 'shellydimmer-test', 'output-set', {'value': 1 }, assertSubscribe = {'shellies/shellydimmer-YYYYYY/light/0/set': {"turn": "on"}})
  test.assertAction('dset_on2', 'shellydimmer-test', 'output-set', {'intensity': 100 }, assertSubscribe = {'shellies/shellydimmer-YYYYYY/light/0/set': {"brightness": 100}})
  test.assertAction('dset_on3', 'shellydimmer-test', 'output-set', {'value': 0, 'intensity': 0 }, assertSubscribe = {'shellies/shellydimmer-YYYYYY/light/0/set': {"turn": "off", "brightness": 0}})
