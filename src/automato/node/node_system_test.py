# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test
from automato.node import node_system

def test_init():
  pass

def test_run(entries):
  e_scripting = { "module": "scripting" }
  e_module0 = {
      "module": "module0",
      "module1": "on",
      "methods": {
        "entry_load": [ "print('> Loading module0 on ' + str(args[1].id))", "test.assertChild('module0_loaded_on_' + str(args[1].id))" ]
      }
    }
  e_module1 = {
      "module": "module1",
      "install_on": { "module1": "on" },
      "methods": {
        "entry_install": [ "print('> Installing module1 on ' + str(args[1].id))", "test.assertChild('module1_installed_on_' + str(args[1].id))" ]
      }
    }
  
  # Installati in ordine, riesce a fare tutto
  test.assertx('t1', assertChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST'], wait = False)
  system.entry_load([e_scripting, e_module0, e_module1], id_from_definition = True)
  test.waitRunning()
  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])
  
  # Scripting per ultimo: non viene chiamato script entry_load dei moduli, perchè è un handler gestito via script che viene caricato dopo, però viene chiamato entry_install (perchè gli install sono dopo i load)
  test.assertx('t2', assertNotChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST'], assertChild = ['module1_installed_on_module0@TEST'], wait = False)
  system.entry_load([e_module0, e_module1, e_scripting], id_from_definition = True)
  test.waitRunning()
  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])

  # Caricando scripting in un secondo momento fa un reload generale, e quindi va (ma fa dei loading di troppo)
  test.assertx('t3a', assertNotChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST'], wait = False)
  system.entry_load([e_module0, e_module1], id_from_definition = True)
  test.waitRunning()
  test.assertx('t3b', assertChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST'], wait = False)
  system.entry_load([e_scripting], id_from_definition = True)
  test.waitRunning()
  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])
