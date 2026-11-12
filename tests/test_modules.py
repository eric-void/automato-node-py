# require python3
# -*- coding: utf-8 -*-

import unittest

from automato.core import system
from automato.node import node_system
from automato.modules import scripting

import fake_notifier
from node_helpers import NodeTestCase

class NotificationsTest(NodeTestCase):
  entries = [
    { 'module': 'notifications', 'config': { 'history_max_items': 3, 'history_length': 100 } },
    { 'module': 'fake_notifier' },
    {
      'item': 'sensor',
      'publish': {
        'sensor/value': { 'type': 'int', 'notify': 'Sensor value is {payload}' },
        'sensor/telemetry': { 'type': 'int', 'notify': 'Sensor telemetry is {payload}', 'notify_level': 'debug' },
      },
    },
  ]

  def setUp(self):
    super().setUp()
    system.time_pause()
    fake_notifier.sent.clear()

  def tearDown(self):
    system.time_resume()
    super().tearDown()

  def history(self):
    return [(h['topic'], h['message']) for h in self.entry('notifications').data['history']]

  def test_history_contains_info_notifications(self):
    self.receive('sensor/value', '1')
    self.receive('sensor/telemetry', '2')
    self.receive('sensor/value', '3', retain = True)
    self.assertEqual(self.history(), [('sensor/value', 'Sensor value is 1')])

  def test_history_max_items(self):
    for i in range(5):
      self.receive('sensor/value', str(i))
    self.assertEqual(self.history(), [('sensor/value', 'Sensor value is ' + str(i)) for i in [2, 3, 4]])

  def test_history_length(self):
    self.receive('sensor/value', '1')
    system.time_offset(101)
    self.receive('sensor/value', '2')
    self.assertEqual(self.history(), [('sensor/value', 'Sensor value is 2')])

  def test_notifications_below_used_levels_are_not_built(self):
    from unittest import mock
    from automato.core import notifications as core_notifications
    with mock.patch.object(core_notifications, 'notification_build', wraps = core_notifications.notification_build) as build:
      self.receive('sensor/telemetry', '1')
      self.assertEqual(build.call_count, 0)
      self.receive('sensor/value', '1')
      self.assertEqual(build.call_count, 1)
      # A subscription to all levels needs also debug notifications
      self.receive('notifications/subscribe/_', 'fake:chat1')
      self.receive('sensor/telemetry', '2')
      self.assertEqual(build.call_count, 2)
    self.assertIn(('chat1', 'sensor/telemetry', 'Sensor telemetry is 2', 'debug'), fake_notifier.sent)
    self.assertEqual(self.history(), [('sensor/value', 'Sensor value is 1')])

  def test_notify_if_level_is_considered(self):
    system.entry_load([{ 'item': 'cond', 'publish': { 'cond/value': { 'type': 'int', 'notify': 'Cond {payload}', 'notify_level': 'debug', 'notify_if': { 'js: payload > 5': { 'notify_level': 'warn' } } } } }], id_from_definition = True)
    self.receive('cond/value', '1')
    self.receive('cond/value', '10')
    self.assertEqual(self.history(), [('cond/value', 'Cond 10')])

  def test_subscribe_send_unsubscribe(self):
    self.receive('notifications/subscribe/info', 'fake:chat1')
    self.receive('notifications/subscribe/info', 'fake:chat2')
    self.assertEqual([s['data'] for s in self.entry('notifications').notification_subscriptions], ['chat1', 'chat2'])
    self.receive('sensor/value', '1')
    self.assertEqual(sorted(s[0] for s in fake_notifier.sent), ['chat1', 'chat2'])
    self.receive('notifications/unsubscribe/info', 'fake:chat1')
    self.assertEqual([s['data'] for s in self.entry('notifications').notification_subscriptions], ['chat2'])
    with open(self.storage_path('notifications-subscribptions.db')) as f:
      lines = f.read().split('\n')
    self.assertEqual(len([l for l in lines if l.strip()]), 1)
    self.assertNotIn('', lines[:-1])

class ZigbeeNotificationsTest(NodeTestCase):
  entries = [
    { 'module': 'zigbee2mqtt' },
    { 'device': 'z_temp', 'caption': 'Temp', 'device_type': 'zigbee_temperature', 'zigbee_id': 'temp1' },
    { 'device': 'z_plug', 'caption': 'Plug', 'device_type': 'zigbee_plug', 'zigbee_id': 'plug1', 'publish': { 'status': { 'notify_level': 'info' } } },
  ]

  def test_raw_data_notifications_are_debug(self):
    self.assertEqual(system.entry_get('z_temp').definition['publish']['zigbee2mqtt/temp1']['notify_level'], 'debug')
    # The level can be changed in the entry definition
    self.assertEqual(system.entry_get('z_plug').definition['publish']['zigbee2mqtt/plug1']['notify_level'], 'info')

class ScriptingTest(NodeTestCase):
  entries = [
    { 'module': 'scripting' },
    {
      'item': 'a',
      'data': { 'counter': 0, 'items': [] },
      'methods': {
        'inc': [ 'counter = counter + args[0]', 'return counter' ],
        'inc_twice': [ 'inc(1)', 'inc(1)' ],
        'add_item': 'items.append(args[0])',
        'call_b': "return entry_invoke('b', 'get_value')",
        'with_py_prefix': [ 'py:', 'return 7' ],
        'new_var': 'not_declared = 1',
      },
    },
    {
      'item': 'b',
      'data': { 'value': 'b' },
      'methods': { 'get_value': 'return value' },
    },
  ]

  def call(self, entry_id, method, *args):
    return self.entry(entry_id).methods[method](*args)

  def test_data_is_updated(self):
    self.assertEqual(self.call('a', 'inc', 2), 2)
    self.assertEqual(self.call('a', 'inc', 3), 5)
    self.assertEqual(self.entry('a').data['counter'], 5)

  def test_nested_calls_of_the_same_entry_share_data(self):
    self.assertIsNone(self.call('a', 'inc_twice'))
    self.assertEqual(self.entry('a').data['counter'], 2)

  def test_mutable_data(self):
    self.call('a', 'add_item', 'x')
    self.assertEqual(self.entry('a').data['items'], ['x'])

  def test_nested_call_of_another_entry_uses_its_data(self):
    self.assertEqual(self.call('a', 'call_b'), 'b')

  def test_py_prefix(self):
    self.assertEqual(self.call('a', 'with_py_prefix'), 7)

  def test_not_declared_vars_are_not_stored(self):
    self.call('a', 'new_var')
    self.assertNotIn('not_declared', self.entry('a').data)

  def test_compiled_scripts_are_cached(self):
    self.call('a', 'inc', 1)
    n = len(scripting._compiled_scripts)
    for i in range(5):
      self.call('a', 'inc', 1)
    self.assertEqual(len(scripting._compiled_scripts), n)

  def test_error_in_script_releases_lock(self):
    e = self.entry('a')
    self.assertIsNone(scripting.exec_script(e, 'raise ValueError("x")'))
    self.assertTrue(e.data_lock.acquire(False))
    e.data_lock.release()

class HealthTest(NodeTestCase):
  entries = [
    { 'module': 'health' },
    { 'item': 'required_one', 'publish': { 'required_one/health': {} } },
    { 'item': 'dependent', 'required': ['required_one'] },
  ]

  def test_required_entry_event_without_received_message(self):
    # An "alive" event not generated by a received message (current_received_message() is None)
    required = self.entry('required_one')
    system._entry_event_invoke_listeners(required, {'name': 'alive', 'params': {'value': False}, 'changed_params': {}, 'keys': {}, 'time': system.time()}, 'group')
    self.assertEqual(self.entry('dependent').health_required, {'required_one@test': 'dead'})

if __name__ == '__main__':
  unittest.main()
