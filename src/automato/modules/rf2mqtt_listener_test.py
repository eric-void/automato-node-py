# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "rf2mqtt_listener",
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
  test.assertPublish('t1', 'rf2mqtt', { "rx_code": 1234567, "rx_pulselength": "0", "rx_code_timestamp": 3708306975498, "rx_proto": "P" }, assertSubscribe = {'device/test-rf-1/detected': ''}, assertEventsTopic = 'device/test-rf-1/detected', assertEvents = {'connected': {'value': True, 'temporary': True }, 'input': {'value': 1, 'temporary': True }})
  test.assertPublish('t2', 'rf2mqtt', { "rx_code": 1234566, "rx_pulselength": "0", "rx_code_timestamp": 3708306975498, "rx_proto": "P" }, assertSubscribeNotReceive = [ 'device/test-rf-1/detected', 'device/test-rf-2/detected' ])
  test.assertPublish('t3', 'rf2mqtt', { "rx_code": 1234569, "rx_pulselength": "0", "rx_code_timestamp": 3708306975498, "rx_proto": "P" }, assertSubscribe = {'device/test-rf-2/detected': 'port2'}, assertEventsTopic = 'device/test-rf-2/detected', assertEvents = {'connected': { 'value': True, 'temporary': True, 'port': 'port2' }, 'input': {'value': 1, 'temporary': True, 'port': 'port2'}})
