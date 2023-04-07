# require python3
# -*- coding: utf-8 -*-

from automato.core import test
from automato.core import system

def test_init():
  test.add_node_config({
    "listen_all_events": True,
    "entries": [
      {
        "module": "nut",
        "config": {
          "nut_test_result": { "GetUPSVars": {b'battery.charge': b'100', b'battery.charge.low': b'20', b'battery.runtime': b'3000', b'battery.type': b'PbAc', b'device.mfr': b'EATON', b'device.model': b'Ellipse ECO 1200', b'device.serial': b'000000000', b'device.type': b'ups', b'driver.name': b'usbhid-ups', b'driver.parameter.bus': b'001', b'driver.parameter.pollfreq': b'30', b'driver.parameter.pollinterval': b'2', b'driver.parameter.port': b'auto', b'driver.parameter.product': b'Ellipse ECO', b'driver.parameter.productid': b'FFFF', b'driver.parameter.serial': b'000000000', b'driver.parameter.synchronous': b'auto', b'driver.parameter.vendor': b'EATON', b'driver.parameter.vendorid': b'0463', b'driver.version': b'2.8.0', b'driver.version.data': b'MGE HID 1.46', b'driver.version.internal': b'0.47', b'driver.version.usb': b'libusb-1.0.26 (API: 0x1000109)', b'input.transfer.high': b'264', b'input.transfer.low': b'184', b'outlet.1.desc': b'PowerShare Outlet 1', b'outlet.1.id': b'2', b'outlet.1.status': b'on', b'outlet.1.switchable': b'no', b'outlet.2.desc': b'PowerShare Outlet 2', b'outlet.2.id': b'3', b'outlet.2.status': b'on', b'outlet.2.switchable': b'no', b'outlet.desc': b'Main Outlet', b'outlet.id': b'1', b'outlet.power': b'25', b'outlet.switchable': b'no', b'output.frequency.nominal': b'50', b'output.voltage': b'230.0', b'output.voltage.nominal': b'230', b'ups.beeper.status': b'enabled', b'ups.delay.shutdown': b'20', b'ups.delay.start': b'30', b'ups.firmware': b'02', b'ups.load': b'8', b'ups.mfr': b'EATON', b'ups.model': b'Ellipse ECO 1200', b'ups.power.nominal': b'1200', b'ups.productid': b'ffff', b'ups.realpower': b'77', b'ups.serial': b'000000000', b'ups.status': b'OL', b'ups.timer.shutdown': b'-1', b'ups.timer.start': b'-1', b'ups.vendorid': b'0463'}},
        },
        'run_interval': 60, # = polling interval
      },
    ]
  }) 

def test_run(entries):
  test.assertx('t1-init', 
    assertSubscribe = {
      'nut/var/ups_status': 'OL',
      'nut/var/battery_charge': '100',
    }, 
    assertSomeEvents = {
      'connected': {'value': 1},
      'battery': {'value': 100}
    },
    wait = False)
  entries['nut@TEST'].module.run(entries['nut@TEST'])
  test.waitRunning()
  
  test.assertx('t2-nochanged', 
    assertSubscribe = {
      'nut/var/time': (),
    },
    assertSubscribeNotReceive = ['nut/var/ups_status', 'nut/var/battery_charge'],
    wait = False)
  entries['nut@TEST'].module.run(entries['nut@TEST'])
  test.waitRunning()
  
  entries['nut@TEST'].config['nut_test_result']['GetUPSVars'][b'battery.charge']=b'99'
  test.assertPublish('t3-changes', 'nut/refresh', '',
    assertSubscribe = {
      'nut/var/battery_charge': '99',
    },
    assertEventsTopic = None, assertSomeEvents = {
      'battery': {'value': 99}
    })

  test.assertx('t4-changes',
    assertSubscribe = {
      'nut/var/ups_status': 'OB DISCHRG',
    },
    assertSomeEvents = {
      'output': {'port': 'on_battery', 'value': 1}
    },
  wait = False)
  entries['nut@TEST'].config['nut_test_result']['GetUPSVars'][b'ups.status']=b'OB DISCHRG'
  entries['nut@TEST'].module.run(entries['nut@TEST'])
  test.waitRunning()
