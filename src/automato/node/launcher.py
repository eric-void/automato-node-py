#!/usr/bin/python3
# require python3
# -*- coding: utf-8 -*-

import logging
from logging.handlers import TimedRotatingFileHandler
import argparse
import gettext
import sys
import os
import glob
import copy
# https://github.com/linjackson78/jstyleson
import jstyleson
import json

from automato.node import node_system

from automato.core import test

from automato.core import system_test
from automato.node import node_system_test
from automato.modules import health_test
from automato.modules import toggle_test
from automato.modules import shelly_test
from automato.modules import tasmota_test
from automato.modules import rf_listener_test
from automato.modules import rf2mqtt_listener_test
from automato.modules import location_owntracks_test
from automato.modules import net_sniffer_scapy_test
from automato.modules import net_sniffer_iw_test
from automato.modules import presence_test
from automato.modules import nodes_test
from automato.modules import owrtwifi2mqtt_test
from automato.modules import scheduler_test

def init_base():
  global config, args
  config = {}
  args = None  

  if not init_config():
    return False
  # node_system.boot() calls automato.core.system.boot(), and this initialize logging envinronment
  node_system.boot(config)
  logging.info("\n--------------------------------------------------------------------------------\nStarting AUTOMATO node \"" + config['name'] + "\"\n--------------------------------------------------------------------------------");
  return True
  
def init_env():
  global args
  node_system.init(_storage_fetch_data = not args.reset)
  logging.info("\n--------------------------------------------------------------------------------\nInitialization done for AUTOMATO node \"" + config['name'] + "\"\n--------------------------------------------------------------------------------");

def destroy():
  node_system.destroy()
  logging.info("\n--------------------------------------------------------------------------------\nStopped AUTOMATO node \"" + config['name'] + "\"\n--------------------------------------------------------------------------------\n");

def init_config():
  global config, mqtt_config, args
  
  # Logger used for this phase, where full logging environment is not inizialized (i need config to initialize it!)
  h = logging.StreamHandler(sys.stdout)
  h.setFormatter(logging.Formatter('%(asctime)s - BOOT> %(message)s', datefmt = '%Y-%m-%d %H:%M:%S'))
  boot_logger = logging.getLogger("boot")
  boot_logger.propagate = False
  boot_logger.setLevel(logging.INFO)
  boot_logger.addHandler(h)
  
  # https://docs.python.org/2/library/argparse.html
  parser = argparse.ArgumentParser(description = 'Automato node')
  # parser.add_argument('event_dir', help = 'The directory in which the event files are stored')
  parser.add_argument('-c', '--config', metavar='file', help = 'Load the specified config file', default = '/etc/automato/automato.conf')
  parser.add_argument('-r', '--reset', action='store_true', required = False, help = 'Do not load module states (the same as starting from scratch)')
  parser.add_argument('--mqtt-client-id', dest='client_id', metavar='client-id', required = False, help = 'Use this client-id for mqtt connection')
  parser.add_argument('--mqtt-client-id-prefix', dest='client_id_prefix', metavar='prefix', required = False, help = 'The client-id for mqtt connection will be this value + a random string')
  parser.add_argument('-t', '--mqtt-topic', dest='topic', metavar='topic', required = False, help = 'This command will turn "sender" mode on: the node will connecto to mqtt broker, send this message, close the connection and exit. Use with --mqtt-payload, --mqtt-qos and --mqtt-retain')
  parser.add_argument('-p', '--mqtt-payload', dest='payload', metavar='payload', required = False, help = 'The payload to send in sender mode. See --mqtt-topic')
  parser.add_argument('-q', '--mqtt-qos', dest='qos', type=int, metavar='qos', required = False, help = 'The qos of the message to be sent in sender mode. See --mqtt-topic')
  parser.add_argument('--mqtt-retain', dest='retain', action='store_true', required = False, help = 'The retain flag of the message to be sent in sender mode. See --mqtt-topic')
  parser.add_argument('--test', dest='test', nargs="?", const="*", help = 'Start test suite (you can specifify a test id to execute only that one)')
  #action='store_true', 
  args = parser.parse_args()
  
  base_path = os.path.dirname(os.path.realpath(args.config))
  config = {}
  todo = [ args.config ]
  done = []
  
  while len(todo):
    f = todo.pop(0)
    if f and f not in done:
      done.append(f)
      try:
        boot_logger.info("Loaded config from file {file}". format(file = f))
        fconfig = jstyleson.load(open(f))
      except FileNotFoundError:
        boot_logger.error("File not found: %s" % (f))
        return False
      except json.decoder.JSONDecodeError as e:
        boot_logger.error("Error reading configuration file \"" + str(f) + "\": " + str(e))
        if hasattr(e, "lineno") and hasattr(e, "colno"):
          lineno = 0
          for line in e.doc.split("\n"):
            lineno += 1
            if lineno >= e.lineno - 3 and lineno <= e.lineno + 3:
              boot_logger.error(str(lineno).rjust(5, " ") + ": " + line.rstrip())
              if lineno == e.lineno:
                boot_logger.error("".rjust(len(str(lineno)), "!").rjust(5, " ") + ":" + "^".rjust(e.colno, " "))
        return False
      except:
        boot_logger.exception("Error reading configuration file")
        return False
    if 'include' in fconfig:
      if not isinstance(fconfig['include'], list):
        boot_logger.error("Error reading configuration file \"" + str(f) + "\": include must be a list of file specifications")
        return False
      
      for ff in fconfig['include']:
        l = glob.glob(os.path.realpath(os.path.dirname(os.path.realpath(f))) + '/' + ff)
        l.sort()
        for fff in l:
          if os.path.isfile(fff):
            todo.append(fff)
    # Merge strategy: first-level lists and dict will be merged together. Other levels or types will be overwritten.
    for k in fconfig:
      if isinstance(fconfig[k], list) and k in config and isinstance(config[k], list):
        config[k] = config[k] + fconfig[k]
      elif isinstance(fconfig[k], dict) and k in config and isinstance(config[k], dict):
        config[k] = {**config[k], **fconfig[k]}
      else:
        config[k] = fconfig[k]
  
  if 'name' not in config:
    config['name'] = os.uname().nodename
  if 'base_path' not in config:
    config['base_path'] = base_path
  if 'mqtt' not in config:
    config['mqtt'] = {}

  if args.client_id:
    config['mqtt']['client_id'] = args.client_id
    config['mqtt']['client_id_random_postfix'] = False
  if args.client_id_prefix:
    config['mqtt']['client_id'] = args.client_id_prefix
  if 'client_id' not in config['mqtt']:
    config['mqtt']['client_id'] = 'automato_' + config['name']
    
  if config['base_path'] not in sys.path:
    sys.path.insert(0, config['base_path'])
    
  return True

def boot():
  global args
  
  if not init_base():
    return False
  
  if args.topic:
    boot_publish()
  elif args.test:
    boot_test()
  else:
    init_env()
    try:
      node_system.run()
    except KeyboardInterrupt:
      logging.info('keyboard interrupt')
    except:
      logging.exception('system failure')
    finally:
      destroy()
  
  return True
  
def boot_test():
  global args, config
  
  test_config = copy.deepcopy(config)
  
  test_config['name'] = 'TEST'
  node_system.node_name = test_config['name']
  node_system.system.on_message(test.on_all_mqtt_messages)
  # TODO config['storage'] = '...' # Sistema per non "sporcare" lo storage base
  args.reset = True
  
  node_system.system.test_mode = True
  
  tests = [ system_test, node_system_test, nodes_test, health_test, toggle_test, shelly_test, tasmota_test, rf_listener_test, rf2mqtt_listener_test, location_owntracks_test, net_sniffer_scapy_test, net_sniffer_iw_test, presence_test, owrtwifi2mqtt_test, scheduler_test ] if args.test == "*" else [ globals()[args.test] ]
  
  try:
    for unit in tests:
      test_config['entries'] = {}
      test.init(test_config, unit)
      node_system.system.set_config(test_config)
      init_env()
      test.run()
      #while not test.finished:
      #  system.sleep(1)
      destroy()

  except KeyboardInterrupt:
    logging.info('keyboard interrupt')
  except:
    logging.exception('system failure')
  finally:
    destroy()
    
  test.summary()

def boot_publish():
  global args
  node_system().system().publish(args.topic, args.payload, args.qos if args.qos != None else 0, args.retain if args.retain != None else False)
  destroy()
  
if __name__ == '__main__':
  boot()

'''
# https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting
print(_("prova %s %s") % (args.config, "123"))
# https://docs.python.org/3/library/string.html#format-string-syntax
print(_("altra prova {a}, {b}").format(a=args.config, b=123))
'''
