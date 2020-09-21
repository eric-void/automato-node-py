# require python3
# -*- coding: utf-8 -*-

import logging
import json

# Install: sudo pip install pywebpush
from pywebpush import webpush

definition = {
  'config': {
    #'private_key': '...',
    #'mailto': '...',
  }
}

def notifications_subscribe(entry, driver, data, pattern):
  if driver == "webpush":
    return data

def notifications_matches(entry, driver, data_passed, data_saved, pattern):
  if driver == "webpush":
    data_passed = json.loads(data_passed)
    data_saved = json.loads(data_saved)
    return data_passed and data_saved and data_passed['keys']['auth'] == data_saved['keys']['auth']

def notifications_send(entry, driver, data, pattern, topic, message, notify_level):
  if driver == "webpush":
    logging.debug('#{id}> send webpush notification ({line}, {message})'.format(id = entry.id, line = data, message = message))
    try:
      webpush(json.loads(data), json.dumps(message), vapid_private_key=entry.config['private_key'], vapid_claims={"sub": "mailto:" + entry.config['mailto']})
    except:
      # TODO In caso di errore, se l'errore si ripete molte volte dovrebbe eliminare (o commentare) la riga dal file
      logging.exception('')
