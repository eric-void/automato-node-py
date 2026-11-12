# require python3
# -*- coding: utf-8 -*-

import logging
import os
import json
import zlib
import hashlib
import threading

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
  entry.store_data = lambda blocking = True, timeout = -1: storeData(entry, blocking, timeout)
  entry.store_data_saved = None
  entry.store_backup_saved = None
  entry.store_write_lock = threading.Lock()
  entry.store_backup_time = 0
  # First periodic check is spread over the interval, so entries are not all checked in the same second
  entry.store_data_next = 0

def entry_uninstall(self, entry):
  pass

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
    if loaded:
      # Data is the same as the stored one: no need to write it back until it changes
      entry.store_data_saved = _data_signature(entry.data)
    else:
      loaded = _retrieveDataFrom(entry, entry.node_name + '_data_' + entry.id_local + '.backup.json')
  finally:
    entry.data_lock.release()

def _retrieveDataFrom(entry, filename):
  if os.path.isfile(path + '/' + filename):
    with fileOpen(filename, 'r') as f:
      c = f.read()
      if c:
        try:
          data = utils.json_import(c)
          if not isinstance(data, dict):
            raise ValueError("invalid data (not a json object)")
          entry.data = data
          logging.debug("#{id}> storage: retrieved data from {filename}: {data}".format(id = entry.id, filename = filename, data = entry.data if len(str(entry.data)) < 500 else str(entry.data)[:500] + '...'))
          return True
        except:
          logging.exception("#{id}> storage: failed retrieving data from {filename}".format(id = entry.id, filename = filename))
      else:
        logging.error("#{id}> storage: retrieved empty data from {filename}".format(id = entry.id, filename = filename))
  else:
    logging.info("#{id}> storage: data file not found: {filename}".format(id = entry.id, filename = filename))
  return False
  
STORAGE_CHECK_INTERVAL = 10

def storeDataIfDue(entry, now, interval = STORAGE_CHECK_INTERVAL):
  """
  Periodic store (called by node run loop): checks entry data for changes (and stores it) at most every "interval" seconds.
  Checking means a repr() of entry.data, that is expensive with big data on slow nodes: doing it every second is a waste.
  """
  if not entry.store_data_next:
    entry.store_data_next = now + zlib.crc32(entry.id.encode('utf-8')) % max(1, int(interval))
  if now < entry.store_data_next:
    return False
  entry.store_data_next = now + interval
  return storeData(entry, False)

def _data_signature(data):
  # A digest of repr(data) is kept, instead of the repr itself (data can be big)
  return hashlib.md5(repr(data).encode('utf-8', 'backslashreplace')).digest()

def storeData(entry, blocking = True, timeout = -1):
  """
  Store entry data, if changed from last store. A backup copy is written every STORAGE_BACKUP_TIME seconds, if data changed from last backup.
  entry.data_lock is held only to take a snapshot of data (json), not during file writing (that can be slow, with fsync on a slow disk): scripts and handlers of the entry are not blocked by it.
  Writes of the same entry are serialized by entry.store_write_lock (so an older snapshot can't overwrite a newer one).
  @param blocking, timeout passed to locks acquire (if locks can't be acquired, data is not stored)
  """
  if not entry.data and entry.store_data_saved is None:
    return False
  if not entry.store_write_lock.acquire(blocking, timeout if blocking else -1):
    return False
  _s = system._stats_start()
  try:
    if not entry.data_lock.acquire(blocking, timeout if blocking else -1):
      return False
    try:
      signature = _data_signature(entry.data)
      write_data = entry.store_data_saved != signature
      write_backup = entry.store_backup_saved != signature and system.time() - entry.store_backup_time > STORAGE_BACKUP_TIME
      data = utils.json_export(entry.data) if write_data or write_backup else None
    finally:
      entry.data_lock.release()

    if data is None:
      return not (write_data or write_backup)
    if write_data and _storeDataTo(entry, entry.node_name + '_data_' + entry.id_local + '.json', data):
      entry.store_data_saved = signature
    if write_backup and _storeDataTo(entry, entry.node_name + '_data_' + entry.id_local + '.backup.json', data):
      entry.store_backup_saved = signature
      entry.store_backup_time = system.time()
    return True
  except:
    logging.exception("#{id}> failed storing data".format(id = entry.id))
    return False
  finally:
    entry.store_write_lock.release()
    system._stats_end('storage.store_data', _s)

def _storeDataTo(entry, filename, data):
  """
  Write data to a temporary file, and replace the destination only if writing succeeded (os.replace is atomic: the previous file is kept until the new one is complete)
  @return True if stored
  """
  tmp = path + '/' + filename + '.new'
  try:
    with open(tmp, 'w') as f:
      f.write(data)
      f.flush()
      os.fsync(f.fileno())
    os.replace(tmp, path + '/' + filename)
    return True
  except:
    logging.exception("#{id}> storage: failed storing data to {filename}".format(id = entry.id, filename = filename))
    try:
      if os.path.isfile(tmp):
        os.remove(tmp)
    except:
      pass
    return False

