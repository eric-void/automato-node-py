# require python3
# -*- coding: utf-8 -*-

import logging
import datetime
import hashlib
from croniter import croniter

from automato.core import system
from automato.core import utils
from automato.core import scripting_js

definition = {
  'description': _('Scheduler'),
  'notify_level': 'debug',
  'entry_topic': 'scheduler',
  'run_interval': 10,
  'install_on': {
    '/^schedule.*/': ()
  },
  'config': {
    'scheduler_enabled': False, # E' solo il valore di default, impostato all'init del modulo se non ci sono dati in storage precedenti (o se i dati in storage sono corrotti)
  },
  'jobs': [],
  'groups': {},
  
  'publish': {
    '@/status': {
      'type': 'object',
      'description': _('Scheduler and jobs status'),
      'handler': 'run_publish',
      'run_interval': '10m',
      'events': {
        'clock': 'js:({"value": payload["time"]})',
      }
    },
    '@/result': {
      'type': 'object',
      'description': _('Result of enable or disable action'),
      'events': {
        'output': 'js:({"value": payload["enabled"] ? 1 : 0, "port": payload["target"] != "*" ? payload["target"] : "", "timer_to": payload["timer_to"]})',
      }
    }
  },
  'subscribe': {
    # @/set, payload['target'] could be "" or "*" (all jobs), "job_id", "group_name", "@entry_id", "@entry_id@node"
    '@/set': {
      'type': 'object',
      'response': [ '@/result' ],
      'handler': 'on_set',
      'actions': {
        'output-set': 'js: "value" in params ? { "enabled": params["value"] ? true : false, "target": "port" in params ? params["port"] : "", "timer_to": "timer_to" in params ? params["timer_to"] : 0 } : null',
      }
    },
    '@/get': {
      'type': 'none',
      'publish': [ '@/status' ],
    }
  }
}

"""
MODULE DEFINITION:
'jobs': [
  {
    'run_interval|run_cron': '...', 
    'do': ["entry@NODE.action(init)", ...],
    'do_if_event_not_match': False,
    'if': 'js:...', # TODO viene passato "job", ma dovrebbe poter fare almeno event_get
    'group': '...',
    'id': '...',
    'entry_id': '...' # if 'do' does not reference an entry, this entry is used
  }
],
'groups': {
  'NAME': [ ... jobs ... ] # job 'group' property is filled with NAME (if not specified)
}

ON OTHER ENTRIES:
 'schedule': [ ... jobs ...] # job 'entry_id' property is filled with entry id (if not specified)
 'schedule_groups': { ... groups ... } # job 'entry_id' property is filled with entry id (if not specified)
"""

def load(entry):
  if 'enabled' not in entry.data:
    entry.data['enabled'] = entry.definition['config']['scheduler_enabled']
    entry.data['timer_to'] = 0
  
  if 'groups' in entry.definition and entry.definition['groups']:
    for group in entry.definition['groups']:
      for job in entry.definition['groups'][group]:
        entry.definition['jobs'].append({
          'group': group,
          **job,
        })
        
  entry.scheduler_oldjobs = entry.data['jobs'] if 'jobs' in entry.data else {}
  entry.scheduler_oldgroups = entry.data['groups'] if 'groups' in entry.data else {}
  entry.data['jobs'] = {}
  entry.data['groups'] = {}
  
  for job in entry.definition['jobs']:
    job_load(entry, job)

def job_load(entry, job):
  jid = None
  if 'run_interval' in job or 'run_cron' in job:
    if 'id' in job:
      jid = job['id']
      del job['id']
    if not jid or jid in entry.data['jobs']:
      #jid = ((job['group'] + '.') if 'group' in job and job['group'] else ((job['entry_id'] + '.') if 'entry_id' in job and job['entry_id'] else '')) + hashlib.sha1((str(i) + ':' + str(job)).encode('UTF-8')).hexdigest()[:16]
      i = 0
      while True:
        jid = ((job['group'] + '.') if 'group' in job and job['group'] else ((job['entry_id'] + '.') if 'entry_id' in job and job['entry_id'] else '')) + hashlib.sha1((str(job)).encode('UTF-8')).hexdigest()[:16] + (('_' + str(i)) if i else '')
        if not (jid in entry.data['jobs']):
          break;
        i = i + 1
    if jid in entry.scheduler_oldjobs:
      job = { ** entry.scheduler_oldjobs[jid], ** job }
    
    if 'do' in job and isinstance(job['do'], str):
      job['do'] = [ job['do'] ]
    if 'enabled' not in job:
      job['enabled'] = True
    if 'max_delay' not in job:
      job['max_delay'] = 60 if 'run_cron' in job else 0
    job['max_delay'] = utils.read_duration(job['max_delay'])
    if 'timer_to' not in job:
      job['timer_to'] = 0
    if 'last_run' not in job:
      job['last_run'] = 0
    if 'run_interval' in job:
      job['run_interval'] = utils.read_duration(job['run_interval'])
      if job['run_interval'] <= 0:
        job = False
    if job and 'run_cron' in job and not croniter.is_valid(job['run_cron']):
      logging.error('#{id}> invalid cron rule: {cron} in job: {job}'.format(id = entry.id, cron = job['run_cron'], job = job))
      job = False
    if job:
      if 'next_run' not in job or (job['max_delay'] > 0 and system.time() >= job['next_run'] + job['max_delay']):
        job_set_next_run(job)
      entry.data['jobs'][jid] = job
      
      if 'group' in job and job['group'] and not job['group'] in entry.data['groups']:
        entry.data['groups'][job['group']] = { 'enabled': True, 'timer_to': 0 } if job['group'] not in entry.scheduler_oldgroups else entry.scheduler_oldgroups[job['group']]
  return jid

def job_unload(entry, jid):
  if jid in entry.data['jobs']:
    entry.scheduler_oldjobs[jid] = entry.data['jobs'][jid]
    del entry.data['jobs'][jid]

def entry_install(self_entry, entry, conf):
  entry.schedule_jids = []
  if 'schedule' in conf:
    if not isinstance(conf['schedule'], list):
      conf['schedule'] = [ conf['schedule'] ]
    for job in conf['schedule']:
      jid = job_load(self_entry, {
        'entry_id': entry.id,
        **job,
      })
      if jid:
        entry.schedule_jids.append(jid)
  if 'schedule_groups' in conf:
    for group in conf['schedule_groups']:
      for job in conf['schedule_groups'][group]:
        jid = job_load(self_entry, {
          'entry_id': entry.id,
          'group': group,
          **job,
        })
        if jid:
          entry.schedule_jids.append(jid)

def entry_uninstall(self_entry, entry, conf):
  if entry.schedule_jids:
    for jid in entry.schedule_jids:
      job_unload(self_entry, jid)

def run(entry):
  _s = system._stats_start()
  now = system.time()
  changed = False
  
  if entry.data['timer_to'] > 0 and now >= entry.data['timer_to']:
    entry.data['enabled'] = not entry.data['enabled']
    entry.data['timer_to'] = 0
    changed = True
    
  for groupname, group in entry.data['groups'].items():
    if group['timer_to'] > 0 and now > group['timer_to']:
      group['enabled'] = not group['enabled']
      group['timer_to'] = 0
      changed = True

  for jid, job in entry.data['jobs'].items():
    if job['timer_to'] > 0 and now > job['timer_to']:
      job['enabled'] = not job['enabled']
      job['timer_to'] = 0
      changed = True
  
  if entry.data['enabled']:
    for jid, job in entry.data['jobs'].items():
      if job['enabled'] and ('group' not in job or job['group'] not in entry.data['groups'] or entry.data['groups'][job['group']]['enabled']):
        if job['max_delay'] > 0 and now >= job['next_run'] + job['max_delay']:
          logging.warn('#{id}> max_delay passed, run skipped for job {job}'.format(id = entry.id, job = job))
          job_set_next_run(job)
        if now >= job['next_run']:
          run_job(entry, job)
          job['last_run'] = now
          job_set_next_run(job)
          changed = True

  if changed:
    run_publish(entry, '', {})

  system._stats_end('scheduler', _s)

def run_job(entry, job):
  logging.debug('#{id}> running scheduled job {job} ...'.format(id = entry.id, job = job))
  if 'do' in job:
    go = True
    if 'if' in job:
      go = scripting_js.script_eval(job['if'], {"job": job}, cache = True)
    if go:
      for do in job['do']:
        system.do_action(do, {}, reference_entry_id = job['entry_id'] if 'entry_id' in job else None, if_event_not_match = job['do_if_event_not_match'] if 'do_if_event_not_match' in job else False)

def job_set_next_run(job):
  now = system.time()
  t = job['next_run'] if 'next_run' in job and job['next_run'] else now
  first = True # at least a cycle must be done (the loop should be a do ... while)
  while first or (job['max_delay'] > 0 and now >= job['next_run'] + job['max_delay']):
    if 'run_cron' in job:
      itr = croniter(job['run_cron'], datetime.datetime.fromtimestamp(t).astimezone())
      job['next_run'] = itr.get_next()
    elif 'run_interval' in job:
      job['next_run'] = t + job['run_interval']
    t = job['next_run']
    first = False

def on_set(entry, subscribed_message):
  payload = subscribed_message.payload
  done = []
  if "enabled" in payload:
    target = payload['target'] if 'target' in payload else ''
    
    timer_to = utils.read_duration(payload['timer_to']) if 'timer_to' in payload else 0
    if timer_to > 0:
      if timer_to < 1000000000:
        timer_to = system.time() + timer_to
    else:
      timer_to = 0

    if not target or target == '*':
      if entry.data['enabled'] != payload['enabled']:
        entry.data['enabled'] = payload['enabled']
        entry.data['timer_to'] = timer_to
      done = [ '*' ]

    elif target.startswith('@'):
      for jid, job in entry.data['jobs'].items():
        if 'entry_id' in job and (job['entry_id'] == target[1:] or job['entry_id'].startswith(target[1:] + '@')):
          if entry.data['jobs'][jid]['enabled'] != payload['enabled']:
            entry.data['jobs'][jid]['enabled'] = payload['enabled']
            entry.data['jobs'][jid]['timer_to'] = timer_to
          done.append(jid)
      
    elif target in entry.data['jobs']:
      if entry.data['jobs'][target]['enabled'] != payload['enabled']:
        entry.data['jobs'][target]['enabled'] = payload['enabled']
        entry.data['jobs'][target]['timer_to'] = timer_to
      done = [ target ]
      
    elif target in entry.data['groups']:
      if entry.data['groups'][target]['enabled'] != payload['enabled']:
        entry.data['groups'][target]['enabled'] = payload['enabled']
        entry.data['groups'][target]['timer_to'] = timer_to
      done = [ target ]

  entry.publish('@/result', { 'enabled': payload['enabled'], 'target': ','.join(done), 'timer_to': timer_to } if done else {})

def run_publish(entry, topic_rule, topic_definition):
  entry.publish('@/status', { 'enabled': entry.data['enabled'], 'time': system.time(), 'timer_to': entry.data['timer_to'], 'groups': entry.data['groups'], 'jobs': entry.data['jobs'] })
