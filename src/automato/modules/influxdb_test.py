# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test

def test_init():
  test.add_node_config({
    "listen_all_events": True,
    "entries": [
      {
        "module": "influxdb",
        "config": {
          "influxdb_url": "https://eu-central-1-1.aws.cloud2.influxdata.com",
          "influxdb_org": "...",
          "influxdb_bucket": "...",
          "influxdb_token": "...",
          "influxdb_debug": True,
        },
      },
      
      {
        "item": "entry_a",
        "publish": {
          "@/event": {
            "type": "int",
            "events": {
              "test_event_a": "js:({ port: 'a', channel: 'ca', value: parseInt(payload) })",
            }
          }
        },
      },
      {
        "item": "entry_b",
        "publish": {
          "@/event": {
            "type": "int",
            "events": {
              "test_event_b": "js:({ port: 'b', value: parseInt(payload) })",
            }
          }
        },
      },
    ],
  })

def test_run(entries):
  test.assertPublish('s1', 'item/entry_a/event', 9, assertEvents = {'test_event_a': {'port': 'a', 'channel': 'ca', 'value': 9}})
  test.assertPublish('s2', 'item/entry_b/event', 10, assertEvents = {'test_event_b': {'port': 'b', 'value': 10}})
  entries['influxdb@TEST'].module.run(entries['influxdb@TEST'])
