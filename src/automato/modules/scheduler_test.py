# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system
from automato.core import utils
from automato.node import node_system

def test_init():
  test.add_node_config({
    "listen_all_events": True,
    "entries": [
      {
        "module": "scheduler",
        "config": {
          "scheduler_enabled": True,
        },
        "jobs": [
          {"run_cron": "*/10 * * * *", "do": "item1.action(params['value']='1')"}
        ],
        'run_interval': 1,
        'publish': {
          '@/status': {
            'run_interval': 1,
          }
        },
      },
      {
        "item": "item1",
        "subscribe": {
          "@/action": {
            "type": "string",
            'response': [ ],
            "actions": {
              "action": "js:params['value']",
            }
          }
        },
        "schedule": [
          {"id": "testsched", "run_interval": "1d", "do": ".action(params['value']='2')"}
        ],
        "schedule_groups": {
          "groupname": [
            {"run_cron": "0 0 */7 * *", "do": ".action(params['value']='3')"}
          ]
        },
      }
    ]
  })

  system.time_set(1577833200) # 2020-01-01 00:00:00

def test_run(entries):
  #print(utils.strftime(system.time()))
  
  test.assertx("check1-idle", assertSubscribe = { 'scheduler/status': {
    "enabled": True, 
    "time": (), "timer_to": 0,
    "groups": {
      "groupname": { "enabled": True, "timer_to": 0 },
    },
    "jobs": {
      "7e78a032ef642f62": {"run_cron": "*/10 * * * *", "do": ["item1.action(params['value']='1')"], "enabled": True, "max_delay": 60, "last_run": 0, "next_run": (), "timer_to": 0},
      "testsched": {"entry_id": "item1@TEST", "run_interval": 86400, "do": [".action(params['value']='2')"], "enabled": True, "max_delay": 0, "last_run": 0, "next_run": (), "timer_to": 0},
      "groupname.6abc8cf88f7957a5": {"group": "groupname", "entry_id": "item1@TEST", "run_cron": "0 0 */7 * *", "do": [".action(params[\'value\']=\'3\')"], "enabled": True, "max_delay": 60, "last_run": 0, "next_run": (), "timer_to": 0}
    }
  }}, assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  #entries['scheduler@TEST'].module.run(entries['scheduler@TEST'])
  test.waitRunning()
  
  system.time_offset(600)
  test.assertx("check2-run", assertSubscribe = {'item/item1/action': '1'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  system.time_offset(10)
  test.assertx("check3-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  # test max_delay: too much time waited, job should NOT be executed
  system.time_offset(660)
  test.assertx("check4-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  system.time_offset(530)
  test.assertx("check5-run", assertSubscribe = {'item/item1/action': '1'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  test.assertAction("check6-disable", 'scheduler', 'output-set', {'value': 0, 'timer_to': '20m'}, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': '', 'timer_to': '20m' }, 'scheduler/result': { 'enabled': False, 'target': '*', 'timer_to': ('d', system.time() + 1200)}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': '', 'timer_to': ('d', system.time() + 1200)}})
  
  system.time_offset(600)
  test.assertx("check7-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  """
  test.assertAction("check8-enable", 'scheduler', 'output-set', {'value': 1}, 
    assertSubscribe = { 'scheduler/set': { 'enabled': True, 'target': '', 'timer_to': 0 }, 'scheduler/result': { 'enabled': True, 'target': '*', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 1, 'port': '', 'timer_to': 0}})
  """
  
  system.time_offset(600)
  test.assertx("check9-run", assertSubscribe = {'item/item1/action': '1'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  test.assertAction("check10-disable", 'scheduler', 'output-set', {'value': 0, 'port': '7e78a032ef642f62', 'timer_to': 1200 }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': '7e78a032ef642f62', 'timer_to': 1200}, 'scheduler/result': { 'enabled': False, 'target': '7e78a032ef642f62', 'timer_to': ('d', system.time() + 1200)}},
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': '7e78a032ef642f62', 'timer_to': ('d', system.time() + 1200)}})
  
  system.time_offset(600)
  test.assertx("check11-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  """
  test.assertAction("check12-enable", 'scheduler', 'output-set', {'value': 1, 'port': '7e78a032ef642f62'}, 
    assertSubscribe = { 'scheduler/set': { 'enabled': True, 'target': '7e78a032ef642f62', 'timer_to': 0}, 'scheduler/result': { 'enabled': True, 'target': '7e78a032ef642f62', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 1, 'port': '7e78a032ef642f62', 'timer_to': 0}})
  """
  
  system.time_offset(600)
  test.assertx("check13-run", assertSubscribe = {'item/item1/action': '1'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  test.assertAction("check14-disable", 'scheduler', 'output-set', {'value': 0, 'port': '7e78a032ef642f62' }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': '7e78a032ef642f62', 'timer_to': 0}, 'scheduler/result': { 'enabled': False, 'target': '7e78a032ef642f62', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': '7e78a032ef642f62', 'timer_to': 0}})
  
  system.time_offset(86400)
  test.assertx("check15-run", assertSubscribe = {'item/item1/action': '2'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  system.time_offset(43200)
  test.assertx("check16-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  test.assertAction("check17-disable", 'scheduler', 'output-set', {'value': 0, 'port': '@item1' }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': '@item1', 'timer_to': 0}, 'scheduler/result': { 'enabled': False, 'target': 'testsched,groupname.6abc8cf88f7957a5', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': 'testsched,groupname.6abc8cf88f7957a5', 'timer_to': 0}})

  system.time_offset(86400)
  test.assertx("check18-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()

  test.assertAction("check19-enable", 'scheduler', 'output-set', {'value': 1, 'port': '@item1@TEST'}, 
    assertSubscribe = { 'scheduler/set': { 'enabled': True, 'target': '@item1@TEST', 'timer_to': 0}, 'scheduler/result': { 'enabled': True, 'target': 'testsched,groupname.6abc8cf88f7957a5', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 1, 'port': 'testsched,groupname.6abc8cf88f7957a5', 'timer_to': 0}})
  
  test.assertx("check20-run", assertSubscribe = {'item/item1/action': '2'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  test.assertAction("check20-disable", 'scheduler', 'output-set', {'value': 0, 'port': 'testsched' }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': 'testsched', 'timer_to': 0}, 'scheduler/result': { 'enabled': False, 'target': 'testsched', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': 'testsched', 'timer_to': 0}})
  
  test.assertAction("check21-enable", 'scheduler', 'output-set', {'value': 1, 'port': 'groupname' }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': True, 'target': 'groupname', 'timer_to': 0}, 'scheduler/result': { 'enabled': True, 'target': 'groupname', 'timer_to': 0}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 1, 'port': 'groupname', 'timer_to': 0}})
  
  system.time_set(1577833200 + 7 * 86400 + 30) # 2020-01-01 00:00:00
  test.assertx("check22-run", assertSubscribe = {'item/item1/action': '3'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  t1 = system.time() + 14 * 86400
  test.assertAction("check23-disable", 'scheduler', 'output-set', {'value': 0, 'port': 'groupname', 'timer_to': '2w' }, 
    assertSubscribe = { 'scheduler/set': { 'enabled': False, 'target': 'groupname', 'timer_to': '2w'}, 'scheduler/result': { 'enabled': False, 'target': 'groupname', 'timer_to': ('d', t1)}}, 
    assertEventsTopic = 'scheduler/result', assertEvents = { 'output': {'value': 0, 'port': 'groupname', 'timer_to': ('d', t1)}})

  system.time_offset(7 * 86400)
  test.assertx("check24-idle", assertSubscribeNotReceive = ['item/item1/action'], wait = False)
  node_system.run_step()
  test.waitRunning()
  
  system.time_offset(1)
  test.assertx("check25-status", assertSubscribe = { 'scheduler/status': {
    "enabled": True, 
    "time": (), "timer_to": 0,
    "groups": {
      "groupname": { "enabled": False, "timer_to": ('d', t1) },
    },
    "jobs": {
      "7e78a032ef642f62": {"run_cron": "*/10 * * * *", "do": ["item1.action(params['value']='1')"], "enabled": False, "max_delay": 60, "last_run": (), "next_run": (), "timer_to": 0},
      "testsched": {"entry_id": "item1@TEST", "run_interval": 86400, "do": [".action(params['value']='2')"], "enabled": False, "max_delay": 0, "last_run": (), "next_run": (), "timer_to": 0},
      "groupname.6abc8cf88f7957a5": {"group": "groupname", "entry_id": "item1@TEST", "run_cron": "0 0 */7 * *", "do": [".action(params[\'value\']=\'3\')"], "enabled": True, "max_delay": 60, "last_run": (), "next_run": (), "timer_to": 0}
    }
  }}, wait = False)
  node_system.run_step()
  test.waitRunning()

  system.time_offset(7 * 86400)
  test.assertx("check26-run", assertSubscribe = {'item/item1/action': '3'}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  system.time_offset(2)
  test.assertx("check27-status", assertSubscribe = { 'scheduler/status': {
    "enabled": True, 
    "time": (), "timer_to": 0,
    "groups": {
      "groupname": { "enabled": True, "timer_to": 0 },
    },
    "jobs": {
      "7e78a032ef642f62": {"run_cron": "*/10 * * * *", "do": ["item1.action(params['value']='1')"], "enabled": False, "max_delay": 60, "last_run": (), "next_run": (), "timer_to": 0},
      "testsched": {"entry_id": "item1@TEST", "run_interval": 86400, "do": [".action(params['value']='2')"], "enabled": False, "max_delay": 0, "last_run": (), "next_run": (), "timer_to": 0},
      "groupname.6abc8cf88f7957a5": {"group": "groupname", "entry_id": "item1@TEST", "run_cron": "0 0 */7 * *", "do": [".action(params[\'value\']=\'3\')"], "enabled": True, "max_delay": 60, "last_run": (), "next_run": (), "timer_to": 0}
    }
  }}, wait = False)
  node_system.run_step()
  test.waitRunning()
  
  # TODO testare if
