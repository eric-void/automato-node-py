# require python3
# -*- coding: utf-8 -*-

import logging
import datetime
import threading

from automato.core import system

# @see https://github.com/influxdata/influxdb-client-python
from influxdb_client import InfluxDBClient, WriteOptions
#from influxdb_client.client.write_api import SYNCHRONOUS

# TODO Al momento funziona solo con listen_all_events = TRUE

definition = {
  "config": {
    "influxdb_url": "",
    "influxdb_org": "",
    "influxdb_bucket": "",
    "influxdb_token": "",
    "influxdb_debug": False,
    
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
        installer_entry.influxdb_event_buffer[entry.id][eventname][k] = [ eventdata ]
      else:
        installer_entry.influxdb_event_buffer[entry.id][eventname][k].append(eventdata)

def run(entry):
  with entry.influxdb_event_buffer_lock:
    with InfluxDBClient(url = entry.config['influxdb_url'], token = entry.config['influxdb_token'], org = entry.config['influxdb_org'], debug = entry.config['influxdb_debug']) as _client:
      with _client.write_api(write_options=WriteOptions(batch_size=500, flush_interval=10_000, jitter_interval=2_000, retry_interval=5_000, max_retries=5, max_retry_delay=30_000, exponential_base = 2)) as _write_client:
        for entry_id in entry.influxdb_event_buffer:
          for eventname in entry.influxdb_event_buffer[entry_id]:
            for k in entry.influxdb_event_buffer[entry_id][eventname]:
              for d in entry.influxdb_event_buffer[entry_id][eventname][k]:
                # Keep only primitive values
                p = {x: d['changed_params'][x] for x in d['changed_params'] if isinstance(d['changed_params'][x], (int, str, bool, float))}
                if p:
                  _write_client.write(entry.config['influxdb_bucket'], entry.config['influxdb_org'], {
                    "measurement": entry_id + "." + eventname,
                    "tags": d['keys'],
                    "fields": p,
                    "time": datetime.datetime.utcfromtimestamp(d['time']),
                  })
              entry.influxdb_event_buffer[entry_id][eventname][k] = []




  

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
"""
