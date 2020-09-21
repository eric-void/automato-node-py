# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "rf_listener",
        "config": {
          "rf_listener_gpio": -1, # To disable GPIO initialization during tests
        },
        "events_listen": ["*.connected", "*.input"],
      },
      {
        "caption": "RF Device #1",
        "device": "test-rf-1",
        "rf_code": "1234567",
      },
      {
        "caption": "RF Device #2",
        "device": "test-rf-2",
        "rf_code": {"1234568": "port1", "1234569": "port2"},
      },
    ],
  })

def test_run(entries):
  test.assertx('t1', assertSubscribe = {'device/test-rf-1/detected': ''}, assertEventsTopic = 'device/test-rf-1/detected', assertEvents = {'connected': {'value': True, 'temporary': True }, 'input': {'value': 1, 'temporary': True }}, wait = False)
  entries['rf_listener@TEST'].module.rf_rx_callback(entries['rf_listener@TEST'], { "rx_code": "1234567", "rx_pulselength": "0", "rx_proto": "P" })
  test.waitRunning()
  test.assertx('t2', assertSubscribeNotReceive = [ 'device/test-rf-1/detected', 'device/test-rf-2/detected' ], wait = False)
  entries['rf_listener@TEST'].module.rf_rx_callback(entries['rf_listener@TEST'], { "rx_code": "1234566", "rx_pulselength": "0", "rx_proto": "P" })
  test.waitRunning()
  test.assertx('t3', assertSubscribe = {'device/test-rf-2/detected': 'port2'}, assertEventsTopic = 'device/test-rf-2/detected', assertEvents = {'connected': { 'value': True, 'temporary': True, 'port': 'port2' }, 'input': {'value': 1, 'temporary': True, 'port': 'port2'}}, wait = False)
  entries['rf_listener@TEST'].module.rf_rx_callback(entries['rf_listener@TEST'], { "rx_code": "1234569", "rx_pulselength": "0", "rx_proto": "P" })
  test.waitRunning()
