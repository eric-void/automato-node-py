# require python3
# -*- coding: utf-8 -*-

import logging
import requests
import re

from automato.core import utils

definition = {
  'config': {
    'charset': 'utf-8',
    'url': '',
    'request_timeout': 10,
  },
  
  'description': _('Publish content by parsing an HTTP request'),
}
'''
definition['publish'] = {
  'topic' : {
    ...
    'url': '...', # url da richiedere. Se non specificato usa config['url']
    'publish': '...', # Espressione che definisce cosa pubblicare, in formato interno (vedi "decode_http_fetch_expression")
  }
}
'''

def load(entry):
  definition = {
    'publish': {},
    'subscribe': {}
  }
  if 'publish' in entry.definition:
    for topic in entry.definition['publish']:
      definition['publish'][topic] = {
        'handler': publish
      }
      definition['subscribe'][topic + '/get'] = {
        'description': entry.definition['publish'][topic]['description'] if 'description' in entry.definition['publish'][topic] else topic + ' getter',
        'response': [ topic ],
        'publish': [ topic ],
        'type': entry.definition['publish'][topic]['type'] if 'type' in entry.definition['publish'][topic] else 'unknown',
      }
  return definition

def publish(entry, topic, definition):
  logging.debug("Publishing topic %s" % (topic))
  url = definition['url'] if 'url' in definition else entry.config['url']
  content = False
  if url:
    try:
      page = requests.get(url, timeout = utils.read_duration(entry.config['request_timeout']))
      content = page.content.decode(entry.config['charset'])
    except:
      logging.exception("Failed fetching %s" % (url))
  if content and 'publish' in definition:
    v = decode_http_fetch_expression(entry, content, definition['publish'])
    if v:
      entry.publish('', v)
    else:
      logging.warning('HTTP fetch expression return empty value')

def decode_http_fetch_expression(entry, content, expression):
  if isinstance(expression, list) and expression[0] == ">":
    return decode_http_fetch_expression_script(entry, content, expression[1])
  elif isinstance(expression, list):
    ret = []
    for idx in expression:
      ret.append(decode_http_fetch_expression(entry, content, expression[idx]))
    return ret
  elif isinstance(expression, dict):
    ret = {}
    for idx in expression:
      ret[idx] = decode_http_fetch_expression(entry, content, expression[idx])
    return ret
  return expression

def decode_http_fetch_expression_script(entry, content, script):
  v = None
  if "regexp" in script:
    m = re.search(script["regexp"], content)
    if m:
      v = m[1]
  if "expr" in script and hasattr(entry, "script_eval"):
    v = entry.script_eval(script["expr"], v =  v, content = content)
  return v

#if __name__ == '__main__':
#  print(str(decode_http_fetch_expression('proza', {
#    "a": ['>', { "regexp": "o(.)a", "expr": "v + 'xax'"}],
#    "b": "b"
#  })))
