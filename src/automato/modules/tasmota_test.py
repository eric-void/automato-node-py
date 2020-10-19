# require python3
# -*- coding: utf-8 -*-

from automato.core import test

def test_init():
  test.add_node_config({
    "listen_all_events": True,
    "entries": [
      { "module": "toggle" },
      { "module": "tasmota" },
      {
        "device": "sonoff-test",
        "caption": "SonoffTest",
        "device_type": "tasmota",
        "tasmota_id": "XXXXXX",
        "events_listen": ["*.output", ".input", ".connected", ".temperature", ".humidity", ".clock"]
      },
    ],
  })

def test_run(entries):
  test.assertPublish('clock', 'tele/XXXXXX/STATE', '{"Time":"2019-05-10T10:17:01", "Uptime":220, "Vcc":3.260, "POWER":"OFF", "Wifi":{"AP":1, "SSID":"TANELORN", "RSSI":80, "APMac":"30:B5:C2:4F:D1:16"}}', assertSomeEvents = {'clock': {'value': 1557476221}})
  test.assertPublish('get_on', 'stat/XXXXXX/POWER', 'ON', assertEvents = {'output': {'value': 1, 'port': '0', 'port:def': ['0'], 'value:def': [0, 1]}})
  test.assertPublish('get_off', 'stat/XXXXXX/POWER2', 'OFF', assertEvents = {'output': {'value': 0, 'port': '2', 'port:def': ['0'], 'value:def': [0, 1]}})
  test.assertAction('set_on', 'sonoff-test', 'output-set', {'value': 1}, assertSubscribe = {'cmnd/XXXXXX/POWER': 'ON'})
  test.assertAction('set_off', 'sonoff-test', 'output-set', {'value': 0, 'port': '2'}, assertSubscribe = {'cmnd/XXXXXX/POWER2': 'OFF'})
  #test.assertPublish('get_input_on', '...', '1', assertEvents = {'input': {'value': 1, 'port': '0'}})
  ##test.assertPublish('get_power', '...', '3.5', assertEvents = {'power': {'value': 3.5, 'port': '1'}})
  test.assertPublish('lwt_online', 'tele/XXXXXX/LWT', 'Online', assertEvents = {'connected': { 'value': True }})
  test.assertPublish('lwt_offline', 'tele/XXXXXX/LWT', 'Offline', assertEvents = {'connected': { 'value': False }})
  test.assertPublish('sensor', 'stat/XXXXXX/STATUS8', '{"StatusSNS":{"Time":"2018-12-03T13:48:08","SI7021":{"Temperature":17.7,"Humidity":51.2},"TempUnit":"C"}}', assertEvents = {'temperature': {'value': 17.7, 'value:unit': '°C'}, 'humidity': {'value': 51.2}, 'clock': {'value': 1543841288}}, assertNotification = ['debug', "Tasmota device 'SonoffTest' reports sensor SI7021 data: {'Humidity': 51.2, 'Temperature': 17.7}"])
  test.assertPublish('button', 'stat/XXXXXX/BUTTON3', '{"ACTION":"SINGLE"}', assertEvents = {'input': {'value': 1, 'port': '3', 'temporary': True, 'channel': "SINGLE", 'port:def': ['0'], 'value:def': [0, 1], 'channel:def': ['SINGLE', 'DOUBLE', 'TRIPLE', 'QUAD', 'PENTA', 'HOLD']}})
  test.assertPublish('energy', 'stat/XXXXXX/STATUS8', '{"StatusSNS":{"Time":"2020-10-20T10:34:05","ENERGY":{"TotalStartTime":"2018-11-20T00:00:51","Total":[16.90943,0.00000,16.90943],"Yesterday":1.25883,"Today":0.36116,"Power":101,"ApparentPower":156,"ReactivePower":119,"Factor":0.65,"Voltage":236,"Current":0.662}}}', 
    assertEvents = {'energy': {'current': 0.662, 'energy_today': 0.36116, 'energy_total': 16.90943, 'energy_yesterday': 1.25883, 'power': 101, 'power_apparent': 156, 'power_factor': 0.65, 'power_reactive': 119, 'total_duration': 60514394, 'total_starttime': 1542668451, 'voltage': 236, 'power:unit': 'W', 'energy:unit': 'kWh', 'current:unit': 'A', 'voltage:unit': 'V'}, 'clock': {'value': 1603182845}})
