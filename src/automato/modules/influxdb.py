# require python3
# -*- coding: utf-8 -*-

import logging
import datetime
import threading

from automato.core import system

# @see https://github.com/influxdata/influxdb-client-python https://influxdb-client.readthedocs.io/en/stable/api.html
from influxdb_client import InfluxDBClient, WriteOptions
#from influxdb_client.client.write_api import SYNCHRONOUS

# TODO Al momento funziona solo con listen_all_events = TRUE (oppure inserendo i listen degli eventi che si vogliono esportare)

definition = {
  "config": {
    "influxdb_url": "",
    "influxdb_org": "",
    "influxdb_bucket": "",
    "influxdb_token": "",
    "influxdb_debug": False,
    "influxdb_verify_ssl": False,
    
    "influxdb2_url": "",
    "influxdb2_org": "",
    "influxdb2_bucket": "",
    "influxdb2_token": "",
    "influxdb2_debug": False,
    "influxdb2_verify_ssl": False,

    "ignore_events": ["clock", "stats"],
  },
  "run_interval": 60,
}

def load(entry):
  entry.influxdb_event_buffer = {}
  entry.influxdb_event_buffer_lock = threading.Lock()
  system.on_all_events(lambda _entry, eventname, eventdata, caller, published_message: on_all_events(entry, _entry, eventname, eventdata, caller, published_message))

def on_all_events(installer_entry, entry, eventname, eventdata, caller, published_message):
  if eventname not in installer_entry.config['ignore_events']:
    with installer_entry.influxdb_event_buffer_lock:
      if entry.id not in installer_entry.influxdb_event_buffer:
        installer_entry.influxdb_event_buffer[entry.id] = {}
      if eventname not in installer_entry.influxdb_event_buffer[entry.id]:
        installer_entry.influxdb_event_buffer[entry.id][eventname] = {}
      k = system.entry_event_keys_index(eventdata['keys'])
      if k not in installer_entry.influxdb_event_buffer[entry.id][eventname]:
        installer_entry.influxdb_event_buffer[entry.id][eventname][k] = []
      installer_entry.influxdb_event_buffer[entry.id][eventname][k].append(eventdata)

def run(entry):
  with entry.influxdb_event_buffer_lock:
    if entry.config['influxdb_url']:
      _influxdb_write(entry, entry.config['influxdb_url'], entry.config['influxdb_token'], entry.config['influxdb_org'], entry.config['influxdb_bucket'], entry.config['influxdb_debug'], entry.config['influxdb_verify_ssl'], True)
    if entry.config['influxdb2_url']:
      _influxdb_write(entry, entry.config['influxdb2_url'], entry.config['influxdb2_token'], entry.config['influxdb2_org'], entry.config['influxdb2_bucket'], entry.config['influxdb2_debug'], entry.config['influxdb2_verify_ssl'], True)

    for entry_id in entry.influxdb_event_buffer:
      for eventname in entry.influxdb_event_buffer[entry_id]:
        for k in entry.influxdb_event_buffer[entry_id][eventname]:
          entry.influxdb_event_buffer[entry_id][eventname][k] = []

def _influxdb_write(entry, url, token, org, bucket, debug, verify_ssl, convert):
  with InfluxDBClient(url = url, token = token, org = org, debug = debug, verify_ssl = verify_ssl) as _client:
    with _client.write_api(write_options=WriteOptions(batch_size=500, flush_interval=10_000, jitter_interval=2_000, retry_interval=5_000, max_retries=2, max_retry_delay=30_000, exponential_base = 2)) as _write_client:
      for entry_id in entry.influxdb_event_buffer:
        for eventname in entry.influxdb_event_buffer[entry_id]:
          for k in entry.influxdb_event_buffer[entry_id][eventname]:
            for d in entry.influxdb_event_buffer[entry_id][eventname][k]:
              # Keep only eventdata of really published messages
              if d['time'] > 0:
                #params = d['changed_params'] if d['changed_params'] else d['params']
                params = d['params']
                # Keep only primitive values and convert values
                params = {x: _influxdb_type_conversion(params[x], x, d['params']) if convert else params[x] for x in params if x != "temporary" and (":" not in x) and isinstance(params[x], (int, str, bool, float))}
                # Use keys and "temporary" as tags
                tags = d['keys']
                if 'temporary' in d['params'] and d['params']['temporary']:
                  tags['temporary'] = True
                if params:
                  _write_client.write(bucket, org, {
                    "measurement": entry_id + "." + eventname,
                    "tags": tags,
                    "fields": params,
                    "time": datetime.datetime.utcfromtimestamp(d['time']),
                  })

def _influxdb_type_conversion(value, name, params):
  # If there is a type definition, enforce that one
  """
  if name + ":def" in params:
    if params[name + ":def"] == "int":
      try:
        return int(value)
      except:
        return 0
    if params[name + ":def"] == "float":
      try:
        return float(value)
      except:
        return 0
  """
  # Else, convert every number or boolean to float (to avoid type conflicts)
  if isinstance(value, (int, bool, float)):
    return float(value)
  return value

"""
Codice di test (occorre mettere SYNCHRONOUS altrimenti quando esce lo script non ha ancora inviato)

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

client = InfluxDBClient(url="https://eu-central-1-1.aws.cloud2.influxdata.com", token=token, debug = True)
write_api = client.write_api(write_options=SYNCHRONOUS)
t = datetime.utcfromtimestamp(time.time() - 3600)
#t = datetime.fromtimestamp(time.time(), timezone.utc)
point = Point("memx").tag("host", "host").field("x", 4.0).time(t)
write_api.write(bucket, org, point)


TROUBLESHOOTING:

Se da errori del tipo:
HTTP response body: {"code":"unprocessable entity","message":"failure writing points to database: partial write: field type conflict: input field \"value\" on measurement \"telemetry-bot@golconda.humidity\" is type float, already exists as type integer dropped=1"}

Significa che è cambiato il tipo di dato di uno degli eventi. (_influxdb_type_conversion cerca di evitarlo castando tutto a float, ma non sempre si riesce)
Nel caso va eliminato TUTTO il dato precedente con il comando:
influx delete --bucket #BUCKET# --predicate '_measurement="#NOME"' --start '1970-01-01T00:00:00Z' --stop '2030-12-31T00:00:00Z' -o #ORG#
Es: 
influx delete --bucket automato --predicate '_measurement="zigbee_sensor_x2_test@golconda.humidity"' --start '1970-01-01T00:00:00Z' --stop '2030-12-31T00:00:00Z' -o default
Per cancellare tutti i dati di un bucket:
influx delete --bucket #BUCKET# --start '1970-01-01T00:00:00Z' --stop '2030-12-31T00:00:00Z' -o #ORG#

"""

