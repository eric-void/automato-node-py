# require python3
# -*- coding: utf-8 -*-

"""
A notification driver module for tests (implements the hooks used by the notifications module), driver name: "fake"
"""

definition = {}

sent = []

def notifications_subscribe(entry, driver, data, pattern):
  return data if driver == 'fake' else False

def notifications_matches(entry, driver, data, stored_data, pattern):
  return driver == 'fake' and data == stored_data

def notifications_send(entry, driver, data, pattern, topic, string, notify_level):
  if driver == 'fake':
    sent.append((data, topic, string, notify_level))
