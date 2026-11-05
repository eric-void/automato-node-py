# require python3
# -*- coding: utf-8 -*-

from automato.core import test

def test_init():
  # health is loaded before notifications (as in golconda): both subscribe to "#", so for each of them a specific rule and "#" match the same topic
  test.add_node_config({
    "entries": [
      { "module": "health" },
      { "module": "notifications" },
    ],
  })

def test_run(entries):
  # The specific rule (with "publish") must be chosen instead of "#", whatever the loading order of the entries
  test.assertPublish("history-get", "notifications/history/get", "", assertSubscribeSomePayload = {
    'notifications/history': { 'time': ('*', ) },
  })

  test.assertPublish("health-status-get", "health/status/get", "", assertSubscribeSomePayload = {
    'health/status': { 'notifications@TEST': ('*', ) },
  })
