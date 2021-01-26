# require python3
# -*- coding: utf-8 -*-

import logging

import time
import datetime
from threading import Event
from collections import namedtuple

from automato.core import system

if not system.test_mode:
  from RPi import GPIO

definition = {
  'config': {
    'rf_listener_gpio': -1, # If set => 0, enable the internal rf_listener on this gpio. DO NOT USE on small systems (Raspbbery PI Zero). Use rf2mqtt app instead.
    'rf_listener_ignore_protocols': [], # Use [1,2] to filter out rf signal detected with protocols #1 and #2
  },
  
  'subscribe': {
    'rf2mqtt': {
      'handler': 'on_rf2mqtt_message',
    }
  }
}
"""
ERIC: NOTA TECNICA
Usare l'rf_listener interno invece dello script rf2mqtt su raspberry è un problema.
Se lo eseguo su un automato vuoto (e in particolare senza il modulo "nodes") nessun problema.
Ma se c'è il modulo "nodes", e quindi le configurazioni degli altri nodi, inizia ad andare malissimo. Fa il detect di un sacco di segnali invalidi, e prende pochissimo quelli validi.
Debuggando il problema è con system._entry_add_to_index la parte che fa il for ... _entry_add_to_index_topic_published.
Che però è una procedura che non fa altro che riempire una struttura in memoria, e basta. Sembra quindi essere un problema di memoria usata (anche se, simulando l'inserimento in memoria di una variabile molto grande, non sono riuscito a riprodurre).
Per questo è stato fatto rf2mqtt. Se si lancia uno script esterno che fa solo rf -> mqtt e BASTA va decisamente meglio (anche della versione vecchia di automato che non aveva il problema sopra, ma che prendeva comunque un sacco di segnali invalidi)
"""

"""
ENTRY DEFINITIONS:
entry = {
  "rf_code": '1234567' | {'1234567': 'port'},
}
"""

def load(self_entry):
  if not hasattr(self_entry, 'rf_codes'):
    self_entry.rf_codes = {}

def entry_load(self_entry, entry):
  if "rf_code" in entry.definition:
    entry_install(self_entry, entry, entry.definition['rf_code'])

def entry_unload(self_entry, entry):
  if "rf_code" in entry.definition:
    rf_code = entry.definition['rf_code']
    if isinstance(rf_code, dict):
      for c in rf_code:
        del self_entry.rf_codes[c]
    else:
      del self_entry.rf_codes[rf_code]

def entry_install(self_entry, entry, rf_code):
  if isinstance(rf_code, dict):
    for c in rf_code:
      self_entry.rf_codes[c] = (entry.id, rf_code[c])
  else:
    self_entry.rf_codes[rf_code] = (entry.id, '')
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append('rf_listener')
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {
      '@/detected': {
        'description': _('Detects RF signal from {caption} device'),
        'type': 'string',
        'notify': _('Detected RF signal from {caption} device'),
        'notify_if': {
          'js:payload': { 'notify': _('Detected RF signal from {caption} device ({payload})') }
        },
        'events': {
          'connected': 'js:(payload == "" ? { value: true, temporary: true } : { value: true, temporary: true, port: payload })',
          'input': 'js:(payload == "" ? { value: 1, temporary: true } : { value: 1, temporary: true, port: payload })',
        }
      }
    },
  })
  
def rf_rx_callback(self_entry, rfdevice):
  for rf_code in self_entry.rf_codes:
    if str(rfdevice['rx_code']) == str(rf_code):
      entry_id, port = self_entry.rf_codes[rf_code]
      logging.debug("#{id}> found matching code: {rx_code} for {entry_id}/{port} [pulselength {rx_pulselength}, protocol {rx_proto}]".format(id = self_entry.id, entry_id = entry_id, port = port if port != '' else '-', rx_code = str(rfdevice['rx_code']), rx_pulselength = str(rfdevice['rx_pulselength']), rx_proto = str(rfdevice['rx_proto'])))
      entry = system.entry_get(entry_id)
      if entry:
        entry.publish('@/detected', port)
      else:
        logging.error('#{id}> entry {entry_id} not found for rf_code {rf_code}'.format(id = id, entry_id = entry_id, rf_code = rf_code))

def start(entry):
  if entry.config['rf_listener_gpio'] >= 0:
    rfdevice = None
    try:
      rfdevice = RFDevice(entry.config['rf_listener_gpio'])
      rfdevice.rx_extcallback = lambda device: rf_rx_callback(entry, device)
      rfdevice.rx_extcallback_filtertime = 30
      rfdevice.rx_extcallback_filterprotocols = entry.config['rf_listener_ignore_protocols']
      rfdevice.enable_rx()
      Event().wait()

    except:
      logging.exception("#{id}> exception in listening rf codes".format(id = entry.id))

    finally:
      logging.debug("#{id}> cleanup".format(id = entry.id))
      if rfdevice:
        rfdevice.cleanup()

def on_rf2mqtt_message(entry, subscribed_message):
  rf_rx_callback(entry, subscribed_message.payload)

"""
Sending and receiving 433/315Mhz signals with low-cost GPIO RF Modules on a Raspberry Pi.

Based on https://github.com/milaq/rpi-rf/ (last commit: 3bbd31cc3bbd4f1a7c2aba776d2541b37480e45b)
@see https://github.com/milaq/rpi-rf/blob/3bbd31cc3bbd4f1a7c2aba776d2541b37480e45b/rpi_rf/rpi_rf.py

CHANGED:
- logging
- __init__ contains self.rx_extcallback* initialization
- rx_callback contains external callback management
- indentation
"""

MAX_CHANGES = 67

Protocol = namedtuple('Protocol',
            ['pulselength',
            'sync_high', 'sync_low',
            'zero_high', 'zero_low',
            'one_high', 'one_low'])
PROTOCOLS = (None,
      Protocol(350, 1, 31, 1, 3, 3, 1),
      Protocol(650, 1, 10, 1, 2, 2, 1),
      Protocol(100, 30, 71, 4, 11, 9, 6),
      Protocol(380, 1, 6, 1, 3, 3, 1),
      Protocol(500, 6, 14, 1, 2, 2, 1),
      Protocol(200, 1, 10, 1, 5, 1, 1))


class RFDevice:
  """Representation of a GPIO RF device."""

  # pylint: disable=too-many-instance-attributes,too-many-arguments
  def __init__(self, gpio,
        tx_proto=1, tx_pulselength=None, tx_repeat=10, tx_length=24, rx_tolerance=80):
    """Initialize the RF device."""
    self.gpio = gpio
    self.tx_enabled = False
    self.tx_proto = tx_proto
    if tx_pulselength:
      self.tx_pulselength = tx_pulselength
    else:
      self.tx_pulselength = PROTOCOLS[tx_proto].pulselength
    self.tx_repeat = tx_repeat
    self.tx_length = tx_length
    self.rx_enabled = False
    self.rx_tolerance = rx_tolerance
    # internal values
    self._rx_timings = [0] * (MAX_CHANGES + 1)
    self._rx_last_timestamp = 0
    self._rx_change_count = 0
    self._rx_repeat_count = 0
    # successful RX values
    self.rx_code = None
    self.rx_code_timestamp = None
    self.rx_proto = None
    self.rx_bitlength = None
    self.rx_pulselength = None

    # ADDED
    self.rx_extcallback = None
    self.rx_extcallback_filtertime = 0
    self.rx_extcallback_filterprotocols = []
    self.rx_extcallback_codes = {}
    self.rx_extcallback_timestamp = None

    GPIO.setmode(GPIO.BCM)
    logging.debug("#RFDevice> using GPIO " + str(gpio))

  def cleanup(self):
    """Disable TX and RX and clean up GPIO."""
    if self.tx_enabled:
      self.disable_tx()
    if self.rx_enabled:
      self.disable_rx()
    logging.debug("#RFDevice> Cleanup")
    GPIO.cleanup()

  def enable_tx(self):
    """Enable TX, set up GPIO."""
    if self.rx_enabled:
      logging.error("#RFDevice> RX is enabled, not enabling TX")
      return False
    if not self.tx_enabled:
      self.tx_enabled = True
      GPIO.setup(self.gpio, GPIO.OUT)
      logging.debug("#RFDevice> TX enabled")
    return True

  def disable_tx(self):
    """Disable TX, reset GPIO."""
    if self.tx_enabled:
      # set up GPIO pin as input for safety
      GPIO.setup(self.gpio, GPIO.IN)
      self.tx_enabled = False
      logging.debug("#RFDevice> TX disabled")
    return True

  def tx_code(self, code, tx_proto=None, tx_pulselength=None, tx_length=None):
    """
    Send a decimal code.
    Optionally set protocol, pulselength and code length.
    When none given reset to default protocol, default pulselength and set code length to 24 bits.
    """
    if tx_proto:
      self.tx_proto = tx_proto
    else:
      self.tx_proto = 1
    if tx_pulselength:
      self.tx_pulselength = tx_pulselength
    elif not self.tx_pulselength:
      self.tx_pulselength = PROTOCOLS[self.tx_proto].pulselength
    if tx_length:
      self.tx_length = tx_length
    elif self.tx_proto == 6:
      self.tx_length = 32
    elif (code > 16777216):
      self.tx_length = 32
    else:
      self.tx_length = 24
    rawcode = format(code, '#0{}b'.format(self.tx_length + 2))[2:]
    if self.tx_proto == 6:
      nexacode = ""
      for b in rawcode:
        if b == '0':
          nexacode = nexacode + "01"
        if b == '1':
          nexacode = nexacode + "10"
      rawcode = nexacode
      self.tx_length = 64
    logging.debug("#RFDevice> TX code: " + str(code))
    return self.tx_bin(rawcode)

  def tx_bin(self, rawcode):
    """Send a binary code."""
    logging.debug("#RFDevice> TX bin: " + str(rawcode))
    for _ in range(0, self.tx_repeat):
      if self.tx_proto == 6:
        if not self.tx_sync():
          return False
      for byte in range(0, self.tx_length):
        if rawcode[byte] == '0':
          if not self.tx_l0():
            return False
        else:
          if not self.tx_l1():
            return False
      if not self.tx_sync():
        return False

    return True

  def tx_l0(self):
    """Send a '0' bit."""
    if not 0 < self.tx_proto < len(PROTOCOLS):
      logging.error("#RFDevice> Unknown TX protocol")
      return False
    return self.tx_waveform(PROTOCOLS[self.tx_proto].zero_high,
                PROTOCOLS[self.tx_proto].zero_low)

  def tx_l1(self):
    """Send a '1' bit."""
    if not 0 < self.tx_proto < len(PROTOCOLS):
      logging.error("#RFDevice> Unknown TX protocol")
      return False
    return self.tx_waveform(PROTOCOLS[self.tx_proto].one_high,
                PROTOCOLS[self.tx_proto].one_low)

  def tx_sync(self):
    """Send a sync."""
    if not 0 < self.tx_proto < len(PROTOCOLS):
      logging.error("#RFDevice> Unknown TX protocol")
      return False
    return self.tx_waveform(PROTOCOLS[self.tx_proto].sync_high,
                PROTOCOLS[self.tx_proto].sync_low)

  def tx_waveform(self, highpulses, lowpulses):
    """Send basic waveform."""
    if not self.tx_enabled:
      logging.error("#RFDevice> TX is not enabled, not sending data")
      return False
    GPIO.output(self.gpio, GPIO.HIGH)
    self._sleep((highpulses * self.tx_pulselength) / 1000000)
    GPIO.output(self.gpio, GPIO.LOW)
    self._sleep((lowpulses * self.tx_pulselength) / 1000000)
    return True

  def enable_rx(self):
    """Enable RX, set up GPIO and add event detection."""
    if self.tx_enabled:
      logging.error("#RFDevice> TX is enabled, not enabling RX")
      return False
    if not self.rx_enabled:
      self.rx_enabled = True
      GPIO.setup(self.gpio, GPIO.IN)
      GPIO.add_event_detect(self.gpio, GPIO.BOTH)
      GPIO.add_event_callback(self.gpio, self.rx_callback)
      logging.debug("#RFDevice> RX enabled")
    return True

  def disable_rx(self):
    """Disable RX, remove GPIO event detection."""
    if self.rx_enabled:
      GPIO.remove_event_detect(self.gpio)
      self.rx_enabled = False
      logging.debug("#RFDevice> RX disabled")
    return True

  # pylint: disable=unused-argument
  def rx_callback(self, gpio):
    """RX callback for GPIO event detection. Handle basic signal detection."""
    timestamp = int(time.perf_counter() * 1000000)
    unix_timestamp = system.time()
    duration = timestamp - self._rx_last_timestamp

    found = False
    if duration > 5000:
      if abs(duration - self._rx_timings[0]) < 200:
        self._rx_repeat_count += 1
        self._rx_change_count -= 1
        if self._rx_repeat_count == 2:
          for pnum in range(1, len(PROTOCOLS)):
            if self._rx_waveform(pnum, self._rx_change_count, timestamp):
              #logging.debug("#RFDevice> detected RX code " + str(self.rx_code))
              found = True
              break
          self._rx_repeat_count = 0
      self._rx_change_count = 0

    if self._rx_change_count >= MAX_CHANGES:
      self._rx_change_count = 0
      self._rx_repeat_count = 0
    self._rx_timings[self._rx_change_count] = duration
    self._rx_change_count += 1
    self._rx_last_timestamp = timestamp
    
    if found and not self.rx_proto in self.rx_extcallback_filterprotocols:
      current = {
        'rx_code': self.rx_code,
        'rx_code_timestamp': self.rx_code_timestamp,
        'rx_pulselength': self.rx_pulselength,
        'rx_proto': self.rx_proto
      }
      logging.debug("#RFDevice> detected code: " + str(current['rx_code']) + " [pulselength " + str(current['rx_pulselength']) + ", protocol " + str(current['rx_proto']) + "], time: " + ("-" if current['rx_code'] not in self.rx_extcallback_codes else datetime.datetime.fromtimestamp(self.rx_extcallback_codes[current['rx_code']]).strftime('%H:%M:%S') ) )
      if self.rx_extcallback and current['rx_code_timestamp'] != self.rx_extcallback_timestamp: # and ((current['rx_code'] not in self.rx_extcallback_codes) or (unix_timestamp - self.rx_extcallback_codes[current['rx_code']]) >= self.rx_extcallback_filtertime)
        self.rx_extcallback_timestamp = current['rx_code_timestamp']
        if (current['rx_code'] not in self.rx_extcallback_codes) or (unix_timestamp - self.rx_extcallback_codes[current['rx_code']]) >= self.rx_extcallback_filtertime:
          logging.debug("#RFDevice> sending detected code to callback...")
          self.rx_extcallback(current)
          self.rx_extcallback_codes[current['rx_code']] = unix_timestamp

  def _rx_waveform(self, pnum, change_count, timestamp):
    """Detect waveform and format code."""
    code = 0
    delay = int(self._rx_timings[0] / PROTOCOLS[pnum].sync_low)
    delay_tolerance = delay * self.rx_tolerance / 100

    for i in range(1, change_count, 2):
      if (abs(self._rx_timings[i] - delay * PROTOCOLS[pnum].zero_high) < delay_tolerance and
        abs(self._rx_timings[i+1] - delay * PROTOCOLS[pnum].zero_low) < delay_tolerance):
        code <<= 1
      elif (abs(self._rx_timings[i] - delay * PROTOCOLS[pnum].one_high) < delay_tolerance and
          abs(self._rx_timings[i+1] - delay * PROTOCOLS[pnum].one_low) < delay_tolerance):
        code <<= 1
        code |= 1
      else:
        return False

    if self._rx_change_count > 6 and code != 0:
      self.rx_code = code
      self.rx_code_timestamp = timestamp
      self.rx_bitlength = int(change_count / 2)
      self.rx_pulselength = delay
      self.rx_proto = pnum
      return True

    return False
        
  def _sleep(self, delay):    
    _delay = delay / 100
    end = time.time() + delay - _delay
    while time.time() < end:
      time.sleep(_delay)
