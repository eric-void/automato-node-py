# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

# TODO test presence_connection_after_disconnect > 0

def test_init():
  test.add_node_config({
    "entries": [
      { 
        "module": "presence",
        "config": {
          "presence_home_location": { "latitude": 45.123, "longitude": 12.123, "radius": 500 },
          "presence_home_regions": [ "home", "Region" ],
          "presence_location_session_duration": 30,
          "presence_connection_after_disconnect": 0,
        },
        "publish": {
          './presence': {
            'run_interval': 2,
          }
        },
        "events_listen": [".presence-out", ".presence-in", "*.clock"],
      },
      {
        "module": "net_sniffer_scapy",
        "config": {
          "momentary_flood_time": 30,
          "connection_time": 30,
        }
      },
      { "module": "location_owntracks" },

      {
        "caption": "Device1",
        "device": "device1",
        "mac_address": "01:02:03:04:05",
        "owntracks_id": "xxx",
        "presence_detect": "mary",
      },
      {
        "caption": "Device2",
        "device": "device2",
        "mac_address": "0A:0B:0C:0D:0E",
        "presence_detect": "john",
      },
    ]
  }) 

def test_run(entries):
  #print("DIST: " + str(entries['presence@TEST'].module.locations_distance((45.123,12.123), (45.127,12.123))))
  
  # Mary enters via device
  t1 = system.time()
  test.assertx('t1', 
    assertSubscribeSomePayload = {
      'home/presence/in': {'name': 'mary', 'before_someone_inside': False, 'time': ('d', t1)},
      'home/presence': {'occupants': {'mary': {"firstseen": ('d', t1), "lastseen": ('d', t1), "methods": ["connected/device1@TEST"]}}, "time": ('d', t1)}, },
    assertNotification = ['info', 'mary has entered', 'home/presence/in' ],
      # ['debug', ('re', 'People detected:.*mary.*'), 'home/presence' ],
    assertEventsTopic = 'home/presence/in', assertEvents = {
      'presence-in': {'who': 'mary', 'before_someone_inside': False, 'region': 'home' }, 
      'clock': {'value': ('d', t1)}},
    assertExports = {'presence_someone_inside': True, 'presence_no_one_inside': False},
    wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '01:02:03:04:05')
  test.waitRunning()

  # ... via location region
  t2 = system.time()
  test.assertPublish('t2a', 'owntracks/device/xxx', '{"_type":"location","acc":78,"alt":0,"batt":86,"conn":"w","inregions":["Region"],"lat":35.123,"lon":22.123,"tid":"ic","tst":1546871086,"vac":0,"vel":0}', 
    assertEvents = {
      'location': {'latitude': 35.123, 'longitude': 22.123, 'altitude': 0, 'radius': 78, 'radius_unit': 'm', 'regions': ['Region'], 'source': 'owntracks'},
      'clock': {'value': 1546871086}
    },
    assertSubscribeNotReceive = ['home/presence/in'])

  test.assertx('t2b', 
    assertSubscribeSomePayload = {
      'home/presence': {'occupants': {'mary': {"firstseen": ('d', t1), "lastseen": ('d', t2), "methods": ["connected/device1@TEST", "location_region/owntracks"]}}, "time": ('d', system.time())}, },
    assertNotification = [ 'debug', ('re', 'People detected:.*mary.*'), 'home/presence' ],
    assertSubscribeNotReceive = ['home/presence/in'],
    wait = False)
  entries['presence@TEST'].module.publish(entries['presence@TEST'], 'home/presence', entries['presence@TEST'].definition['publish']['home/presence'])
  test.waitRunning()
  
  # ... via location position
  t3 = system.time()
  test.assertPublish('t3a', 'owntracks/device/xxx', '{"_type":"location","acc":78,"alt":0,"batt":86,"conn":"w","inregions":["Out"],"lat":45.127,"lon":12.123,"tid":"ic","tst":1546871086,"vac":0,"vel":0}', 
    assertSubscribeNotReceive = ['home/presence/in'])

  test.assertx('t3b', 
    assertSubscribeSomePayload = {
      'home/presence': {'occupants': {'mary': {"firstseen": ('d', t1), "lastseen": ('d', t3), "methods": ["connected/device1@TEST", "location_region/owntracks", "location/owntracks"]}}, "time": ('d', system.time())}, },
    assertNotification = [ 'debug', ('re', 'People detected:.*mary.*'), 'home/presence' ],
    assertSubscribeNotReceive = ['home/presence/in'],
    wait = False)
  entries['presence@TEST'].module.publish(entries['presence@TEST'], 'home/presence', entries['presence@TEST'].definition['publish']['home/presence'])
  test.waitRunning()
  
  # Also John enters via device
  t4 = system.time()
  test.assertx('t4', 
    assertSubscribeSomePayload = {
      'home/presence/in': {'name': 'john', 'before_someone_inside': True, 'time': ('d', t4)},
      'home/presence': {'occupants': {'mary': {"firstseen": ('d', t1), "lastseen": ('d', t3), "methods": ["connected/device1@TEST", "location_region/owntracks", "location/owntracks"]}, "john": {"firstseen": ('d', t4), "lastseen": ('d', t4), "methods": ["connected/device2@TEST"]}}, "time": ('d', t4)}, },
    assertNotification = [ 'info', 'john has entered', 'home/presence/in' ],
      # 'debug', ('re', 'People detected:.*mary.*john.*'), 'home/presence'
    assertEventsTopic = 'home/presence/in', assertEvents = {
      'presence-in': {'who': 'john', 'before_someone_inside': True, 'region': 'home' }, 
      'clock': {'value': ('d', t4)}},
    assertExports = {'presence_someone_inside': True, 'presence_no_one_inside': False},
    wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '0A:0B:0C:0D:0E')
  test.waitRunning()
  
  # Mary should exit if we wait connection_time/presence_location_session_duration
  system.time_offset(40)
  t5 = system.time()
  test.assertx('t5', 
    assertSubscribeSomePayload = {
      'home/presence/out': {'name': 'mary', 'after_someone_inside': True, 'time': ('d', t5)},
      'home/presence': {'occupants': {"john": {"firstseen": ('d', t4), "lastseen": ('d', t4), "methods": ["connected/device2@TEST"]}}, "time": ('d', t5)}, },
    assertNotification = [ 'info', 'mary has gone away', 'home/presence/out' ],
      # 'debug', ('re', 'People detected:.*john.*'), 'home/presence'
    assertEventsTopic = 'home/presence/out', assertEvents = {
      'presence-out': {'who': 'mary', 'after_someone_inside': True, 'region': 'home' }, 
      'clock': {'value': ('d', t5)}},
    wait = False)
  entries['net_sniffer_scapy@TEST'].module.sniff_callback(entries['net_sniffer_scapy@TEST'], '0A:0B:0C:0D:0E') # John should stay there
  entries['net_sniffer_scapy@TEST'].module.status_check(entries['net_sniffer_scapy@TEST'])
  system.sleep(1) # To ensure the execution of events callbacks
  entries['presence@TEST'].module.publish(entries['presence@TEST'], 'home/presence', entries['presence@TEST'].definition['publish']['home/presence'])
  test.waitRunning()

  # And now its time for John to exit too
  system.time_offset(40)
  t6 = system.time()
  test.assertx('t6', 
    assertSubscribeSomePayload = {
      'home/presence/out': {'name': 'john', 'after_someone_inside': False, 'time': ('d', t6)},
      'home/presence': {'occupants': {}, "time": ('d', t6)}, },
    assertNotification = [ 'info', 'john has gone away', 'home/presence/out' ],
      # 'debug', 'No people detected', 'home/presence'
    assertEventsTopic = 'home/presence/out', assertEvents = {
      'presence-out': {'who': 'john', 'after_someone_inside': False, 'region': 'home' }, 
      'clock': {'value': ('d', t6)}},
    assertExports = {'presence_someone_inside': False, 'presence_no_one_inside': True},
    wait = False)
  entries['net_sniffer_scapy@TEST'].module.status_check(entries['net_sniffer_scapy@TEST'])
  system.sleep(1) # To ensure the execution of events callbacks
  entries['presence@TEST'].module.publish(entries['presence@TEST'], 'home/presence', entries['presence@TEST'].definition['publish']['home/presence'])
  test.waitRunning()
