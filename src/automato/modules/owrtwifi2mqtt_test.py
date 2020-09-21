# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "owrtwifi2mqtt",
        "config": {
          "momentary_flood_time": 30,
          "connection_time": 5,
        },
        "events_listen": ["*.connected"],
      },
      {
        "caption": "Device1",
        "device": "device1",
        "mac_address": "01:02:03:04:05",
      },
      {
        "caption": "Device2",
        "device": "device2",
        "mac_address": "0A:0B:0C:0D:0E",
        "net_connection_momentary": True,
      },
    ]
  }) 

def test_run(entries):
  test.assertPublish('t1', 'owrtwifi/status/mac-01-02-03-04-05/lastseen/epoch', 1576164173, assertSubscribe = {'device/device1/connected': ''}, assertEventsTopic = 'device/device1/connected', assertEvents = {'connected': {'value': True }})
  test.assertPublish('t2', 'owrtwifi/status/mac-0A-0B-0C-0D-0E/lastseen/iso8601', '2019-12-12T16:22:53+0100', assertSubscribe = {'device/device2/detected': ''}, assertEventsTopic = 'device/device2/detected', assertEvents = {'connected': {'value': True, 'temporary': True }})
  # Test disconnection by timeout (connection_time)
  test.assertx('t3', assertSubscribe = {'device/device1/disconnected': ''}, assertEventsTopic = 'device/device1/disconnected', assertEvents = {'connected': {'value': False }}, timeoutms = 5000)
  # Test "momentary_flood_time"
  test.assertPublish('t4', 'owrtwifi/status/mac-0A-0B-0C-0D-0E/lastseen/iso8601', '2019-12-12T16:22:53+0100', assertSubscribeNotReceive = {'device/device2/detected': ''})
 
