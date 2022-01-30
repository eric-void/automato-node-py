# require python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import requests
import json
import http.client as httplib
import os
import subprocess

from automato.core import system
from automato.core import utils

definition = {
  'config': {
    'bandwidth-enabled': False,
    'wan-reconnect-enabled': False,
    
    "wan-connected-check-method": "http", # "ping" to use linux shell command ping, or "http" for a http head connection
    "wan-connected-check-ip": "8.8.8.8",
    "wan-connected-check-timeout": 2, # timeout in seconds. Can be a float number
    
    'external-ip-http-service': 'https://api.ipify.org', # Alternative: 'ifconfig.me'
    'wan-ip-detect-method': 'if', # Values: if, snmpwalk-command, module
    
    # CONFIG FOR 'if':
    'wan-ip-ifstatus-command': 'ifstatus wan',
    'wan-ip-ifrenew-command': 'ifdown wan; sleep 10; ifup wan; sleep 10; ifstatus wan',
    # NOTE if you're not running automato with root user, in some systems (ex: openwrt) commands used will not work. You should prefix "sudo" to them, and you should add this rule to sudoers file (edit it with "visudo"): automato ALL=(ALL) NOPASSWD: /sbin/ifstatus,/sbin/ifup,/sbin/ifdown
    #'wan-ip-ifstatus-command': 'sudo ifstatus wan',
    #'wan-ip-ifrenew-command': 'sudo ifdown wan; sleep 10; sudo ifup wan; sleep 10; sudo ifstatus wan',
    
    # CONFIG FOR 'wan-ip-detect-method': 'snmpwalk-command'
    'wan-ip-snmpwalk-command': 'snmpwalk -v 2c -c public 192.168.1.1 ipAdEntIfIndex',
    'wan-ip-exclude-ip-family': ['127', '192', '169', '10'],
    
    # CONFIG FOR 'wan-ip-detect-method': 'module'
    'wan-ip-module': 'net-router',
    'wan-ip-method': 'wan_ip_get',
    'wan-ip-reconnect-method': False,
    
    'bandwidth_proc_file': '/proc/net/dev',
    # Default: iface=brlan, down_col=9 (trasmitted), up_col=1 (received) | Alternative: iface=pppoe-wan, down_col=1 (received), up_col=9 (trasmitted)
    'bandwidth_interface': 'br-lan',
    'bandwidth_down_column': 9, # 1 = received, 9 = transmitted
    'bandwidth_up_column': 1,
    'bandwidth_check_time': '5s',
    'bandwidth_max_download_mbps': 1000,
    'bandwidth_max_upload_mbps': 1000,
  },

  'description': _('Network utilities'),
  'notify_level': 'info',
  'topic_root': 'net',
  'publish': {
    './wan-ip': {
      'type': 'string',
      'description': _('IP address of the wan connection'),
      'notify': _('Current wan ip is {payload[wan-ip]}'),
      'qos': 0,
      'retain': True,
      'handler': 'publish_wan_ip',
    },
    './external-ip': {
      'type': 'string',
      'description': _('IP address detected by internet'),
      'notify': _('Current external ip is {payload[external-ip]}'),
      'qos': 0,
      'retain': True,
      'handler': 'publish_external_ip',
    },
    './wan-reconnect/response': {
      'type': 'string',
    },
    './bandwidth': {
      'type': 'object',
      'description': _('Bandwidth used'),
      'notify': _('Bandwidth used: download = {payload[download_mbps]} Mbps, upload = {payload[upload_mbps]} Mbps (data: {payload[time!strftime(%Y-%m-%d %H:%M:%S)]})'),
      'qos': 1,
      'retain': True,
      'handler': 'publish_bandwidth',
      'run_interval': '5m',
      'events': {
        'bandwidth': 'js:({"type": "lan", "download": payload["download_bps"], "download:unit": "bps", "upload": payload["upload_bps"], "upload:unit": "bps", "error": payload["error"]})',
        'clock': 'js:({"value": t(payload["time"])})',
      }
    },
    './wan-connected': {
      'type': 'int',
      'description': _('Checks if internet connection is on'),
      'notify': _('Internet connection is {payload}'),
      'notify_change_level': 'warn',
      'payload': {
        'payload': {
          '0': { 'caption': 'OFF' },
          '1': { 'caption': 'on' },
        },
      },
      'run_interval': '5m',
      'run_throttle': 'force',
      'handler': 'publish_wan_connected',
      'events': {
        'connected': 'js:({"value": parseInt(payload), "port": "wan"})',
      }
    }
  },
  'subscribe': {
    './get-ips': {
      'description': _('Get IP addresses of the wan connection and detected by internet (if different, probabily you are behind a NAT)'),
      'response': [ './wan-ip', './external-ip' ],
      'handler': 'on_get_ips',
    },
    './wan-ip/get': {
      'description': _('Get IP address of the wan connection'),
      'response': [ './wan-ip' ],
      'publish': [ './wan-ip' ]
    },
    './external-ip/get': {
      'description': _('Get IP address detected by internet'),
      'response': [ './external-ip' ],
      'publish': [ './external-ip' ]
    },
    # TODO Available only if method = if or method = module and module supports it
    './wan-reconnect': {
      'description': _('Disconnect and reconnect WAN connection (usually to obtain a new IP address)'),
      'response': [ { 'count': 10, 'duration': 10 } ],
      'handler': 'on_wan_reconnect'
    },
    './bandwidth-get': {
      'description': _('Check for bandwidth used'),
      'response': [ './bandwidth' ],
      'publish': [ './bandwidth' ],
    }
  }
}

def on_get_ips(entry, subscribed_message):
  publish_external_ip(entry, entry.topic('./external-ip'), None)
  publish_wan_ip(entry, entry.topic('./wan-ip'), None)

def publish_external_ip(entry, topic_rule, topic_definition):
  entry.publish('./external-ip', { 'external-ip': requests.get(entry.config['external-ip-http-service']).text, 'time': system.time() })
  
def publish_wan_ip(entry, topic_rule, topic_definition):
  if entry.config['wan-ip-detect-method'] == 'if':
    try:
      output = subprocess.check_output(entry.config['wan-ip-ifstatus-command'], shell=True).decode("utf-8")
      if output:
        data = utils.json_import(output)
        if data and "ipv4-address" in data and "address" in data["ipv4-address"][0]:
          entry.publish('./wan-ip', { 'wan-ip': str(data["ipv4-address"][0]["address"]), 'time': system.time() })
        else:
          entry.publish('./wan-ip', { 'wan-ip': 'N/A', 'error': 'NOT-DETECTED', 'time': system.time() })
    except:
      logging.exception("#{id}> failed executing wan-ip-ifstatus-command".format(id = entry.id))
      entry.publish('./wan-ip', { 'wan-ip': 'N/A', 'error': 'NOT-DETECTED', 'time': system.time() })
    
  elif entry.config['wan-ip-detect-method'] == 'snmpwalk-command':
    ip = wan_ip_snmpwalk_command(entry)
    if ip is not None:
      entry.publish('./wan-ip', { 'wan-ip': ip, 'time': system.time() })
    else:
      entry.publish('./wan-ip', { 'wan-ip': 'N/A', 'error': 'NOT-DETECTED', 'time': system.time() })

  elif entry.config['wan-ip-detect-method'] == 'module':
    ip = system.entry_invoke(entry.config['wan-ip-module'], entry.config['wan-ip-method'], topic_rule, topic_definition)
    if ip:
      entry.publish('./wan-ip', { 'wan-ip': ip, 'time': system.time() })
    else:
      entry.publish('./wan-ip', { 'wan-ip': 'N/A', 'error': 'NOT-AVAILABLE', 'time': system.time() })
  else:
    entry.publish('./wan-ip', { 'wan-ip': 'N/A', 'error': 'UNSUPPORTED', 'time': system.time() })

def publish_wan_connected(entry, topic_rule, topic_definition):
  res = 0
  if entry.config['wan-connected-check-method'] == 'http':
    conn = httplib.HTTPSConnection(entry.config['wan-connected-check-ip'], timeout = entry.config['wan-connected-check-timeout'])
    try:
      conn.request("HEAD", "/")
      res = 1
    except Exception:
      res = 0
    finally:
      conn.close()

  elif entry.config['wan-connected-check-method'] == 'ping':
    #response = os.system("ping -c 1 -W " + str(entry.config['wan-connected-check-timeout']) + " " + entry.config['wan-connected-check-ip'] + " > /dev/null 2>&1")
    with open(os.devnull, 'wb') as devnull:
      response = subprocess.call(['ping', '-c',  '1', '-W', str(entry.config['wan-connected-check-timeout']), entry.config['wan-connected-check-ip']], stdout=devnull, stderr=devnull)
    
    if response == 0:
      res = 1

  entry.publish('', res)

def wan_ip_snmpwalk_command(entry):
  PIPE = subprocess.PIPE
  r = subprocess.Popen(entry.config['wan-ip-snmpwalk-command'], shell=True, stdout=PIPE, stderr=PIPE)
  result = r.communicate()[0]
  result = result.decode("utf-8")
  # import pdb; pdb.set_trace()
  for ip in result.split('\n'):
    if '=' in ip:
      parts = ip.split('=')[0]
      ipaddress = ".".join(parts.split('.')[1:])
      first_part = parts.split('.')[1]
      if first_part not in entry.config['wan-ip-exclude-ip-family']:
        return ipaddress
  return None

def on_wan_reconnect(entry, subscribed_message):
  if not entry.config['wan-reconnect-enabled']:
    return

  if entry.config['wan-ip-detect-method'] == 'if' and entry.config['wan-ip-ifrenew-command']:
    try:
      entry.publish('./wan-reconnect/response', "Reconnecting ...")
      output = subprocess.check_output(entry.config['wan-ip-ifrenew-command'], shell=True).decode("utf-8")
      if output:
        data = utils.json_import(output)
        if data:
          entry.publish('./wan-reconnect/response', "Reconnected")
          return
    except:
      logging.exception("Failed executing wan-ip-ifrenew-command")
    entry.publish('./wan-reconnect/response', "Failed reconnection")
  
  elif entry.config['wan-ip-detect-method'] == 'module' and entry.config['wan-ip-reconnect-method']:
    system.entry_invoke(entry.config['wan-ip-module'], entry.config['wan-ip-reconnect-method'], '', {})

  entry.publish('./wan-reconnect/response', "WAN reconnection unsupported")
  
def publish_bandwidth(entry, topic_rule, topic_definition):
  if not entry.config['bandwidth-enabled']:
    return
  
  data1 = _bandwidth_proc_net_dev_data(entry.config)
  if not data1:
    entry.publish('', { 'error': 'error getting bandwidth' })
    return
  
  seconds = utils.read_duration(entry.config['bandwidth_check_time'])
  system.sleep(seconds)
  data2 = _bandwidth_proc_net_dev_data(entry.config)
  down_bps = (data2['down'] - data1['down']) * 8 / seconds
  up_bps = (data2['up'] - data1['up']) * 8 / seconds
  if down_bps > entry.config['bandwidth_max_download_mbps'] * 1024 * 1024:
    down_bps = entry.config['bandwidth_max_download_mbps'] * 1024 * 1024
  if down_bps < 0:
    down_bps = 0
  if up_bps > entry.config['bandwidth_max_upload_mbps'] * 1024 * 1024:
    up_bps = entry.config['bandwidth_max_upload_mbps'] * 1024 * 1024
  if up_bps < 0:
    up_bps = 0
  
  entry.publish('', {
    'download_bps': round(down_bps),
    'download_mbps': round(down_bps / (1024 * 1024), 1),
    'upload_bps': round(up_bps),
    'upload_mbps': round(up_bps / (1024 * 1024), 1),
    'time': system.time(),
  })

def _bandwidth_proc_net_dev_data(config):
  data = {}
  with open(config['bandwidth_proc_file'], 'r') as f:
    output = f.read()
  for line in output.split("\n"):
    if line:
      line = line.split()
      if line[0] and line[0][-1] == ":":
        if line[0][0:-1] == config['bandwidth_interface']:
          return { 'up': int(line[config['bandwidth_up_column']]), 'down': int(line[config['bandwidth_down_column']])} # data extracted is in bytes
  return False
