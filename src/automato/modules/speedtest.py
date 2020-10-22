# require python3
# -*- coding: utf-8 -*-

import logging
import speedtest
import sys

from automato.core import system

# Configurazione di default (usata anche per la dichiarazione delle proprietà utilizzabili)
definition = {
  'config': {
    "server": 0, # 0 = detect best server, [id] use that server id
  },
  
  'description': _('Test internet connection speed via speedtest.net'),
  'topic_root': 'net',
  'notify_level': 'info',
  
  'publish': {
    './speedtest' : {
      'description': _('Test internet connection speed via speedtest.net'),
      'type': 'object',
      'notify': _('Internet speed test: download = {payload[download_mbps]} Mbps, upload = {payload[upload_mbps]} Mbps, ping = {payload[ping_ms]} ms via {payload[server_name]} (data: {payload[time!strftime(%Y-%m-%d %H:%M:%S)]})'),
      'qos': 1,
      'retain': True,
      'handler': 'publish',
      'events': {
        'netspeed': 'js:({"download": payload["download_bps"], "download:unit": "bps", "upload": payload["upload_bps"], "upload:unit": "bps", "ping": payload["ping_ms"], "ping:unit": "ms", "error": payload["error"]})',
        'clock': 'js:({"value": t(payload["time"])})',
      }
    }
  },
  'subscribe': {
    './speedtest/get': {
      'description': _('Get latest internet connection speed test done (if present)'),
      'response': [ './speedtest' ],
      'handler': 'on_speedtest_get',
    },
    './speedtest/run': {
      'description': _('Test internet connection speed via speedtest.net'),
      'publish': [ './speedtest' ],
    }
  }
}

def on_speedtest_get(entry, subscribed_message):
  if 'last_download' in entry.data:
    err = 'last_error' in entry.data and entry.data['last_error']
    entry.publish('./speedtest', {
      'download_bps': round(entry.data['last_download']) if not err else -1,
      'download_mbps': round(entry.data['last_download'] / (1024 * 1024), 1) if not err else -1,
      'upload_bps': round(entry.data['last_upload']) if not err else -1,
      'upload_mbps': round(entry.data['last_upload'] / (1024 * 1024), 1) if not err else -1,
      'ping_ms': entry.data['last_ping'] if not err else -1,
      'server_id': entry.data['last_server_id'] if not err else -1,
      'server_name': entry.data['last_server_name'] if not err else "",
      'error': entry.data['last_error'] if err else False,
      'time': entry.data['last_time']
    })
  else:
    entry.publish('', {'error': _('No previous test found')} )

def publish(entry, topic, definition):
  entry.data['last_time'] = system.time()
  try:
    logging.debug("#{id}> Starting speedtest...".format(id = entry.id))
    spdtest = speedtest.Speedtest()
    if entry.config['server'] > 0:
      servers = []
      servers.append(entry.config['server'])
      spdtest.get_servers(servers)
    spdtest.get_best_server()
    entry.data['last_download'] = spdtest.download()
    entry.data['last_upload'] = spdtest.upload()
    entry.data['last_ping'] = spdtest.results.ping
    entry.data['last_server_id'] = spdtest.results.server['id']
    entry.data['last_server_name'] = spdtest.results.server['name'] + ' (' + spdtest.results.server['sponsor'] + ')'
    entry.data['last_error'] = False
    logging.debug("#{id}> Speedtest done.".format(id = entry.id))
  except:
    logging.exception()
    entry.data['last_download'] = -1
    entry.data['last_upload'] = -1
    entry.data['last_ping'] = -1
    entry.data['last_server_id'] = -1
    entry.data['last_server_name'] = ""
    entry.data['last_error'] = str(sys.exc_info()[0]) + " - " + str(sys.exc_info()[1])
  on_speedtest_get(entry, topic, None, None)
