# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system
from automato.node import node_system as node

def test_init():
  global t0
  t0 = system.time()
  test.add_node_config({
    "entries": [
      { "module": "nodes", "config": { "master": True, "compress": False } },
      { "module": "scripting" },
      {
        "device": "light1",
        "publish": {
          "@/status": {
            "type": "int",
            "events": {
              "output": "js:({value: payload})",
            }
          }
        },
        "subscribe": {
          "@/set": {
            "actions": {
              "output-set": "js:params['value']"
            },
          }
        },
        "on": {
          "otherbutton1@OTHERNODE.input": {
            "do": "light1.output-set",
            #"script": [ "entry.do('output-set', params)" ] # Alternativa via script
          },
          "light1.output": {
            "do": ["otherlight2@OTHERNODE.output-set"],
            #"script": [ "do('otherlight2@OTHERNODE', 'output-set', params)" ] # Alternativa via script
          }
        }
      }
    ]
  })
  # Devo mettere qui un...

def test_run(entries):
  global t0
  
  # TODO Mi tocca farlo perchè "test" non avvia system.run()
  node.entries_invoke_threaded('start')
  system.sleep(1)
  
  other_node_config = {
    "name": "OTHERNODE",
    "entries": [
      { "id": "nodes", "module": "nodes", "config": { "compress": False }},
      {
        "id": "otherbutton1", "device": "otherbutton1",
        "publish": {
          "device/otherbutton1/input": {
            "type": "int",
            "events": { "input": "js:({value: payload})" }
          }
        },
      },
      {
        "id": "otherlight2", "device": "otherlight2",
        "publish": {
          "device/otherlight2/status": {
            "type": "int",
            "events": { "output": "js:({value: payload})" }
          }
        },
        "subscribe": {
          "device/otherlight2/turnon": {
            "actions": {
              "output-set": "js:params['value']"
            },
          }
        },
      },
    ]
  }

  system.default_node_name = other_node_config["name"]
  entries_exportable = {}
  for definition in other_node_config["entries"]:
    entry = system.Entry(definition["id"] + "@" + other_node_config["name"], definition, system.config)
    if entry.type != 'module':
      entry.definition_exportable = system._entry_definition_exportable(entry.definition)
      entries_exportable[entry.id] = entry.definition_exportable
  system.default_node_name = "TEST"

  t1 = system.time()
  metadata = {
    'from_node': other_node_config['name'],
    'time': t1,
    'nodes': {other_node_config['name']: { 'description': '', 'time': t1}},
    'entries': entries_exportable
  }
  test.assertx('t1', 
    waitPublish = [('automato/metadata', metadata)],
    assertSubscribe = {'automato/metadata': {
      "from_node": "TEST",
      "time": ('d', t1),
      "nodes": {"TEST": {"description": "", "time": ('d', t0, 5) }, "OTHERNODE": {"description": "", "time": ('d', t1)}},
      'entries': {
        'nodes@TEST': ('*', ), 'scripting@TEST': ('*', ),
        'light1@TEST': {'publish': {'device/light1/status': {'type': 'int', 'events': {'output': 'js:({value: payload})'}}}, 'subscribe': {'device/light1/set': {'actions': {'output-set': "js:params['value']"}}}, 'type': 'device'},
        'otherbutton1@OTHERNODE': {'publish': {'device/otherbutton1/input': {'type': 'int', 'events': {'input': 'js:({value: payload})'}}}, 'type': 'device', 'subscribe': {}}, 
        'otherlight2@OTHERNODE': {'publish': {'device/otherlight2/status': {'type': 'int', 'events': {'output': 'js:({value: payload})'}}}, 'subscribe': {'device/otherlight2/turnon': {'actions': {'output-set': "js:params['value']"}}}, 'type': 'device'}}
    }})
  
  t1 = system.time()
  test.assertPublish('t2', 'device/otherbutton1/input', 1,
    assertEvents = {"input": { "value": '1' }},
    assertSubscribe = { 'device/light1/set': '1' }
  )
  
  test.assertPublish('t3', 'device/light1/status', 2,
    assertEvents = {"output": { "value": '2' }},
    assertSubscribe = { 'device/otherlight2/turnon': '2' }
  )
  
  t2 = system.time()
  test.assertPublish('t4', 'automato/data/get', '',
    assertSubscribe = { 'automato/data': {
      "from_node": "TEST", 
      "time": ('d', t2),
      "entries": {
        "nodes@TEST": ('*', ), "scripting@TEST": ('*', ),  "light1@TEST": ('*', ), 
        "otherbutton1@OTHERNODE": ('*', ), "otherlight2@OTHERNODE": ('*', )
      },
      "events": {
        "nodes@TEST": {}, 
        "scripting@TEST": {}, 
        "light1@TEST": {"output": {"{}": {"name": "output", "time": ('d', t1), "params": {"value": "2"}, "changed_params": {"value": "2"}, "keys": {}}}}, 
        "otherbutton1@OTHERNODE": {"input": {"{}": {"name": "input", "time": ('d', t1), "params": {"value": "1"}, "changed_params": {"value": "1"}, "keys": {}}}}, 
        "otherlight2@OTHERNODE": {"output": {}}
      },
      "last_seen": ()
    }}
  )
