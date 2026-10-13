#!/usr/bin/env bash
# Start the UNO Q flashing bridge. Leave this terminal running while you flash.
# It forwards the on-board OpenOCD server (running on the Linux side) to your laptop.
set -e
adb devices | grep -q "device$" || { echo "No UNO Q found. Check the USB cable and wait for Linux to boot (adb devices)."; exit 1; }
echo "Starting bridge - keep this terminal open. Ctrl-C to stop."
adb forward tcp:3333 tcp:3333
adb shell arduino-debug
