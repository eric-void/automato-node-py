# require python3
# -*- coding: utf-8 -*-

# @see https://pypi.org/project/astral/ https://astral.readthedocs.io/en/stable/index.html https://github.com/sffjunkie/astral

import logging
import datetime

import astral
import astral.geocoder
import astral.location

from automato.core import system
from automato.core import utils

definition = {
  'config': {
    'city': 'Rome', # see https://astral.readthedocs.io/en/stable/index.html#cities
    # If your city is not supported, fill 'city' AND parameters below
    'latitude': None,
    'longitude': None,
    'timezone': None, # es: 'Europe/Rome',
    #'elevation': 0,
  },
  
  'description': _('Export times for various positions of the sun: dawn, sunrise, solar noon, sunset, dusk.'),
  'run_interval': "5m",
}

def init(entry):
  try:
    if entry.config['latitude'] is not None:
      entry.location = astral.location.Location(astral.LocationInfo(name=entry.config['city'], timezone=entry.config['timezone'], latitude=entry.config['latitude'], longitude=entry.config['longitude']))
    else:
      entry.location = astral.location.Location(astral.geocoder.lookup(entry.config['city'], astral.geocoder.database()))
  except:
    logging.exception("Location not configured correctly")
    entry.location = None
  entry.sun_updated = 0
  
  run(entry)

def run(entry):
  #logging.debug('#{id}> clock {topic}: {value}'.format(id = entry.id, topic = topic, value = system.time()))
  #entry.publish('', system.time())
  
  if entry.location:
    now = system.time()
    h = utils.hour(datetime.datetime.now())
    
    if datetime.date.today() != datetime.date.fromtimestamp(entry.sun_updated):
      sun = entry.location.sun(local = True)
      entry.exports['ts'] = now
      entry.exports['ts_dawn'] = int(sun['dawn'].timestamp())
      entry.exports['ts_sunrise'] = int(sun['sunrise'].timestamp())
      entry.exports['ts_noon'] = int(sun['noon'].timestamp())
      entry.exports['ts_sunset'] = int(sun['sunset'].timestamp())
      entry.exports['ts_dusk'] = int(sun['dusk'].timestamp())
      entry.exports['tsd'] = utils.read_duration
      
      entry.exports['h'] = h
      entry.exports['h_dawn'] = utils.hour(sun['dawn'])
      entry.exports['h_sunrise'] = utils.hour(sun['sunrise'])
      entry.exports['h_noon'] = utils.hour(sun['noon'])
      entry.exports['h_sunset'] = utils.hour(sun['sunset'])
      entry.exports['h_dusk'] = utils.hour(sun['dusk'])
      entry.exports['hour'] = utils.hour
      entry.exports['hd'] = utils.read_duration_hour
      
      entry.sun_updated = now
      logging.debug('#{id}> sun info for today: dawn={dawn}, sunrise={sunrise}, noon={noon}, sunset={sunset}, dusk={dusk}'.format(id = entry.id, dawn=sun['dawn'], sunrise=sun['sunrise'], noon=sun['noon'], sunset=sun['sunset'], dusk=sun['dusk']))
      
    entry.exports['is_day'] = h >= entry.exports['h_sunrise'] and h < entry.exports['h_sunset']
    entry.exports['is_night'] = not entry.exports['is_day']
