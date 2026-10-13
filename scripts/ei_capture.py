#!/usr/bin/env python3
"""
Capture accelerometer data from the UNO Q's /dev/ttyHS1 and upload it to
Edge Impulse as a labelled sample, bypassing the (USB-only) data forwarder.

Usage:
    sudo python3 ei_capture.py <label> [seconds]

Example:
    sudo python3 ei_capture.py idle 10
    sudo python3 ei_capture.py wave 10
    sudo python3 ei_capture.py updown 10

Set your key first (from Studio -> Dashboard -> Keys):
    export EI_API_KEY=ei_xxxxxxxx...
"""
import sys, os, time, json, hmac, hashlib, urllib.request, serial

PORT      = "/dev/ttyHS1"
BAUD      = 115200
HZ        = 100                       # must match your firmware + your impulse
AXES      = ["accX", "accY", "accZ"]
API_KEY   = os.environ.get("EI_API_KEY", "ei_***")
INGEST    = "https://ingestion.edgeimpulse.com/api/training/data"

def main():
    if not API_KEY:
        sys.exit("Set EI_API_KEY first:  export EI_API_KEY=ei_...")
    if len(sys.argv) < 2:
        sys.exit("Usage: sudo python3 ei_capture.py <label> [seconds]")
    label   = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    want    = int(seconds * HZ)

    print(f"Recording '{label}' for {seconds:.0f}s ({want} samples). Perform the gesture now...")
    ser = serial.Serial(PORT, BAUD, timeout=2)
    ser.reset_input_buffer()

    values = []
    t0 = time.time()
    while len(values) < want and time.time() - t0 < seconds + 5:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 3:
            continue
        try:
            values.append([float(p) for p in parts])
        except ValueError:
            continue
    ser.close()
    print(f"Captured {len(values)} samples.")
    if len(values) < want * 0.5:
        sys.exit("Too few samples - is the stream flowing on /dev/ttyHS1 and arduino-router stopped?")

    payload = {
        "protected": {"ver": "v1", "alg": "HS256", "iat": int(time.time())},
        "signature": "0" * 64,
        "payload": {
            "device_name": "uno-q-01",
            "device_type": "ARDUINO_UNO_Q",
            "interval_ms": 1000.0 / HZ,
            "sensors": [{"name": a, "units": "m/s2"} for a in AXES],
            "values": values,
        },
    }
    body = json.dumps(payload).encode()
    # HMAC signature over the body with the empty-signature placeholder
    sig = hmac.new(API_KEY.encode(), body, hashlib.sha256).hexdigest()
    payload["signature"] = sig
    body = json.dumps(payload).encode()

    req = urllib.request.Request(
        INGEST, data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "x-file-name": f"{label}.{int(time.time())}",
            "x-label": label,
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            print("Upload OK:", r.status, r.read().decode()[:200])
    except urllib.error.HTTPError as e:
        print("Upload failed:", e.code, e.read().decode()[:400])

if __name__ == "__main__":
    main()