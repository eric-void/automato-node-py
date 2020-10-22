# require python3
# -*- coding: utf-8 -*-

"""
Examples:
2019-01-07 15:25:06 - received message owntracks/device/eric/event = b'{"_type":"transition","acc":77.6,"desc":"Casa","event":"enter","lat":44.2792575,"lon":11.9055914,"t":"l","tid":"ic","tst":1546871106,"wtst":1546866906}'
2019-01-07 15:25:07 - received message owntracks/device/eric = b'{"_type":"location","acc":78,"alt":0,"batt":86,"conn":"w","inregions":["Casa"],"lat":44.2792575,"lon":11.9055914,"tid":"ic","tst":1546871086,"vac":0,"vel":0}'
2019-01-07 15:28:48 - received message owntracks/device/eric/event = b'{"_type":"transition","acc":14.907,"desc":"Genitori","event":"leave","lat":44.2789083,"lon":11.9022358,"t":"l","tid":"ic","tst":1546871328,"wtst":1546866906}'
"""

import logging
from automato.core import system

definition = {
  'install_on': {
    'owntracks_id': (),
  }
}
  
def entry_install(installer_entry, entry, conf):
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(installer_entry.id)
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      'owntracks/device/' + conf['owntracks_id']: {
        'description': _('Owntracks app sent device location'),
        'type': 'object',
        'events': {
          'location': "js:(payload['_type'] == 'location' ? {latitude: payload['lat'], longitude: payload['lon'], altitude: payload['alt'], radius: payload['acc'], 'radius:unit': 'm', regions: 'inregions' in payload ? payload['inregions'] : [], source: 'owntracks'} : false)",
          'clock': "js:({value: payload['tst']})",
        }
      },
      'owntracks/device/' + conf['owntracks_id'] + '/event': {
        'description': _('Owntracks app sent device location event'),
        'type': 'object',
        'events': {
          'clock': "js:({value: payload['tst']})",
        }
      },
    }
  });
