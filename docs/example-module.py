# require python3
# -*- coding: utf-8 -*-

# Documentazione "entry", passato a ogni chiamata
# entry è un ambiente specifico per l'istanza di modulo chiamata, e può essere usato per accedere a proprietà e metodi, o per memorizzare dati aggiuntivi da mantenere tra le chiamate
# (@see modules.py per la generazione)

# ID univoco, può essere passato come definition['id'], altrimenti viene generato
entry.id = 'xxx'

# Nome parlante, passato come definition['caption'] oppure impostato = id
entry.caption = '...'

# Tipologia di entry. In caso di entry.type == 'module' viene instanziato anche entry.module, con l'istanza del modulo (l'import della classe)
entry.type = 'module|device|item'

# created (int/timestamp)
entry.created

# last_seen(int/timestamp): data dell'ultimo messaggio del quale l'entry è risultato publisher (in caso di publisher multipli, per ognuno è impostato il last_seen).
entry.last_seen

# node_config (dict): l'intera configurazione del nodo (quella definita nel config caricato via riga di comando)
entry.node_config = {}

# definition (dict): la definizione completa dell'entry (arricchita da module.definition e hook module.load(), se l'entry è un module)
# NOTA: contiene SEMPRE entry_topic, topic_root, publish, subscribe
entry.definition = {}

# Contiene solo la parte normalizzata, e con solo le chiavi di tipo [L.0] e [L.0N], della definizione
entry.definition_exportable = {}

# config (dict): configurazione del modulo. E' solo uno shortcut di entry.definition.config
entry.config = {}

# broker (class): una istanza del broker mqtt (in genere non si usa direttamente, ma si usano i metodi publish / notify di entry)
entry.broker = None

# system (class): accesso alla libreria "system", che può essere usato per le chiamate a module_implements/module_invoke (e quindi chiamare metodi di altri moduli)
entry.system = None

# storage (class) [core/storage]: una istanza dell'oggetto "storage", al quale chiedere accesso al file-system
entry.storage = None

# publish (method): permette di pubblicare un contenuto nel broker (prendendo qos e retain da metadata)
# - response_callback (entry, id, message, matches, final, response_to_message)
# - no_response_callback (entry, id, response_to_message)
entry.publish(topic, payload, qos = None, retain = None, response_callback = None, no_response_callback = None, response_id = None)

# run_publish (method): esegue l'handler di un publish topic (che deve essere gestito da questo nodo)
entry.run_publish(topic)

# topic (method) [core/system]: ottiene il topic reale (dopo aver applicato entry_topic / topic_root / topic aliases) del topic passato
entry.topic(topic)

# request: oggetto thread_local, è possibile metterci dei dati che rimangono solo all'interno del thread della richiesta. Es: entry.request.callme = 'xxx'
entry.request = class

# exports (dict): i moduli possono aggiungere elementi in questo dizionario, che è visto tra gli elementi "globals" di ogni script. Ad esempio un modulo può inserire entry.exports['is_day'] = True (e poi tenerlo aggiornato), e uno script potrà usare "if is_day: turn_on()"
entry.exports = {}

# data (dict): tutti gli elementi inseriti in questo dizionario vengono automaticamente persistiti e ricaricati quando viene caricato il nodo. Inoltre sono passati come parametri locali agli script.
entry.data = {}

# methods (dict): si possono inserire qui dentro i metodi che vogliono poter essere invocati tramite system.entry|entries_invoke[_threaded] . Si possono anche inserire funzioni di altro tipo (scripting mette le funzioni dichiarate)
entry.methods = {}
# TODO NEW
entry.handlers = {}
entry.handlers_add(method, key, handler) # Esempio: entry.handlers_add("init", "toggle", func)

# script_exec|script_eval (method) [modules/scripting]: aggiunti dal modulo scripting, permettono di eseguire del codice, e valutare il risultato di una espressione. Usare [if hasattr(entry, "script_eval"):] prima di usare questi metodi
entry.script_exec(code, *args, **kwargs)
entry.script_eval(code, *args, **kwargs)

# TODO NEW
entry.events = {} # INTERNO: usare system.entry_events_supported(). A uso prevalentemente interno, per ogni evento c'è una lista di topic in cui è definito
entry.actions = {} # INTERNO: usare system.entry_actions_supported(). Come sopra per events
entry.on(event, listener, condition_eval = None, reference_entry = None, reference_tag = None)
# def listener(entry, eventname, eventdata, caller, published_message): ... eventdata = { 'params': {...}, 'changed_params': {...} }, caller = "message|import|events_passthrough", published_message = source message (null for import)
#   For eventdata description @see system._entry_event_publish
# NOTE: eventdata is a local copy, so you can change it freely. Other params must not be changed (the changes will be propagated to next listeners and code)
entry.do(action, params = {}, init_exec = None)

# E' possibile arricchire entry con qualsiasi elemento si vuole mantenere tra le chiamate
entry.MODULE_*

##########################################################################################

# Livelli di configurazione:
# Metadati generici, passati dal modulo system:
# [L.0] configurazioni base, che qualunque nodo/client deve essere in grado di capire e gestire
# [L.0N] descrizione delle notifiche (non è obbligatorio conoscere le notifiche per far andare i sistemi, ma è consigliato)
# Impostazioni locali, NON passati dal modulo system:
# [L.1] shortcut, estensioni, possibilità di non impostare certi dati in quanto sono impostati come default da altri, uso di entry_topic/topic_root
# [L.2] handler, script, gestioni locali del nodo

definition = {
  # [L.0]
  'caption': '...', # Imposta entry.caption (se non presente viene lasciato id)
  'description': _('...'),
  
  'config': {},
  
  # [L.1]
  'entry_topic': 'device-id', # Se specificato DEVE essere univoco per entry. Se non specificato ne viene impostato uno di default <device|module|item>/<id>. I topic che iniziano per "@" lo usano
  'topic_root': 'home', # Se specificato da una base per i topic che iniziano per ".". Se non specificato viene impostato uguale a entry_topic
  # Sono riportati come valori di default per gli altri livelli di notify (publish, subscribe...)
  'notify_type': 'core', # Usato per la notifica "notify/NOTIFY_TYPE/NOTIFY_LEVEL/TOPIC". Default: 'unknown'
  'notify_level': 'debug|info|warn|error|critical', # Usato per la notifica "notify/NOTIFY_TYPE/NOTIFY_LEVEL/TOPIC". Default: 'info'
  'notify_change_level': '...', 
  'event_keys': ['...'], # I nomi dei parametri degli eventi che permettono di discriminare eventi diversi, con lo stesso nome. La cache degli eventi (per event_get) e il changed_params dipendono da questo. Il default è ['port', 'channel']. Ad esempio event_get('x.output(js:params['port'] == '1') deve dare un risultato diverso (e cachato a parte) di params['port'] == '2'.

  # [L.2]
  'run_interval': 30, # Se specificato, richiama il metodo "run(entry)" ogni X secondi
  'run_cron': "*/2 * * * *", # In alternativa a run_interval, specifica ogni quanto avviare il run in base a una regola di cron @see https://en.wikipedia.org/wiki/Cron
  'run_trottle': "skip", # throttle_policy = "skip" (skip this run) | "wait" (postpone this run when possibile) | "force" (do it - if load level is critical this is turned to "wait") | XXX (wait max this number of seconds). This value can be a list ["policy on high load", "policy on very high load"]
  
  # [L.2] Gestito da scripting (per ora)
  "data": {
    "status": 0,
  },
  
  # [L.0] Elenco di entries che servono a questo entry per funzionare
  "required": [ "..." ],
  
  # [L.2] Execute "entry_install" handler for each entry that matches this conditions
  "install_on": {
    "property": "value", # Entry property has this value
    "/^regexp(.*)/": (), # Property name matches regexp, no value is matched. If regexp contains (variables) these are passed as conf parameter in entry_install handler. If not, entire property name is used
    "property": ('in', ["val1", "val2"]), # To see full () rules, look at system._entry_install_on_match()
  },
  
  # [L.0]
  'publish': {
    # Elenco di topic_rule da matchare. Ogni messaggio in ingresso verrà associato a un solo topic_rule. Se ci sono più match, verrà scelto quello con più alto "topic_match_priority", o uno a caso in caso di equivalenza.
    
    'topic' : { # In formato "topic_rule" (Vedi sotto)
      # [L.1]
      'topic': '...', # Il vero "topic_rule" di questo publish. Se specificato significa che la chiave 'topic' in realtà è un alias, il topic vero è specificato qui
      # [L.0]
      'topic_match_priority': 1, # Se per un topic ci sono più topic_match in questo publish, sceglie quello con la priority più alta. Se non specificata = 1, a meno che la definition sia vuota ({}), nel caso è 0
      
      # [L.0]
      'description': _('...'),
      'type': 'object|array|string|int|unknown|none|...', # Può essere anche l'oggetto python None, o un array python di possibili valori
      'qos': 0,
      'retain': True,
      'payload': {
        'state': {
          '0': { 'caption': 'off' },
          '1': { 'caption': 'ON' },
        },
        'payload': { ... } # In caso di payload a singolo valore
      },
      # Trasforma il payload usato da notifiche e eventi
      'payload_transform': 'js:if ("StatusSNS" in payload) payload = payload["StatusSNS"]; payload["Data"] = {}; for (k in payload) { if (payload[k] && typeof payload[k] == "object" && !(payload[k] instanceof Array)) { for (x in payload[k]) payload["Data"][x] = payload[k][x]; payload["SensorType"] = k } }; payload',
      
      'notify': 'Temperatura interna di {caption}: {payload[temperature]}° (umidità: {payload[humidity!caption]}%), ora: {payload[time!strftime(%Y-%m-%d %H:%M:%S)]}' # Stringa in formato ".format", dove {payload} contiene il payload, {caption} il nome e {matches} l'array di eventuali match del topic. @see https://docs.python.org/3/library/string.html#format-string-syntax
      'notify': _('Current time is {_[payload!strftime(%Y-%m-%d %H:%M:%S)]}'), # Esempio in caso di valore diretto da formattare con strftime
      'notify_handler': 'js:let output = '';[...];(output + ".")', # Chiama il metodo specificato, con i parametri "def as_string(entry, topic, payload):" (payload se è un dict è wrappato da PayloadDict, che supporta i formattatori)
      'notify_type': '', # Se specificato, usa questo invece di metadata['notify_type'] 
      'notify_level': '', # Se specificato, usa questo invece di metadata['notify_level'] 
      'notify_change_level': '', # Usa questo livello se il payload del topic cambia rispetto al precedente
      'notify_change_duration': '30m', # Se specificato, se il payload cambia usa notify_change_level, poi per almeno X tempo non lo usa piu' (usa il notify_level standard)
      'notify_if': {
        "js:payload == 'Offline'": { 'notify_level': 'warn', 'notify_type': ..., 'notify': ..., 'notify_handler': ..., 'notify_next_level': ... }, # notify_next_level si può usare solo in notify_if: nel caso l'espressione sia matchata, usa il livello specificato per il messaggio SUCCESSIVO },
        "js:payload['x'] > 0": { ... }
      },
      
      # [L.2]
      'run_interval': 30, # Se specificato, richiama il metodo "publish(entry, realtopic, metadata)" ogni X secondi
      'run_cron': "*/2 * * * *", # In alternativa a run_interval, specifica ogni quanto avviare il publish in base a una regola di cron @see https://en.wikipedia.org/wiki/Cron
        # WARN: a differenza di run_interval, run_cron non è verificato dal modulo health. Se viene usato è consigliabile mettere anche un "check_interval" con un tetto massimo di intervallo tra le chiamate
      'run_trottle': "skip", # throttle_policy = "skip" (skip this run) | "wait" (postpone this run when possibile) | "force" (do it - if load level is critical this is turned to "wait") | XXX (wait max this number of seconds). This value can be a list ["policy on high load", "policy on very high load"]
      'check_interval': 30, # [health module] Controlla che il publish sia fatto almeno ogni X secondi (moltiplicato per 1.5, @see health). Non c'è bisogno di specificarlo se è già specificato 'run_interval'
      # In caso di "run" (quindi con run_interval o run_cron, oppure chiamata a run_publish, esegue questo handler - E' possibile usare una stringa, nel caso cerca dentro entry.module o entry.methods l'handler con quel nome
      'handler': publish(entry, topic_rule, topic_definition),
      # Solo se c'è il modulo "scripting", come "handler" ma tramite script
      'script': [ 'codice python' ]
      'script': [ 'py:codice python' ]
      'script': [ 'py:', 'if x:', '  pass' ]
      'script': [ 'py:', 'if x:', [ 'pass' ] ]
      
      # [L.0] Dichiarazioni eventi
      # WARN: il risultato delle esecuzioni di codice degli eventi può essere messo in cache, e quindi è importante che il codice sia DETERMINISTICO rispetto ai parametri: se do gli stessi parametri 2 volte, il codice deve dare lo stesso risultato!
      "events": { # Variabili a disposizione di definizione: {topic}, {payload}, {matches}
        "state": "js:({value: payload['value'] == 'on' ? 1 : 0, value2: 0 + payload['value2']})",
        "clock": "js:({value: parseInt(payload['time'])})",
        "location": "js:(payload['_type'] == 'location' ? {latitude: payload['lat'], longitude: payload['lon'], altitude: payload['alt'], radius: payload['acc'], radius:unit: 'm', regions: 'inregions' in payload ? payload['inregions'] : [], source: 'owntracks'} : null)",
        "test": 'js:let payload = {}; if ("value" in params) payload.turn = params["value"] ? "on" : "off"; if ("intensity" in params) payload.brightness = params["intensity"]; payload',
        "eventname": ["js:...", "js:..."], # Se è possibile invocare più eventi con lo stesso nome è possibile specificare un array di definizioni
        "eventname:keys": [ "port", "channel"], # Le chiavi da usare per discriminare gli eventi (e la sua cache), da usare al posto di "event_keys" di entry (o globale). WARN: Se vengono dichiarati più ":keys" per lo stesso eventname, ne verrà considerato solo uno (di solito l'ultimo)
        "eventname:init": { "unit": "W" }, # Inizializzazione per gli stati, fatta a caricamento dell'entry. WARN: Se vengono dichiarati più ":init" per lo stesso eventname, ne verrà considerato solo uno (di solito l'ultimo)
        "eventname:init": [{ "port": "0", "unit": "W" }, { "port": "1", "unit": "J"}], # Inizializzazione per gli stati, con "event_keys" diversi
      },
      
      # [L.2] Esegue questo publish quando viene emesso l'evento specificato
      "run_on": [ "entry_id.event(condition)", "..." ],
      
      ... # Metadati specifici del tipo di modulo
    },
      
    'topic_base/#': {}, # In questo modo si fa un "catchall" di tutti i topic che sono associato a questo entry, ma non hanno una loro definizione (solo per sapere il publisher). Non avendo definizione (o avendo solo "topic", "description", o "notify*") il loro "topic_match_priority" è 0.
      # WARN: in caso di topic_match_priority = 0 (quindi in genere per un catchall) non verranno associati i topic che hanno un match anche con dei "subscribe": in quel caso il topic è considerato solo in subscribe, e NON in published
  },
  # [L.0]
  'subscribe': {
    # Elenco di topic_rule da matchare. Ogni messaggio in ingresso verrà associato a un solo topic_rule. Se ci sono più match, verrà scelto quello con più alto "topic_match_priority", o uno a caso in caso di equivalenza.

    # IMPORTANTE: A meno che non siamo in un subscribe "interno" (cioè un subscribe che non deve figurare come subscribe di entry nella descrizione dell'entry) occorre definire "description" o "response"/"publish"
    'topic': { # In formato "topic_rule", vedi sotto
      # [L.1]
      'topic': '...', # topic_rule assegnato a questo subscribe. Se specificato significa che la chiave 'topic' in realtà è un alias, il topic vero è specificato qui
      # [L.0]
      'topic_match_priority': 1, # Se per un topic ci sono più topic_match in questo subscribe, sceglie quello con la priority più alta. Se non specificata = 1, a meno che la definition sia vuota ({}) o contenente solo "topic", "description", "notify*", nel caso è 0
      
      # [L.0]
      'description': _('...'),
      "topic_syntax": "notifications/subscribe/[LEVEL]/[TYPE]/[TOPIC]",
      "topic_syntax_description": "LEVEL = _|string|string_, TYPE=_|string, TOPIC=_|string",
      "payload_syntax": "[CLIENT_TYPE]:[CLIENT_DATA]",
      # response: in alternativa si può usare "publish" (che pubblica anche il topic specificato)
      'response': [ 'topic' ], # L'elenco di topic (logici) dati in risposta quando si fa questa richiesta
      'response': [ { topic: 'topic/#', count: 10, duration: 10 } ], # Può inviare piu' risposte (massimo 10) e aspetta 10 secondi per riceverle tutte. For topic, you can use mqtt patterns (topic/#) or regexp (/topic/.*/)
      # nota su response e system.subscribe_response(... final ...). Una risposta è considerata finale se c'è stato almeno 1 messaggio di ogni topic specificato con count >= 1 (se il topic è stato specificato senza 'count', viene considerato 'count': 1)
      # quindi response [ 'topic1', 'topic2'] è final se sono stati ricevuti entrambi, [ { topic: 'topic1', count: 0}, { topic: 'topic2', count: 0} ] basta un response qualsiasi perchè sia finale, [ 'topic1', { topic: 'topic2', count: 0} ] indica che 'topic1' ci deve essere, 'topic2' è facoltativo
      # da notare che final può essere True più volte. Nell'ultimo esempio al primo 'topic1' viene chiamata la callback con final = True. Se poi arriva un 'topic2' viene chiamato di nuovo, sempre con final = True.
      # il numero di count > 1 non serve per capire se è final, ma solo per decidere dopo quanti messaggi la callback non viene più chiamata
      'type': '...', # Vedi sopra (notare che è il tipo di PAYLOAD associato al topic che il nodo riceve, non il tipo di risposta)
      
      # [L.???? TODO SERVE???]
      'internal': 1, # dichiara il subscribe come "interno", ovvero serve per ascoltare dei topic interni e non per dare funzionalità all'esterno. In genere per fare questo si mette solo la "subscription()" senza dichiarare nei metadata il subscribe, ma in alcuni casi questo è necessario (es: per fare un bot), e quindi si usa questa proprietà
      
      # OBSOLETE! [L.0N] In caso il subscribe faccia degli entry.notify, si usano i default sotto (se non ci sono va a vedere il publish relativo al topic notificato)
      #'notify_type': '', # Se specificato, usa questo invece di metadata['notify_type'] 
      #'notify_level': '', # Se specificato, usa questo invece di metadata['notify_level'] 
      #'notify_change_level': '', 
      #'notify_if': { ... },
      
      # [L.2]
      'handler': on_subscribed_message,
      # Solo se c'è il modulo "scripting", come "handler" ma tramite script (variabili disponibili: subscribed_message, topic, payload, matches)
      'script': [...]
      # Se specificato esegue il "run_publish" di quei topic (al termine di handler|script, se presenti). Se non specificato "response", viene impostato "response" = "publish". Se non va bene fare cosi' occorre specificare "response"
      'publish': [ 'topic' ],
      
      # [L.0] Dichiarazioni actions. "js:" può usare le variabili: params, e deve ritornare il payload del messaggio mqtt
      "actions": {
        "state-get": "",
        "state-set": "js:params['value'] ? 'on' : 'off'",
        'output-set': "js:('timer-to' in params ? { state: params['value'], timer_to: params['timer-to'] } : { state: params['value'] })",
        'output-set': {
          'init': 'js:params["port"] = "0"; if ("port1" not in params) params["port1"] = "X"', 
          'topic': 'js:"' + base_topic + 'relay/" + ("port" in params ? params["port"] : "0") + "/command"', 
          'payload': 'js:params["value"] ? "on" : "off"'
        },
        # initialize an event 'action/output-set' with this params (and time = -1)
        'output-set:init': { 'value:unit': 'W', 'value:def': [0, 1] }
      }
      # FOCUS: Come funziona la gestione "params" e "init" nelle actions (vedi anche system_test dove ci sono test appositiv)
      # Abbiamo una action definita come 'payload': 'js:({"v": params["v"]})', 'init': 'js:...'
      # E quindi facciamo una azione do(params = {'v': 1}, init = 'js:...')
      # L'esecuzione, in ordine è params = do.params; exec(def.init, {params}); exec(do.init, {params}); payload = eval(def.payload, {params})
      # @see system.entry_do_action() per il codice che gestisce
      # 
      # ATTENZIONE:
      # La manipolazione dei parametri 'port', 'channel' o altri event_keys (vedi sopra) deve SEMPRE avvenire dentro gli 'init' code (ovviamente se il parametro non viene manipolato non ci sono problemi).
      # In caso contrario la gestione delle cache "event_get" non li rileva, e quindi potrebbe non essere ottimizzata (vedi event_get_invalidate_on_action)
      
      ... # Metadati specifici del tipo di modulo
    },
    
    # [L.0] topic_rule: Le dichiarazioni di topic regexp e mqtt, [L.1] l'uso di . e @, [L.2] gli handler
    '/^.*$/': { 'handler': run_regexp }, # Usando '/' iniziale e finale si fa una regexp
    'time/#': { 'handler': run_match }, # Si possono usare anche i match "mqtt-style" (@see mqtt.topic_matches_sub)
     # Rule completa di match: a/b | a/# | /^(.*)$/ | a/b[payload1|payload2] | a/#[/^(payload.*)$/] | /^(.*)$/[js: payload['a']==1 && matches[1] == 'x']

    # Replace fatti inizialmente (e in runtime nel .publish())
    '.': {}, # Usa il topic root
    './data': {},
    '@', # Usa il entry topic 
    '@/data': {},
    
    'lambda': { 'handler': _on_subscribed_message_def(local_variable) }, # Esempio di lambda-function (per passare una variabile alla chiamata interna)
  },

  # TODO [L.0]
  "events_passthrough": "event_reference", # equivalent to [{ "on": "event_reference", "remove_keys": true}],
  "events_passthrough": [
    { "on": "entry.event(condition)", "rename": "event2", "init": "js: code", "remove_keys": true},
    "entry.event(condition)", # equivalent to { "on": "entry.event(condition)", "remove_keys": true},
  ],
  
  # [L.2]
  "on": {
    "entry_id.event(condition)": { # condition è nella forma "js:params['value'] == 1 && params['value'] == 1" ...
      "handler": on_event, # def on_event(entry, eventname, eventdata, caller, published_message): eventdata = {'params': {...}, 'changed_params': {...}}, caller = "message|import|events_passthrough", published_message = source message (null for import)
        # For eventdata description @see system._entry_event_publish
        # NOTE: eventdata is a local copy, so you can change it freely. Other params must not be changed (the changes will be propagated to next listeners and code)
      "script": [...], # Parametry passati: entry, on_entry, eventname, eventdata, params, caller, published_message, caller = "message|import|events_passthrough", published_message = source message (null for import). "entry" passato allo script è quello che ha impostato questa definition, mentre "on_entry" è quello specificato nell'"on" (del quale è stato preso l'evento)
      "do": "entry@NODE.action(init)", # init è nella forma "js:params['value'] = 1; params['value'] = 1;"
      "do": ["entry@NODE.action(init)", ...],
      "do_if_event_not_match": False, # Imposta "if_event_not_match" in system.do_action (default: False). In pratica il do viene fatto solo se l'evento corrispondente non è già in quello stato
    },
    ".event(condition)": { ... } # in questo caso è sull'entry stesso
    ".event": { ... }
    "entry@NODE.event(condition)": { ... }
  },
    
  # [L.2] Permette di "ascoltare" degli eventi, ovvero di memorizzarli nei "listened_events" (passati ad esempio agli handler "on_subscribed_message") e di poter fare degli event_get.
  # Non è necessario fare l'events_listen di eventi che sono già in "on" (che sono già automaticamente ascoltati)
  "events_listen": [
    "entry_id.event",
    "*.event",
    ".event",
  ],
  
  # [L.2] via scripting module
  "methods": {
    "init": [ "print(entry.id)" ], # parametri: (entry, *args, **kwargs)
    "start": [ "print(entry.id)" ], # parametri: (entry, *args, **kwargs)
    "...": [ "print(args[0].id)" ], # parametri: (*args, **kwargs)
  },

}

##########################################################################################

import logging

# Per ogni handler che c'è sotto, possiamo farlo eseguire prima|dopo gli altri impostando questa proprietà (-N viene eseguito prima degli altri, N dopo)
SYSTEM_HANDLER_ORDER_handlername = -10

# La prima chiamata effettuata serve per aggiungere elementi alla definition del modulo
# Viene chiamato PRIMA di init
# WARN: NON è possibile usare i metodi entry.*() [publish|notify] a questo livello, è possibile farlo solo da init(entry) in poi
# Può invece usare .data
# In generale la definizione di self_entry è in caricamento, può ancora essere modificata, e quindi mancano diverse normalizzazioni ed espansioni (ad esempio dei topic di publish / subscribe)
def load(self_entry):
  # Se si vogliono prendere i metadati definiti da configurazione guardare su entry.definition (questi verrano poi uniti al risultato di questa chiamata)
  # self_entry.definition.che contiene già la definizione impostata dal modulo + la definizione caricata da config
  # self_entry.config ancora non è initializzato, usare self_entry.definition['config']
  if self_entry.definition['config']['myconfig']:
    pass
  return {} # Ritorna la parte di definition che si vuole aggiungere/modificare

# OBSOLETE Primissima chiamata di un entry, fatta dopo aver caricato TUTTI gli entry ma prima di chiamare il loro init e di processare publish/subscribe/events/actions
# Le restrizioni sono le stesse di load()
# ATTENZIONE: questa chiamata viene effettuata anche ogni volta che c'è un nuovo load di entries
#def system_loaded(self_entry, entries):
#  # WARN: tutti i publish|subscribe|riferimenti a topic NON sono ancora stati riscritti in riferimenti assoluti (sono ancora logici)
#  
#  self_entry.system.entry_definition_add_default(entries[x], {
#    'publish': ...
#  });
#  pass

# Chiamato durante il load di un entry, dopo l'instanziamento di entry ma prima della sua inizializzazione (è quindi possibile fare l'inject di proprietà/definition/config...)
# WARN: In questa fase non tutte le proprietà dell'entry sono caricate o sono definitive (ad esempio entry.config esiste ma è la versione "iniziale", visto che definition potrebbe cambiare)
# IMPORTANTE: Questo metodo potrebbe essere chiamato mentre lo stesso self_entry è in loading, e dove quindi init() non è ancora stato chiamato. Occorre usare strutture che sono state inizializzate da self_entry.load()
# In generale ci sono le stesse restrizioni di load()
# WARN: Non viene chiamato per l'entry stesso che definisce il metodo (self_entry)
def entry_load(self_entry, entry):
  pass

def entry_unload(self_entry, entry):
  # Deve effettuare la pulizia di eventuale ambiente inizializzato in entry_load
  # Da notare che eventuali event_listener inizializzati in entry_load, se correttamente passato il reference_entry, non è necessario pulirli
  pass

# Usato se il modulo specifica definition.install_on, per "installarsi" su altri entry che hanno delle specifiche proprietà
# WARN + IMPORTANTE:  tutto quanto scritto per entry_load
#
# @param self_entry l'entry del modulo che vuole installare le nuove funzionalità (quello che ha "install_on")
# @param entry l'entry destinazione, alla quale vanno aggiunte le funzionalità
# @param conf la configurazione estratta dalle property dell'entry, in base alle condizioni specificate in "install_on"
def entry_install(self_entry, entry, conf):
  required = entry.definition['required'] if 'required' in entry.definition else []
  required.append(self_entry.id)
  # Aggiunge delle definizioni
  system.entry_definition_add_default(entry, {
    'required': required,
    'publish': {},
  })
  # Aggiunge un handler "init" specifico (può aggiungere solo da "init" in poi, dal momento che load, system_loaded... sono già stati chiamati
  entry.handlers_add('init', 'toggle', entry_init)

def entry_uninstall(self_entry, entry, conf):
  # Deve effettuare la pulizia di eventuale ambiente inizializzato in entry_load
  # Da notare che eventuali event_listener inizializzati in entry_load, se correttamente passato il reference_entry, non è necessario pulirli
  pass

# Inizializzazione: avviata alla creazione del modulo
# Da notare che il broker potrebbe essere ancora sconnesso (se siamo in fase di boot del nodo), ma si possono comunque fare dei publish (che verranno effettuati alla connessione)
def init(self_entry):
  logging.debug('#{id}> debug...'.format(id = self_entry.id))
  
  print(_("Plugin init"))
  print(_("prova %s %s") % ("Plugin", "123"))

# Chiamato quando un entry viene inizializzato (dopo entry_load e entry_install)
# WARN: Non viene chiamato per l'entry stesso che definisce il metodo (self_entry)
def entry_init(self_entry, entry):
  pass

# Chiamato quando viene fatto l'unload dell'entry (alla chiusura del nodo, oppure se l'entry viene eliminato o ricaricato)
def destroy(self_entry):
  pass

# ------------------

# Esempio di callback di subscriptions
def on_subscribed_message(entry, subscribed_message):
  first_published_message = subscribed_message.message.firstPublishedMessage() # Primo messaggio pubblicato (potrebbe essercene anche piu' di uno se dello stesso messaggio ci sono più "publish", nel caso si possono vedere subscribed_message.message.publishedMessages())
  source_entry = firstpm.entry if firstpm else None # Entry che ha pubblicato il messaggio (o meglio, risconosciuto come primo pubblicatore del messaggio, potrebbe essercene più di uno)
  listened_events = subscribed_message.message.events() # [{ 'eventname': ..., 'params': ..., 'changed_params': ..., 'key': ..., 'time': ...}, ...] Tutti gli eventi legati a questo messaggio (da tutti i pubblicatori)
  is_retained = subscribed_message.message.retain # Il messaggio è stato ricevuto in quanto retained e il client si è appena connesso al broker
  
  print(matches[1])

def _on_subscribed_messagel_def(variable):
  return lambda _entry, _subscribed_message: on_subscribed_messagel(_entry, variable, _subscribed_message)

def on_subscribed_messagel(entry, variable, subscribed_message):
  print(matches[1])

  
# Avvio: l'ambiente è stato completamente inizializzato e inizia a partire il processo principale, mqtt è disponibile
def start(entry):
  pass

# Invocato ogni "run_interval" o "run_cron"
def run(entry):
  print("Plugin run")

# Invocato ogni metadata['publish'][topic]['runinterval'] o ['run_cron'] per lo specifico topic, oppure se specificato come callback diretta per una subscription
# @param realtopic Il topic effettivo (quindi comprensivo di entry_topic/topic_root
# @param metadata La porzione di metadati specifici del topic (equivalente a entry.metadata['publish'][topic])
def publish(entry, realtopic, metadata):
  # Per pubblicare lo stesso topic in ingresso si può usare '' in entry.publish()
  entry.publish('', {})
  pass

# Chiamato ogni volta che gli entries vengono cambiati (quindi all'init del nodo, se la configurazione viene ricaricata, se entra un nuovo nodo nel sistema o se esce)
def system_entries_change(entry, entry_ids_loaded, entry_ids_unloaded):
  pass

# Esempio di uso thread interno:
def init(entry):
  entry._module_thread = threading.Thread(target = _timer, args = [entry], daemon = True) # daemon = True allows the main application to exit even though the thread is running. It will also (therefore) make it possible to use ctrl+c to terminate the application
  entry._module_thread.start()

def destroy(entry):
  if hasattr(entry, '_module_thread'):
    entry._module_thread._destroyed = True
    entry._module_thread.join()

def _timer(entry):
  while not threading.currentThread()._destroyed:
    pass


