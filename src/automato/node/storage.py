# require python3
# -*- coding: utf-8 -*-

import logging
import os
import json

from automato.core import system
from automato.core import utils

path = './data'

STORAGE_BACKUP_TIME = 5 * 60

def init(_path):
  global path
  path = os.path.realpath(os.path.join(os.getcwd(), _path))
  
def destroy():
  pass
  
def entry_install(self, entry):
  entry.storage = self
  entry.store_data = lambda blocking = True: storeData(entry, blocking)
  entry.store_data_saved = None
  entry.store_backup_time = 0

def fileExists(file):
  return os.path.isfile(path + '/' + file)

def fileOpen(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
  return open(path + '/' + file, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline, closefd=closefd, opener=opener)

def fileRemove(file):
  return os.remove(path + '/' + file)
  
def fileRename(file1, file2):
  return os.rename(path + '/' + file1, path + '/' + file2)

def retrieveData(entry):
  entry.data_lock.acquire()
  try:
    loaded = _retrieveDataFrom(entry, entry.node_name + '_data_' + entry.id_local + '.json')
    if not loaded:
      loaded = _retrieveDataFrom(entry, entry.node_name + '_data_' + entry.id_local + '.backup.json')
  finally:
    entry.data_lock.release()

def _retrieveDataFrom(entry, filename):
  if os.path.isfile(path + '/' + filename):
    with fileOpen(filename, 'r') as f:
      c = f.read()
      if c:
        try:
          entry.data = utils.json_import(c)
          logging.debug("#{id}> storage: retrieved data from {filename}: {data}".format(id = entry.id, filename = filename, data = entry.data if len(str(entry.data)) < 500 else str(entry.data)[:500] + '...'))
          return True
        except:
          logging.exception("#{id}> storage: failed retrieving data from {filename}".format(id = entry.id, filename = filename))
      else:
        logging.error("#{id}> storage: retrieved empty data from {filename}".format(id = entry.id, filename = filename))
  else:
    logging.info("#{id}> storage: data file not found: {filename}".format(id = entry.id, filename = filename))
  return False
  
def storeData(entry, blocking = True):
  if not entry.data:
    return False
  if not entry.data_lock.acquire(blocking):
    return False
  try:
    _s = system._stats_start()

    cmpdata = repr(entry.data)
    data = None
    if entry.store_data_saved != cmpdata:
      data = utils.json_export(entry.data)
      _storeDataTo(entry, entry.node_name + '_data_' + entry.id_local + '.json', data)
      entry.store_data_saved = cmpdata
    if system.time() - entry.store_backup_time > STORAGE_BACKUP_TIME:
      if not data:
        data = utils.json_export(entry.data)
      _storeDataTo(entry, entry.node_name + '_data_' + entry.id_local + '.backup.json', data)
      entry.store_backup_time = system.time()

    return True
  except:
    logging.exception("#{id}> failed storing data".format(id = entry.id))
    return False
  finally:
    entry.data_lock.release()
    system._stats_end('storage.store_data', _s)

def _storeDataTo(entry, filename, data):
  if os.path.isfile(path + '/' + filename + '.new'):
    os.remove(path + '/' + filename + '.new')
  with fileOpen(filename + '.new', 'w') as f:
    try:
      f.write(data)
    except:
      logging.exception("Failed storing data for module {id}: {data}".format(id = entry.id, data = entry.data))
  if os.path.isfile(path + '/' + filename + '.new'):
    if os.path.isfile(path + '/' + filename):
      os.remove(path + '/' + filename)
    os.rename(path + '/' + filename + '.new', path + '/' + filename)
  
'''
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
notifications_file = os.path.join(__location__, notifications_file)
'''
