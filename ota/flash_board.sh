#!/usr/bin/env bash
# flash_board.sh — flash the STM32 on the UNO Q, on the board itself.
# Called by ota_gateway.py as:  flash_board.sh <path-to-firmware.elf>
# Uses the on-board OpenOCD/SWD over gpiochip1. No Mac, no adb, no gdb.
set -euo pipefail

ELF="${1:?usage: flash_board.sh <firmware.elf>}"
GPIOCHIP=/dev/gpiochip1
OCD_TELNET=4444

# 1) Must be an ELF. OpenOCD needs the load addresses a .bin does not carry.
#    Read the 4-byte magic with python3 (guaranteed on the board; xxd is not).
magic=$(python3 -c 'import sys; print(open(sys.argv[1],"rb").read(4).hex())' "$ELF" 2>/dev/null || true)
if [ "$magic" != "7f454c46" ]; then
  echo "[flash] ERROR: $ELF is not an ELF (magic=$magic)"; exit 1
fi

# 2) SWD needs write access to the GPIO chip. The systemd unit's ExecStartPre
#    already sets this as root; this is a best-effort fallback for manual runs.
chmod 666 "$GPIOCHIP" 2>/dev/null || true

# 3) Bring up the on-board OpenOCD SWD server (same tool bridge.sh uses).
arduino-debug >/tmp/flash-ocd.log 2>&1 &
OCD_PID=$!
trap 'kill "$OCD_PID" 2>/dev/null || true' EXIT

# 4) Wait for OpenOCD's telnet command port to come up.
for _ in $(seq 1 30); do
  if (exec 3<>"/dev/tcp/localhost/$OCD_TELNET") 2>/dev/null; then
    exec 3>&- 3<&-; break
  fi
  sleep 1
done

# 5) Program + verify + reset via OpenOCD's command interface (python3 is on the board).
python3 - "$ELF" <<'PY'
import socket, sys, time
elf = sys.argv[1]
s = socket.create_connection(("localhost", 4444), timeout=180)
time.sleep(0.5)
for c in (f"program {elf} verify reset", "shutdown"):
    s.sendall((c + "\n").encode()); time.sleep(1)
out = b""
s.settimeout(180)
try:
    while True:
        b = s.recv(4096)
        if not b:
            break
        out += b
except Exception:
    pass
text = out.decode(errors="replace")
print(text)
sys.exit(0 if ("verified" in text.lower() or "Verified OK" in text) else 1)
PY
rc=$?
echo "[flash] done rc=$rc"
exit $rc