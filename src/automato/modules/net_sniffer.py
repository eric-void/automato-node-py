# require python3
# -*- coding: utf-8 -*-

import logging
import threading
import subprocess
import os
import re

from automato.core import system
from automato.core import utils
from automato.node import node_system as node

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
    'confidence_timeout': '15m', # After a connection with confidence detected (via method or PING), we consider the device as detected with confidence for this period (= no other ping will be made)
    
    # The 3 options below could also be an array of handlers, or None/False to disable that handler. For event_monitor or polling_handler you can user "HANDLERNAME+ping" if you want to ping connected devices with no confidence about real presence. (Overriden by entry.definition['net_sniffer_ping'], and considering config['confidence_timeout'] or entry.definition['net_sniffer_confidence_timeout'])
    'event_monitor_handler': 'iw',
    'polling_handler': 'iw',
    'ip_get_handler': 'arp', # method for retrieving ip if original handler doesn't provide it
    
    'iw_event_command': 'iw event',
    'iw_dev_command': 'iw dev | grep Interface | cut -f 2 -s -d" "',
    'iw_station_dump_command': 'iw dev {INTERFACE} station dump | grep Station | cut -f 2 -s -d" "',
    
    'ip_neigh_command': 'ip neigh',
    
    'arp_location': '/proc/net/arp',
    
    'use_ping_command': False, # Use ping command to detect if a device is connected when in doubt (used for "ip neigh" line with "STALE" or "DELAY" status). WARN: NEED ROOT PRIVILEGES
    'ping_command': 'ping -c 2 -W 1 -A', # c: number of pings sent, W: wait for each ping after all sent, A: stop at first received. "-c 2 -W 1 -A" waits max 2 seconds
    
    'use_ping_module': False, # Use ping module (via icmplib library) to detect if a device is connected when in doubt (same as use_ping_command). Can be executed without ROOT privileges, but the system should be prepared. See module docs or icmplib docs
  },
  
  'run_interval': 60, # = polling interval
}
"""
entry.definition = {
  'net_sniffer_ping': True, # Force ping when there is no confidence over current connection
  'net_sniffer_ignore_handler_confidence': True, # If true, do not trust confidence given by handler
  'net_sniffer_confidence_timeout': '15m', # Override confidence timeout for this entry
}
"""


def load(installer_entry):
  installer_entry.net_sniffer_mac_addresses = {} # mac_address:{ 'entry_id': STR, 'momentary': BOOL, 'connected': BOOL, 'last_seen': TIMESTAMP, 'last_seen_confidence': TIMESTAMP, 'last_published': TIMESTAMP, 'last_ip_address': [STR] }

def init(installer_entry):
  installer_entry.destroyed = False
  
  installer_entry.net_sniffer_all_handlers = {}
  installer_entry.net_sniffer_monitor_handlers = []
  installer_entry.net_sniffer_polling_handlers = []
  installer_entry.net_sniffer_ip_get_handlers = []
  for k in ['event_monitor_handler', 'polling_handler', 'ip_get_handler']:
    if not installer_entry.config[k]:
      installer_entry.config[k] = []
    elif isinstance(installer_entry.config[k], str):
      installer_entry.config[k] = [installer_entry.config[k]]
  for h in installer_entry.config['event_monitor_handler'] + installer_entry.config['polling_handler'] + installer_entry.config['ip_get_handler']:
    h = h.split('+ping')[0]
    if not h in installer_entry.net_sniffer_all_handlers:
      installer_entry.net_sniffer_all_handlers[h] = {'event_monitor': False, 'polling': False, 'ip_get': False}
  for h in installer_entry.config['event_monitor_handler']:
    ping = h.endswith('+ping')
    h = h.split('+ping')[0]
    installer_entry.net_sniffer_all_handlers[h]['event_monitor'] = True
    installer_entry.net_sniffer_all_handlers[h]['event_monitor_ping'] = ping
    installer_entry.net_sniffer_monitor_handlers.append(h)
  for h in installer_entry.config['polling_handler']:
    ping = h.endswith('+ping')
    h = h.split('+ping')[0]
    if (h + '_polling_run') in globals():
      installer_entry.net_sniffer_all_handlers[h]['polling'] = True
      installer_entry.net_sniffer_all_handlers[h]['polling_ping'] = ping
      installer_entry.net_sniffer_all_handlers[h]['polling_callable'] = globals()[h + '_polling_run']
      installer_entry.net_sniffer_polling_handlers.append(h)
  for h in installer_entry.config['ip_get_handler']:
    if (h + '_ip_get') in globals():
      installer_entry.net_sniffer_all_handlers[h]['ip_get'] = True
      installer_entry.net_sniffer_all_handlers[h]['ip_get_callable'] =  globals()[h + '_ip_get']
      installer_entry.net_sniffer_ip_get_handlers.append(h)
  
  for h in installer_entry.net_sniffer_all_handlers:
    if (h + '_init') in globals():
      globals()[h + '_init'](installer_entry, installer_entry.net_sniffer_all_handlers[h])
  
  installer_entry.thread_polling = threading.Thread(target = _thread_polling, args = [installer_entry], daemon = True)
  installer_entry.thread_polling._destroyed = False
  installer_entry.thread_polling.start()

def destroy(installer_entry):
  for h in installer_entry.net_sniffer_all_handlers:
    if (h + '_destroy') in globals():
      globals()[h + '_destroy'](installer_entry, installer_entry.net_sniffer_all_handlers[h])

  installer_entry.thread_polling._destroyed = True
  installer_entry.thread_polling.join()

def entry_install(installer_entry, entry, conf):
  installer_entry.net_sniffer_mac_addresses[conf['mac_address'].upper()] = { 'entry_id': entry.id, 'momentary': 'net_connection_momentary' in conf and conf['net_connection_momentary'], 'connected': False, 'last_seen': 0, 'last_seen_confidence': 0, 'last_published': 0, 'last_ip_address': None}

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
          'connected': 'js:payload_transfer({value: 1}, payload, ["mac_address", "ip_address", "was_connected", "handler"])'
        },
      },
      '@/disconnected': {
        'description': _('Device disconnected from the network'),
        'type': 'object',
        'notify': _('Device {caption} disconnected from the local network'),
        'events': {
          'connected': 'js:payload_transfer({value: 0}, payload, ["mac_address", "ip_address", "was_connected", "handler", "prev_ip_address"])'
        },
        'events_debug': 1,
      },
      '@/detected': {
        'description': _('Device momentarily detected on the network'),
        'type': 'object',
        'notify': _('Device {caption} momentarily detected on local network'),
        'events': {
          'connected': 'js:payload_transfer({value: 1, temporary: true}, payload, ["mac_address", "ip_address", "was_connected", "handler"])',
          'input': 'js:({ value: 1, temporary: true})',
        }
      }
    },
  })

def start(installer_entry):
  for h in installer_entry.net_sniffer_all_handlers:
    if (h + '_start') in globals():
      globals()[h + '_start'](installer_entry, installer_entry.net_sniffer_all_handlers[h])

def run(installer_entry):
  env = {}
  for h in installer_entry.net_sniffer_polling_handlers:
    installer_entry.net_sniffer_all_handlers[h]['polling_callable'](installer_entry, installer_entry.net_sniffer_all_handlers[h], env)

"""
@param confidence: True if the device is surely present (no PING needed), False if the device is probably present (but a PING is advisable)
@param ip_address: Only ipv4 address, set to None if the method could not obtain the ip address
@param handler: handler name
@param event_monitor: indicates the detection is started from an event monitor handler
"""
def mac_address_detected(installer_entry, env, mac_address, connected = True, confidence = False, ip_address = None, handler = None, event_monitor = False):
  if mac_address in installer_entry.net_sniffer_mac_addresses:
    if ip_address:
      ip_address_set(env, mac_address, ip_address)
    entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address]['entry_id'])
    if entry:
      was_connected = installer_entry.net_sniffer_mac_addresses[mac_address]['connected']
      last_seen = installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen']
      last_seen_confidence = installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen_confidence']
      if 'net_sniffer_ignore_handler_confidence' in entry.definition and entry.definition['net_sniffer_ignore_handler_confidence']:
        confidence = False
      ping = entry.definition['net_sniffer_ping'] if 'net_sniffer_ping' in entry.definition else (
        (
          installer_entry.net_sniffer_all_handlers[handler]['event_monitor_ping'] if event_monitor and 'event_monitor_ping' in installer_entry.net_sniffer_all_handlers[handler] else 
          (installer_entry.net_sniffer_all_handlers[handler]['polling_ping'] if not event_monitor and 'polling_ping' in installer_entry.net_sniffer_all_handlers[handler] else False)
        ) if handler and handler in installer_entry.net_sniffer_all_handlers else False)

      if ping and connected and not confidence:
        if not ip_address:
          ip_address = ip_address_get(installer_entry, env, mac_address)
        if ip_address:
          confidence_timeout = utils.read_duration(entry.definition['net_sniffer_confidence_timeout']) if 'net_sniffer_confidence_timeout' in entry.definition else utils.read_duration(installer_entry.config['confidence_timeout'])
          if system.time() - installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen_confidence'] > confidence_timeout:
            logging.debug("#{id}> {entry}: no confidence on {mac_address} connection, try pinging it ...".format(id = installer_entry.id, entry = entry.id, mac_address = mac_address))
            connected = _ping(installer_entry, ip_address)
            confidence = True
        else:
          # If config requires ping for this entry, and ip_address is not available, ignore the detection
          return
      
      # If the entry was disconnected WITH CONFIDENCE, only a connection with confidence is considered
      if connected and not confidence and not was_connected and last_seen_confidence == last_seen:
        return
      
      installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen'] = system.time()
      if confidence:
        installer_entry.net_sniffer_mac_addresses[mac_address]['last_seen_confidence'] = system.time()
      publish = None
      if connected and installer_entry.net_sniffer_mac_addresses[mac_address]['momentary']:
        if system.time() - last_seen < utils.read_duration(installer_entry.config['momentary_flood_time']):
          return
        else:
          publish = '@/detected'
      elif connected and not was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] = True
        publish = '@/connected'
      elif not connected and was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address]['connected'] = False
        publish = '@/disconnected'
        ip_address = None
      elif installer_entry.config['send_connect_message_every'] and connected and system.time() - installer_entry.net_sniffer_mac_addresses[mac_address]['last_published'] >= utils.read_duration(installer_entry.config['send_connect_message_every']):
        publish = '@/connected'
        if not ip_address and installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          ip_address = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']

      logging.debug("#{id}> {entry}: mac_address_detected, res: {publish}, mac: {mac_address}, connected: {connected}, confidence: {confidence}, ip_address: {ip_address}, momentary: {momentary}, was_connected: {was_connected}, last_seen: {last_seen}, last_seen_confidence: {last_seen_confidence}, handler: {handler}".format(id = installer_entry.id, entry = entry.id, publish = publish, mac_address = mac_address, connected = connected, confidence = confidence, ip_address = ip_address, momentary = installer_entry.net_sniffer_mac_addresses[mac_address]['momentary'], was_connected = was_connected, last_seen = last_seen, last_seen_confidence = last_seen_confidence, handler = (handler + ('_monitor' if event_monitor else '_polling')) if handler else '-'))
      
      if publish:
        data = { 'mac_address': mac_address, 'was_connected': was_connected, 'handler': (handler + ('_monitor' if event_monitor else '_polling')) if handler else None }
        if connected and not ip_address:
          ip_address = ip_address_get(installer_entry, env, mac_address)
        data['ip_address'] = ip_address
        if publish == '@/disconnected' and installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          data['prev_ip_address'] = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']
        entry.publish(publish, data)
        installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address'] = ip_address
        installer_entry.net_sniffer_mac_addresses[mac_address]['last_published'] = system.time()

def ip_address_get(installer_entry, env, mac_address):
  if 'ip' in env and mac_address in env['ip']:
    return env['ip'][mac_address]
  for h in installer_entry.net_sniffer_ip_get_handlers:
    r = installer_entry.net_sniffer_all_handlers[h]['ip_get_callable'](installer_entry, env, mac_address)
    if r:
      return ip_address_set(env, mac_address, r)
  return ip_address_set(env, mac_address, None)

def ip_address_set(env, mac_address, ip_address):
  if 'ip' not in env:
    env['ip'] = {}
  env['ip'][mac_address] = ip_address
  return ip_address

def _thread_polling(installer_entry):
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
        data = {'mac_address': mac_address, 'ip_address': None, 'was_connected': True, 'handler': 'timeout'}
        if installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']:
          data['prev_ip_address'] = installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address']
          installer_entry.net_sniffer_mac_addresses[mac_address]['last_ip_address'] = None
        entry.publish('@/disconnected', data)
        
        logging.debug("#{id}> {entry}: status_check, res: disconnected".format(id = installer_entry.id, entry = entry.id))




###############################################################################
# IW
# Pro: events for real time monitor
# Cons: only wifi, no IP addresses, don't detect stale connections (PING needed to detect inactive connections)
###############################################################################

def iw_init(installer_entry, conf):
  if not system.test_mode and conf['event_monitor']:
    installer_entry.thread_iwevent = None
    installer_entry.thread_iwevent_proc = None

def iw_destroy(installer_entry, conf):
  if not system.test_mode and conf['event_monitor']:
    _iwevent_thread_kill(installer_entry)
    if installer_entry.thread_iwevent and not installer_entry.thread_iwevent._destroyed:
      installer_entry.thread_iwevent._destroyed = True
      installer_entry.thread_iwevent.join()

def iw_start(installer_entry, conf):
  if not system.test_mode and conf['event_monitor']:
    installer_entry.thread_iwevent = threading.Thread(target = _iwevent_thread, args = [installer_entry], daemon = True)
    installer_entry.thread_iwevent._destroyed = False
    installer_entry.thread_iwevent.start()

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
    mac_address_detected(installer_entry, env, m.group(2).upper(), connected = not (m.group(1) == 'del'), confidence = True, ip_address = None, handler = 'iw', event_monitor = True)

def iw_polling_run(installer_entry, conf, env):
  interfaces = subprocess.check_output(installer_entry.config['iw_dev_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  for interface in interfaces.split("\n"):
    mac_addresses = subprocess.check_output(installer_entry.config['iw_station_dump_command'].replace("{INTERFACE}", interface.strip()), shell=True, stderr=subprocess.STDOUT).decode("utf-8")
    for mac_address in mac_addresses.split("\n"):
      if re.search('^([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})$', mac_address.strip(), re.IGNORECASE):
        mac_address_detected(installer_entry, env, mac_address.strip().upper(), connected = True, confidence = False, ip_address = None, handler = 'iw', event_monitor = False)



###############################################################################
# ARP
# Pro: ip addresses, wifi+wired connections
# Cons: no events for real time monitoring, don't detect stale connections (PING is needed to confirm activity)
###############################################################################

def arp_ip_get(installer_entry, env, mac_address):
  if 'arp_list' not in env:
    env['arp_list'] = _arp_list(installer_entry)
  if mac_address in env['arp_list']:
    return env['arp_list'][mac_address]

#def _arp_run(installer_entry):
#  env = {}
#  l = _arp_list(installer_entry)
#  for mac_address in l:
#    mac_address_detected(installer_entry, env, mac_address, True, False, l[mac_address], 'arp')

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




###############################################################################
# IP NEIGH
# Pro: ip addresses, wifi+wired connections, detect active connections (no PING needed on them, but needed on STALE/DELAY connections)
# Cons: no events for real time monitoring
###############################################################################

def ip_neigh_polling_run(installer_entry, conf, env):
  logging.debug("#{id}> ip neigh fetching ...".format(id = installer_entry.id))
  result = subprocess.check_output(installer_entry.config['ip_neigh_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  for line in result.split("\n"):
    r = __ip_neigh_process_line(line)
    if r and r['mac_address'] and r['mac_address'] in installer_entry.net_sniffer_mac_addresses:
      # if REACHABLE, the entry is considered running, so i can set it as detected
      if r['state'] == 'REACHABLE':
        mac_address_detected(installer_entry, env, r['mac_address'], connected = True, confidence = True, ip_address = r['ipv4'], handler = 'ip_neigh', event_monitor = False)
      # FAILED state must be considered as a certain disconnection
      elif r['state'] == 'FAILED':
        mac_address_detected(installer_entry, env, r['mac_address'], connected = False, confidence = True, ip_address = r['ipv4'], handler = 'ip_neigh', event_monitor = False)
      # NONE, INCOMPLETE and PROBE states tells nothing so must be ignored. Other states must be considered as if the device is present, but no strong confidence about it
      elif r['state'] != 'NONE' and r['state'] != 'INCOMPLETE' and r['state'] != 'PROBE':
        mac_address_detected(installer_entry, env, r['mac_address'], connected = True, confidence = False, ip_address = r['ipv4'], handler = 'ip_neigh', event_monitor = False)

def ip_neigh_ip_get(installer_entry, env, mac_address):
  if 'ip_neigh_list' not in env:
    env['ip_neigh_list'] = {}
    result = subprocess.check_output(installer_entry.config['ip_neigh_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
    for line in result.split("\n"):
      r = __ip_neigh_process_line(line)
      if r['ipv4']:
        env['ip_neigh_list'][r['mac_address']] = r['ipv4']
  if mac_address in env['ip_neigh_list']:
    return env['ip_neigh_list'][mac_address]

def __ip_neigh_process_line(line):
  # IPV4|IPV6 "dev" INTERFACE ["lladdr" MAC_ADDRESS_LOWECASE] [ref X] [used X/X/X] [probes X] "STALE|DELAY|REACHABLE|FAILED"
  # Ex: 192.168.2.234 dev wlan1-1 lladdr a8:03:2a:bc:71:58 STALE|DELAY|REACHABLE
  # Ex: fe80::32b5:c2ff:fe4f:d116 dev br-lan  FAILED
  m = re.search('^\s*(([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})|([0-9a-f]+(:+[0-9a-f]+)*))\s+dev\s+([a-z0-9-]+)\s+'+
                '(lladdr ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})\s+)?' +
                '(ref ([0-9]+)\s+)?' +
                '(used ([0-9]+)/([0-9]+)/([0-9]+)\s+)?' +
                '(probes ([0-9]+)\s+)?' +
                '([a-z]+)\s*$', line, re.IGNORECASE)
  return {"ipv4": m.group(2), "ipv6": m.group(3), "iface": m.group(5), "mac_address": m.group(7).upper() if m.group(7) else None, "ref": m.group(9), "used": [m.group(11),m.group(12),m.group(13)], "probes": m.group(15), "state": m.group(16)} if m else None





###############################################################################
# PING
###############################################################################

def _ping(installer_entry, ip):
  # WARN Used also in net.module (@see entry.config['wan-connected-check-method'] == 'ping'), should be unified
  if installer_entry.config['use_ping_command']:
    response = subprocess.run(installer_entry.config['ping_command'].split(' ') + [ip], capture_output = True)
    logging.debug("#{id}> pinged {ip}: {response}".format(id = installer_entry.id, ip = ip, response = response))
    return response.returncode == 0
  if installer_entry.config['use_ping_module']:
    return node.entries_invoke('ping', ip)



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
