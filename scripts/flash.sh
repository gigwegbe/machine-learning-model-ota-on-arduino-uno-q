#!/usr/bin/env bash
# Usage: scripts/flash.sh forwarder | inference
# Run scripts/bridge.sh in another terminal first and wait for
# "Listening on port 3333" before running this.
set -e
cd "$(dirname "$0")/.."
case "$1" in
  forwarder) cd firmware/data-forwarder ;;
  inference) cd firmware/inference ;;
  *) echo "Usage: $0 forwarder|inference"; exit 1 ;;
esac

# Flash over the bridge with gdb. The on-board programmer is reached
# through the gdb server bridge.sh exposes on localhost:3333, not a
# local adapter, so `west flash -r openocd` cannot work on this board.
GDB="${ZEPHYR_GDB:-$HOME/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gdb}"
PORT="${BRIDGE_PORT:-3333}"
ELF="build/zephyr/zephyr.elf"

[ -x "$GDB" ] || { echo "gdb not found at $GDB. Set ZEPHYR_GDB to your arm-zephyr-eabi-gdb."; exit 1; }
[ -f "$ELF" ]  || { echo "No $ELF. Run scripts/build.sh $1 first."; exit 1; }

"$GDB" "$ELF" \
  -ex "target extended-remote localhost:$PORT" \
  -ex "load" \
  -ex "monitor reset run" \
  -ex "detach" \
  -ex "quit"