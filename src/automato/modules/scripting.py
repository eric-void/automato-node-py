# require python3
# -*- coding: utf-8 -*-

import logging
import textwrap
import re
import threading
from threading import Timer

from automato.core import system
from automato.core import utils
from automato.core import test

from automato.node import node_system as node

thread_data = threading.local()

definition = {
  'config': {
  }
}

def scripting_globals(entry, _globals):
  return { **_globals, **entry.exports, **entry.methods,
    # LIBS
    'utils': utils,
    'logging': logging,
    'test': test,
    
    # ENTITIES
    'entry': entry,
    'config': entry.config,
    'broker': system.broker(),
    'now': system.time(),
    'timems': system.timems,
    #'hour': int(time.strftime("%H")), 
    
    # METHODS
    'd': utils.read_duration, # (duration)
    'array_sum': utils.array_sum,
    'array_avg': utils.array_avg,
    'array_min': utils.array_min,
    'array_max': utils.array_max,
    
    'publish': entry.publish, # (topic, payload = None, qos = None, retain = None, response_callback = None, no_response_callback = None, response_id = None)
    'entry_invoke': node.entry_invoke, # (entry, method, *args, **kwargs)
    #'entries_invoke': node.entries_invoke, # (method, *args, **kwargs)
    'run_publish': entry.run_publish, # (topic_rule)
    'do': system.do_action, # (actionref, params, if_event_not_match = False, if_event_not_match_keys = False, if_event_not_match_timeout = None)
    'entry_do': system.entry_do_action, # (entry_or_id, action, params = {}, init = None, if_event_not_match = False, if_event_not_match_keys = False, if_event_not_match_timeout = None)
    'self_do': entry.do, # (action, params = {}, init = None, if_event_not_match = False, if_event_not_match_keys = False, if_event_not_match_timeout = None)
    'event_get': system.event_get, # (eventref, timeout = None, keys = None, topic = None)
    'event_get_time': system.event_get_time, # (eventref, timeout = None, topic = None)
    'entry_event_get': system.entry_event_get, # (entry_or_id, eventname, condition = None, keys = None, timeout = None, topic = None)
    'call_method_delayed': call_method_delayed_lambda(entry), # (methodname, delay, *args, **kwargs)
    'cancel_call_method_delayed': cancel_call_method_delayed_lambda(entry), # ()
    
    '__builtins__': { 
      'locals': locals, 're': re, 'logging': logging, 
      'GeneratorExit': GeneratorExit,
      'abs': abs,'dict': dict,'help': help,'min': min,'setattr': setattr,'all': all,'dir': dir,'hex': hex,'next': next,'slice': slice,'any': any,'divmod': divmod,'id': id,'object': object,'sorted': sorted,'ascii': ascii,'enumerate': enumerate,'input': input,'oct': oct,'bin': bin,'int': int,'str': str,'bool': bool,'isinstance': isinstance,'ord': ord,'sum': sum,'bytearray': bytearray,'filter': filter, 'pow': pow,'super': super,'bytes': bytes,'float': float,'iter': iter,'print': print,'tuple': tuple,'format': format,'len': len,'property': property,'type': type,'chr': chr,'list': list,'range': range,'getattr': getattr,'zip': zip,'map': map,'reversed': reversed,'complex': complex,'hasattr': hasattr,'max': max,'round': round,'delattr': delattr,'hash': hash,'set': set
    }
  }


def entry_load(self_entry, entry):
  entry.script_exec_depth = 0
  entry.script_exec = _exec_script_entry_lambda(entry)
  entry.script_eval = _eval_script_entry_lambda(entry)

  if 'data' in entry.definition:
    for v in entry.definition['data']:
      if v not in entry.data:
        entry.data[v] = entry.definition['data'][v]
  if 'methods' in entry.definition:
    for method in entry.definition['methods']:
      script = decode_script(entry.definition['methods'][method])
      #logging.debug("#{id}@scripting> loaded method: {method}\n--------------------\n{script}".format(id = m, method = method, script = script))
      # TODO i method base (chiamati tramite system.entry_invoke) sono in formato (entry, *args, **kwargs). I metodi chiamabili da script sono in formato (*args, **kwargs). Per questo la differenza, ma non è molto elegante cosi'
      if method in ['init', 'start']:
        #setattr(entry.module, method, _exec_script_lambda_noentry(script))
        entry.methods[method] = _exec_script_lambda_noentry(script)
      else:
        entry.methods[method] = _exec_script_lambda(entry, script)
        
  if 'subscribe' in entry.definition:
    for s in entry.definition['subscribe']:
      if isinstance(entry.definition['subscribe'][s], dict) and 'script' in entry.definition['subscribe'][s]:
        script = decode_script(entry.definition['subscribe'][s]['script'])
        #logging.debug("#{id}@scripting> loaded script for topic subscription: {topic}\n--------------------\n{script}".format(id = m, topic = s, script = script))
        entry.definition['subscribe'][s]['handler'] = _exec_script_lambda(entry, "subscribed_message = args[1]; topic = args[1].topic; payload = args[1].payload; matches = args[1].matches\n" + script)
        entry.definition['subscribe'][s].pop('script', None)

  if 'publish' in entry.definition:
    for s in entry.definition['publish']:
      if 'script' in entry.definition['publish'][s]:
        script = decode_script(entry.definition['publish'][s]['script'])
        #logging.debug("#{id}@scripting> loaded script for topic publishing: {topic}\n--------------------\n{script}".format(id = m, topic = s, script = script))
        entry.definition['publish'][s]['handler'] = _exec_script_lambda(entry, "topic = args[1]; topic_definition = args[2]\n" + script)
        entry.definition['publish'][s].pop('script', None)

      """
      if 'notify_script' in entry.definition['publish'][s]:
        script = decode_script(entry.definition['publish'][s]['notify_script'])
        #logging.debug("#{id}> loaded script for topic publishing notification: {topic}\n--------------------\n{script}".format(id = m, topic = s, script = script))
        entry.definition['publish'][s]['notify_handler'] = _exec_script_lambda(entry, "topic = args[1]; payload = args[2]\n" + script)
        entry.definition['publish'][s].pop('notify_script', None)
      """
  
  if 'on' in entry.definition:
    for s in entry.definition['on']:
      if 'script' in entry.definition['on'][s]:
        script = decode_script(entry.definition['on'][s]['script'])
        #logging.debug("#{id}@scripting> loaded script for topic on: {topic}\n--------------------\n{script}".format(id = m, topic = s, script = script))
        entry.definition['on'][s]['handler'] = _exec_script_lambda(entry, "on_entry = args[0]; eventname = args[1]; eventdata = args[2]; params = eventdata['params']; caller = args[3]; published_message = args[4]; \n" + script)
        entry.definition['on'][s].pop('script', None)

def entry_unload(self_entry, entry):
  pass

def exec_script(entry, code, *args, **kwargs):
    # WARN: Ciò che metto in "globals" nella mia exec è "read-only" (nel senso che le modifiche che verranno fatte NON si rifletteranno all'esterno)
    # Invece se modifico __locals questo si rifletterà, purchè __locals sia assegnato direttamente a entry.data. Se faccio __locals = { **entry.data } allora le modifiche non si rifletteranno più
    # Ma impostare __locals = entry.data da problemi di concorrenza (gli script e le altre routine modificano le variabili tra di loro, e storage.storeData si trova a memorizzare roba sbagliata)
    # Per questo uso un threading_local che mi permette di gestire tutto l'albero delle chiamate innestate e di avere una copia di entry.data che, alla fine di esecuzione del tree, verrà portato nell'entry.data ufficiale.
    # In questo modo funziona bene anche la condivisione dei dati tra chiamate dentro lo stesso script (la funzione1 modifica la var "a", poi chiama una sottofunzione2 che la modifica a sua volta => questo funziona solo se le 2 funzioni lavorano direttamente su entry.data)
  
  acquired_lock = False
  if not hasattr(thread_data, 'running_script') or not thread_data.running_script:
    entry.data_lock.acquire()
    thread_data.running_script = True
    thread_data.locals = { ** entry.data }
    thread_data.locals_copy = { ** entry.data }
    acquired_lock = True

  try:
    __globals = scripting_globals(entry, { 'args': args, **kwargs })
    __locals = thread_data.locals
    code = 'try:\n' + textwrap.indent(re.sub(r'^([ \t]*)return[ ]*$', r'\1_return = None; raise GeneratorExit()', re.sub(r'^([ \t]*)return[ ]+([^ ].*)$', r'\1_return = \2; raise GeneratorExit()', code, flags=re.MULTILINE), flags=re.MULTILINE), '  ') + '\nexcept GeneratorExit as _exc:\n  pass\n'
    exec(code, __globals, __locals)
    return __locals['_return'] if '_return' in __locals else None
    
  except:
    logging.exception('error in executing script: \n' + format_script_lines(code) + '\nargs:\n' + str(args) + '\nkwargs:\n' + str(kwargs) + '\n')
    
  finally:
    if acquired_lock:
      for k in thread_data.locals_copy:
        if thread_data.locals_copy[k] != thread_data.locals[k]:
          #print("SET " + k + " = " + str(thread_data.locals[k]))
          entry.data[k] = thread_data.locals[k]

      del thread_data.running_script
      del thread_data.locals
      del thread_data.locals_copy
      entry.data_lock.release()

def _exec_script_lambda(entry, script):
  return lambda *args, **kwargs: exec_script(entry, script, *args, **kwargs)

def _exec_script_lambda_noentry(script):
  return lambda entry, *args, **kwargs: exec_script(entry, script, *args, **kwargs)

def _exec_script_entry_lambda(entry):
  return lambda code, *args, **kwargs: exec_script(entry, code, *args, **kwargs)

def eval_script(entry, code, *args, **kwargs):
  return exec_script(entry, 'return ' + code, *args, **kwargs)

def _eval_script_entry_lambda(entry):
  return lambda code, *args, **kwargs: eval_script(entry, code, *args, **kwargs)

def call_method_delayed(entry, methodname, delay, *args, **kwargs):
  node.entry_invoke_delayed(entry, 'script', delay, methodname, _pass_entry = False, *args, **kwargs)
  """
  if not methodname in entry.methods:
    return None
  cancel_call_method_delayed(entry)
  entry.scripting_call_method_timer = Timer(delay, entry.methods[methodname], args = args, kwargs = kwargs)
  entry.scripting_call_method_timer.start()
  return entry.scripting_call_method_timer
  """

def call_method_delayed_lambda(entry):
  return lambda methodname, delay, *args, **kwargs: call_method_delayed(entry, methodname, delay, *args, **kwargs)
  
def cancel_call_method_delayed(entry):
  node.cancel_entry_invoke_delayed(entry, 'script')
  """
  if hasattr(entry, 'scripting_call_method_timer') and entry.scripting_call_method_timer:
    entry.scripting_call_method_timer.cancel()
  entry.scripting_call_method_timer = False
  """

def cancel_call_method_delayed_lambda(entry):
  return lambda: cancel_call_method_delayed(entry)

def decode_script(lines, store = None):
  if isinstance(lines, str):
    if not store and lines.startswith('py:'):
      lines = lines[3:]
    return (store['indent'] if store else '') + lines + "\n"

  if isinstance(lines, list):
    if not store and len(lines) >= 1 and lines[0] == 'py:':
      lines = lines.pop(0)
    script = ''
    for line in lines:
      script += str(decode_script(line, {'indent': store['indent'] + '  ' if store else ''}))
    return script

  logging.error('Invalid script: ' + str(lines))
  return ''

def format_script_lines(code):
  a = code.splitlines()
  cstr = ''
  for i in range(len(a)):
    cstr += str(i + 1).zfill(2) + ': ' + a[i] + '\n'
  return cstr
