"""
E' un modulo da fare, tengo qui il codice estrapolato da presence visto che si basa su quello
Da copiare quello che fa net_sniffer_scapy
"""


# require python3
# -*- coding: utf-8 -*-

import logging
import subprocess

from automato.core import system
from automato.core import utils

# exports: someone_inside, no_one_inside

definition = {
  'config': {
    # WARN arp-scan necessita di root, quindi o si esegue automato/presence come root, oppure si mette il comando "arp-scan" in sudoers per permetterne l'esecuzione da utente semplice
    
    # Necessita di aggiungere l'utente che esegue lo script tra i sudoers come NOPASSWD
    # visudo > poi aggiungere:
    # username ALL=(ALL) NOPASSWD: [...],/usr/bin/arp-scan
    # In alternativa eseguire come root
    # Se arp-scan non usa l'interfaccia giusta, aggiungere "-I interface"
    'arpscan_command': 'sudo arp-scan -l',
    'arpscan_session_length': '15M',
    
  },
}

################################################################################

def arpscan_check(entry):
  try:
    output = subprocess.check_output(entry.config['arpscan_command'], shell=True).decode("utf-8").lower()
    d = 0
    for i in entry.config["occupants"]:
      if 'mac_address' in i and i['mac_address'].lower() in output:
        presence_detected(entry, i['name'], 'arpscan', utils.read_duration(entry.config['arpscan_session_length']))
        d = d + 1
    
    return d > 0

  except:
    logging.exception("arpscan_check exception")
    return False

