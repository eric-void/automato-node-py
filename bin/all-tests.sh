echo "----------------------------------------------------------------------------------------------------------------------------------------------------------------"
automato-node-py/bin/automato-node.sh -c test-config.json --test  system_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  node_system_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  health_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  scheduler_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  toggle_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  shelly_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  tasmota_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  rf_listener_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  rf2mqtt_listener_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  location_owntracks_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  net_sniffer_scapy_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  net_sniffer_iw_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  presence_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  nodes_test
automato-node-py/bin/automato-node.sh -c test-config.json --test  owrtwifi2mqtt_test
echo "----------------------------------------------------------------------------------------------------------------------------------------------------------------"
