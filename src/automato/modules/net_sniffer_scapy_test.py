# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "net_sniffer_scapy",
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
  test.assertx('t1', assertSubscribe = {'device/device1/connected': ''}, assertEventsTopic = 'device/device1/connected', assertEvents = {'connected': {'value': True }}, wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '01:02:03:04:05')
  test.waitRunning()
  test.assertx('t2', assertSubscribe = {'device/device2/detected': ''}, assertEventsTopic = 'device/device2/detected', assertEvents = {'connected': {'value': True, 'temporary': True }}, wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '0A:0B:0C:0D:0E')
  test.waitRunning()
  # Test disconnection by timeout (connection_time)
  test.assertx('t3', assertSubscribe = {'device/device1/disconnected': ''}, assertEventsTopic = 'device/device1/disconnected', assertEvents = {'connected': {'value': False }}, timeoutms = 6000)
  # Test "momentary_flood_time"
  test.assertx('t4', assertSubscribeNotReceive = {'device/device2/detected': ''}, wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '0A:0B:0C:0D:0E')
  test.waitRunning()
