# require python3
# -*- coding: utf-8 -*-

import logging
import os
import json

from automato.core import system

path = './data'

def init(_path):
  global path
  path = os.path.realpath(os.path.join(os.getcwd(), _path))
  
def destroy():
  pass
  
def entry_install(self, entry):
  entry.storage = self
  entry.store_data = lambda blocking = True: storeData(entry, blocking)
  entry.store_data_saved = None
  entry.store_timems = 0

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
    if os.path.isfile(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json'):
      with fileOpen(entry.node_name + '_data_' + entry.id_local + '.json', 'r') as f:
        c = f.read()
        if c:
          try:
            entry.data = json.loads(c)
            logging.debug("#{id}> retrieved data: {data}".format(id = entry.id, data = entry.data if len(str(entry.data)) < 500 else str(entry.data)[:500] + '...'))
          except:
            logging.exception("#{id}> failed retrieving data".format(id = entry.id))
  finally:
    entry.data_lock.release()

def storeData(entry, blocking = True):
  if not entry.data:
    return False
  if not entry.data_lock.acquire(blocking):
    return False
  try:
    _s = system._stats_start()
    _s2 = False

    cmpdata = repr(entry.data)
    if entry.store_data_saved != cmpdata:
      data = json.dumps(entry.data)
      
      _s2 = system._stats_start()
      if os.path.isfile(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json.new'):
        os.remove(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json.new')
      with fileOpen(entry.node_name + '_data_' + entry.id_local + '.json.new', 'w') as f:
        try:
          f.write(data)
        except:
          logging.exception("Failed storing data for module {id}: {data}".format(id = entry.id, data = entry.data))
      if os.path.isfile(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json.new'):
        if os.path.isfile(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json'):
          os.remove(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json')
        os.rename(path + '/' + entry.node_name + '_data_' + entry.id_local + '.json.new', path + '/' + entry.node_name + '_data_' + entry.id_local + '.json')
      
      entry.store_data_saved = cmpdata
    return True
  except:
    logging.exception("#{id}> failed storing data".format(id = entry.id))
    return False
  finally:
    entry.data_lock.release()
    system._stats_end('storage.store_data', _s)
    if _s2:
      system._stats_end('storage.store_data', _s)

'''
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
notifications_file = os.path.join(__location__, notifications_file)
'''
