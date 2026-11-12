# require python3
# -*- coding: utf-8 -*-

import types
import unittest
from unittest import mock

from automato.core import system
from automato.node import node_system

from node_helpers import NodeTestCase

class ThrottlePolicyTest(unittest.TestCase):
  def policy(self, level, definition, next_run = 10, last_run = 0):
    entry = types.SimpleNamespace(data = {'next_run': next_run, 'last_run': last_run})
    with mock.patch.object(node_system, 'load_level', return_value = level):
      return node_system._run_step_throttle_policy(entry, definition)

  def test_low_load_forces(self):
    self.assertEqual(self.policy(0, {'run_throttle': 'skip'}), 'force')

  def test_definition_policy_is_used(self):
    self.assertEqual(self.policy(1, {'run_throttle': 'force'}), 'force')
    self.assertEqual(self.policy(2, {'run_throttle': 'skip'}), 'skip')
    self.assertEqual(self.policy(1, {'run_throttle': ['wait', 'skip']}), 'wait')
    self.assertEqual(self.policy(2, {'run_throttle': ['wait', 'skip']}), 'skip')

  def test_default_policy(self):
    # Frequent runs are skipped, rare ones wait
    self.assertEqual(self.policy(1, {}, next_run = 60, last_run = 0), 'skip')
    self.assertEqual(self.policy(1, {}, next_run = 86400, last_run = 0), 'wait')

  def test_critical_load(self):
    self.assertEqual(self.policy(3, {'run_throttle': 'force'}), 'skip')

class RunStepTest(NodeTestCase):
  entries = [
    { 'module': 'scripting' },
    {
      'item': 'counter',
      'run_interval': 10,
      'data': { 'runs': 0 },
      'methods': { 'run': 'runs = runs + 1' },
      'publish': {
        'counter/value': {
          'run_interval': '30s',
          'script': "publish('counter/value', runs)",
        },
      },
    },
  ]

  def setUp(self):
    super().setUp()
    system.time_pause()
    # Invoke threaded methods synchronously
    self.patcher = mock.patch.object(node_system, 'entry_invoke_threaded', side_effect = lambda entry, method, *args, **kwargs: node_system.entry_invoke(entry, method, *args))
    self.patcher.start()
    self.patcher2 = mock.patch.object(node_system, 'entry_invoke_handler_threaded', side_effect = lambda entry, handler, name, *args, **kwargs: node_system.get_handler(entry, handler)(entry, *args))
    self.patcher2.start()

  def tearDown(self):
    self.patcher.stop()
    self.patcher2.stop()
    system.time_resume()
    super().tearDown()

  def test_run_interval(self):
    e = self.entry('counter')
    for i in range(25):
      node_system.run_step()
      system.time_offset(1)
    # runs at 0, 10, 20
    self.assertEqual(e.data['runs'], 3)
    self.assertEqual([p['payload'] for p in self.broker.published if p['topic'] == 'counter/value'], ['1'])

  def test_data_is_stored_on_destroy(self):
    e = self.entry('counter')
    node_system.run_step()
    node_system.store_all_data()
    with open(self.storage_path('test_data_counter.json')) as f:
      self.assertIn('"runs": 1', f.read())

class EntriesImplementsTest(NodeTestCase):
  entries = [
    { 'module': 'scripting' },
    { 'item': 'a', 'methods': { 'custom_method': 'return 1' } },
  ]

  def test_cache_is_invalidated_on_entries_change(self):
    self.assertEqual([e.id for e in node_system.entries_implements('custom_method')], ['a@test'])
    system.entry_load([{ 'item': 'b', 'methods': { 'custom_method': 'return 2' } }], id_from_definition = True)
    self.assertEqual(sorted(e.id for e in node_system.entries_implements('custom_method')), ['a@test', 'b@test'])
    system.entry_unload('a@test')
    self.assertEqual([e.id for e in node_system.entries_implements('custom_method')], ['b@test'])

class HandlersTest(NodeTestCase):
  entries = [
    { 'module': 'scripting' },
    { 'item': 'a', 'methods': { 'm': 'return args[1] * 2' } },
  ]

  def test_invoke(self):
    self.assertEqual(node_system.entry_invoke('a', 'm', 21), 42)
    self.assertIsNone(node_system.entry_invoke('a', 'missing'))
    self.assertFalse(node_system.entry_invoke('missing_entry', 'm'))

  def test_invoke_handler_threaded_without_handler(self):
    self.assertFalse(node_system.entry_invoke_handler_threaded('a', 'missing', 'missing'))
    self.assertFalse(node_system.entry_invoke_handler_threaded('missing_entry', 'm', 'm'))

if __name__ == '__main__':
  unittest.main()
