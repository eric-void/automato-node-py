# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "net_sniffer_iw",
        "config": {
          "momentary_flood_time": 30,
          "connection_time": 5,
        },
        "events_listen": ["*.connected"],
      },
      {
        "caption": "Device1",
        "device": "device1",
        "mac_address": "01:02:03:04:05:06",
      },
      {
        "caption": "Device2",
        "device": "device2",
        "mac_address": "0A:0B:0C:0D:0E:0F",
        "net_connection_momentary": True,
      },
    ]
  }) 

def test_run(entries):
  test.assertx('t1', assertSubscribe = {'device/device1/connected': {'mac_address': '01:02:03:04:05:06'}}, assertEventsTopic = 'device/device1/connected', assertEvents = {'connected': {'value': True, 'ip_address': None, 'mac_address': '01:02:03:04:05:06' }}, wait = False)
  entries['net_sniffer_iw@TEST'].module._iwevent_process_line(entries['net_sniffer_iw@TEST'], 'new station 01:02:03:04:05:06')
  test.waitRunning()
  test.assertx('t2', assertSubscribe = {'device/device2/detected': {'mac_address': '0A:0B:0C:0D:0E:0F'}}, assertEventsTopic = 'device/device2/detected', assertEvents = {'connected': {'value': True, 'temporary': True, 'ip_address': None, 'mac_address': '0A:0B:0C:0D:0E:0F' }}, wait = False)
  entries['net_sniffer_iw@TEST'].module._iwevent_process_line(entries['net_sniffer_iw@TEST'], 'new station 0A:0B:0C:0D:0E:0F')
  test.waitRunning()
  # Test disconnection by timeout (connection_time)
  test.assertx('t3', assertSubscribe = {'device/device1/disconnected': ''}, assertEventsTopic = 'device/device1/disconnected', assertEvents = {'connected': {'value': False }}, timeoutms = 5000)
  # Test "momentary_flood_time"
  test.assertx('t4', assertSubscribeNotReceive = {'device/device2/detected': ''}, wait = False)
  entries['net_sniffer_iw@TEST'].module._iwevent_process_line(entries['net_sniffer_iw@TEST'], 'new station 0A:0B:0C:0D:0E:0F')
  test.waitRunning()
  
  x = entries['net_sniffer_iw@TEST'].module._arp_process_line("192.168.1.199    0x1         0x0         01:02:03:04:05:06     *        br-lan")
  test.assertx('t5', assertEq = [(x, ['01:02:03:04:05:06', '192.168.1.199'])])
  env = { 'arp_list': {x[0]: x[1]} }
  
  test.assertx('t6', assertSubscribe = {'device/device1/connected': {'mac_address': '01:02:03:04:05:06', 'ip_address': '192.168.1.199'}}, assertEventsTopic = 'device/device1/connected', assertEvents = {'connected': {'value': True, 'ip_address': '192.168.1.199', 'mac_address': '01:02:03:04:05:06' }}, wait = False)
  entries['net_sniffer_iw@TEST'].module.mac_address_detected(entries['net_sniffer_iw@TEST'], env, '01:02:03:04:05:06')
  test.waitRunning()
  test.assertx('t7', assertSubscribe = {'device/device1/disconnected': {'mac_address': '01:02:03:04:05:06'}}, assertEventsTopic = 'device/device1/disconnected', assertEvents = {'connected': {'value': False, }}, wait = False)
  entries['net_sniffer_iw@TEST'].module.mac_address_detected(entries['net_sniffer_iw@TEST'], env, '01:02:03:04:05:06', disconnected = True)
  test.waitRunning()
