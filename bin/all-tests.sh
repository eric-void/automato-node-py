#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NODE_LAUNCHER="$SCRIPT_DIR/automato-node.sh"
TEST_CONFIG=${AUTOMATO_TEST_CONFIG:-"$SCRIPT_DIR/../docker/test-config.json"}

if [ "$#" -eq 0 ]; then
  set -- system_test node_system_test health_test scheduler_test toggle_test \
    shelly_test tasmota_test rf_listener_test rf2mqtt_listener_test \
    location_owntracks_test net_test net_sniffer_test net_sniffer_scapy_test \
    presence_test nodes_test owrtwifi2mqtt_test influxdb_test
fi

failed=0
for test_name do
  printf '\n===== Automato test: %s =====\n' "$test_name"
  if "$NODE_LAUNCHER" -c "$TEST_CONFIG" --test "$test_name"; then
    :
  else
    status=$?
    printf '===== FAILED: %s (exit %s) =====\n' "$test_name" "$status" >&2
    failed=1
  fi
done

exit "$failed"
