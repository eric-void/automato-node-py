# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

def test_init():
  test.add_node_config({
    "entries": [
      { "module": "location_owntracks" },
      {
        "caption": "Device",
        "device": "test",
        "owntracks_id": "xxx",
        "events_listen": [".location", ".clock"],
      },
    ]
  })

def test_run(entries):
  test.assertPublish('s1', 'owntracks/device/xxx', '{"_type":"location","acc":78,"alt":0,"batt":86,"conn":"w","inregions":["Region"],"lat":45.123,"lon":12.123,"tid":"ic","tst":1546871086,"vac":0,"vel":0}', 
    assertEvents = {
      'location': {'latitude': 45.123, 'longitude': 12.123, 'altitude': 0, 'radius': 78, 'radius:unit': 'm', 'regions': ['Region'], 'source': 'owntracks'},
      'clock': {'value': 1546871086}
    })
