# require python3
# -*- coding: utf-8 -*-

import logging
import threading
import subprocess
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
    
    'iw_event_command': 'iw event',
    'iw_dev_command': 'iw dev | grep Interface | cut -f 2 -s -d" "',
    'iw_station_dump_command': 'iw dev {INTERFACE} station dump | grep Station | cut -f 2 -s -d" "',
    'use_arp': True, # Use arp file to detect ip addresses
    'arp_location': '/proc/net/arp',
  },
  
  'run_interval': 60,
}

def load(entry):
  entry.net_sniffer_mac_addresses = {}

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
  installer_entry.net_sniffer_mac_addresses[conf['mac_address'].upper()] = [entry.id, 'net_connection_momentary' in conf and conf['net_connection_momentary'], False, 0]

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
          'connected': 'js:({ value: true, mac_address: "mac_address" in payload ? payload["mac_address"] : null, ip_address: "ip_address" in payload ? payload["ip_address"] : null})'
        }
      },
      '@/disconnected': {
        'description': _('Device disconnected from the network'),
        'type': 'object',
        'notify': _('Device {caption} disconnected from the local network'),
        'events': {
          'connected': 'js:({ value: false })'
        }
      },
      '@/detected': {
        'description': _('Device momentarily detected on the network'),
        'type': 'object',
        'notify': _('Device {caption} momentarily detected on local network'),
        'events': {
          'connected': 'js:({ value: true, temporary: true, mac_address: "mac_address" in payload ? payload["mac_address"] : null, ip_address: "ip_address" in payload ? payload["ip_address"] : null})',
          'input': 'js:({ value: 1, temporary: true})'
        }
      }
    },
  })

def start(entry):
  if not system.test_mode:
    entry.thread_iwevent = threading.Thread(target = _iwevent_thread, args = [entry], daemon = True)
    entry.thread_iwevent._destroyed = False
    entry.thread_iwevent.start()    

def run(installer_entry):
  _iwdev_run(installer_entry)

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
    mac_address_detected(installer_entry, env, m.group(2).upper(), disconnected = m.group(1) == 'del')

def _iwdev_run(installer_entry):
  env = {}
  interfaces = subprocess.check_output(installer_entry.config['iw_dev_command'], shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  for interface in interfaces.split("\n"):
    mac_addresses = subprocess.check_output(installer_entry.config['iw_station_dump_command'].replace("{INTERFACE}", interface.strip()), shell=True, stderr=subprocess.STDOUT).decode("utf-8")
    for mac_address in mac_addresses.split("\n"):
      if re.search('^([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})$', mac_address.strip(), re.IGNORECASE):
        mac_address_detected(installer_entry, env, mac_address.strip().upper())

#def _arp_run(installer_entry):
#  env = {}
#  l = _arp_list(installer_entry)
#  for mac_address in l:
#    mac_address_detected(installer_entry, env, mac_address, ip_address = l[mac_address])

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

def mac_address_detected(installer_entry, env, mac_address, disconnected = False, ip_address = None):
  if mac_address in installer_entry.net_sniffer_mac_addresses:
    logging.debug("#{id}> mac_address_detected: {mac_address}, connected: {connected}, ip_address: {ip_address}".format(id = installer_entry.id, mac_address = mac_address, connected = not disconnected, ip_address = ip_address))
    entry = system.entry_get(installer_entry.net_sniffer_mac_addresses[mac_address][0])
    if entry:
      momentary = installer_entry.net_sniffer_mac_addresses[mac_address][1]
      was_connected = installer_entry.net_sniffer_mac_addresses[mac_address][2]
      last_seen = installer_entry.net_sniffer_mac_addresses[mac_address][3]
      installer_entry.net_sniffer_mac_addresses[mac_address][3] = system.time()
      publish = None
      if not disconnected and momentary:
        if system.time() - last_seen < utils.read_duration(installer_entry.config['momentary_flood_time']):
          return
        else:
          publish = '@/detected'
      elif not disconnected and not was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address][2] = True
        publish = '@/connected'
      elif disconnected and was_connected:
        installer_entry.net_sniffer_mac_addresses[mac_address][2] = False
        publish = '@/disconnected'
      
      logging.debug("#{id}> {entry}: mac_address_detected, res: {publish}, mac: {mac_address}, connected: {connected}, ip_address: {ip_address}, momentary: {momentary}, was_connected: {was_connected}, last_seen: {last_seen}".format(id = installer_entry.id, entry = entry.id, publish = publish, mac_address = mac_address, connected = not disconnected, ip_address = ip_address, momentary = momentary, was_connected = was_connected, last_seen = last_seen))
      
      if publish:
        data = { 'mac_address': mac_address }
        if not disconnected and not ip_address and installer_entry.config['use_arp']:
          if 'arp_list' not in env:
            env['arp_list'] = _arp_list(installer_entry)
          if mac_address in env['arp_list']:
            ip_address = env['arp_list'][mac_address]
        if ip_address:
          data['ip_address'] = ip_address
        entry.publish(publish, data)

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
