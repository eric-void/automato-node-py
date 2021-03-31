# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test
from automato.node import node_system

def test_init():
  pass

def system_on_entry_load(entry):
  test.assertChild("system_started_loading_" + entry.id)

def test_run(entries):
  system.on_entry_load(system_on_entry_load)
  
  e_scripting = { "module": "scripting" }
  e_module0 = {
      "module": "module0",
      "module1": "on",
      "methods": {
        "entry_load": [ "print('> Loading module0 on ' + str(args[1].id))", "test.assertChild('module0_loaded_on_' + str(args[1].id))" ],
      }
    }
  e_module1 = {
      "module": "module1",
      "install_on": { "module1": "on" },
      "methods": {
        "entry_install": [ "print('> Installing module1 on ' + str(args[1].id))", "test.assertChild('module1_installed_on_' + str(args[1].id))" ],
        "init": [ "print('> Initializing module1' + entry.id)", "entry.test_val = 'x'" ],
        "entry_init": [ "print('> Entry init module1 on ' + str(args[1].id))", "test.assertChild('module1_initialized_' + str(args[1].id), assertEq = [(hasattr(args[0], 'test_val') and args[0].test_val == 'x', True)])" ],
      }
    }
  
  # Installati in ordine, riesce a fare tutto
  test.assertx('t1', 
    assertChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST', 'module1_initialized_module0@TEST', "system_started_loading_module0@TEST", "system_started_loading_module1@TEST"], 
    assertNotChild = ['module1_installed_on_module1@TEST', 'module1_initialized_module1@TEST'], wait = False)
  system.entry_load([e_scripting, e_module0, e_module1], id_from_definition = True)
  test.waitRunning()
  
  # Test signatures (non deve ricaricare se gli do le stesse definizioni)
  test.assertx('t1_sign_unchanged', 
    assertNotChild = ["system_started_loading_module0@TEST", "system_started_loading_module1@TEST"], wait = False)
  system.entry_load([e_module0, e_module1], id_from_definition = True)
  test.waitRunning()
  
  test.assertx('t1_sign_changed',
    # WARN module0_loaded_on_scripting@TEST is called with a warning "Calling module0@TEST.entry_load on scripting@TEST, but scripting@TEST has not been reloaded". See the code on node_system to understand the problem.
    assertChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST', 'module1_initialized_module0@TEST', "system_started_loading_module0@TEST", "system_started_loading_module1@TEST"], 
    assertNotChild = ['system_started_loading_scripting@TEST'], wait = False)
  e_module1["description"] = "..."
  system.entry_load([e_module0, e_module1], id_from_definition = True)
  test.waitRunning()

  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])
  
  # Scripting per ultimo: non viene chiamato script entry_load dei moduli, perchè è un handler gestito via script che viene caricato dopo, però viene chiamato entry_install (perchè gli install sono dopo i load)
  test.assertx('t2', assertNotChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST'], assertChild = ['module1_installed_on_module0@TEST', 'module1_initialized_module0@TEST'], wait = False)
  system.entry_load([e_module0, e_module1, e_scripting], id_from_definition = True)
  test.waitRunning()
  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])

  # Caricando scripting in un secondo momento fa un reload generale, e quindi va (ma fa dei loading di troppo)
  test.assertx('t3a', assertNotChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST', 'module1_initialized_module0@TEST'], wait = False)
  system.entry_load([e_module0, e_module1], id_from_definition = True)
  test.waitRunning()
  test.assertx('t3b', assertChild = ['module0_loaded_on_scripting@TEST', 'module0_loaded_on_module1@TEST', 'module1_installed_on_module0@TEST', 'module1_initialized_module0@TEST'], wait = False)
  system.entry_load([e_scripting], id_from_definition = True)
  test.waitRunning()
  system.entry_unload(["scripting@TEST", "module0@TEST", "module1@TEST"])
