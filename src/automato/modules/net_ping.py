# require python3
# -*- coding: utf-8 -*-

# @see https://github.com/ValentinBELYN/icmplib/
# @see https://github.com/ValentinBELYN/icmplib/blob/main/docs/6-use-icmplib-without-privileges.md

import logging
import icmplib

definition = {
  "description": _("Provide ping functionality via icmplib module"),
  "config": {
    "ping_timeout": 1,
    "ping_privileged": False, # @see https://github.com/ValentinBELYN/icmplib/blob/main/docs/6-use-icmplib-without-privileges.md
  }
}

def ping(entry, ip, p_timeout = None):
  try:
    h = icmplib.ping(ip, count = 1, timeout = p_timeout if p_timeout is not None else entry.config['ping_timeout'], privileged = entry.config['ping_privileged'])
    logging.debug("#{id}> pinged {ip}, is_alive: {is_alive} (timeout: {timeout})".format(id = entry.id, ip = ip, is_alive = h.is_alive, timeout = p_timeout if p_timeout is not None else entry.config['ping_timeout']))
    return h.is_alive
  except:
    logging.exception("#{id}> failed executing ping {ip}".format(id = entry.id, ip = ip))
