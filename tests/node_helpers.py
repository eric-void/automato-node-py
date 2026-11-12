# require python3
# -*- coding: utf-8 -*-

"""
Helpers for code-oriented node tests: the node runs without a broker (see automato-core-py/tests/helpers.py), with storage in a temporary directory.
node_system.run() is not called (so "start" handlers and the run loop are not executed): tests call node_system.run_step() when needed.
"""

import copy
import logging
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'automato-core-py', 'tests'))

from helpers import FakeBroker, receive

from automato.core import system
from automato.node import node_system

class NodeTestCase(unittest.TestCase):
  config = {}
  entries = []

  def setUp(self):
    logging.disable(logging.CRITICAL)
    self.tmp = tempfile.mkdtemp(prefix = 'automato-unit-')
    os.makedirs(os.path.join(self.tmp, 'data'))
    self.broker = FakeBroker()
    node_system.boot({'name': 'test', 'base_path': self.tmp, 'storage': 'data', 'console-log': False, 'entries': copy.deepcopy(self.entries), **self.config})
    self.broker.install()
    node_system.init()
    # The subscription timer thread is stopped: tests call system._subscription_timer_step() directly
    system.destroyed = True
    system.subscription_thread_stop.set()
    system.subscription_thread.join()
    system.destroyed = False

  def tearDown(self):
    node_system.destroy()
    shutil.rmtree(self.tmp, ignore_errors = True)
    logging.disable(logging.NOTSET)

  def entry(self, entry_id):
    return system.entry_get(entry_id)

  def storage_path(self, filename = ''):
    return os.path.join(self.tmp, 'data', filename)

  def receive(self, topic, payload, retain = False):
    receive(topic, payload, retain)
