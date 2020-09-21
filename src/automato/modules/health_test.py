# require python3
# -*- coding: utf-8 -*-

from automato.core import system
from automato.core import test

def test_init():
  test.add_node_config({
    "entries": [
      {
        "module": "health",
        "config": {
          'health-dead-disconnected-timeout': '1s',
          'health-alive-on-message': True,
          
          'health-check_interval-multiplier': 1.5,
          'health-checker-secs': .1,
        },
        "publish": {
          "health/status": {
            "run_interval": 1,
          }
        }
      },
      
      {
        "device": "test-device",
        "publish": {
          "@/lwt": {
            "type": ["online", "offline"],
            "events": {
              "connected": "js:({ value: payload == 'online' })",
            }
          },
          "@/check": {
            "type": None,
            "check_interval": "60",
          }
        },
        "subscribe": {
          "@/sub1": { "response": [ "@/sub1-res" ] },
          "@/sub2": { "response": [ { "topic": "@/sub2-resa", "count": 2 }, "@/sub2-resb" ] },
          "/^device/test-device/sub3(.*)$/": { "response": [ "@/sub3{matches[1]}-res" ] },
        }
      },
      {
        "item": "test-item",
        "required": [ "test-device" ],
      },
      {
        "item": "test-item2",
        "config": {
          "health-dead-message-timeout": "2s",
        },
        "publish": {
          "@/check": {
            "type": None,
          }
        }
      }
    ],
  })

def test_run(entries):
  # INIT
  test.waitPublish("device/test-device/lwt", "online")
  test.waitPublish("device/test-device/check", "") # sending @/check topic to avoid the "check_interval" failure
  
  if True:
    
    # Test device really offline (more than 1seconds) and health of device and item (that requires the device)
    test.assertPublish("dead", "device/test-device/lwt", "offline", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'dead', 'reason': 'disconnected for too long', 'time': ('d', system.time() + 1, 2) },
      'item/test-item/health': { 'value': 'failure', 'reason': ('re', '.*test-device.*dead.*'), 'time': ('d', system.time() + 1, 2) },
    }, timeoutms = 3000)
    
    # Online again
    test.assertPublish("alive-after-dead", "device/test-device/lwt", "online", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
      'item/test-item/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
    })
    
    # Offline, but not really
    test.waitPublish("device/test-device/lwt", "offline")
    test.assertPublish("not-dead", "device/test-device/lwt", "online", assertSubscribeNotReceive = ['device/test-device/health', 'item/test-item/health'])
  
  # check_interval
  if True:
    system.time_offset(90)
    test.assertx("check-interval", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'failure', 'reason': ('re', '.*device/test-device/check.*'), 'time': ('d', system.time(), 2) },
      'item/test-item/health': { 'value': 'failure', 'reason': ('re', '.*test-device.*failure.*'), 'time': ('d', system.time(), 2) },
    })
  
    test.assertPublish("check-interval-resume", "device/test-device/check", "", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
      'item/test-item/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
    })
  
  if True:
    test.assertPublish("no-response", "device/test-device/sub1", "", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'failure', 'reason': ('re', '.*device/test-device/sub1.*'), 'time': ('d', system.time(), 6) },
      'item/test-item/health': { 'value': 'failure', 'reason': ('re', '.*test-device.*failure.*'), 'time': ('d', system.time(), 6) },
    }, timeoutms = 7000)
    
    test.waitPublish("device/test-device/sub1", "")
    test.assertPublish("correct-response", "device/test-device/sub1-res", "", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
      'item/test-item/health': { 'value': 'alive','reason': '',  'time': ('d', system.time()) },
    })
    
    """ TODO Il testo sotto sarebbe per la gestione corretta del "count", ma al momento non funziona (basta una qualunque risposta per evitare il failure)
      Questo perchè per il momento si è deciso che "response_callback" viene chiamato (con final = False) per qualunque risposta, e no_response_callback se anche solo un response_callback è stato chiamato non viene chiamato
      Volendo gestire il check "stretto" bisognerebbe fare anche un response_incomplete_callback oppure cambiare no_response_callback in response_error_callback con errore che può essere "no_response" o "incomplete" ... ma per ora è eccessivo
    test.assertx("no-response2", waitPublish = [
      ("device/test-device/sub2", None), 
      ("device/test-device/sub2-resa", None), 
      #("device/test-device/sub2-resa", None), 
      ("device/test-device/sub2-resb", None), 
    ], assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'failure', 'reason': ('re', '.*device/test-device/sub2.*'), 'time': ('d', system.time(), 6) },
      'item/test-item/health': { 'value': 'failure', 'reason': ('re', '.*test-device.*failure.*'), 'time': ('d', system.time(), 6) },
    }, timeoutms = 7000)
    """

    test.waitPublish("device/test-device/sub3xxx", "")
    test.assertPublish("no-response3", "device/test-device/sub3yyy-res", "", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'failure', 'reason': ('re', '.*device/test-device/sub3.*'), 'time': ('d', system.time(), 6) },
      'item/test-item/health': { 'value': 'failure', 'reason': ('re', '.*test-device.*failure.*'), 'time': ('d', system.time(), 6) },
    }, timeoutms = 7000)
    
    test.waitPublish("device/test-device/sub3xxx", "")
    test.assertPublish("correct-response3", "device/test-device/sub3xxx-res", "", assertSubscribeSomePayload = { 
      'device/test-device/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time()) },
      'item/test-item/health': { 'value': 'alive','reason': '',  'time': ('d', system.time()) },
    })

  if True:
    # dead-message-timeout
    test.assertPublish("dead-message-timeout-pre", "item/test-item2/check", "", assertSubscribeSomePayload = {
      'item/test-item2/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time(), 2) },
    })
    test.assertx("dead-message-timeout", assertSubscribeSomePayload = { 
      'item/test-item2/health': { 'value': 'dead', 'reason': 'silent for too long', 'time': ('d', system.time(), 4) },
    }, timeoutms = 3000)
    test.assertPublish("dead-message-timeout-post", "item/test-item2/check", "", assertSubscribeSomePayload = {
      'item/test-item2/health': { 'value': 'alive', 'reason': '', 'time': ('d', system.time(), 2) },
    })
