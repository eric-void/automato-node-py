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
import signal
import importlib
# https://github.com/linjackson78/jstyleson
import jstyleson
import json

from automato.node import node_system


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

  # Container deployments can keep runtime data and logs on separate mounts,
  # without changing the location used for config includes and local modules.
  storage_dir = os.environ.get('AUTOMATO_STORAGE_DIR')
  if storage_dir:
    config['storage'] = storage_dir
  elif 'storage' not in config:
    config['storage'] = 'data'

  log_dir = os.environ.get('AUTOMATO_LOG_DIR')
  if log_dir:
    for key in ('log', 'error-log', 'messages-log', 'debug-log'):
      if config.get(key):
        config[key] = os.path.join(log_dir, os.path.basename(config[key]))

  if config.get('storage'):
    os.makedirs(config['storage'] if os.path.isabs(config['storage']) else os.path.join(config['base_path'], config['storage']), exist_ok=True)
  if log_dir:
    os.makedirs(log_dir, exist_ok=True)

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
    return boot_test()
  else:
    # SIGTERM (procd stop, docker stop, kill) is handled like ctrl+c: node_system.run() exits and destroy() stores entries data
    signal.signal(signal.SIGTERM, _on_sigterm)
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
  
def _on_sigterm(signum, frame):
  # Ignore further SIGTERMs, so they don't interrupt destroy()
  signal.signal(signal.SIGTERM, signal.SIG_IGN)
  raise KeyboardInterrupt()

def boot_test():
  global args, config
  from automato.core import test
  
  test_config = copy.deepcopy(config)
  
  test_config['name'] = 'TEST'
  node_system.node_name = test_config['name']
  node_system.system.on_message(test.on_all_mqtt_messages)
  # TODO config['storage'] = '...' # Sistema per non "sporcare" lo storage base
  args.reset = True
  
  node_system.system.test_mode = True
  
  # Test modules are imported only here (not needed, and not loaded, in normal node execution)
  test_names = [ 'system_test', 'node_system_test', 'nodes_test', 'health_test', 'toggle_test', 'shelly_test', 'tasmota_test', 'rf_listener_test', 'rf2mqtt_listener_test', 'location_owntracks_test', 'net_test', 'net_sniffer_scapy_test', 'net_sniffer_test', 'presence_test', 'owrtwifi2mqtt_test', 'scheduler_test', 'influxdb_test', 'nut_test', 'notifications_test', 'telegram_test' ] if args.test == "*" else [ args.test ]
  tests = [ importlib.import_module(('automato.core.' if name == 'system_test' else ('automato.node.' if name == 'node_system_test' else 'automato.modules.')) + name) for name in test_names ]
  
  success = True
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
    success = False
  except:
    logging.exception('system failure')
    success = False
  finally:
    destroy()
    
  return test.summary() and success

def boot_publish():
  global args
  broker = node_system.system.broker()
  broker.config({'publish_before_connection_policy': 'connect'})
  broker.publish(args.topic, args.payload, args.qos if args.qos != None else 0, args.retain if args.retain != None else False)
  destroy()
  
if __name__ == '__main__':
  sys.exit(0 if boot() else 1)

'''
# https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting
print(_("prova %s %s") % (args.config, "123"))
# https://docs.python.org/3/library/string.html#format-string-syntax
print(_("altra prova {a}, {b}").format(a=args.config, b=123))
'''
