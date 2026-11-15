# require python3
# -*- coding: utf-8 -*-

import os
import unittest

from automato.core import system

from node_helpers import NodeTestCase

MAC = '26:4A:D7:44:4D:0B'

ARP_AWAY = """IP address       HW type     Flags       HW address            Mask     Device
100.89.193.62    0x1         0x0         26:4a:d7:44:4d:0b     *        br-lan.1
192.168.1.221    0x1         0x0         26:4a:d7:44:4d:0b     *        br-lan.1
100.89.81.56     0x1         0x0         26:4a:d7:44:4d:0b     *        br-lan.1
"""

ARP_HOME = """IP address       HW type     Flags       HW address            Mask     Device
100.89.81.56     0x1         0x2         26:4a:d7:44:4d:0b     *        br-lan.1
192.168.1.221    0x1         0x2         26:4a:d7:44:4d:0b     *        br-lan.1
"""

class NetSnifferTest(NodeTestCase):
  entries = [
    { 'module': 'net_sniffer', 'config': { 'event_monitor_handler': None, 'polling_handler': None, 'ip_get_handler': 'arp', 'connection_time': '10s' } },
    { 'item': 'phone', 'mac_address': MAC },
  ]

  def setUp(self):
    super().setUp()
    system.time_pause()
    self.sniffer = self.entry('net_sniffer@test')
    self.ns = self.sniffer.module
    self.arp = self.storage_path('arp')
    self.sniffer.config['arp_location'] = self.arp
    self.write_arp(ARP_HOME)
    self.published = []
    self.phone = self.entry('phone@test')
    publish = self.phone.publish
    self.phone.publish = lambda topic, data = None, *a, **k: self.published.append((topic, data))

  def tearDown(self):
    system.time_resume()
    super().tearDown()

  def write_arp(self, content):
    with open(self.arp, 'w') as f:
      f.write(content)

  def detected(self, **kwargs):
    self.ns.mac_address_detected(self.sniffer, {}, MAC, **kwargs)

  def topics(self):
    return [t for t, d in self.published]

  def test_ip_address_usable(self):
    self.assertTrue(self.ns.ip_address_usable('192.168.1.221'))
    self.assertTrue(self.ns.ip_address_usable('10.0.0.5'))
    for ip in ['100.89.81.56', '100.64.0.1', '100.127.255.254', '127.0.0.1', '169.254.1.1', 'fe80::1', 'x', '']:
      self.assertFalse(self.ns.ip_address_usable(ip), ip)

  def test_arp_ignores_incomplete_entries(self):
    self.write_arp(ARP_AWAY)
    self.assertEqual(self.ns._arp_list(self.sniffer), {})

  def test_arp_ignores_overlay_addresses(self):
    self.write_arp(ARP_HOME)
    self.assertEqual(self.ns._arp_list(self.sniffer), {MAC.upper(): '192.168.1.221'})

  def test_overlay_ip_from_handler_is_ignored(self):
    self.write_arp(ARP_HOME)
    self.detected(connected = True, confidence = True, ip_address = '100.89.81.56', handler = 'ip_neigh')
    self.assertEqual(self.published[0][1]['ip_address'], '192.168.1.221')

  def test_no_ping_without_usable_ip_and_device_times_out(self):
    # Away: no usable ip, the stale detection must not refresh "last_seen", so the connection times out
    self.write_arp(ARP_HOME)
    self.detected(connected = True, confidence = True, handler = 'iw')
    self.assertEqual(self.topics(), ['@/connected'])
    self.write_arp(ARP_AWAY)
    last_seen = self.sniffer.net_sniffer_mac_addresses[MAC]['last_seen']
    self.sniffer.net_sniffer_mac_addresses[MAC]['last_seen'] = last_seen - 1000
    # a STALE detection through ip_neigh with ping enabled and no usable ip is ignored
    self.sniffer.net_sniffer_all_handlers['ip_neigh'] = { 'polling_ping': True }
    self.detected(connected = True, confidence = False, handler = 'ip_neigh')
    self.assertEqual(self.sniffer.net_sniffer_mac_addresses[MAC]['last_seen'], last_seen - 1000)
    self.ns.status_check(self.sniffer)
    self.assertEqual(self.topics(), ['@/connected', '@/disconnected'])

  def test_reachable_entry_does_not_cancel_a_disconnection_by_event(self):
    self.detected(connected = True, confidence = True, handler = 'iw', event_monitor = True)
    self.detected(connected = False, confidence = True, handler = 'iw', event_monitor = True)
    # the neighbours table still has a REACHABLE entry
    self.detected(connected = True, confidence = True, ip_address = '192.168.1.221', handler = 'ip_neigh')
    self.assertEqual(self.topics(), ['@/connected', '@/disconnected'])
    self.assertFalse(self.sniffer.net_sniffer_mac_addresses[MAC]['connected'])

  def test_reconnection_event_is_always_accepted(self):
    self.detected(connected = True, confidence = True, handler = 'iw', event_monitor = True)
    self.detected(connected = False, confidence = True, handler = 'iw', event_monitor = True)
    self.detected(connected = True, confidence = True, handler = 'iw', event_monitor = True)
    self.assertEqual(self.topics(), ['@/connected', '@/disconnected', '@/connected'])

  def test_other_handlers_accepted_after_grace_time(self):
    self.detected(connected = True, confidence = True, handler = 'iw', event_monitor = True)
    self.detected(connected = False, confidence = True, handler = 'iw', event_monitor = True)
    system.time_pause()
    self.sniffer.net_sniffer_mac_addresses[MAC]['disconnected_by_event'] -= 120
    self.detected(connected = True, confidence = True, ip_address = '192.168.1.221', handler = 'ip_neigh')
    self.assertEqual(self.topics(), ['@/connected', '@/disconnected', '@/connected'])

if __name__ == '__main__':
  unittest.main()
