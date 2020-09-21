# require python3
# -*- coding: utf-8 -*-

import logging
import threading

# sudo pip3 install scapy-python3
# needs also "tcpdump" system package
# and the executable needs sudo privileges. To avoid this read: https://stackoverflow.com/questions/36215201/python-scapy-sniff-without-root
from scapy.all import *

from automato.core import system
from automato.core import utils

definition = {
  'description': _('Sniff network searching for devices with mac addresses'),
  
  'install_on': {
    'mac_address': (),
    'net_connection_momentary': (),
  },
  
  'config': {
    # Used for sniffer
    'sniff_filter': 'udp',
    'momentary_flood_time': 30,
    'connection_time': '15m',

    # Used for mac scanner
    'interface': 'eth0',
    'ips': '192.168.1.0/24',
    'timeout': 2, # timeout: The timeout parameter specify the time to wait after the last packet has been sent:
    'retry': 1, # retry: If retry is 3, scapy will try to resend unanswered packets 3 times. If retry is -3, scapy will resend unanswered packets until no more answer is given for the same set of unanswered packets 3 times in a row
    'inter': 0.01, # inter: If there is a limited rate of answers, you can specify a time interval to wait between two packets with the inter parameter
  },
  
  'run_interval': 15,
}

def load(entry):
  entry.net_sniffer_mac_addresses = {}

def init(entry):
  entry.destroyed = False
  entry.thread_checker = threading.Thread(target = _thread_checker, args = [entry], daemon = True)
  entry.thread_checker._destroyed = False
  entry.thread_checker.start()

def destroy(entry):
  entry.thread_checker._destroyed = True
  entry.thread_checker.join()

def entry_install(installer_entry, entry, conf):
  installer_entry.net_sniffer_mac_addresses[conf['mac_address'].upper()] = [entry.id, 'net_connection_momentary' in conf and conf['net_connection_momentary'], False, 0]
  
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      '@/connected': {
        'description': _('Device connected to the network'),
        'type': 'none',
        'notify': _('Device {caption} connected to the local network'),
        'events': {
          'connected': 'js:({ value: true })'
        }
      },
      '@/disconnected': {
        'description': _('Device disconnected from the network'),
        'type': 'none',
        'notify': _('Device {caption} disconnected from the local network'),
        'events': {
          'connected': 'js:({ value: false })'
        }
      },
      '@/detected': {
        'description': _('Device momentarily detected on the network'),
        'type': 'none',
        'notify': _('Device {caption} momentarily detected on local network'),
        'events': {
          'connected': 'js:({ value: true, temporary: true})',
          'input': 'js:({ value: 1, temporary: true})'
        }
      }
    },
  })

def start(entry):
  if not system.test_mode:
    try:
      sniff(prn = _sniff_callback_call(entry), filter = entry.config['sniff_filter'], store = 0, count = 0)
    except PermissionError:
      logging.exception("#{id}> you need ROOT permissions".format(id = entry.id))

def _sniff_callback_call(entry):
  return lambda pkt: sniff_callback(entry, pkt.src)

def sniff_callback(installer_entry, mac_address):
  mac_address = mac_address.upper()
  
  if mac_address in installer_entry.net_sniffer_mac_addresses:
    entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address][0])
    if entry:
      momentary = installer_entry.net_sniffer_mac_addresses[mac_address][1]
      connected = installer_entry.net_sniffer_mac_addresses[mac_address][2]
      last_seen = installer_entry.net_sniffer_mac_addresses[mac_address][3]
      installer_entry.net_sniffer_mac_addresses[mac_address][3] = system.time()
      if momentary:
        if system.time() - last_seen < utils.read_duration(installer_entry.config['momentary_flood_time']):
          return
        else:
          entry.publish('@/detected')
      elif not connected:
        installer_entry.net_sniffer_mac_addresses[mac_address][2] = True
        entry.publish('@/connected')

def run(installer_entry):
  data = net_sniffer_mac_scanner(installer_entry, installer_entry.config['interface'], installer_entry.config['ips'], installer_entry.config['timeout'], installer_entry.config['retry'], installer_entry.config['inter'])
  for mac_address in data:
    sniff_callback(installer_entry, mac_address)
  
def net_sniffer_mac_scanner(entry, interface = None, ips = None, timeout = None, retry = None, inter = None):
  ret = {}
  try:
    conf.verb = 0
    logging.debug("#{id}> starting mac_scanner of {interface}, ips: {ips} ...".format(id = entry.id, interface = interface, ips = ips))
    ans, unans = srp(Ether(dst='ff:ff:ff:ff:ff:ff')/ARP(pdst = ips), timeout = timeout, retry = retry, iface = interface, inter = inter)
    for snd, rcv in ans:
      mac = str(rcv.src).upper() #rcv.sprintf("%Ether.src%")
      ip = str(rcv.psrc) # rcv.sprintf("%ARP.psrc%")
      ret[mac] = ip
    logging.debug("#{id}> done mac_scanner of {interface}, ips: {ips}".format(id = entry.id, interface = interface, ips = ips))
  except PermissionError:
    logging.exception("#{id}> you need ROOT permissions".format(id = entry.id))
  return ret

def _thread_checker(installer_entry):
  while not threading.currentThread()._destroyed:
    status_check(installer_entry)
    system.sleep(utils.read_duration(installer_entry.config['connection_time']) / 10)

def status_check(installer_entry):
  config_connection_time = utils.read_duration(installer_entry.config['connection_time'])
  for mac_address in installer_entry.net_sniffer_mac_addresses:
    if installer_entry.net_sniffer_mac_addresses[mac_address][2] and system.time() - installer_entry.net_sniffer_mac_addresses[mac_address][3] > config_connection_time:
      entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address][0])
      if entry:
        installer_entry.net_sniffer_mac_addresses[mac_address][2] = False
        entry.publish('@/disconnected')
