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
  system.on_entry_load_batch(_on_system_entry_load_batch)
  system.on_entry_init(_on_system_entry_init)
  system.on_entry_init_batch(_on_system_entry_init_batch)
  system.on_entry_unload(_on_system_entry_unload)
  system.on_entries_change(_on_system_entries_change)
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

  clone_entry_names = list(system.entries().keys()) # I make a clone of entry names, because some handler could change "entries"
  for entry_id in clone_entry_names:
    entry = system.entry_get(entry_id)
    if entry and entry.is_local:
      entry.store_data()
  
  storage.destroy()
  system.destroy()
  _system_initialized = False

def _on_system_entry_load(entry):
  global storage_fetch_data #, node_name

  #entry.is_local = entry.node_name == node_name
  # TODO data and timers can be used also by remote nodes (modules like "health" uses them, VERIFY THIS!)
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
          logging.warning("module not found: %s" % (name))
      
      if entry.module and hasattr(entry.module, 'definition'):
        entry.definition = utils.dict_merge(entry.module.definition, entry.definition)

    storage.entry_install(storage, entry)
    if storage_fetch_data:
      storage.retrieveData(entry)
  
    # calls load hook
    # MUST be after storage init (entry.data must be available in next calls)
    if entry.type == 'module' and hasattr(entry.module, 'load'):
      loaded_definition = entry.module.load(entry)
      if loaded_definition:
        entry.definition = utils.dict_merge(entry.definition, loaded_definition)

    entry._refresh_definition_based_properties()

def _on_system_entry_load_batch(loading_defs):
  # @see system.on_entry_load_batch for docs
  
  # reloading check
  previously_loaded_entries_to_reload = []
  for entry in loading_defs.values():
    # if this entry define an "entry_load" hook, all running entries should be reloaded
    if entry.type == 'module' and has_handler(entry, 'entry_load'):
      for other_entry in system.entries().values():
        if other_entry.loaded and other_entry.id not in previously_loaded_entries_to_reload:
          previously_loaded_entries_to_reload.append(other_entry.id)
    else:
      # if this entry define an "entry_install" hook, all running entries matching install rules should be reloaded
      if entry.type == 'module' and 'install_on' in entry.definition:
        for other_entry in system.entries().values():
          if other_entry.loaded and other_entry.id not in previously_loaded_entries_to_reload:
            conf = _entry_install_on_conf(entry, entry.definition['install_on'], other_entry)
            if conf:
              previously_loaded_entries_to_reload.append(other_entry.id)
  
  for entry in loading_defs.values():
    # entry_load: calls previously_loaded.entry_load(entry). I process loaded in the past and initialized entries, and loading now entries, but only already called by this callback
    for previously_loaded_entry in system.entries().values():
      if previously_loaded_entry.is_local and previously_loaded_entry.id not in loading_defs and previously_loaded_entry.id not in previously_loaded_entries_to_reload:
        entry_invoke(previously_loaded_entry, 'entry_load', entry)
        
    # entry_load on currently loading entries and initialized ones: calls entry.entry_load(other_entry). I process all entries loading now, even if already processed by this callback. I consider loaded and initialized entries only if NOT in previously_loaded_entries_to_reload (they should be reloaded, it's useless to call methods on them).
    if entry.type == 'module' and has_handler(entry, 'entry_load'):
      for other_entry in system.entries().values():
        if other_entry.id != entry.id and (not other_entry.loaded or other_entry.id not in previously_loaded_entries_to_reload):
          # WARN: Usually ALL previously loaded and initialized entries should be in previously_loaded_entries_to_reload (for the rule above, if i'm loading and entry with entry_load method, this invalidates all previously loaded entries), so the condition below should skip all of these entries. The only exception happens if the presence of "entry_load" method changes between the code above and the code below (for example, the "entry_load" method is defined by the scripting module via scripting.entry_load)
          # In this situation, entry.entry_load(other_entry) is called, even if it's already called before (by a previous "entry" version). We print a warning about this. (It's not convenient to invalidate the entry now)
          if other_entry.loaded and other_entry.id not in previously_loaded_entries_to_reload:
            logging.warn("NODE_SYSTEM> Calling {eid}.entry_load on {eid2}, but {eid2} has not been reloaded (during the reloading check {eid}.entry_load was not present). So it's possibile {eid}.entry_load has been called before on {eid2} (by a previous {eid} version).".format(eid = entry.id, eid2 = other_entry.id))
          entry_invoke(entry, 'entry_load', other_entry)

  for entry in loading_defs.values():
    # entry_install: calls previously_loaded.entry_install(entry). I process loaded in the past and initialized entries, and loading now entries, but only already called by this callback
    for previously_loaded_entry in system.entries().values():
      if previously_loaded_entry.is_local and previously_loaded_entry.id not in loading_defs and previously_loaded_entry.id not in previously_loaded_entries_to_reload:
        if 'install_on' in previously_loaded_entry.definition:
          conf = _entry_install_on_conf(previously_loaded_entry, previously_loaded_entry.definition['install_on'], entry)
          if conf:
            entry_invoke(previously_loaded_entry, 'entry_install', entry, conf)
    
    # entry_install on currently loading entries and initialized ones: calls entry.entry_install(other_entry). I process all entries loading now, even if already processed by this callback. I consider loaded and initialized entries only if NOT in previously_loaded_entries_to_reload (they should be reloaded, it's useless to call methods on them).
    if entry.type == 'module' and 'install_on' in entry.definition:
      for other_entry in system.entries().values():
        if other_entry.id != entry.id and (not other_entry.loaded or other_entry.id not in previously_loaded_entries_to_reload):
          conf = _entry_install_on_conf(entry, entry.definition['install_on'], other_entry)
          if conf:
            # WARN: Usually ALL previously loaded and initialized entries (matching the install_on rule) should be in previously_loaded_entries_to_reload (for the rule above), so the condition below should skip all of these entries. The only exception happens if the presence of "entry_install" method, or the install_rule, changes between the code above and the code below (for example, the "entry_install" method is defined by the scripting module via scripting.entry_load)
            # In this situation, entry.entry_install(other_entry) is called, even if it's already called before (by a previous "entry" version). We print a warning about this. (It's not convenient to invalidate the entry now)
            if other_entry.loaded and other_entry.id not in previously_loaded_entries_to_reload:
              logging.warn("NODE_SYSTEM> Calling {eid}.entry_install on {eid2}, but {eid2} has not been reloaded (during the reloading check {eid}.entry_install was not present or the install rule was different). So it's possibile {eid}.entry_install has been called before on {eid2} (by a previous {eid} version).".format(eid = entry.id, eid2 = other_entry.id))
            entry_invoke(entry, 'entry_install', other_entry, conf)

  return previously_loaded_entries_to_reload

def _on_system_entry_init(entry):
  if entry.is_local:
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
    
    entry_invoke(entry, 'init')

def _on_system_entry_init_batch(entries):
  for entry in entries.values():
    # calls *.entry_init(entry)
    entries_invoke('entry_init', entry, _skip_entry_id = entry.id)
    
    # calls entry.entry_init(*): if this entry define an "entry_init" hook, all previous entries should be passed to it
    if entry.is_local and entry.type == 'module' and hasattr(entry.module, 'entry_init'):
      for eid, eentry in system.entries().items():
        if eid != entry.id:
          entry.module.entry_init(entry, eentry)

def _on_system_entry_unload(entry):
  if entry.is_local:
    entry.store_data()
    storage.entry_uninstall(storage, entry)
    entries_invoke('entry_unload', entry);
  
    for installer_entry_id, installer_entry in system.entries().items():
      if installer_entry.is_local and 'install_on' in installer_entry.definition:
        conf = _entry_install_on_conf(installer_entry, installer_entry.definition['install_on'], entry)
        if conf:
          entry_invoke(installer_entry, 'entry_uninstall', entry, conf)
    
    # if this entry define an "entry_unload" hook, all previous entries should be passed to it
    if entry.type == 'module' and hasattr(entry.module, 'entry_unload'):
      for eid, eentry in system.entries().items():
        entry.module.entry_unload(entry, eentry)
    # if this entry define an "entry_uninstall" hook, all previous entries matching install rules should be passed to it
    if entry.type == 'module' and hasattr(entry.module, 'entry_uninstall'):
      for eid, eentry in system.entries().items():
        conf = _entry_install_on_conf(entry, entry.definition['install_on'], eentry)
        if conf:
          entry.module.entry_uninstall(entry, eentry, conf)
    
    entry_invoke(entry, 'destroy')
  
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

def _on_system_entries_change(entry_ids_loaded, entry_ids_unloaded):
  """
  global system_entries_to_reload
  antiflood = 5
  while system_entries_to_reload and antiflood > 0:
    logging.warn("NODE_SYSTEM> An entry just loaded need to install over previous entries, reloading them: {e}".format(e = system_entries_to_reload))
    system_entries_to_reload2 = system_entries_to_reload
    system_entries_to_reload = []
    for entry_id in system_entries_to_reload2:
      system.entry_reload(entry_id, call_on_entries_change = False)
    antiflood = antiflood - 1
    if antiflood == 0:
      logging.error("ANTIFLOOD!")
  """
  entries_invoke_threaded('system_entries_change', entry_ids_loaded, entry_ids_unloaded)

def _on_system_message(message):
  for sm in message.subscribedMessages():
    if sm.entry.is_local:
      if sm.topic_rule in sm.entry.subscription_handlers:
        for record in sm.entry.subscription_handlers[sm.topic_rule]:
          system.entry_publish_current_default_topic(message.topic)
          # TODO 2020CHANGE non dovrebbe servire più current_*
          #record[1].request.current_action = 'subscribe'
          #record[1].request.current_message = message
          _s = system._stats_start()
          record[0](record[1], sm.copy())
          #20201012 Disabled, too time consuming (and no store_data() is present for a lot of other conditions like event listeners and so on). store_data is done every seconds by run()>run_step()
          #record[1].store_data()
          system._stats_end('subscribe_handler(' + sm.topic_rule + '@' + sm.entry.id + ')', _s)

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


def load_level():
  """
  @return load_level. 0 = low, 1 = high / 2 = very high (follow definition['run_throttle'] or auto skip/wait based on timing), critical (skip everything, except "force" transformed to "wait")
  """
  delay = system.broker().queueDelay();
  return 0 if delay < 1000 else (1 if delay < 5000 else (2 if delay < 20000 else 3))

def _run_step_throttle_policy(entry, definition, topic_rule = None):
  """
  Return throttle policy for a specific execution handler ("run" method or "topic_rule" publisher)
  """
  level = load_level()
  throttle_policy = 'force' if level <= 0 else ('skip' if level >= 3 else (definition['run_throttle'] if 'run_thottle' in definition else ('skip' if entry.data['next_run' + (('_' + topic_rule) if topic_rule else '')] - entry.data['last_run' + (('_' + topic_rule) if topic_rule else '')] < 3600 else 'wait')))
  
  if isinstance(throttle_policy, list):
    throttle_policy = throttle_policy[0 if level == 1 else 1]
  if level >= 3:
    throttle_policy = 'skip' if throttle_policy != 'force' else 'wait'
  return throttle_policy

def run_step():
  _s = system._stats_start()
  now = system.time()
  clone_entry_names = list(system.entries().keys()) # I make a clone of entry names, because some handler could change "entries"
  for entry_id in clone_entry_names:
    entry = system.entry_get(entry_id)
    if entry and entry.is_local:
      # Initialization / check configuration validity
      if 'run_interval' in entry.definition and utils.read_duration(entry.definition['run_interval']) <= 0:
        logging.error('#{id}> invalid run_interval: {run_interval}'.format(id = entry_id, run_interval = entry.definition['run_interval']))
        del entry.definition['run_interval']
      if 'run_cron' in entry.definition and entry_implements(entry_id, 'run') and not ('cron' in entry.data and entry.data['cron'] == entry.definition['run_cron'] and 'next_run' in entry.data):
        if not croniter.is_valid(entry.definition['run_cron']):
          logging.error('#{id}> invalid cron rule: {cron}'.format(id = entry_id, cron = entry.definition['run_cron']))
          del entry.definition['run_cron']
        else:
          entry.data['cron'] = entry.definition['run_cron']
          #itr = croniter(entry.data['cron'], datetime.datetime.now().astimezone())
          itr = croniter(entry.data['cron'], datetime.datetime.fromtimestamp(now).astimezone())
          entry.data['next_run'] = itr.get_next()
      if 'last_run' not in entry.data:
        entry.data['last_run'] = 0
      if 'next_run' not in entry.data:
        entry.data['next_run'] = now
      
      if entry_implements(entry_id, 'run') and ('run_interval' in entry.definition or 'run_cron' in entry.definition):
        throttle_policy = _run_step_throttle_policy(entry, entry.definition, None)
        
        if now >= entry.data['next_run']:
          if throttle_policy == 'force' or throttle_policy == 'skip' or (isinstance(throttle_policy, int) and now - entry.data['last_run'] > throttle_policy):
            entry.data['last_run'] = now
            if 'run_interval' in entry.definition:
              entry.data['next_run'] = now + utils.read_duration(entry.definition['run_interval'])
            else:
              #itr = croniter(entry.data['cron'], datetime.datetime.now().astimezone())
              itr = croniter(entry.data['cron'], datetime.datetime.fromtimestamp(now).astimezone())
              entry.data['next_run'] = itr.get_next()

            if throttle_policy != 'skip':
              entry_invoke_threaded(entry_id, 'run')
            else:
              logging.debug("#{entry}> system overload ({load}), skipped invokation of {method}.".format(entry=entry.id, load = load_level, method='run'))
          else:
            logging.debug("#{entry}> system overload ({load}), postponed invokation of {method}.".format(entry=entry.id, load = load_level, method='run'))

      if 'publish' in entry.definition:
        for topic_rule in entry.definition['publish']:
          # Initialization / check configuration validity
          if 'run_interval' in entry.definition['publish'][topic_rule] and utils.read_duration(entry.definition['publish'][topic_rule]['run_interval']) <= 0:
            logging.error('#{id}> invalid run_interval for topic rule {topic_rule}: {run_interval}'.format(id = entry_id, topic_rule = topic_rule, run_interval = entry.definition['publish'][topic_rule]['run_interval']))
            del entry.definition['publish'][topic_rule]['run_interval']
          if 'run_cron' in entry.definition['publish'][topic_rule] and not ('cron_' + topic_rule in entry.data and entry.data['cron_' + topic_rule] == entry.definition['publish'][topic_rule]['run_cron'] and 'next_run_' + topic_rule in entry.data):
            if not croniter.is_valid(entry.definition['publish'][topic_rule]['run_cron']):
              logging.error('#{id}> invalid cron rule for publishing topic rule {topic_rule}: {cron}'.format(id = entry_id, topic_rule = topic_rule, cron = entry.definition['publish'][topic_rule]['run_cron']))
              del entry.definition['publish'][topic_rule]['run_cron']
            else:
              entry.data['cron_' + topic_rule] = entry.definition['publish'][topic_rule]['run_cron']
              #itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.now().astimezone())
              itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.fromtimestamp(now).astimezone())
              entry.data['next_run_' + topic_rule] = itr.get_next()
          if 'last_run_' + topic_rule not in entry.data:
            entry.data['last_run_' + topic_rule] = 0
          if 'next_run_' + topic_rule not in entry.data:
            entry.data['next_run_' + topic_rule] = now
          
          throttle_policy = _run_step_throttle_policy(entry, entry.definition['publish'][topic_rule], topic_rule)
          
          if now >= entry.data['next_run_' + topic_rule]:
            if throttle_policy == 'force' or throttle_policy == 'skip' or (isinstance(throttle_policy, int) and now - entry.data['last_run_' + topic_rule] > throttle_policy):
              entry.data['last_run_' + topic_rule] = now
              if 'run_interval' in entry.definition['publish'][topic_rule]:
                entry.data['next_run_' + topic_rule] = now + utils.read_duration(entry.definition['publish'][topic_rule]['run_interval'])
              else:
                #itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.now().astimezone())
                itr = croniter(entry.data['cron_' + topic_rule], datetime.datetime.fromtimestamp(now).astimezone())
                entry.data['next_run_' + topic_rule] = itr.get_next()
              
              if throttle_policy != 'skip':
                entry_invoke_publish(entry, topic_rule, entry.definition['publish'][topic_rule])
              else:
                logging.debug("#{entry}> system overload ({load}), skipped invokation of publish {method}.".format(entry=entry.id, load = load_level, method=topic_rule))
            else:
              logging.debug("#{entry}> system overload ({load}), postponed invokation of publish {method}.".format(entry=entry.id, load = load_level, method=topic_rule))

      _s1 = system._stats_start()
      entry.store_data(False)
      system._stats_end('node.run.store_data', _s1)
  system._stats_end('node.run', _s)

def _on_mqtt_subscribed_message_publish_lambda(_entry, _topic):
  return lambda entry, subscribed_message: _entry.run_publish(_topic)

def _on_run_on_event_lambda(_entry, _topic):
  return lambda entry, eventname, eventdata, caller, published_message: _entry.run_publish(_topic)

def _do_action_on_event_lambda(actionref, if_event_not_match = False):
  return lambda entry, eventname, eventdata, caller, published_message: system.do_action(actionref, eventdata['params'], if_event_not_match = if_event_not_match)






###############################################################################################################################################################
#
# HANDLERS & METHODS
#
###############################################################################################################################################################

def has_handler(entry, method):
  if not isinstance(method, str):
    return True
  
  if not entry.is_local:
    return False

  if entry.type == 'module' and hasattr(entry.module, method):
    return True
  if method in entry.methods:
    return True
  if method in entry.handlers and len(entry.handlers[method]):
    return True
  return False

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
  if method in entry.handlers and len(entry.handlers[method]):
    handlers += list(entry.handlers[method].values())
    
  if not handlers:
    return None
  if len(handlers) == 1:
    return handlers[0]
  return lambda entry, *args, **kwargs: call_handlers(handlers, entry, *args, **kwargs)

def call_handlers(handlers, entry, *args, **kwargs):
  ret = None
  for h in handlers:
    try:
      ret = h(entry, *args, **kwargs)
    except:
      logging.exception("#{id}> exception in calling handler {h}".format(id = entry.id, h = h))
  return ret

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
      logging.error("#NODE_SYSTEM> skipped invocation of {method}: entry {entry} not found!".format(entry=entry_str, method=method))
      return False
  
  func = get_handler(entry, method)
  if func:
    logging.debug("#{entry}> invoking {method} ...".format(entry=entry.id, method=method))
    ret = None
    try:
      ret = func(entry, *args, **kwargs)
    except:
      logging.exception("#{id}> exception in entry_invoke of method {method}".format(id = entry.id, method = method))
    return ret

def entry_invoke_delayed(entry, timer_key, delay, method, *args, _pass_entry = True, **kwargs):
  if isinstance(entry, str):
    entry_str = entry
    entry = system.entry_get(entry_str)
    if not entry:
      logging.error("#NODE_SYSTEM> skipped invocation of {method} (delayed): entry {entry} not found!".format(entry=entry_str, method=method))
      return False
  func = get_handler(entry, method)
  if func:
    cancel_entry_invoke_delayed(entry, timer_key)
    if _pass_entry:
      args = [entry] + list(args)
    #else:
    #  args = list(args)
    #entry.timers[timer_key] = threading.Timer(delay, func, args = args, kwargs = kwargs)
    #entry.timers[timer_key].start()
    args = [func, method, entry.id] + list(args);
    entry.timers[timer_key] = threading.Timer(delay, entry_invoke_delayed_wrapper, args = args, kwargs = kwargs)
    entry.timers[timer_key].start()
    
# wrapper for threads invokation, used to catch and log exception
def entry_invoke_delayed_wrapper(func, method, entry_id, *args, **kwargs):
  _s = system._stats_start()
  try:
    func(*args, **kwargs)
  except:
    logging.exception("#{id}> exception in running method {method} (delayed)".format(id = entry_id, method = method))
  system._stats_end('entry_invoke_delayed:' + entry_id + '.' + str(method), _s)

def cancel_entry_invoke_delayed(entry, timer_key):
  if timer_key in entry.timers:
    entry.timers[timer_key].cancel()
    del entry.timers[timer_key]

def entries_invoke(method, *args, _skip_entry_id = False, **kwargs):
  ret = None
  for entry_id, entry in system.entries().items():
    if not _skip_entry_id or entry_id != _skip_entry_id:
      func = get_handler(entry, method)
      if func:
        logging.debug("#{entry}> invoking {method} ...".format(entry = entry_id, method = method))
        try:
          ret = func(entry, *args, **kwargs)
        except:
          logging.exception("#{id}> exception in entries_invoke of method {method}".format(id = entry.id, method = method))
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
      logging.error("#NODE_SYSTEM> skipped invocation of {method}: entry {entry} not found!".format(entry=entry_str, method=method))
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
  system._stats_end('entry_invoke:' + entry_id + '.' + str(method), _s)

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
