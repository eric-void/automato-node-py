# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system
from automato.node import node_system

def test_init():
  test.add_node_config({
    "listen_all_events": True,
    "entries": [
      {
        "module": "net",
        "config": {
          "wan-connected-check-method": "http", # "ping" to use linux shell command ping, or "http" for a http head connection
        },
        "events_listen": ["*.connected"],
        "publish": {
          './wan-connected': {
            "run_interval": 1,
          }
        },
      },
    ]
  })

def test_run(entries):
  test.assertx('t1-http', assertSubscribe = {'net/wan-connected': '1'}, assertEvents = {'connected': {'value': 1, 'port': 'wan'}}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  entries['net@TEST'].config["wan-connected-check-method"] = "ping"
  test.assertx('t2-ping', assertSubscribe = {'net/wan-connected': '1'}, assertEvents = {'connected': {'value': 1, 'port': 'wan'}}, wait = False)
  system.sleep(1)
  node_system.run_step()
  test.waitRunning()
