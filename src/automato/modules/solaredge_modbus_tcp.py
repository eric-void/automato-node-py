# require python3
# -*- coding: utf-8 -*-

import logging

# @see https://github.com/nmakel/solaredge_modbus
# pip3 install solaredge_modbus
import solaredge_modbus

from automato.core import system
from automato.core import utils

definition = {
  'description': _('Report data from solaredge inverter'),
  'topic_root': 'solaredge',
  'config': {
    "solaredge_modbus_tcp_host": "192.168.1.1",
    "solaredge_modbus_tcp_port": 1502,
    "solaredge_modbus_tcp_timeout": 2,
    "solaredge_modbus_tcp_unit": 1,
    "solaredge_modbus_tcp_data_filter": {
      "inverter": [
        #"c_manufacturer", "c_model", "c_version", "c_serialnumber", "c_deviceaddress", "c_sunspec_did",
        "current", # "p1_current", "p2_current", "p3_current",
        "p1_voltage", # "p2_voltage", "p3_voltage",
        #"p1n_voltage", "p2n_voltage", "p3n_voltage", 
        "power_ac",
        "frequency",
        #"power_apparent", "power_reactive", "power_factor",
        "energy_total",
        "current_dc",
        "voltage_dc",
        "power_dc",
        "temperature",
        "status", # "vendor_status",
        #"rrcr_state",
        #"active_power_limit",
        #"cosphi",
      ],
      "meter": [
        #"c_manufacturer", "c_model", "c_option", "c_version", "c_serialnumber", "c_deviceaddress", "c_sunspec_did",
        "current",
        #"p1_current", "p2_current", "p3_current",
        "voltage_ln",
        #"p1n_voltage", "p2n_voltage", "p3n_voltage",
        #"voltage_ll",
        #"p12_voltage", "p23_voltage", "p31_voltage",
        "frequency",
        "power", #"p1_power", "p2_power", "p3_power",
        #"power_apparent", "p1_power_apparent", "p2_power_apparent", "p3_power_apparent",
        #"power_reactive", "p1_power_reactive", "p2_power_reactive", "p3_power_reactive",
        #"power_factor", "p1_power_factor", "p2_power_factor", "p3_power_factor",
        "export_energy_active", #"p1_export_energy_active", "p2_export_energy_active", "p3_export_energy_active",
        "import_energy_active", #"p1_import_energy_active", "p2_import_energy_active", "p3_import_energy_active",
        #"export_energy_apparent", "p1_export_energy_apparent", "p2_export_energy_apparent", "p3_export_energy_apparent",
        #"import_energy_apparent", "p1_import_energy_apparent", "p2_import_energy_apparent", "p3_import_energy_apparent",
        #"import_energy_reactive_q1", "p1_import_energy_reactive_q1", "p2_import_energy_reactive_q1", "p3_import_energy_reactive_q1",
        #"import_energy_reactive_q2", "p1_import_energy_reactive_q2", "p2_import_energy_reactive_q2", "p3_import_energy_reactive_q2",
        #"export_energy_reactive_q3", "p1_export_energy_reactive_q3", "p2_export_energy_reactive_q3", "p3_export_energy_reactive_q3",
        #"export_energy_reactive_q4", "p1_export_energy_reactive_q4", "p2_export_energy_reactive_q4", "p3_export_energy_reactive_q4",
      ],
      "battery": [
        #"c_manufacturer", "c_model", "c_version", "c_serialnumber", "c_deviceaddress", "c_sunspec_did",
        #"rated_energy",
        #"maximum_charge_continuous_power",
        #"maximum_discharge_continuous_power",
        #"maximum_charge_peak_power",
        #"maximum_discharge_peak_power",
        #"average_temperature",
        #"maximum_temperature",
        "instantaneous_voltage",
        "instantaneous_current",
        "instantaneous_power",
        "lifetime_export_energy_counter",
        "lifetime_import_energy_counter",
        #"maximum_energy",
        #"available_energy",
        "soh", # = State of charge (>=100%)
        "soe", # = State of energy (% of battery level)
        "status",
        "status_internal",
        #"event_log",
        #"event_log_internal",
      ]
    }
    
  },
  'publish': {
    'solaredge/inverter': {
      'type': 'object',
      'description': _('Report data from solaredge inverter'),
      'run_interval': 30,
      'check_interval': '5m',
      'handler': 'publish',
      'notify_level': 'debug',
      #'events_debug' : 2,
      'events': {
        "stats": "js:payload_transfer({'port': 'inverter'}, payload, ['c_manufacturer', 'c_model', 'c_version', 'c_serialnumber', 'c_deviceaddress', 'c_sunspec_did', 'status', 'vendor_status', 'rrcr_state', 'active_power_limit', 'cosphi'])",
        "energy": [
          "js:payload_transfer({'port': 'inverter_ac'}, payload, {'energy_total': '', 'current': '', 'power_ac': 'power', 'frequency': '', 'power_apparent': '', 'power_reactive': '', 'power_factor': ''})",
          "js:payload_transfer({'port': 'inverter_dc'}, payload, {'power_dc': 'power', 'current_dc': 'current', 'voltage_dc': 'voltage'})",
        ],
        "temperature": "js:payload_transfer({'port': 'inverter'}, payload, {'temperature': 'value'})",
      }
    },
    '/^solaredge/meter/(.*)$/': {
      'type': 'object',
      'description': _('Report data from meter connected to solaredge inverter'),
      'notify_level': 'debug',
      # TODO Mancano le fasi p1, p2, p3
      #'events_debug' : 2,
      'events': {
        "stats": "js:payload_transfer({'port': matches[1]}, payload, ['c_manufacturer', 'c_model', 'c_option', 'c_version', 'c_serialnumber', 'c_deviceaddress', 'c_sunspec_did'])",
        "energy": [
          "js:payload_transfer({'port': matches[1]}, payload, {'current': '', 'voltage_ln': 'voltage', 'voltage_ll': '', 'frequency': '', 'power': '', 'power_apparent': '', 'power_reactive': '', 'power_factor': ''})",
          "js:payload_transfer({'port': matches[1] + '_import'}, payload, {'import_energy_active': 'energy_total', 'import_energy_apparent': 'energy_apparent', 'import_energy_reactive_q1': 'energy_reactive_q1', 'import_energy_reactive_q2': 'energy_reactive_q2'})",
          "js:payload_transfer({'port': matches[1] + '_export'}, payload, {'export_energy_active': 'energy_total', 'export_energy_apparent': 'energy_apparent', 'export_energy_reactive_q3': 'energy_reactive_q3', 'export_energy_reactive_q4': 'energy_reactive_q4'})",
        ],
      }
    },
    '/^solaredge/battery/(.*)$/': {
      'type': 'object',
      'description': _('Report data from battery connected to solaredge inverter'),
      'notify_level': 'debug',
      #'events_debug' : 2,
      'events': {
        "stats": "js:payload_transfer({'port': matches[1]}, payload, ['c_manufacturer', 'c_model', 'c_version', 'c_serialnumber', 'c_deviceaddress', 'c_sunspec_did', 'status', 'status_internal', 'event_log', 'event_log_internal'])",
        "temperature": "js:payload_transfer({'port': matches[1]}, payload, {'average_temperature': 'value', 'maximum_temperature': 'max'})",
        "energy": [
          "js:payload_transfer({'port': matches[1]}, payload, {'instantaneous_voltage': 'voltage', 'instantaneous_current': 'current', 'instantaneous_power': 'power', 'rated_energy': '', 'maximum_charge_continuous_power': '', 'maximum_discharge_continuous_power': '', 'maximum_charge_peak_power': '', 'maximum_discharge_peak_power': '', 'maximum_energy': '', 'available_energy': '', 'soh': '', 'soe': ''})",
          "js:payload_transfer({'port': matches[1] + '_import'}, payload, {'lifetime_import_energy_counter': 'energy_total'})",
          "js:payload_transfer({'port': matches[1] + '_export'}, payload, {'lifetime_export_energy_counter': 'energy_total'})",
        ]
      }
    },
  }
}

def init(entry):
  l = logging.getLogger('pymodbus')
  l.propagate = False

def publish(entry, topic, definition):
  try:
    inverter = solaredge_modbus.Inverter(
      host = entry.config['solaredge_modbus_tcp_host'],
      port = entry.config['solaredge_modbus_tcp_port'],
      timeout = utils.read_duration(entry.config['solaredge_modbus_tcp_timeout']),
      unit = entry.config['solaredge_modbus_tcp_unit']
    )
    
    inverter_data = {}
    values = inverter.read_all()
    if "c_serialnumber" in values:
      inverter_data["c_serialnumber"] = values["c_serialnumber"]
    for k, v in values.items():
      if not entry.config['solaredge_modbus_tcp_data_filter'] or ("inverter" not in entry.config['solaredge_modbus_tcp_data_filter']) or not entry.config['solaredge_modbus_tcp_data_filter']["inverter"] or k in entry.config['solaredge_modbus_tcp_data_filter']["inverter"]:
        if (isinstance(v, int) or isinstance(v, float)) and "_scale" not in k:
          k_split = k.split("_")
          scale = 0
          if f"{k_split[len(k_split) - 1]}_scale" in values:
            scale = values[f"{k_split[len(k_split) - 1]}_scale"]
          elif f"{k}_scale" in values:
            scale = values[f"{k}_scale"]

          inverter_data.update({k: float(v * (10 ** scale))})
        elif "_scale" not in k:
          inverter_data.update({k: v})
    if (inverter_data):
      entry.publish('./inverter', inverter_data)

    meter_data = {}
    meters = inverter.meters()
    for meter, params in meters.items():
      meter = meter.lower()
      meter_data[meter] = {}
      values = params.read_all()
      if "c_serialnumber" in values:
        meter_data[meter]["c_serialnumber"] = values["c_serialnumber"]
      for k, v in values.items():
        if not entry.config['solaredge_modbus_tcp_data_filter'] or ("meter" not in entry.config['solaredge_modbus_tcp_data_filter']) or not entry.config['solaredge_modbus_tcp_data_filter']["meter"] or k in entry.config['solaredge_modbus_tcp_data_filter']["meter"]:
          if (isinstance(v, int) or isinstance(v, float)) and "_scale" not in k:
            k_split = k.split("_")
            scale = 0
            if f"{k_split[len(k_split) - 1]}_scale" in values:
              scale = values[f"{k_split[len(k_split) - 1]}_scale"]
            elif f"{k}_scale" in values:
              scale = values[f"{k}_scale"]

            meter_data[meter].update({k: float(v * (10 ** scale))})
          elif "_scale" not in k:
            meter_data[meter].update({k: v})
      if meter_data[meter]:
        entry.publish('./meter/' + meter, meter_data[meter])

    battery_data = {}
    batteries = inverter.batteries()
    for battery, params in batteries.items():
      battery = battery.lower()
      battery_data[battery] = {}
      values = params.read_all()
      if "c_serialnumber" in values:
        battery_data[battery]["c_serialnumber"] = values["c_serialnumber"]
      for k, v in values.items():
        if not entry.config['solaredge_modbus_tcp_data_filter'] or ("battery" not in entry.config['solaredge_modbus_tcp_data_filter']) or not entry.config['solaredge_modbus_tcp_data_filter']["battery"] or k in entry.config['solaredge_modbus_tcp_data_filter']["battery"]:
          if (isinstance(v, int) or isinstance(v, float)) and "_scale" not in k:
            k_split = k.split("_")
            scale = 0
            if f"{k_split[len(k_split) - 1]}_scale" in values:
              scale = values[f"{k_split[len(k_split) - 1]}_scale"]
            elif f"{k}_scale" in values:
              scale = values[f"{k}_scale"]

            battery_data[battery].update({k: float(v * (10 ** scale))})
          elif "_scale" not in k:
            battery_data[battery].update({k: v})
      if battery_data[battery]:
        entry.publish('./battery/' + battery, battery_data[battery])

  except:
    logging.exception("{id}> Exception during inverter data collection...".format(id = entry.id))
