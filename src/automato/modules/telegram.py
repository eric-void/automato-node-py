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
    "threshold_duration": "6h",
    "threshold_duration_max": "24h",
  }
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
      
    entry.threshold_lock = threading.Lock()
    entry.threshold_queue_collapsed = []
    entry.threshold_queue_win = []
    entry.threshold_level = notifications_levels[entry.config["threshold_level"]] if entry.config["threshold_level"] in notifications_levels else -1
    entry.threshold_max = entry.config["threshold_max"]
    entry.threshold_duration = utils.read_duration(entry.config["threshold_duration"])
    entry.threshold_duration_max = utils.read_duration(entry.config["threshold_duration_max"])
    
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

def telegram_buffsend(entry, chat_id, mbuffer, message = -1):
  if message == -1 or len(mbuffer) + len(message) + 2 >= 4096:
    entry.updater.bot.send_message(chat_id = chat_id, text = mbuffer)
    mbuffer = ""
  if message != -1:
    mbuffer += message + "\n"
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
def notifications_send(entry, driver, data, pattern, topic, message, notify_level):
  if driver == entry.config["notifications_client_id"]:
    #logging.debug("{id}> sending telegram message ...".format(id = entry.id))
    
    if entry.threshold_level >= 0 and notify_level in notifications_levels and notifications_levels[level] <= entry.threshold_level:
      with entry.threshold_lock:
        entry.threshold_queue_win = [x for x in entry.threshold_queue_win if system.time() - x < entry.threshold_duration]
        entry.threshold_queue_win.append(system.time())
        if len(entry.threshold_queue_collapsed) > 0 and (len(entry.threshold_queue_win) <= entry.threshold_max / 2 or system.time() - entry.threshold_queue_collapsed[0][0] >= entry.threshold_duration_max):
          threshold_queue_collapsed_send(entry, data)

        if len(entry.threshold_queue_win) > entry.threshold_max:
          if len(entry.threshold_queue_collapsed) == 0:
            entry.updater.bot.send_message(chat_id = data, text = _("Start collapsing messages..."))
            
          entry.threshold_queue_collapsed.append([system.time(), notify_level, topic, message])
          return
    
    entry.updater.bot.send_message(chat_id = data, text = message + " " + _("({level} notification from {f})").format(f = topic, level = notify_level))

def threshold_queue_collapsed_send(entry, chat_id):
  if len(entry.threshold_queue_collapsed):
    _b = telegram_buffsend(entry, chat_id, "", _("Collapsed messages:"))
    for x in entry.threshold_queue_collapsed:
      _b = telegram_buffsend(entry, chat_id, _b, utils.strftime(x[0]) + "> " + x[3] + " " + _("({level} notification from {f})").format(f = x[2], level = x[1]))
    telegram_buffsend(entry, chat_id, _b)
    entry.threshold_queue_collapsed = []
  else:
    entry.updater.bot.send_message(chat_id = chat_id, text = _("No collapsed messages"))

def telegram_help_handler(entry, update, context):
  # https://core.telegram.org/bots/api#sendmessage
  chat_id = update.message.chat_id
  _b = telegram_buffsend(entry, chat_id, "", "/notify_sub <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>: " + _("subscribe to notifications described by pattern"))
  _b = telegram_buffsend(entry, chat_id, _b, "/show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  _b = telegram_buffsend(entry, chat_id, _b, "/collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in topics_help:
    context.bot.send_message(chat_id = update.message.chat_id, text = topics_help[t])
  _b = telegram_buffsend(entry, chat_id, _b, "/TOPIC MESSAGE: " + _("send a generic TOPIC+MESSAGE to MQTT broker"))
  telegram_buffsend(entry, chat_id, _b)

def telegram_show_setcommands_handler(entry, update, context):
  chat_id = update.message.chat_id
  _b = telegram_buffsend(entry, chat_id, "", "notify_sub - " + _("subscribe to notifications described by pattern") + " - " + _("Syntax") + ": <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>")
  _b = telegram_buffsend(entry, chat_id, _b, "show_setcommands - " + _("Show commands description, use this for botfather's /setcommands"))
  _b = telegram_buffsend(entry, chat_id, _b, "collapsed - " + _("Show collapsed messages, if present, and clear collapsed messages queue"))
  for t in commands:
    _b = telegram_buffsend(entry, chat_id, _b, t + " - " + commands[t]['help'])
  telegram_buffsend(entry, chat_id, _b)
  
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
