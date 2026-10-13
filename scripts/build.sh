#!/usr/bin/env bash
# Usage: scripts/build.sh forwarder | inference
set -e
cd "$(dirname "$0")/.."
case "$1" in
  forwarder)
    cd firmware/data-forwarder
    west build --pristine -b arduino_uno_q -- -DSHIELD=x_nucleo_iks4a1 ;;
  inference)
    [ -f firmware/inference/model/CMakeLists.txt ] || { echo "No model found in firmware/inference/model/. Unzip your Edge Impulse Zephyr library there first (README step 4)."; exit 1; }
    cd firmware/inference
    west build --pristine -b arduino_uno_q -- -DCONFIG_EI_IKS4A1=y ;;
  *) echo "Usage: $0 forwarder|inference"; exit 1 ;;
esac
