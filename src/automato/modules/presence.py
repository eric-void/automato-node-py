# require python3
# -*- coding: utf-8 -*-

import logging
import math

from automato.core import system
from automato.core import utils

"""
Detected presence of a person using two method
- connection of a person device, via events "connected": temporary events are ignored, and the device MUST send connected(value=1) when connected and connected(value=0) after disconnected. When disconnected, the presence is mantained for "presence_connection_after_disconnect" time
- location of a persona, via "location" events: a location event must be sent at least every "presence_location_session_duration" interval, or the presence is considered gone
"""

definition = {
  'description': _('List people connected to local wi-fi'),
  'install_on': {
    'presence_detect': () # Device declaring this properties will send a "presence-detected" event as soon as the device connects, or has a location event
  },
  'topic_root': 'home',
  'config': {
    #"presence_home_location": { "latitude": 0, "longitude": 0, "radius": 1000 },
    #"presence_home_regions": [ "home", "Casa" ],
    "presence_location_session_duration": "15m",
    "presence_connection_after_disconnect": "5m",
  },
  
  'publish': {
    './presence': {
      'type': 'object',
      'description': _('List people connected to local wi-fi'),
      'notify_handler': 'js:' +
        'let output = "";' +
        'for (name in payload["occupants"]) output += (output ? ", " :  "") + _(name + " since " + strftime(payload["occupants"][name]["firstseen"], "%H:%M:%S"));' +
        '(output ? _("People detected:") + " " + output : _("No people detected"));',
      'run_interval': 15,
      'handler': 'publish',
      'notify_level': 'debug',
      'events': {
        'clock': "js:({value: payload['time']})",
      }
    },
    './presence/in': {
      'description': _('A new occupant has been detected'),
      'type': 'string',
      'notify': _("{payload[name]} has entered"),
      'events': {
        'presence-in': "js:({ 'who': payload['name'], 'before_someone_inside': payload['before_someone_inside'], 'region': 'home' })",
        'clock': "js:({value: payload['time']})",
      }
    },
    './presence/out': {
      'description': _('An occupant has gone away'),
      'type': 'string',
      'notify': _("{payload[name]} has gone away"),
      'events': {
        'presence-out': "js:({ 'who': payload['name'], 'after_someone_inside': payload['after_someone_inside'], 'region': 'home' })",
        'clock': "js:({value: payload['time']})",
      }
    },
  },
  'subscribe': {
    './presence/get': {
      'description': _('List people connected to local wi-fi'),
      'response': [ './presence' ],
      'handler': 'publish_status'
    },
    'status': {
      'response': [ './presence' ],
      'handler': 'publish_status'
    }
  }
}

def entry_install(self_entry, entry, conf):
  entry.on("connected", lambda _entry, _eventname, _eventdata, caller, published_message: on_entry_event_connected(self_entry, _entry, _eventname, _eventdata, caller, published_message), None, self_entry)
  entry.on("location", lambda _entry, _eventname, _eventdata, caller, published_message: on_entry_event_location(self_entry, _entry, _eventname, _eventdata, caller, published_message), None, self_entry)

def init(entry):
  if not 'presence' in entry.data:
    entry.data['presence'] = {}
  if not presence_check_sessions(entry):
    exports(entry)
  
def exports(entry):
  entry.exports['presence_someone_inside'] = True if entry.data['presence'] else False
  entry.exports['presence_no_one_inside'] = not entry.exports['presence_someone_inside']

#def presence_occupants(entry):
#  return entry.config['occupants']

def presence_method_detected(entry, name, method, session_length = 0):
  now = system.time()
  session_length = utils.read_duration(session_length)
  someone_inside = True if entry.data['presence'] else False
  
  isnew = False
  if not name in entry.data['presence']:
    entry.data['presence'][name] = { 'firstseen': now, 'lastseen': now, 'methods': {} }
    isnew = True
  else:
    entry.data['presence'][name]['lastseen'] = now
  
  if not method in entry.data['presence'][name]['methods']:
    entry.data['presence'][name]['methods'][method] = { 'firstseen': now, 'lastseen': now, 'session_length': session_length }
  else:
    entry.data['presence'][name]['methods'][method]['lastseen'] = now
    if session_length > 0 and (entry.data['presence'][name]['methods'][method]['session_length'] == 0 or session_length < entry.data['presence'][name]['methods'][method]['session_length']):
      entry.data['presence'][name]['methods'][method]['session_length'] = session_length
    if 'delete_at' in entry.data['presence'][name]['methods'][method]:
      del entry.data['presence'][name]['methods'][method]['delete_at']
    
  if isnew:
    entry.publish('./presence/in', { 'name': name, 'before_someone_inside': someone_inside, 'method': method, 'time': now })
    exports(entry)
    publish_status(entry)
    logging.debug("{id}> {name} presence detected ({method} => {methods})".format(id = entry.id, name = name, method = method, methods = list(entry.data['presence'][name]['methods'])))
  else:
    logging.debug("{id}> {name} presence confirmed ({method} => {methods})".format(id = entry.id, name = name, method = method, methods = list(entry.data['presence'][name]['methods'])))

  return isnew

def presence_method_gone_away(entry, name, method, delete_after = 0):
  now = system.time()
  delete_after = utils.read_duration(delete_after)
  
  d = 0
  for pname, p in list(entry.data['presence'].items()):
    if pname == name:
      if method in entry.data['presence'][name]['methods']:
        if not delete_after:
          del entry.data['presence'][name]['methods'][method]
          if not entry.data['presence'][name]['methods']:
            del entry.data['presence'][name]
            entry.publish('./presence/out', { 'name': name, 'after_someone_inside': True if entry.data['presence'] else False, 'method': method, 'time': now })
            logging.debug("{id}> {name} gone away ({method})".format(id = entry.id, name = name, method = method))
            d = d + 1
          else:
            entry.data['presence'][name]['lastseen'] = now
        else:
          entry.data['presence'][name]['methods'][method]['delete_at'] = now + delete_after
  if d > 0:
    exports(entry)
  else:
    logging.debug("{id}> {name} removed method ({method} => {methods})".format(id = entry.id, name = name, method = method, methods = list(entry.data['presence'][name]['methods'])))
  return d > 0

def presence_check_sessions(entry):
  now = system.time()
  
  d = 0
  for name, p in list(entry.data['presence'].items()):
    for method, m in list(entry.data['presence'][name]['methods'].items()):
      if m['session_length'] > 0 and now - m['lastseen'] > m['session_length']:
        del entry.data['presence'][name]['methods'][method]
      if 'delete_at' in m and now > m['delete_at']:
        del entry.data['presence'][name]['methods'][method]
    if not entry.data['presence'][name]['methods']:
      del entry.data['presence'][name]
      entry.publish('./presence/out', { 'name': name, 'after_someone_inside': True if entry.data['presence'] else False, 'method': 'CHECK', 'time': now })
      logging.debug("{id}> {name} gone away (CHECK)".format(id = entry.id, name = name))
      d = d + 1
  if d > 0:
    exports(entry)
  return d > 0

def publish_status(entry, subscribed_message = None):
  if hasattr(entry.request, 'skip_publish_status') and entry.request.skip_publish_status:
    return
  
  res = {}
  for name, p in list(entry.data['presence'].items()):
    res[name] = { 'firstseen': p['firstseen'], 'lastseen': p['lastseen'], 'methods': list(p['methods']) }
  entry.publish('./presence', {"occupants": res, "time": system.time()})

def publish(entry, topic, definition):
  entry.request.skip_publish_status = True
  presence_check_sessions(entry)
  entry.request.skip_publish_status = False

  exports(entry)
  publish_status(entry)

def on_entry_event_connected(self_entry, entry, eventname, eventdata, caller, published_message):
  params = eventdata['params']
  if ("temporary" not in params or not params["temporary"]) and "presence_detect" in entry.definition:
    if params['value']:
      presence_method_detected(self_entry, entry.definition["presence_detect"], 'connected/' + entry.id + (('.' + str(params['key'])) if 'key' in params else ''))
    else:
      presence_method_gone_away(self_entry, entry.definition["presence_detect"], 'connected/' + entry.id + (('.' + str(params['key'])) if 'key' in params else ''), self_entry.config["presence_connection_after_disconnect"])

def on_entry_event_location(self_entry, entry, eventname, eventdata, caller, published_message):
  params = eventdata['params']
  if "presence_detect" in entry.definition:
    if 'regions' in params and 'presence_home_regions' in self_entry.config:
      if [v for v in params['regions'] if v in self_entry.config['presence_home_regions']]:
        presence_method_detected(self_entry, entry.definition["presence_detect"], 'location_region' + (('/' + params['source']) if 'source' in params else ''), utils.read_duration(self_entry.config["presence_location_session_duration"]))
    if 'latitude' in params and params['latitude'] > 0 and 'longitude' in params and params['longitude'] > 0 and "presence_home_location" in self_entry.config:
      distance = locations_distance((params['latitude'], params['longitude']), (self_entry.config["presence_home_location"]["latitude"], self_entry.config["presence_home_location"]["longitude"]))
      if distance < self_entry.config["presence_home_location"]["radius"] + (params['radius'] if 'radius' in params else 0):
        presence_method_detected(self_entry, entry.definition["presence_detect"], 'location' + (('/' + params['source']) if 'source' in params else ''), utils.read_duration(self_entry.config["presence_location_session_duration"]))

def locations_distance(origin, destination):
  """
  Calculate the Haversine distance.

  Parameters
  ----------
  origin : tuple of float
 (lat, long)
  destination : tuple of float
 (lat, long)

  Returns
  -------
  distance_in_meters : float

  Examples
  --------
  >>> origin = (48.1372, 11.5756)  # Munich
  >>> destination = (52.5186, 13.4083)  # Berlin
  >>> round(distance(origin, destination), 1)
  504.2
  """
  lat1, lon1 = origin
  lat2, lon2 = destination
  radius = 6371
  
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
 math.sin(dlon / 2) * math.sin(dlon / 2))
  c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
  return radius * c * 1000
