# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test

def test_init():
  test.add_node_config({
    "entries": [
      { "module": "toggle" },
      { "module": "scripting" },
      {
        "device": "test-toggle-device",
        "data": { "status": 0 },
        "publish": {
          "device/toggle-status": {
            "type": "object",
            "events": {
              "output": "js:({value: payload['value'] == 'on' ? 1 : 0})",
              "clock": "js:({value: payload['time']})",
            }
          }
        },
        "subscribe": {
          "device/toggle": {
            "script": ["status = 1 if payload == 'on' else 0"],
            "response": ["device/toggle-status"],
            "publish": ["device/toggle-status"],
            "actions": {
              "output-set": "js:params['value'] ? 'on' : 'off'"
            }
          },
          "device/toggle/get": {
            "response": ["device/toggle-status"],
            "publish": ["device/toggle-status"],
            "actions": {
              "output-get": ""
            }
          },
        },
      },
      
      {
        "item": "test-toggle",
        "caption": "Test toggle",
        "toggle_devices": "test-toggle-device",
        "toggle_detached": False,
        "config": {
          "toggle_defaults": {
            "timer-to-1": 10,
          }
        },
        "events_listen": [".output"],
      },

      {
        "device": "test-toggle-device2",
        "data": { "status": 0 },
        "publish": {
          "/^device2/toggle-status([0-9]+)$/": {
            "type": "object",
            "events": {
              "output": 'js:({value: payload == "ON" ? 1 : 0, port: matches[1] ? matches[1] : "0"})',
            }
          }
        },
        'subscribe': {
          '/^device2/toggle([0-9]*)$/': {
            'type': ['ON', 'OFF'],
            'actions': {
              'output-set': { 'topic': 'js:"device2/toggle" + ("port" in params && params["port"] != "0" ? params["port"] : "")', 'payload': 'js:params["value"] ? "ON" : "OFF"' },
            }
          }
        }
      },
      {
        "item": "test-toggle2",
        "caption": "Test toggle 2",
        "toggle_devices": "test-toggle-device2(params['port'] == '9')",
        "events_listen": [".output"],
      },
      
      {
        "device": "test-toggle-device3",
        "publish": {
          "device3/toggle-status": {
            "type": "object",
            "events": {
              "output": "js:({value: payload['value'] == 'on' ? 1 : 0})",
            }
          }
        },
        "subscribe": {
          "device3/toggle": {
            "response": ["device3/toggle-status"],
            "actions": {
              "output-set": "js:params['value'] ? 'on' : 'off'"
            }
          },
        },
      },
      
      {
        "item": "test-toggle3",
        "caption": "Test toggle",
        "toggle_devices": "test-toggle-device3",
      },
    ],
  })

  # Check that during the init phase, the device status is requested (beacause it supports the "output-get" action)
  # test.assertx('init', assertSubscribe = { 'device/toggle/get': '' }, wait = False)

def test_run(entries):
  test.waitRunning()

  # First device status to initialize the item
  system.broker().publish('device/toggle-status', { 'value': 'off', 'time': system.time() })

  # Test item set
  test.assertPublish('set-on', 'item/test-toggle/set', 1, 
    assertSubscribe = {'device/toggle': 'on'},
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': ('d', system.time() + 10 ), 'defaults': {'timer-to-1': 10} }},
    assertEventsTopic = 'item/test-toggle', assertEvents = { 'output': { 'value': 1, 'timer_to': ('d', system.time() + 10 ) } }
  )
  
  # I need to simulate input button changed to on: so next test could switch if off - if i don't do this, next "device/toggle-status=off" i useless (it's already "off)
  test.assertPublish('device-on', 'device/toggle-status', { 'value': 'on', 'time': system.time() }, 
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': ('d', system.time() + 10 ), 'type': 'toggle'}},
    assertEventsTopic = 'item/test-toggle', assertEvents = { 'output': { 'value': 1, 'timer_to': ('d', system.time() + 10 ) } }
  )
  
  # Test device changing its status (was ON, now i put it OFF), and toggle item should follow
  t = system.time()
  test.assertPublish('device-off', 'device/toggle-status', { 'value': 'off', 'time': t }, 
    #assertEvents = {'output': {'value': 0}, 'clock': {'value': t}}, 
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 0, 'timer-to': 0, 'defaults': {'timer-to-1': 10} }},
    assertEventsTopic = 'item/test-toggle', assertEvents = { 'output': { 'value': 0, 'timer_to': 0 } }
  )
  
  # Test item set via action
  test.assertAction('set-on-action', 'test-toggle', 'output-set', { 'value': 1 },
    assertSubscribe = {'item/test-toggle/set': { 'state': 1 }})
  
  # I need to simulate input button changed to on: so next test could switch if off - if i don't do this, next "device/toggle-status=off" i useless (it's already "off)
  test.assertPublish('device-on2', 'device/toggle-status', { 'value': 'on', 'time': system.time() }, assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': ('d', system.time() + 10 ), 'type': 'toggle'}})
  
  # Test a standard timer
  test.assertPublish('set-off-timer', 'item/test-toggle/set', { 'state': 0, 'timer-to': 1 }, assertSubscribe = {'device/toggle': 'off'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 0, 'timer-to': ('d', system.time() + 1), 'defaults': {'timer-to-1': 10} }})
  test.assertx('set-off-timer-after', assertSubscribe = {'device/toggle': 'on'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0 }})
  
  # Test timer via action
  test.assertAction('set-timer-action', 'test-toggle', 'output-set', { 'value': 0, 'timer_to': 1 },
    assertSubscribe = {'item/test-toggle/set': { 'state': 0, 'timer-to': 1 }, 'device/toggle': 'off'})
  test.assertx('set-timer-action-after', 
    assertSubscribe = {'device/toggle': 'on'},
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0 }})
  
  # Test toggle/invert
  test.assertPublish('invert', 'item/test-toggle/toggle', {}, 
    assertSubscribe = {'device/toggle': 'off'},
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 0, 'timer-to': 0}})
  test.assertAction('invert-action', 'test-toggle', 'output-invert', { 'timer_to': 0 }, 
    assertSubscribe = {'item/test-toggle/toggle': { 'timer-to': 0 }, 'device/toggle': 'on'},
    assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0}})
  
  # Change default timer + get
  system.broker().publish('item/test-toggle/set-defaults', { 'timer-to-1': 1, 'timer-to-0': 1 })
  test.assertPublish('set-defaults', 'item/test-toggle/get', None, assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0, 'defaults': {'timer-to-1': 1, 'timer-to-0': 1} }})
  test.assertPublish('set-off-default-timer', 'item/test-toggle/set', 0, assertSubscribe = {'device/toggle': 'off'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 0, 'timer-to': ('d', system.time() + 1), 'defaults': {'timer-to-1': 1, 'timer-to-0': 1} }})
  test.assertx('set-off-default-timer-after', assertSubscribe = {'device/toggle': 'on'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0 }})
  
  # Test toggle (with default timer setted before)
  test.assertPublish('toggle', 'item/test-toggle/toggle', None, assertSubscribe = {'device/toggle': 'off'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 0, 'timer-to': ('d', system.time() + 1), 'defaults': {'timer-to-1': 1, 'timer-to-0': 1} }})
  test.assertx('toggle-timer-after', assertSubscribe = {'device/toggle': 'on'}, assertSubscribeSomePayload = {'item/test-toggle': {'state': 1, 'timer-to': 0 }})

  # First device status to initialize the item
  test.waitPublish('device2/toggle-status9', 'OFF' )
  
  # Test toggle_devices: "test-toggle-device(port = 1)"
  test.assertPublish('b-set-on', 'item/test-toggle2/set', 1, 
    assertSubscribe = {'device2/toggle9': 'ON'},
    assertSubscribeSomePayload = {'item/test-toggle2': {'state': 1 }},
    assertEventsTopic = 'item/test-toggle2', assertEvents = { 'output': { 'value': 1, 'timer_to': 0 } }
  )
  # TODO Missing ['publish'] directive in device subscribe, so i must publish it to simulate the device status change
  test.assertPublish('b-device-reponse', 'device2/toggle-status9', 'ON',
    assertEvents = { 'output': { 'value': 1, 'port': '9' } }
  )
  test.assertPublish('b-device-on', 'device2/toggle-status9', 'OFF', 
    assertSubscribeSomePayload = {'item/test-toggle2': {'state': 0, 'type': 'toggle'}},
    assertEventsTopic = 'item/test-toggle2', assertEvents = { 'output': { 'value': 0, 'timer_to': 0 } }
    #assertEvents = { 'output': { 'value': 0, 'port': '9' } }
  )
  
  # DEBOUNCE TEST (occour on debounce3)
  
  # First device status to initialize the item
  system.broker().publish('device3/toggle-status', { 'value': 'off' })
  
  test.assertPublish('debounce1', 'item/test-toggle3/set', 1,
    assertSubscribe = {'device3/toggle': 'on'},
    assertSubscribeSomePayload = {'item/test-toggle3': {'state': 1 }}
  )
  test.assertPublish('debounce2', 'item/test-toggle3/set', 0,
    assertSubscribe = {'device3/toggle': 'off'},
    assertSubscribeSomePayload = {'item/test-toggle3': {'state': 0 }}
  )
  
  # If i put a system.sleep() > toggle_debounce_time the bug will occour
  #system.sleep(2)
  
  test.assertPublish('debounce3', 'device3/toggle-status', {'value': 'on'}, 
    assertSubscribeSomePayload = {'item/test-toggle3': {'state': 0 }})
  test.assertPublish('debounce4', 'device3/toggle-status', {'value': 'off'}, 
    assertSubscribeSomePayload = {'item/test-toggle3': {'state': 0 }})
