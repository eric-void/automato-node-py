# require python3
# -*- coding: utf-8 -*-

# https://core.telegram.org/bots
# https://github.com/python-telegram-bot/python-telegram-bot

import logging
import json
import re
import threading
from logging.handlers import TimedRotatingFileHandler

import telegram
from telegram.ext import Updater
from telegram.ext import Filters
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
    
    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.updater.html#telegram.ext.updater.Updater
    entry.updater = Updater(token = entry.config['token'], use_context = True)
    entry.dispatcher = entry.updater.dispatcher

    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.commandhandler.html
    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.dispatcher.html#telegram.ext.dispatcher.Dispatcher.add_handler
    entry.dispatcher.add_handler(CommandHandler('help', lambda update, context: telegram_help_handler(entry, update, context)))
    entry.dispatcher.add_handler(CommandHandler('show_setcommands', lambda update, context: telegram_show_setcommands_handler(entry, update, context)))
    entry.dispatcher.add_handler(CommandHandler('notify_sub', lambda update, context: telegram_notify_sub_handler(entry, update, context), pass_args = True))
    entry.dispatcher.add_handler(CommandHandler('collapsed', lambda update, context: telegram_collapsed_handler(entry, update, context)))
    entry.dispatcher.add_handler(MessageHandler(Filters.command, lambda update, context: telegram_generic_message_handler(entry, update, context)))
    entry.dispatcher.add_error_handler(lambda update, context: telegram_error_handler(entry, update, context))
    
    entry.updater.start_polling()

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
  if entry.config["connect"]:
    entry.updater.stop()

def run(entry):
  for chat_id in entry.threshold_lock:
    with entry.threshold_lock[chat_id]:
      if len(entry.threshold_queue_collapsed[chat_id]) > 0 and system.time() - entry.threshold_queue_collapsed[chat_id][0][0] >= entry.threshold_duration_max:
        threshold_queue_collapsed_send(entry, chat_id)

def telegram_buffsend(mbuffer = None, message = None, init_bot = None, init_entry = None, init_chat_id = None):
  if init_chat_id:
    mbuffer = { 'bot': init_bot if init_bot else init_entry.updater.bot, 'chat_id': init_chat_id, 'text': ""}
    return mbuffer

  if message == None or len(mbuffer['text']) + len(message) + 2 >= 4096:
    mbuffer['bot'].send_message(chat_id = mbuffer['chat_id'], text = mbuffer['text'])
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
  if driver == entry.config["notifications_client_id"]:
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
          entry.updater.bot.send_message(chat_id = chat_id, text = _("Stopped collapsing messages."))

        elif not entry.threshold_collapsed[chat_id] and len(entry.threshold_queue_win[chat_id]) > entry.threshold_max:
          entry.threshold_collapsed[chat_id] = True
          entry.updater.bot.send_message(chat_id = chat_id, text = _("Started collapsing messages..."))
          
        if entry.threshold_collapsed[chat_id]:
          entry.threshold_queue_collapsed[chat_id].append([system.time(), notify_level, topic, message])
          return
    
    entry.updater.bot.send_message(chat_id = chat_id, text = message + " " + _("({level} notification from {f})").format(f = topic, level = notify_level))

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
      if (messages)
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
    entry.updater.bot.send_message(chat_id = chat_id, text = _("No collapsed messages"))

def telegram_help_handler(entry, update, context):
  # https://core.telegram.org/bots/api#sendmessage
  _b = telegram_buffsend(init_bot = context.bot, init_chat_id = update.message.chat_id)
  telegram_buffsend(_b, "/notify_sub <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>: " + _("subscribe to notifications described by pattern"))
  telegram_buffsend(_b, "/show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  telegram_buffsend(_b, "/collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in topics_help:
    telegram_buffsend(_b, topics_help[t])
  telegram_buffsend(_b, "/TOPIC MESSAGE: " + _("send a generic TOPIC+MESSAGE to MQTT broker"))
  telegram_buffsend(_b)

def telegram_show_setcommands_handler(entry, update, context):
  _b = telegram_buffsend(init_bot = context.bot, init_chat_id = update.message.chat_id)
  telegram_buffsend(_b, "notify_sub - " + _("subscribe to notifications described by pattern") + " - " + _("Syntax") + ": <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>")
  telegram_buffsend(_b, "show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  telegram_buffsend(_b, "collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in commands:
    telegram_buffsend(_b, t + " - " + commands[t]['help'])
  telegram_buffsend(_b)
  
def telegram_collapsed_handler(entry, update, context):
  threshold_queue_collapsed_send(entry, update.message.chat_id)

def telegram_notify_sub_handler(entry, update, context):
  message = update.message or update.edited_message
  if not context.args:
    context.bot.send_message(chat_id = message.chat_id, text = _("Syntax error"), reply_to_message_id = message.message_id)
  else:
    telegram_command_handler(entry, update, context, "notifications/subscribe/" + context.args[0], entry.config["notifications_client_id"] + ":" + str(message.chat_id), 'notifications/subscribe/#')

def telegram_generic_message_handler(entry, update, context):
  message = update.message or update.edited_message
  if message.text and message.text.startswith('/') and len(message.text) > 1:
    parts = message.text_html.split(None, 1)
    if len(parts[0]) > 1 and parts[0].startswith('/'):
      command = parts[0][1:].split('@')
      command.append(message.bot.username) # in case the command was sent without a username
      if command[1].lower() == message.bot.username.lower():
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
    context.bot.send_message(chat_id = message.chat_id, text = _("Command not recognized, i'll send it to the broker, but i can't show any response"), reply_to_message_id = message.message_id)
  response_callback = lambda entry, id, message, final, response_to_message: _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message)
  no_response_callback = lambda entry, id, response_to_message: _on_telegram_command_no_response_handler(entry, update, id, response_to_message)
  entry.publish(command, args, response_callback = response_callback, no_response_callback = no_response_callback)

def _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message):
  pm = message.firstPublishedMessage()
  message = update.message or update.edited_message
  entry.updater.bot.send_message(chat_id = message.chat_id, text = pm.topic + ": " + ((pm.notificationString() + " (" + pm.notificationLevelString() + ")" + (" [" + str(pm.payload) + "]" if pm.payload is not None else "")) if pm.notificationString() else str(pm.payload)), reply_to_message_id = message.message_id)

def _on_telegram_command_no_response_handler(entry, update, id, response_to_message):
  message = update.message or update.edited_message
  entry.updater.bot.send_message(chat_id = message.chat_id, text = _("No response received for {command}").format(command = message.text), reply_to_message_id = message.message_id)

def telegram_error_handler(entry, update, context):
  logging.error(_("Telegram update '{update}' caused error '{error}'").format(update = update, error = context.error))
