# require python3
# -*- coding: utf-8 -*-

"""
Telegram module test, against a fake Bot API server (no telegram token or network needed)
"""

import json
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from automato.core import test

CHAT_ID = 123456
TOKEN = '123:TEST'

class FakeBotApi:
  def __init__(self):
    self.lock = threading.Condition()
    self.updates = []
    self.sent = []
    self.next_update_id = 1
    self.next_message_id = 1000
    self.server = ThreadingHTTPServer(('127.0.0.1', 0), self._handler())
    self.server.daemon_threads = True
    self.port = self.server.server_address[1]
    threading.Thread(target = self.server.serve_forever, daemon = True).start()

  def push_command(self, text):
    with self.lock:
      self.next_message_id += 1
      command = text.split()[0]
      self.updates.append({'update_id': self.next_update_id, 'message': {
        'message_id': self.next_message_id, 'date': int(time.time()), 'text': text,
        'chat': {'id': CHAT_ID, 'type': 'private'}, 'from': {'id': CHAT_ID, 'is_bot': False, 'first_name': 'Test'},
        'entities': [{'type': 'bot_command', 'offset': 0, 'length': len(command)}],
      }})
      self.next_update_id += 1
      self.lock.notify_all()
      return self.next_message_id

  def wait_sent(self, check, timeout = 10):
    """ Wait for a sent message matching check(message) """
    end = time.time() + timeout
    with self.lock:
      while True:
        for m in self.sent:
          if check(m):
            return m
        if time.time() >= end:
          return None
        self.lock.wait(end - time.time())

  def _api(self, method, params):
    if method == 'getMe':
      return {'id': 123, 'is_bot': True, 'first_name': 'Test bot', 'username': 'test_bot'}
    if method in ('deleteWebhook', 'setMyCommands'):
      return True
    if method == 'getUpdates':
      offset = int(params.get('offset', 0))
      end = time.time() + min(float(params.get('timeout', 0)), 1)
      with self.lock:
        while True:
          ret = [u for u in self.updates if u['update_id'] >= offset]
          if ret or time.time() >= end:
            return ret
          self.lock.wait(end - time.time())
    if method == 'sendMessage':
      with self.lock:
        self.next_message_id += 1
        m = {'chat_id': int(params['chat_id']), 'text': params['text'], 'reply_to': json.loads(params['reply_parameters'])['message_id'] if 'reply_parameters' in params else None}
        self.sent.append(m)
        self.lock.notify_all()
        return {'message_id': self.next_message_id, 'date': int(time.time()), 'chat': {'id': m['chat_id'], 'type': 'private'}, 'text': m['text']}
    raise Exception('Unknown method ' + method)

  def _handler(self):
    api = self
    class Handler(BaseHTTPRequestHandler):
      def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8')
        if self.headers.get('Content-Type', '').startswith('application/json'):
          params = json.loads(body) if body else {}
        else:
          params = {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}
        method = self.path.rsplit('/', 1)[-1]
        try:
          res = {'ok': True, 'result': api._api(method, params)}
        except Exception as e:
          res = {'ok': False, 'error_code': 400, 'description': str(e)}
        data = json.dumps(res).encode('utf-8')
        try:
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.send_header('Content-Length', str(len(data)))
          self.end_headers()
          self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
          pass # client gone (e.g. getUpdates cancelled by bot stop)
      def log_message(self, format, *args):
        pass
    return Handler

fake = None

def test_init():
  global fake
  fake = FakeBotApi()
  test.add_node_config({
    "entries": [
      { "module": "health" },
      { "module": "telegram", "config": {
        "token": TOKEN,
        "api_base_url": "http://127.0.0.1:" + str(fake.port) + "/bot",
        "threshold_level": "info",
        "threshold_max": 3,
      }},
    ],
  })

def _wait(check, timeout = 10):
  end = time.time() + timeout
  while not check() and time.time() < end:
    time.sleep(.1)
  return check()

def test_run(entries):
  entry = entries['telegram@TEST']
  module = entry.module

  test.assertx('t1-started', assertEq = [(_wait(lambda: entry.telegram_ready), True)])

  # notification sent by a node thread (not the telegram loop)
  module.notifications_send(entry, 'telegram', CHAT_ID, '#', 'some/topic', 'hello', 'info')
  m = fake.wait_sent(lambda m: m['text'].startswith('hello'))
  test.assertx('t2-notification', assertEq = [(m, {'chat_id': CHAT_ID, 'text': 'hello (info notification from some/topic)', 'reply_to': None})])

  fake.push_command('/help')
  m = fake.wait_sent(lambda m: '/notify_sub' in m['text'])
  test.assertx('t3-help', assertEq = [(m is not None and m['chat_id'] == CHAT_ID and '/healthstatus' in m['text'], True)])

  # quick command: published to the broker, the response is sent as a reply (by the response callback)
  _wait(lambda: 'healthstatus' in module.commands)
  message_id = fake.push_command('/healthstatus')
  m = fake.wait_sent(lambda m: m['reply_to'] == message_id)
  test.assertx('t4-command-response', assertEq = [(m is not None and m['text'].startswith('health/status: '), True)])

  # threshold_max = 3 in the window: the 4th notification starts collapsing
  for i in range(2, 5):
    module.notifications_send(entry, 'telegram', CHAT_ID, '#', 'some/topic', 'hello' + str(i), 'info')
  m = fake.wait_sent(lambda m: m['text'] == 'Started collapsing messages...', timeout = 2)
  n = fake.wait_sent(lambda m: m['text'].startswith('hello4'), timeout = 1)
  test.assertx('t5-collapsing', assertEq = [(m is not None and n is None, True)])

  fake.push_command('/collapsed')
  m = fake.wait_sent(lambda m: m['text'].startswith('Collapsed messages'))
  test.assertx('t6-collapsed', assertEq = [(m is not None and 'Collapsed messages: 1' in m['text'] and 'hello4' in m['text'], True)])

  module.destroy(entry)
  test.assertx('t7-destroy', assertEq = [(entry.telegram_thread.is_alive(), False), (entry.telegram_loop.is_closed(), True)])
