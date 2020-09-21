# require python3
# -*- coding: utf-8 -*-

import logging
import json

definition = {
  'config': {
  }
}

# Chiamato al subscribe, può verificare i dati passati (in data, in formato stringa) e eventualmente sostituirli (in modo da salvare per le chiamate successive dei dati diversi)
# @return i dati da salvare (in formato stringa)
def notifications_subscribe(entry, driver, data, pattern):
  if driver == "test":
    return data

# Usato per l'unsubscribe, verifica che i dati passati dalla chiamata mqtt e i dati di un record su db siano equivalenti (e quindi nel caso può eliminare tale record)
def notifications_matches(entry, driver, data_passed, data_saved, pattern):
  if driver == "webpush":
    data_passed = json.loads(data_passed)
    data_saved = json.loads(data_saved)
    return data_passed and data_saved and data_passed['keys']['auth'] == data_saved['keys']['auth']

# Effettua l'invio di una notifica (definitiva da topic + message)
def notifications_send(entry, driver, data, pattern, topic, message, notify_level):
  if driver == "webpush":
    sendto(data, message)
