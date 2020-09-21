# require python3
# -*- coding: utf-8 -*-

# https://core.telegram.org/bots
# https://github.com/python-telegram-bot/python-telegram-bot

import logging
import json
import re
from logging.handlers import TimedRotatingFileHandler

import telegram
from telegram.ext import Updater
from telegram.ext import Filters
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler

from automato.core import system

definition = {
  'config': {
    "token": "",
    "connect": True,
    "exclude_topic_prefixes_in_quick_commands": "home/", # regexp part, example: "home/|net/"
    "quick_commands": True,
    "quick_commands_regexp": "^(?:home/)?(?:get-)?(.*?)(?:/get)?$",
    "log": False,
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
    
    entry.bot = telegram.Bot(token = entry.config['token'])
    
    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.updater.html#telegram.ext.updater.Updater
    entry.updater = Updater(token = entry.config['token'])
    entry.dispatcher = entry.updater.dispatcher

    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.commandhandler.html
    # http://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.dispatcher.html#telegram.ext.dispatcher.Dispatcher.add_handler
    entry.dispatcher.add_handler(CommandHandler('help', lambda bot, update: telegram_help_handler(entry, bot, update), allow_edited = True))
    entry.dispatcher.add_handler(CommandHandler('show_setcommands', lambda bot, update: telegram_show_setcommands_handler(entry, bot, update), allow_edited = True))
    entry.dispatcher.add_handler(CommandHandler('notify_sub', lambda bot, update, args: telegram_notify_sub_handler(entry, bot, update, args), allow_edited = True, pass_args = True))
    entry.dispatcher.add_handler(MessageHandler(Filters.command, lambda bot, update: telegram_generic_message_handler(entry, bot, update), edited_updates = True))
    entry.dispatcher.add_error_handler(lambda bot, update, error: telegram_error_handler(entry, bot, update, error))
    
    entry.updater.start_polling()

def system_metadata_change(entry):
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

# Chiamato al subscribe, può verificare i dati passati (in data, in formato stringa) e eventualmente sostituirli (in modo da salvare per le chiamate successive dei dati diversi)
# @return i dati da salvare (in formato stringa)
def notifications_subscribe(entry, driver, data, pattern):
  if driver == "telegram":
    return data

# Usato per l'unsubscribe, verifica che i dati passati dalla chiamata mqtt e i dati di un record su db siano equivalenti (e quindi nel caso può eliminare tale record)
def notifications_matches(entry, driver, data_passed, data_saved, pattern):
  if driver == "telegram":
    return data_passed == data_saved

# Effettua l'invio di una notifica (definitiva da topic + message)
def notifications_send(entry, driver, data, pattern, topic, message, notify_level):
  if driver == "telegram":
    entry.bot.send_message(chat_id = data, text = message + " " + _("({level} notification from {f})").format(f = topic, level = notify_level))

def telegram_help_handler(entry, bot, update):
  # https://core.telegram.org/bots/api#sendmessage
  message = "/notify_sub <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>: " + _("subscribe to notifications described by pattern") + "\n"
  message += "/show_setcommands - " + _("Show commands description, use this for botfather's /setcommands") + "\n"
  for t in topics_help:
    message += topics_help[t] + "\n"
  message += "/TOPIC MESSAGE: " + _("send a generic TOPIC+MESSAGE to MQTT broker") + "\n"
  bot.send_message(chat_id = update.message.chat_id, text = message)

def telegram_show_setcommands_handler(entry, bot, update):
  message = "notify_sub - " + _("subscribe to notifications described by pattern") + " - " + _("Syntax") + ": <LEVEL:(debug|info|warn|error|critical)[_]|_>/<TYPE|_>/<TOPIC|_>\n"
  message += "show_setcommands - " + _("Show commands description, use this for botfather's /setcommands") + "\n"
  for t in commands:
    message += t + " - " + commands[t]['help'] + "\n"
  bot.send_message(chat_id = update.message.chat_id, text = message)

def telegram_notify_sub_handler(entry, bot, update, args):
  message = update.message or update.edited_message
  if not args:
    entry.bot.send_message(chat_id = message.chat_id, text = _("Syntax error"), reply_to_message_id = message.message_id)
  else:
    telegram_command_handler(entry, bot, update, "notifications/subscribe/" + args[0], "telegram:" + str(message.chat_id), 'notifications/subscribe/#')

def telegram_generic_message_handler(entry, bot, update):
  message = update.message or update.edited_message
  if message.text and message.text.startswith('/') and len(message.text) > 1:
    parts = message.text_html.split(None, 1)
    if len(parts[0]) > 1 and parts[0].startswith('/'):
      command = parts[0][1:].split('@')
      command.append(message.bot.username) # in case the command was sent without a username
      if command[1].lower() == message.bot.username.lower():
        command = command[0]
        return telegram_command_handler(entry, bot, update, command, parts[1] if len(parts) > 1 else None)
      
  return False

def telegram_command_handler(entry, bot, update, command, args, command_def_string = False):
  message = update.message or update.edited_message
  if command in commands:
    command = commands[command]['topic']
  if not command_def_string:
    command_def_string = command
  #username = message.from_user.name
  
  topic_metadata = system.topic_subscription_definition(command_def_string, strict_match = True)
  if not topic_metadata:
    bot.send_message(chat_id = message.chat_id, text = _("Command not recognized, i'll send it to the broker, but i can't show any response"), reply_to_message_id = message.message_id)
  response_callback = lambda entry, id, message, final, response_to_message: _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message)
  no_response_callback = lambda entry, id, response_to_message: _on_telegram_command_no_response_handler(entry, update, id, response_to_message)
  entry.publish(command, args, response_callback = response_callback, no_response_callback = no_response_callback)

def _on_telegram_command_response_handler(entry, update, id, message, final, response_to_message):
  pm = message.firstPublishedMessage()
  message = update.message or update.edited_message
  entry.bot.send_message(chat_id = message.chat_id, text = pm.topic + ": " + ((pm.notificationString() + " (" + pm.notificationLevelString() + ")" + (" [" + str(pm.payload) + "]" if pm.payload is not None else "")) if pm.notificationString() else str(pm.payload)), reply_to_message_id = message.message_id)

def _on_telegram_command_no_response_handler(entry, update, id, response_to_message):
  message = update.message or update.edited_message
  entry.bot.send_message(chat_id = message.chat_id, text = _("No response received for {command}").format(command = message.text), reply_to_message_id = message.message_id)

def telegram_error_handler(entry, bot, update, error):
  logging.error(_("Telegram update '{update}' caused error '{error}'").format(update = update, error = error))
