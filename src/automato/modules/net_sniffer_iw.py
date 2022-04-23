# require python3
# -*- coding: utf-8 -*-

import logging
import threading
import subprocess
import os
import re

from automato.core import system
from automato.core import utils

definition = {
  'description': _('Sniff network searching for devices with mac addresses'),
  
  'install_on': {
    'mac_address': (),
    'net_connection_momentary': (),
  },
  
  'config': {
    'momentary_flood_time': 30, # Used for devices with net_connection_momentary flag set, if a connection is detected within this time from the previous connection, it's ignored
    'connection_time': '15m', # If a connected device is no more detected after this time, it's considered disconnected
    'send_connect_message_every': '10m', # If a device is connected, resend a connect message on this interval (set to 0 to disable)
    
    'use_iw': True,
    'iw_event_command': 'iw event',
    'iw_dev_command': 'iw dev | grep Interface | cut -f 2 -s -d" "',
    'iw_station_dump_command': 'iw dev {INTERFACE} station dump | grep Station | cut -f 2 -s -d" "',
    
    'use_ip_neigh': False,
    'ip_neigh_command': 'ip neigh',
    
    'use_arp': True, # Use arp file to detect ipv4 addresses
    'arp_location': '/proc/net/arp',
    
    'use_ping': False, # Use ping command to detect if a device is connected when in doubt (used for "ip neigh" line with "STALE" or "DELAY" status)
    'ping_timeout': 1, # Seconds for ping timeout (it's a local network ping, so 1 second should be safe)
  },
  
  'run_interval': 60,
}

def load(entry):
  entry.net_sniffer_mac_addresses = {} # mac_address:{ 'entry_id': STR, 'momentary': BOOL, 'connected': BOOL, 'last_seen': TIMESTAMP, 'last_published': TIMESTAMP, 'last_ip_address': [STR] }

def init(entry):
  entry.destroyed = False
  entry.thread_iwevent = None
  entry.thread_iwevent_proc = None
  
  entry.thread_checker = threading.Thread(target = _thread_checker, args = [entry], daemon = True)
  entry.thread_checker._destroyed = False
  entry.thread_checker.start()

def destroy(entry):
  _iwevent_thread_kill(entry)
  if entry.thread_iwevent and not entry.thread_iwevent._destroyed:
    entry.thread_iwevent._destroyed = True
    entry.thread_iwevent.join()
    
  entry.thread_checker._destroyed = True
  entry.thread_checker.join()

def entry_install(installer_entry, entry, conf):
  installer_entry.net_sniffer_mac_addresses[conf['mac_address'].upper()] = { 'entry_id': entry.id, 'momentary': 'net_connection_momentary' in conf and conf['net_connection_momentary'], 'connected': False, 'last_seen': 0, 'last_published': 0, 'last_ip_address': None}

  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      '@/connected': {
        'description': _('Device connected to the network'),
        'type': 'object',
        'notify': _('Device {caption} connected to the local network'),
        'events': {
          'connected': 'js:payload_transfer({value: 1}, payload, ["mac_address", "ip_address", "was_connected", "method"])'
        },
      },
      '@/disconnected': {
        'description': _('Device disconnected from the network'),
        'type': 'object',
        'notify': _('Device {caption} disconnected from the local network'),
        'events': {
          'connected': 'js:payload_transfer({value: 0}, payload, ["mac_address", "ip_address", "was_connected", "method", "prev_ip_address"])'
        },
        'events_debug': 1,
      },
      '@/detected': {
        'description': _('Device momentarily detected on the network'),
        'type': 'object',
        'notify': _('Device {caption} momentarily detected on local network'),
        'events': {
          'connected': 'js:payload_transfer({value: 1, temporary: true}, payload, ["mac_address", "ip_address", "was_connected", "method"])',
          'input': 'js:({ value: 1, temporary: true})',
        }
      }
    },
  })

def start(entry):
  if not system.test_mode and entry.config['use_iw']:
    entry.thread_iwevent = threading.Thread(target = _iwevent_thread, args = [entry], daemon = True)
    entry.thread_iwevent._destroyed = False
    entry.thread_iwevent.start()

def run(installer_entry):
  if installer_entry.config['use_iw']:
    _iwdev_run(installer_entry)
  if installer_entry.config['use_ip_neigh']:
    _ip_neigh_run(installer_entry)

def _iwevent_thread(installer_entry):
  logging.debug("#{id}> starting iw event polling ...".format(id = installer_entry.id))
  installer_entry.thread_iwevent_proc = subprocess.Popen(installer_entry.config['iw_event_command'].split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text = True)
  
  #try:
  while installer_entry.thread_iwevent_proc.poll() is None:
    _iwevent_process_line(installer_entry, str(installer_entry.thread_iwevent_proc.stdout.readline().strip()))
  #except KeyboardInterrupt:
  #  pass
  #finally:
  #  if installer_entry.thread_iwevent_proc:
  #    installer_entry.thread_iwevent_proc.kill()
  #    installer_entry.thread_iwevent_proc = None

def _iwevent_thread_kill(installer_entry):
  if installer_entry.thread_iwevent_proc:
    installer_entry.thread_iwevent_proc.kill()
    installer_entry.thread_iwevent_proc = None

def _iwevent_process_line(installer_entry, line):
  #logging.debug("#{id}> iw event line detected: {line}".format(id = installer_entry.id, line = line))
  env = {}
  m = re.search('(new|del) station.*([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line, re.IGNORECASE)
  if m and (m.group(1) == 'new' or m.group(1) == 'del'):
    mac_address_detected(installer_entry, env, m.group(2).upper(), m.group(1) == 'del', None, 'iw_event')

def _iwdev_run(installer_entry):
  env = {}
  interfaces = subprocess.check_output(installer_entry.config['iw_dev_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  for interface in interfaces.split("\n"):
    mac_addresses = subprocess.check_output(installer_entry.config['iw_station_dump_command'].replace("{INTERFACE}", interface.strip()), shell=True, stderr=subprocess.STDOUT).decode("utf-8")
    for mac_address in mac_addresses.split("\n"):
      if re.search('^([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})$', mac_address.strip(), re.IGNORECASE):
        mac_address_detected(installer_entry, env, mac_address.strip().upper(), False, None, 'iw_dump')

#def _arp_run(installer_entry):
#  env = {}
#  l = _arp_list(installer_entry)
#  for mac_address in l:
#    mac_address_detected(installer_entry, env, mac_address, True, l[mac_address], 'arp')

def _arp_list(installer_entry):
  logging.debug("#{id}> arp list fetching ...".format(id = installer_entry.id))
  ret = {}
  with open(installer_entry.config['arp_location'], 'r') as f:
    output = f.read()
  for line in output.split("\n"):
    r = _arp_process_line(line.strip())
    if r:
      ret[r[0]] = r[1]
  return ret

def _arp_process_line(line):
  m = re.search('([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})?.*([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line, re.IGNORECASE)
  return [m.group(2).upper(), m.group(1)] if m else None

def _ip_neigh_run(installer_entry):
  logging.debug("#{id}> ip neigh fetching ...".format(id = installer_entry.id))
  env = {}
  result = subprocess.check_output(installer_entry.config['ip_neigh_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  for line in result.split("\n"):
    r = __ip_neigh_process_line(line)
    if r and r['mac_address'] and r['mac_address'] in installer_entry.net_sniffer_mac_addresses:
      # if REACHABLE, the entry is considered running, so i can set it as detected
      if r['state'] == 'REACHABLE':
        mac_address_detected(installer_entry, env, r['mac_address'], False, r['ipv4'], 'ip_neigh')
      # if STALE or DELAY i check if it has been detected by other methods. If not, and ping is available, let's try pinging it
      elif (r['state'] == 'STALE' or r['state'] == 'DELAY') and installer_entry.config['use_ping'] and system.time() - installer_entry.net_sniffer_mac_addresses[r['mac_address']]['last_seen'] > utils.read_duration(installer_entry.config['connection_time']):
        mac_address_detected(installer_entry, env, r['mac_address'], not _ping(installer_entry, r['ipv4'] if r['ipv4'] else r['ipv6']), r['ipv4'], 'ip_neigh_ping')

def __ip_neigh_process_line(line):
  # IPV4|IPV6 "dev" INTERFACE ["lladdr" MAC_ADDRESS_LOWECASE] "STALE|DELAY|REACHABLE|FAILED"
  # Ex: 192.168.2.234 dev wlan1-1 lladdr a8:03:2a:bc:71:58 STALE|DELAY|REACHABLE
  # Ex: fe80::32b5:c2ff:fe4f:d116 dev br-lan  FAILED
  m = re.search('^\s*(([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})|([0-9a-f]+(:+[0-9a-f]+)*))\s+dev\s+([a-z0-9-]+)\s+(lladdr ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})\s+)?([a-z]+)\s*$', line, re.IGNORECASE)
  return {"ipv4": m.group(2), "ipv6": m.group(3), "iface": m.group(5), "mac_address": m.group(7).upper() if m.group(7) else None, "state": m.group(8)} if m else None

def _ping(installer_entry, ip):
  # WARN Used also in net.module (@see entry.config['wan-connected-check-method'] == 'ping'), should be unified
  with open(os.devnull, 'wb') as devnull:
    response = subprocess.call(['ping', '-c',  '1', '-W', str(installer_entry.config['ping_timeout']), ip], stdout=devnull, stderr=devnull)
  logging.debug("#{id}> pinged {ip} = {response}".format(id = installer_entry.id, ip = ip, response = (response == 0)))
  return response == 0

def mac_address_detected(installer_entry, env, mac_address, disconnected = False, ip_address = None, method = None):
  if mac_address in installer_entry.net_sniffer_mac_addresses:
    logging.debug("#{id}> mac_address_detected: {mac_address}, connected: {connected}, ip_address: {ip_address}, method: {method}".format(id = installer_entry.id, mac_address = mac_address, connected = not disconnected, ip_address = ip_address, method = method))
    entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address]['entry_id'])
    if entry:
      was_connected = installer_entry.net_sniffer_mac_addresses[mac_address]['connected']
      last_seen = installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen']
      installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen'] = system.time()
      publish = None
      if not disconnected and installer_entry.net_sniffer_mac_addresses[mac_address]['momentary']:
        if system.time() - last_seen < utils.read_duration(installer_entry.config['momentary_flood_time']):
          return
        else:
          publish = '@/detected'
      elif not disconnected and not was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] = True
        publish = '@/connected'
      elif disconnected and was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] = False
        publish = '@/disconnected'
        ip_address = None
      elif installer_entry.config['send_connect_message_every'] and not disconnected and system.time() - installer_entry.net_sniffer_mac_addresses[mac_address]['last_published'] >= utils.read_duration(installer_entry.config['send_connect_message_every']):
        publish = '@/connected'
        if not ip_address and installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          ip_address = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']

      logging.debug("#{id}> {entry}: mac_address_detected, res: {publish}, mac: {mac_address}, connected: {connected}, ip_address: {ip_address}, momentary: {momentary}, was_connected: {was_connected}, last_seen: {last_seen}, method: {method}".format(id = installer_entry.id, entry = entry.id, publish = publish, mac_address = mac_address, connected = not disconnected, ip_address = ip_address, momentary = installer_entry.net_sniffer_mac_addresses[mac_address]['momentary'], was_connected = was_connected, last_seen = last_seen, method = method))
      
      if publish:
        data = { 'mac_address': mac_address, 'was_connected': was_connected, 'method': method }
        if not disconnected and not ip_address and installer_entry.config['use_arp']:
          if 'arp_list' not in env:
            env['arp_list'] = _arp_list(installer_entry)
          if mac_address in env['arp_list']:
            ip_address = env['arp_list'][mac_address]
        data['ip_address'] = ip_address
        if publish == '@/disconnected' and installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          data['prev_ip_address'] = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']
        entry.publish(publish, data)
        installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address'] = ip_address
        installer_entry.net_sniffer_mac_addresses[mac_address]['last_published'] = system.time()

def _thread_checker(installer_entry):
  while not threading.currentThread()._destroyed:
    status_check(installer_entry)
    system.sleep(utils.read_duration(installer_entry.config['connection_time']) / 10)

def status_check(installer_entry):
  config_connection_time = utils.read_duration(installer_entry.config['connection_time'])
  for mac_address in installer_entry.net_sniffer_mac_addresses:
    if installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] and system.time() - installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen'] > config_connection_time:
      entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address]['entry_id'])
      if entry:
        installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] = False
        data = {'mac_address': mac_address, 'ip_address': None, 'was_connected': True, 'method': 'timeout'}
        if installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          data['prev_ip_address'] = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']
          installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address'] = None
        entry.publish('@/disconnected', data)
        
        logging.debug("#{id}> {entry}: status_check, res: disconnected".format(id = installer_entry.id, entry = entry.id))

#############################
# CLI execution for testing purpose

"""
import time

def _cli_publish(topic, message):
  print("PUBLISHING " + str(topic) + " = " + str(message))

if __name__== '__main__':
  system = type('', (), {})()
  system.test_mode = False
  entry = type('', (), {})()
  entry.id = 'X'
  entry.publish = _cli_publish
  entry.config = definition['config']
  entry.net_sniffer_mac_addresses = {}
  start(entry)
  while True:
    run(entry)
    time.sleep(5)
"""
