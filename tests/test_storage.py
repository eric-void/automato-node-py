# require python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import shutil
import tempfile
import threading
import types
import unittest
from unittest import mock

from automato.core import system
from automato.node import storage

def make_entry(entry_id = 'e@test'):
  d = entry_id.find('@')
  entry = types.SimpleNamespace(id = entry_id, id_local = entry_id[:d], node_name = entry_id[d + 1:], data = {}, data_lock = threading.Lock())
  storage.entry_install(storage, entry)
  return entry

class StorageTest(unittest.TestCase):
  def setUp(self):
    logging.disable(logging.CRITICAL)
    self.tmp = tempfile.mkdtemp(prefix = 'automato-unit-')
    storage.init(self.tmp)
    system.time_pause()

  def tearDown(self):
    system.time_resume()
    shutil.rmtree(self.tmp, ignore_errors = True)
    logging.disable(logging.NOTSET)

  def file(self, entry, backup = False):
    return os.path.join(self.tmp, entry.node_name + '_data_' + entry.id_local + ('.backup' if backup else '') + '.json')

  def read(self, entry, backup = False):
    with open(self.file(entry, backup)) as f:
      return json.load(f)

  def test_store_and_retrieve(self):
    e = make_entry()
    e.data = {'a': 1, 'b': [1, 2]}
    self.assertTrue(e.store_data())
    self.assertEqual(self.read(e), {'a': 1, 'b': [1, 2]})
    self.assertEqual(self.read(e, backup = True), {'a': 1, 'b': [1, 2]})
    e2 = make_entry()
    storage.retrieveData(e2)
    self.assertEqual(e2.data, {'a': 1, 'b': [1, 2]})
    self.assertEqual(os.listdir(self.tmp).count('test_data_e.json.new'), 0)

  def test_unchanged_data_is_not_written(self):
    e = make_entry()
    e.data = {'a': 1}
    with mock.patch.object(storage, '_storeDataTo', wraps = storage._storeDataTo) as w:
      e.store_data()
      e.store_data()
      e.store_data()
      # data file + backup, only the first time
      self.assertEqual(w.call_count, 2)

  def test_retrieved_data_is_not_written_back(self):
    e = make_entry()
    e.data = {'a': 1}
    e.store_data()
    e2 = make_entry()
    storage.retrieveData(e2)
    with mock.patch.object(storage, '_storeDataTo', wraps = storage._storeDataTo) as w:
      e2.store_backup_time = system.time()
      e2.store_data()
      self.assertEqual(w.call_count, 0)

  def test_backup_only_when_changed_and_after_backup_time(self):
    e = make_entry()
    e.data = {'a': 1}
    e.store_data()
    e.data['a'] = 2
    e.store_data()
    self.assertEqual(self.read(e), {'a': 2})
    self.assertEqual(self.read(e, backup = True), {'a': 1})
    system.time_offset(storage.STORAGE_BACKUP_TIME + 1)
    with mock.patch.object(storage, '_storeDataTo', wraps = storage._storeDataTo) as w:
      e.store_data()
      self.assertEqual([c.args[1] for c in w.call_args_list], ['test_data_e.backup.json'])
    self.assertEqual(self.read(e, backup = True), {'a': 2})
    system.time_offset(storage.STORAGE_BACKUP_TIME + 1)
    with mock.patch.object(storage, '_storeDataTo', wraps = storage._storeDataTo) as w:
      e.store_data()
      self.assertEqual(w.call_count, 0)

  def test_failed_write_keeps_previous_file(self):
    e = make_entry()
    e.data = {'a': 1}
    e.store_data()
    e.data['a'] = 2
    with mock.patch.object(storage.os, 'fsync', side_effect = OSError('disk full')):
      e.store_data()
    self.assertEqual(self.read(e), {'a': 1})
    self.assertFalse(os.path.exists(self.file(e) + '.new'))
    # Next store retries
    e.store_data()
    self.assertEqual(self.read(e), {'a': 2})

  def test_corrupted_file_uses_backup(self):
    e = make_entry()
    e.data = {'a': 1}
    e.store_data()
    with open(self.file(e), 'w') as f:
      f.write('{"a": ')
    e2 = make_entry()
    storage.retrieveData(e2)
    self.assertEqual(e2.data, {'a': 1})
    # Data file is corrupted, so it must be written again
    e2.store_data()
    self.assertEqual(self.read(e), {'a': 1})

  def test_data_emptied_is_stored(self):
    e = make_entry()
    e.data = {'a': 1}
    e.store_data()
    e.data = {}
    e.store_data()
    self.assertEqual(self.read(e), {})

  def test_periodic_store_interval(self):
    e = make_entry()
    e.data = {'a': 1}
    now = system.time()
    with mock.patch.object(storage, 'storeData', return_value = True) as s:
      calls = 0
      for t in range(now, now + 31):
        storage.storeDataIfDue(e, t, 10)
      # The first check is spread in the first interval, then every 10 seconds
      self.assertIn(s.call_count, [3, 4])

  def test_non_blocking_store_skips_if_locked(self):
    e = make_entry()
    e.data = {'a': 1}
    e.data_lock.acquire()
    try:
      self.assertFalse(e.store_data(False))
      self.assertFalse(e.store_data(True, 0.1))
    finally:
      e.data_lock.release()
    self.assertFalse(os.path.exists(self.file(e)))

if __name__ == '__main__':
  unittest.main()
