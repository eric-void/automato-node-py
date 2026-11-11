# require python3
# -*- coding: utf-8 -*-

# https://core.telegram.org/bots
# https://github.com/python-telegram-bot/python-telegram-bot

"""
Telegram bot, using python-telegram-bot v22 (asyncio).

The library runs in its own asyncio event loop, in a dedicated thread (the node is not asyncio based):
- telegram commands handlers run the (sync) code of this module in a worker thread (asyncio.to_thread)
- every message is sent with _send(), that schedules bot.send_message in the telegram loop and waits for the result,
  so it can be called by any thread except the telegram loop one (as bot.send_message in v13)

@see https://docs.python-telegram-bot.org/en/stable/telegram.ext.application.html (manual start/stop, without run_polling)
"""

import asyncio
import logging
import json
import re
import threading
from logging.handlers import TimedRotatingFileHandler

import telegram
from telegram import ReplyParameters
from telegram.ext import Application
from telegram.ext import filters
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler

from automato.core import system
from automato.core import utils
from automato.core.notifications import notifications_levels

definition = {
  'config': {
    "notifications_client_id": "telegram",
    "token": "",
    "connect": True,
    "exclude_topic_prefixes_in_quick_commands": "home/", # regexp part, example: "home/|net/"
    "quick_commands": True,
    "quick_commands_regexp": "^(?:home/)?(?:get-)?(.*?)(?:/get)?$",
    "log": False,
    "threshold_level": "warn",
    "threshold_max": 6,
    "threshold_duration": "4h",
    "threshold_duration_max": "12h",
    "reduce_http_log": True, # Hide INFO logs of httpx/httpcore (a line for each request to telegram servers)
    "send_timeout": 30, # Max seconds to wait for a message to be sent
    "api_base_url": "", # Bot API server (default: "https://api.telegram.org/bot"; used by tests)
  },
  'run_interval': 600,
}

commands = {}
topics_help = {}

def init(entry):
  if entry.config["connect"]:
    if entry.config["log"]:
      h = TimedRotatingFileHandler(entry.config["log"], when='midnight')
      h.setFormatter(logging.Formatter('%(asctime)s - %(name)s/%(module)s - %(levelname)s - %(message)s'))
      l = logging.getLogger('telegram')
      l.propagate = False
      l.addHandler(h)
    if entry.config["reduce_http_log"]:
      logging.getLogger('httpx').setLevel(logging.WARNING)
      logging.getLogger('httpcore').setLevel(logging.WARNING)
      
    # threshold_config
    entry.threshold_level = notifications_levels[entry.config["threshold_level"]] if entry.config["threshold_level"] in notifications_levels else -1
    entry.threshold_max = entry.config["threshold_max"]
    entry.threshold_duration = utils.read_duration(entry.config["threshold_duration"])
    entry.threshold_duration_max = utils.read_duration(entry.config["threshold_duration_max"])
    # threshold state (by chat_id)
    entry.threshold_lock = {}
    entry.threshold_collapsed = {}
    entry.threshold_queue_collapsed = {}
    entry.threshold_queue_win = {}
    
    # https://docs.python-telegram-bot.org/en/stable/telegram.ext.applicationbuilder.html
    builder = Application.builder().token(entry.config['token'])
    if entry.config["api_base_url"]:
      builder = builder.base_url(entry.config["api_base_url"]).base_file_url(entry.config["api_base_url"] + '/file')
    entry.application = builder.build()

    # https://docs.python-telegram-bot.org/en/stable/telegram.ext.commandhandler.html
    entry.application.add_handler(CommandHandler('help', _sync_handler(entry, telegram_help_handler)))
    entry.application.add_handler(CommandHandler('show_setcommands', _sync_handler(entry, telegram_show_setcommands_handler)))
    entry.application.add_handler(CommandHandler('notify_sub', _sync_handler(entry, telegram_notify_sub_handler)))
    entry.application.add_handler(CommandHandler('collapsed', _sync_handler(entry, telegram_collapsed_handler)))
    entry.application.add_handler(MessageHandler(filters.COMMAND, _sync_handler(entry, telegram_generic_message_handler)))
    entry.application.add_error_handler(_sync_error_handler(entry))

    entry.telegram_ready = False
    entry.telegram_stopping = False
    entry.telegram_loop = asyncio.new_event_loop()
    entry.telegram_thread = threading.Thread(target = _telegram_loop_thread, args = [entry], name = 'telegram', daemon = True)
    entry.telegram_thread.start()
    # Not waiting: the bot connects (and retries if telegram servers are unreachable) in background
    entry.telegram_start_future = asyncio.run_coroutine_threadsafe(_telegram_start(entry), entry.telegram_loop)

def _telegram_loop_thread(entry):
  asyncio.set_event_loop(entry.telegram_loop)
  try:
    entry.telegram_loop.run_forever()
  finally:
    entry.telegram_loop.close()

async def _telegram_start(entry):
  delay = 5
  while not entry.telegram_stopping:
    try:
      # Calls get_me (needed for bot.username): fails if telegram servers are not reachable (or token is invalid)
      await entry.application.initialize()
      break
    except telegram.error.InvalidToken:
      logging.error("{id}> telegram token rejected, bot not started".format(id = entry.id))
      return
    except Exception as e:
      logging.warning("{id}> failed connecting to telegram ({e}), will retry in {delay} seconds ...".format(id = entry.id, e = e, delay = delay))
      await asyncio.sleep(delay)
      delay = min(delay * 2, 300)
  if entry.telegram_stopping:
    return
  try:
    await entry.application.start()
    # bootstrap_retries = -1: retries forever the initial delete_webhook. Errors during polling are logged and retried by the library
    await entry.application.updater.start_polling(bootstrap_retries = -1)
  except Exception:
    logging.exception("{id}> error starting telegram bot".format(id = entry.id))
    return
  entry.telegram_ready = True
  logging.debug("{id}> telegram bot @{username} started".format(id = entry.id, username = entry.application.bot.username))

async def _telegram_stop(entry):
  app = entry.application
  if app.updater and app.updater.running:
    await app.updater.stop()
  if app.running:
    await app.stop()
  await app.shutdown()

def _sync_handler(entry, handler):
  """
  Returns an async callback for telegram handlers, that executes handler(entry, update, context) in a worker thread
  (where it can use _send)
  """
  async def callback(update, context):
    await asyncio.to_thread(handler, entry, update, context)
  return callback

def _sync_error_handler(entry):
  async def callback(update, context):
    telegram_error_handler(entry, update, context)
  return callback

def _send(entry, chat_id, text, reply_to_message_id = None):
  """
  Send a message, waiting for the result (the sent telegram.Message, or None if not sent)
  Don't call it from the telegram loop thread (it would wait forever)
  """
  if not entry.telegram_ready:
    logging.warning("{id}> telegram bot not connected, message to {chat_id} not sent: {text}".format(id = entry.id, chat_id = chat_id, text = text))
    return None
  if threading.current_thread() is entry.telegram_thread:
    raise RuntimeError('_send called by the telegram loop thread')
  future = asyncio.run_coroutine_threadsafe(entry.application.bot.send_message(chat_id = chat_id, text = text, reply_parameters = ReplyParameters(message_id = reply_to_message_id) if reply_to_message_id else None), entry.telegram_loop)
  try:
    return future.result(timeout = entry.config['send_timeout'])
  except Exception as e:
    future.cancel()
    logging.error("{id}> error sending telegram message to {chat_id} ({e}): {text}".format(id = entry.id, chat_id = chat_id, e = repr(e), text = text))
    return None

def system_entries_change(entry, entry_ids_loaded, entry_ids_unloaded):
  global commands, topics_help
  
  commands = {}
  topics_help = {}
  l = system.topic_subscription_list()
  
  for t in l:
    if not system.topic_subscription_is_internal(t):
      tm = system.topic_subscription_definition(t, strict_match = True)
      command = False
      if entry.config["quick_commands"] and not re.search('^/', t) and not re.search('#', t):
        m = re.search(entry.config['quick_commands_regexp'], t)
        command = re.sub('[^a-z0-9]', '', (t if not m else m.group(1)))
        if not command in commands and not command in l:
          commands[command] = {'topic' : t, 'help': (tm['description'] if 'description' in tm else "N/A") + (" - " + _("Syntax: ") + (t if 'topic_syntax' not in tm else tm['topic_syntax']) + ((" " + tm['payload_syntax']) if 'payload_syntax' in tm else "") + ((" (" + tm['topic_syntax_description'] + ")") if 'topic_syntax_description' in tm else "") if 'topic_syntax' in tm or 'payload_syntax' in tm else "")}
        else:
          command = False
      topics_help[t] = ("/" + command + ", " if command else "") + "/" + (t if 'topic_syntax' not in tm else tm['topic_syntax']) + ((" " + tm['payload_syntax']) if 'payload_syntax' in tm else "") + ((": " + tm['description']) if 'description' in tm else "") + ((" (" + tm['topic_syntax_description'] + ")") if 'topic_syntax_description' in tm else "")
  
def destroy(entry):
  if entry.config["connect"] and not entry.telegram_stopping:
    entry.telegram_stopping = True
    entry.telegram_ready = False
    entry.telegram_start_future.cancel()
    try:
      asyncio.run_coroutine_threadsafe(_telegram_stop(entry), entry.telegram_loop).result(timeout = 30)
    except Exception:
      logging.exception("{id}> error stopping telegram bot".format(id = entry.id))
    entry.telegram_loop.call_soon_threadsafe(entry.telegram_loop.stop)
    entry.telegram_thread.join(timeout = 10)

def run(entry):
  if not entry.config["connect"]:
    return
  for chat_id in entry.threshold_lock:
    with entry.threshold_lock[chat_id]:
      if len(entry.threshold_queue_collapsed[chat_id]) > 0 and system.time() - entry.threshold_queue_collapsed[chat_id][0][0] >= entry.threshold_duration_max:
        threshold_queue_collapsed_send(entry, chat_id)

def telegram_buffsend(mbuffer = None, message = None, init_entry = None, init_chat_id = None):
  if init_chat_id:
    mbuffer = { 'entry': init_entry, 'chat_id': init_chat_id, 'text': ""}
    return mbuffer

  if (message == None and mbuffer['text']) or (message != None and len(mbuffer['text']) + len(message) + 2 >= 4096):
    _send(mbuffer['entry'], mbuffer['chat_id'], mbuffer['text'])
    mbuffer['text'] = ""
  if message != None:
    mbuffer['text'] += message + "\n"
  return mbuffer

# Chiamato al subscribe, può verificare i dati passati (in data, in formato stringa) e eventualmente sostituirli (in modo da salvare per le chiamate successive dei dati diversi)
# @return i dati da salvare (in formato stringa)
def notifications_subscribe(entry, driver, data, pattern):
  if driver == entry.config["notifications_client_id"]:
    return data

# Usato per l'unsubscribe, verifica che i dati passati dalla chiamata mqtt e i dati di un record su db siano equivalenti (e quindi nel caso può eliminare tale record)
def notifications_matches(entry, driver, data_passed, data_saved, pattern):
  if driver == entry.config["notifications_client_id"]:
    return data_passed == data_saved

# Effettua l'invio di una notifica (definitiva da topic + message)
def notifications_send(entry, driver, chat_id, pattern, topic, message, notify_level):
  if driver == entry.config["notifications_client_id"] and entry.config["connect"]:
    #logging.debug("{id}> sending telegram message ...".format(id = entry.id))
    
    if entry.threshold_level >= 0 and notify_level in notifications_levels and notifications_levels[notify_level] <= entry.threshold_level:
      if not chat_id in entry.threshold_lock:
        entry.threshold_lock[chat_id] = threading.Lock()
        entry.threshold_collapsed[chat_id] = False
        entry.threshold_queue_collapsed[chat_id] = []
        entry.threshold_queue_win[chat_id] = []
      
      with entry.threshold_lock[chat_id]:
        entry.threshold_queue_win[chat_id] = [x for x in entry.threshold_queue_win[chat_id] if system.time() - x < entry.threshold_duration]
        entry.threshold_queue_win[chat_id].append(system.time())
        if entry.threshold_collapsed[chat_id] and len(entry.threshold_queue_win[chat_id]) <= entry.threshold_max / 2:
          threshold_queue_collapsed_send(entry, chat_id)
          entry.threshold_collapsed[chat_id] = False
          _send(entry, chat_id, _("Stopped collapsing messages."))

        elif not entry.threshold_collapsed[chat_id] and len(entry.threshold_queue_win[chat_id]) > entry.threshold_max:
          entry.threshold_collapsed[chat_id] = True
          _send(entry, chat_id, _("Started collapsing messages..."))
          
        if entry.threshold_collapsed[chat_id]:
          entry.threshold_queue_collapsed[chat_id].append([system.time(), notify_level, topic, message])
          return
    
    _send(entry, chat_id, message + " " + _("({level} notification from {f})").format(f = topic, level = notify_level))

def threshold_queue_collapsed_send(entry, chat_id, summary = True, messages = True, reset = True):
  if chat_id in entry.threshold_queue_collapsed and len(entry.threshold_queue_collapsed[chat_id]):
    _b = telegram_buffsend(init_entry = entry, init_chat_id = chat_id)
    if summary:
      by_level = {}
      c = 0
      for x in entry.threshold_queue_collapsed[chat_id]:
        c += 1
        if notifications_levels[x[1]] not in by_level:
          by_level[notifications_levels[x[1]]] = { 't': x[1], 'c': 0, 'from': {}}
        by_level[notifications_levels[x[1]]]['c'] += 1
        if x[2] not in by_level[notifications_levels[x[1]]]['from']:
          by_level[notifications_levels[x[1]]]['from'][x[2]] = 0
        by_level[notifications_levels[x[1]]]['from'][x[2]] += 1
          
      telegram_buffsend(_b, _("Collapsed messages") + ': ' + str(c))
      for l in sorted(by_level.keys(), reverse = True):
        telegram_buffsend(_b, '- ' + by_level[l]['t'] + ': ' + str(by_level[l]['c']) + ' (' + ', '.join([(x + ': ' + str(by_level[l]['from'][x])) for x in by_level[l]['from']]) + ')')
      if messages:
        telegram_buffsend(_b, '')
    else:
      telegram_buffsend(_b, _("Collapsed messages") + ':')
    
    if messages:
      for x in entry.threshold_queue_collapsed[chat_id]:
        telegram_buffsend(_b, utils.strftime(x[0]) + "> " + x[3] + " " + _("({level} notification from {f})").format(f = x[2], level = x[1]))

    telegram_buffsend(_b)
    
    if reset:
      entry.threshold_queue_collapsed[chat_id] = []
  else:
    _send(entry, chat_id, _("No collapsed messages"))

def telegram_help_handler(entry, update, context):
  # https://core.telegram.org/bots/api#sendmessage
  _b = telegram_buffsend(init_entry = entry, init_chat_id = update.effective_chat.id)
  telegram_buffsend(_b, "/notify_sub <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>: " + _("subscribe to notifications described by pattern"))
  telegram_buffsend(_b, "/show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  telegram_buffsend(_b, "/collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in topics_help:
    telegram_buffsend(_b, topics_help[t])
  telegram_buffsend(_b, "/TOPIC MESSAGE: " + _("send a generic TOPIC+MESSAGE to MQTT broker"))
  telegram_buffsend(_b)

def telegram_show_setcommands_handler(entry, update, context):
  _b = telegram_buffsend(init_entry = entry, init_chat_id = update.effective_chat.id)
  telegram_buffsend(_b, "notify_sub - " + _("subscribe to notifications described by pattern") + " - " + _("Syntax") + ": <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>")
  telegram_buffsend(_b, "show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  telegram_buffsend(_b, "collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in commands:
    telegram_buffsend(_b, t + " - " + commands[t]['help'])
  telegram_buffsend(_b)
  
def telegram_collapsed_handler(entry, update, context):
  threshold_queue_collapsed_send(entry, update.effective_chat.id)

def telegram_notify_sub_handler(entry, update, context):
  message = update.message or update.edited_message
  if not context.args:
    _send(entry, message.chat_id, _("Syntax error"), reply_to_message_id = message.message_id)
  else:
    telegram_command_handler(entry, update, context, "notifications/subscribe/" + context.args[0], entry.config["notifications_client_id"] + ":" + str(message.chat_id), 'notifications/subscribe/#')

def telegram_generic_message_handler(entry, update, context):
  message = update.message or update.edited_message
  if message.text and message.text.startswith('/') and len(message.text) > 1:
    parts = message.text_html.split(None, 1)
    if len(parts[0]) > 1 and parts[0].startswith('/'):
      command = parts[0][1:].split('@')
      command.append(context.bot.username) # in case the command was sent without a username
      if command[1].lower() == context.bot.username.lower():
        command = command[0]
        return telegram_command_handler(entry, update, context, command, parts[1] if len(parts) > 1 else None)
      
  return False

def telegram_command_handler(entry, update, context, command, args, command_def_string = False):
  message = update.message or update.edited_message
  if command in commands:
    command = commands[command]['topic']
  if not command_def_string:
    command_def_string = command
  #username = message.from_user.name
  
  topic_metadata = system.topic_subscription_definition(command_def_string, strict_match = True)
  if not topic_metadata:
    _send(entry, message.chat_id, _("Command not recognized, i'll send it to the broker, but i can't show any response"), reply_to_message_id = message.message_id)
  response_callback = lambda entry, id, message, final, response_to_message: _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message)
  no_response_callback = lambda entry, id, response_to_message: _on_telegram_command_no_response_handler(entry, update, id, response_to_message)
  entry.publish(command, args, response_callback = response_callback, no_response_callback = no_response_callback)

def _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message):
  pm = message.firstPublishedMessage()
  message = update.message or update.edited_message
  _send(entry, message.chat_id, pm.topic + ": " + ((pm.notificationString() + " (" + pm.notificationLevelString() + ")" + (" [" + str(pm.payload) + "]" if pm.payload is not None else "")) if pm.notificationString() else str(pm.payload)), reply_to_message_id = message.message_id)

def _on_telegram_command_no_response_handler(entry, update, id, response_to_message):
  message = update.message or update.edited_message
  _send(entry, message.chat_id, _("No response received for {command}").format(command = message.text), reply_to_message_id = message.message_id)

def telegram_error_handler(entry, update, context):
  logging.error(_("Telegram update '{update}' caused error '{error}'").format(update = update, error = context.error))
