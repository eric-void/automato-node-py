#!/usr/bin/python3
# require python3
# -*- coding: utf-8 -*-

import logging
import sys
import os
import threading
import importlib
import copy
import re
import datetime
from croniter import croniter

from automato.core import system
from automato.core import utils

from automato.node import storage

def boot(config):
  global node_name, node_config
  
  node_name = config['name']
  node_config = config
  system.set_config(config)
  system.boot()

_system_initialized = False

def init(_storage_fetch_data = True):
  global node_config, storage_fetch_data, threads, _system_initialized
  storage_fetch_data = _storage_fetch_data
  
  storage.init(os.path.join(node_config['base_path'], node_config['storage']))
  
  threads = {}
  
  system.on_entry_load(_on_system_entry_load)
  system.on_loaded(_on_system_entries_loaded)
  system.on_initialized(_on_system_entries_init)
  system.on_message(_on_system_message)
  system.init(_on_system_initialized)
  while not _system_initialized:
    system.sleep(.5)

def _on_system_initialized():
  global _system_initialized
  _system_initialized = True

def destroy():
  global threads, _system_initialized
  for t in threads:
    if threads[t] and threads[t].is_alive():
      threads[t].join()

  entries_invoke('destroy')
  storage.destroy()
  system.destroy()
  _system_initialized = False
  
#def system():
#  return system
  
def _on_system_entry_load(entry):
  global storage_fetch_data, node_name
  
  entry.is_local = entry.node_name == node_name
  # TODO data e timers possono essere usati anche su nodi remoti (lo fanno i moduli che aggiungono logiche, come health, ma è da verificare)
  entry.data = {}
  entry.data_lock = threading.Lock()
  entry.timers = {}
  if entry.is_local:
    entry.request = threading.local()
    entry.run_publish = run_publish_lambda(entry)
    entry.methods = {}
    entry.handlers = {}
    entry.handlers_add = entry_handlers_add_lambda(entry)

    if entry.type == 'module':
      entry.module = None
      name = entry.definition['module']
      try:
        entry.module = importlib.import_module("automato.modules." + name.replace("/", "."))
      except ModuleNotFoundError:
        try:
          entry.module = importlib.import_module(name.replace("/", "."))
        except ModuleNotFoundError:
          logging.error("module not found: %s" % (name))
      
      if entry.module and hasattr(entry.module, 'definition'):
        entry.definition = utils.dict_merge(entry.module.definition, entry.definition)

    storage.entry_install(storage, entry)
    if storage_fetch_data:
      storage.retrieveData(entry)
    
    # Caricamento completo definition
    # Deve essere dopo "storage" (cosi' il load può usare entry.data)
    if entry.type == 'module' and hasattr(entry.module, 'load'):
      loaded_definition = entry.module.load(entry)
      if loaded_definition:
        entry.definition = utils.dict_merge(entry.definition, loaded_definition)

def _on_system_entries_loaded(entries, initial = False):
  entries_invoke('system_loaded', entries)
  for e in entries:
    if entries[e].is_local and 'install_on' in entries[e].definition:
      for e1 in entries:
        conf = _entry_install_on_conf(entries[e], entries[e].definition['install_on'], entries[e1])
        if conf:
          entry_invoke(entries[e], 'entry_install', entries[e1], conf)

def _entry_install_on_conf(installer_entry, installer_conditions, entry):
  conf = {}
  for key in installer_conditions:
    value_match = installer_conditions[key]
    if key.startswith("/") and key.endswith("/"):
      for edef in entry.definition:
        m = re.search(key[1:-1], edef)
        if m and _entry_install_on_match(entry.definition[edef], value_match):
          conf[m.group(1) if len(m.groups()) > 0 else edef] = entry.definition[edef]
    elif key in entry.definition and _entry_install_on_match(entry.definition[key], value_match):
      conf[key] = entry.definition[key]
  return conf

# @see test._data_match() (uses same syntax)
def _entry_install_on_match(val, match):
  if isinstance(match, tuple):
    # ()
    if len(match) == 0:
      return True
    # ([val1, val2, ...])
    if len(match) == 2 and match[0] == 'in' and isinstance(match[1], list) and val in match[1]:
      return True
    return False
  return val == match

def _on_system_entries_init(entries):
  for e in entries:
    if entries[e].is_local:
      entry_invoke(entries[e], 'init')

  for e in entries:
    if entries[e].is_local:
      entry = entries[e]
      entry.subscription_handlers = {}

      for topic_rule in entry.definition['publish']:
        if 'run_on' in entry.definition['publish'][topic_rule]:
          for eventref in entry.definition['publish'][topic_rule]['run_on']:
            system.on_event(eventref, _on_run_on_event_lambda(entry, topic_rule), entry, 'run_on')

      for topic_rule in entry.definition['subscribe']:
        if 'handler' in entry.definition['subscribe'][topic_rule] or 'publish' in entry.definition['subscribe'][topic_rule]:
          if not topic_rule in entry.subscription_handlers:
            entry.subscription_handlers[topic_rule] = []
          if 'handler' in entry.definition['subscribe'][topic_rule]:
            handler = get_handler(entry, entry.definition['subscribe'][topic_rule]['handler'])
            if handler:
              entry.subscription_handlers[topic_rule].append([handler, entry])
          if 'publish' in entry.definition['subscribe'][topic_rule]:
            for p in entry.definition['subscribe'][topic_rule]['publish']:
              entry.subscription_handlers[topic_rule].append([_on_mqtt_subscribed_message_publish_lambda(entry, entry.topic(p)), entry])
      
      for eventref in entry.definition['on']:
        if 'handler' in entry.definition['on'][eventref]:
          system.on_event(eventref, entry.definition['on'][eventref]['handler'], entry, 'on')
        if 'do' in entry.definition['on'][eventref]:
          if isinstance(entry.definition['on'][eventref]['do'], str):
            system.on_event(eventref, _do_action_on_event_lambda(entry.definition['on'][eventref]['do'], if_event_not_match = entry.definition['on'][eventref]['do_if_event_not_match'] if 'do_if_event_not_match' in entry.definition['on'][eventref] else False), entry, 'on')
          else:
            for actionref in entry.definition['on'][eventref]['do']:
              system.on_event(eventref, _do_action_on_event_lambda(actionref, if_event_not_match = entry.definition['on'][eventref]['do_if_event_not_match'] if 'do_if_event_not_match' in entry.definition['on'][eventref] else False), entry, 'on')

  entries_invoke('system_initialized', entries)
  entries_invoke_threaded('system_metadata_change')  

def _on_system_message(message):
  for sm in message.subscribedMessages():
    if sm.entry.is_local:
      if sm.topic_rule in sm.entry.subscription_handlers:
        for record in sm.entry.subscription_handlers[sm.topic_rule]:
          system.entry_publish_current_default_topic(message.topic)
          # TODO 2020CHANGE non dovrebbe servire più current_*
          #record[1].request.current_action = 'subscribe'
          #record[1].request.current_message = message
          record[0](record[1], sm.copy())
          record[1].store_data()

def run():
  entries_invoke_threaded('start')
  
  try:
    while True:
      run_step()
      system.sleep(1)
      
  except KeyboardInterrupt:
    logging.info('keyboard interruption detected')
  except:
    logging.exception('system failure on run')

def run_step():
  _s = system._stats_start()
  now = system.time()
  clone_entry_names = list(system.entries().keys()) # I make a clone of entry names, because some handler could change "entries"
  for entry_id in clone_entry_names:
    entry = system.entry_get(entry_id)
    if entry and entry.is_local:
      if 'run_interval' in entry.definition and utils.read_duration(entry.definition['run_interval']) > 0 and entry_implements(entry_id, 'run') and ('last_run' not in entry.data or now - entry.data['last_run'] > utils.read_duration(entry.definition['run_interval'])):
        entry.data['last_run'] = now
        entry_invoke_threaded(entry_id, 'run')

      if 'run_cron' in entry.definition and entry_implements(entry_id, 'run'):
        if not ('cron' in entry.data and entry.data['cron'] == entry.definition['run_cron'] and 'next_run' in entry.data):
          if not croniter.is_valid(entry.definition['run_cron']):
            logging.error('#{id}> invalid cron rule: {cron}'.format(id = entry_id, cron = entry.definition['run_cron']))
            del entry.definition['run_cron']
          else:
            entry.data['cron'] = entry.definition['run_cron']
            #itr = croniter(entry.data['cron'], datetime.datetime.now().astimezone())
            itr = croniter(entry.data['cron'], datetime.datetime.fromtimestamp(now).astimezone())
            entry.data['next_run'] = itr.get_next()
        if 'cron' in entry.data and entry.data['cron'] == entry.definition['run_cron'] and 'next_run' in entry.data and now >= entry.data['next_run']:
          entry_invoke_threaded(entry_id, 'run')
          entry.data['last_run'] = now
          #itr = croniter(entry.data['cron'], datetime.datetime.now().astimezone())
          itr = croniter(entry.data['cron'], datetime.datetime.fromtimestamp(now).astimezone())
          entry.data['next_run'] = itr.get_next()

      if 'publish' in entry.definition:
        for topic_rule in entry.definition['publish']:
          if 'run_interval' in entry.definition['publish'][topic_rule] and utils.read_duration(entry.definition['publish'][topic_rule]['run_interval']) > 0 and ('last_run_' + topic_rule not in entry.data or now - entry.data['last_run_' + topic_rule] > utils.read_duration(entry.definition['publish'][topic_rule]['run_interval'])):
            entry.data['last_run_' + topic_rule] = now
            entry_invoke_publish(entry, topic_rule, entry.definition['publish'][topic_rule])
            
          if 'run_cron' in entry.definition['publish'][topic_rule]:
            if not ('cron_' + topic_rule in entry.data and entry.data['cron_' + topic_rule] == entry.definition['publish'][topic_rule]['run_cron'] and 'next_run_' + topic_rule in entry.data):
              if not croniter.is_valid(entry.definition['publish'][topic_rule]['run_cron']):
                logging.error('#{id}> invalid cron rule for publishing topic rule {topic_rule}: {cron}'.format(id = entry_id, topic_rule = topic_rule, cron = entry.definition['publish'][topic_rule]['run_cron']))
                del entry.definition['publish'][topic_rule]['run_cron']
              else:
                entry.data['cron_' + topic_rule] = entry.definition['publish'][topic_rule]['run_cron']
                #itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.now().astimezone())
                itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.fromtimestamp(now).astimezone())
                entry.data['next_run_' + topic_rule] = itr.get_next()
            if 'cron_' + topic_rule in entry.data and entry.data['cron_' + topic_rule] == entry.definition['publish'][topic_rule]['run_cron'] and 'next_run_' + topic_rule in entry.data and now >= entry.data['next_run_' + topic_rule]:
              entry.data['last_run_' + topic_rule] = now
              #itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.now().astimezone())
              itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.fromtimestamp(now).astimezone())
              entry.data['next_run_' + topic_rule] = itr.get_next()
              entry_invoke_publish(entry, topic_rule, entry.definition['publish'][topic_rule])
      
      _s1 = system._stats_start()
      entry.store_data(False)
      system._stats_end('node.run.store_data', _s1)
  system._stats_end('node.run', _s)

def _on_mqtt_subscribed_message_publish_lambda(_entry, _topic):
  return lambda entry, subscribed_message: _entry.run_publish(_topic)

def _on_run_on_event_lambda(_entry, _topic):
  return lambda entry, eventname, eventdata: _entry.run_publish(_topic)

def _do_action_on_event_lambda(actionref, if_event_not_match = False):
  return lambda entry, eventname, eventdata: system.do_action(actionref, eventdata['params'], if_event_not_match = if_event_not_match)






###############################################################################################################################################################
#
# HANDLERS & METHODS
#
###############################################################################################################################################################

def get_handler(entry, method):
  if not isinstance(method, str):
    return method
  
  if not entry.is_local:
    return None

  handlers = []
  if entry.type == 'module' and hasattr(entry.module, method):
    handlers.append(getattr(entry.module, method))
  if method in entry.methods:
    handlers.append(entry.methods[method])
  if method in entry.handlers and len(entry.handlers):
    handlers += list(entry.handlers[method].values())
    
  if not handlers:
    return None
  if len(handlers) == 1:
    return handlers[0]
  return lambda entry, *args, **kwargs: call_handlers(handlers, entry, *args, **kwargs)

def call_handlers(handlers, entry, *args, **kwargs):
  for h in handlers:
    ret = h(entry, *args, **kwargs)
  return ret;

def entry_handlers_add_lambda(entry):
  return lambda method, key, handler: entry_handlers_add(entry, method, key, handler)

def entry_handlers_add(entry, method, key, handler):
  if not method in entry.handlers:
    entry.handlers[method] = {}
  entry.handlers[method][key] = handler

def entry_invoke(entry, method, *args, **kwargs):
  if isinstance(entry, str):
    entry_str = entry
    entry = system.entry_get(entry_str)
    if not entry:
      logging.error("#system> skipped invocation of {method}: entry {entry} not found!".format(entry=entry_str, method=method))
      return False
  
  func = get_handler(entry, method)
  if func:
    logging.debug("#{entry}> invoking {method} ...".format(entry=entry.id, method=method))
    return func(entry, *args, **kwargs)

def entry_invoke_delayed(entry, timer_key, delay, method, *args, _pass_entry = True, **kwargs):
  if isinstance(entry, str):
    entry_str = entry
    entry = system.entry_get(entry_str)
    if not entry:
      logging.error("#system> skipped invocation of {method} (delayed): entry {entry} not found!".format(entry=entry_str, method=method))
      return False
  func = get_handler(entry, method)
  if func:
    cancel_entry_invoke_delayed(entry, timer_key)
    if _pass_entry:
      cargs = [entry] + list(args)
    else:
      cargs = list(args)
    entry.timers[timer_key] = threading.Timer(delay, func, args = cargs, kwargs = kwargs)
    entry.timers[timer_key].start()
    
def cancel_entry_invoke_delayed(entry, timer_key):
  if timer_key in entry.timers:
    entry.timers[timer_key].cancel()
    del entry.timers[timer_key]

def entries_invoke(method, *args, **kwargs):
  ret = None
  for entry_id, entry in system.entries().items():
    func = get_handler(entry, method)
    if func:
      logging.debug("#{entry}> invoking {method} ...".format(entry = entry_id, method = method))
      ret = func(entry, *args, **kwargs)
  return ret

# Parametri speciali: 
# - _thread_init: con una funzione, che viene lanciata all'inizio dal thread lanciato
# - _thread_key: aggiunge un pezzo alla chiave univoca del thread (ci può essere un solo thread in esecuzione per chiave, quindi impostarlo è un metodo per gestire meglio i limiti di una esecuzione alla volta)
# - _thread_mupliple: crea una chiave random per il thread (in modo che lo stesso method può essere lanciato più volte)
def entry_invoke_threaded(entry, method, *args, **kwargs):
  global threads
  if isinstance(entry, str):
    entry_str = entry
    entry = system.entry_get(entry_str)
    if not entry:
      logging.error("#system> skipped invocation of {method}: entry {entry} not found!".format(entry=entry_str, method=method))
      return False
    
  func = get_handler(entry, method)
  if func:
    thread_key = entry.id + '.' + method
    if '_thread_key' in kwargs:
      thread_key = thread_key + '.' + kwargs['_thread_key']
      del kwargs['_thread_key']
    if '_thread_multiple' in kwargs:
      thread_key = thread_key + '.' + str(random.randrange(1000000))
      del kwargs['_thread_multiple']
      
    if thread_key not in threads or threads[thread_key] is None or not threads[thread_key].is_alive():
      logging.debug("#{entry}> invoking {method} (threaded) ...".format(entry=entry.id, method=method))
      args = [func, method, entry.id, entry] + list(args);
      # https://docs.python.org/3/library/threading.html
      threads[thread_key] = threading.Thread(target=entry_invoke_threaded_wrapper, args=args, kwargs=kwargs, daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
      threads[thread_key].start()
    else:
      logging.warn("#{entry}> skipped invocation of {method}: already running!".format(entry=entry.id, method=method))

def entries_invoke_threaded(method, *args, **kwargs):
  global entries, threads
  base_args = list(args);
  for entry_id, entry in system.entries().items():
    func = get_handler(entry, method)
    if func:
      if (entry.id + '.' + method) not in threads or threads[entry.id + '.' + method] is None or not threads[entry.id + '.' + method].is_alive():
        logging.debug("#{entry}> invoking {method} (threaded) ...".format(entry = entry.id, method = method))
        # https://docs.python.org/3/library/threading.html
        cargs = [func, method, entry_id, entry] + list(args)
        threads[entry.id + '.' + method] = threading.Thread(target=entry_invoke_threaded_wrapper, args=cargs, kwargs=kwargs, daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
        threads[entry.id + '.' + method].start()
      else:
        logging.warn("#{entry}> skipped invocation of {method}: already running!".format(entry=entry.id, method=method))

# wrapper for threads invokation, used to catch and log exception
def entry_invoke_threaded_wrapper(func, method, entry_id, *args, **kwargs):
  _s = system._stats_start()
  try:
    if '_thread_init' in kwargs:
      f = kwargs['_thread_init']
      del kwargs['_thread_init']
      f(*args, **kwargs)
    func(*args, **kwargs)
  except:
    logging.exception("#{id}> exception in running method {method} (threaded)".format(id = entry_id, method = method))
  system._stats_end('entry_invoke:' + entry_id + '.' + method, _s)

def entry_implements(entry, method):
  if isinstance(entry, str):
    entry = system.entry_get(entry)

  return True if get_handler(entry, method) else False

entries_implementations = {}

def entries_implements(method):
  global entries_implementations
  if method not in entries_implementations:
    res = []
    for entry_id, entry in system.entries().items():
      if get_handler(entry, method):
        res.append((entry, getattr(entry.module, 'SYSTEM_HANDLER_ORDER_' + method, 0) if entry.type == 'module' else 0))
    entries_implementations[method] = [i[0] for i in sorted(res, key = lambda d: d[1])]
  return entries_implementations[method]

def run_publish_lambda(entry):
  return lambda topic_rule: run_publish(entry, topic_rule)

# Run all publish handlers in this entry definition about a specific topic
def run_publish(entry, topic_rule):
  defs = system.entries_publishers_of(entry.topic(topic_rule), strict_match = True)
  if defs and entry.id in defs:
    entry_invoke_publish(entry, defs[entry.id]['topic'], entry.definition['publish'][defs[entry.id]['topic']])

def entry_invoke_publish(entry, topic_rule, topic_definition):
  if 'handler' in topic_definition:
    entry_invoke_handler_threaded(entry, topic_definition['handler'], topic_rule, topic_rule, topic_definition, _thread_key = topic_rule, _thread_init = _entry_invoke_publish_thread_init)

def entry_invoke_publish_lambda(stopic_rule, stopic_definition):
  return lambda entry, topic, payload, matches: entry_invoke_publish(entry, stopic_rule, stopic_definition)

def _entry_invoke_publish_thread_init(entry, topic_rule, topic_definition):
  system.entry_publish_current_default_topic(topic_rule)
  # TODO 2020CHANGE Non serve più current_*
  #entry.request.current_action = 'publish'
  #entry.request.current_message = system.Message(topic, None)

def entry_invoke_handler_threaded(entry, handler_param, handler_name, *args, **kwargs):
  if isinstance(entry, str):
    entry = system.entry_get(entry)
  handler = get_handler(entry, handler_param) if entry else None
  if not handler:
    logging.error("#{entry}> handler not found: {handler}".format(entry = entry.id, handler = handler_param))
    
  thread_key = entry.id + '.' + handler_name
  if '_thread_key' in kwargs:
    thread_key = thread_key + '.' + kwargs['_thread_key']
    del kwargs['_thread_key']
  if '_thread_multiple' in kwargs:
    thread_key = thread_key + '.' + str(random.randrange(1000000))
    del kwargs['_thread_multiple']
    
  if thread_key not in threads or threads[thread_key] is None or not threads[thread_key].is_alive():
    logging.debug("#{entry}> invoking handler {method} (threaded) ...".format(entry = entry.id, method = handler_name))
    args = [handler, handler_name, entry.id, entry] + list(args);
    # https://docs.python.org/3/library/threading.html
    threads[thread_key] = threading.Thread(target=entry_invoke_threaded_wrapper, args=args, kwargs=kwargs, daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
    threads[thread_key].start()
  else:
    logging.warn("#{entry}> skipped invocation of {method}: already running!".format(entry = entry.id, method = handler_name))
