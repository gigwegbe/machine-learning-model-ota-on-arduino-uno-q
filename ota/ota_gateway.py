#!/usr/bin/env python3
"""
ota_gateway.py  -  Linux-orchestrated OTA gateway for the Arduino UNO Q.

Runs on the Debian (Qualcomm) side of the UNO Q. It talks to the Golioth
DEVICE HTTP gateway (the HTTP mirror of the CoAP device API), so the board
appears as a real Golioth device: it reads the desired-firmware manifest,
downloads the artifact, flashes the STM32 over the on-board SWD bridge, and
reports its state back to Golioth.

Device API contract (from Golioth docs, mirrored onto HTTP at gw.golioth.io):
    GET  /.u/desired                 -> manifest (which version this device wants)
    GET  /.u/c/{package}@{version}   -> the binary for that component
    POST /.u/c/{package}             -> report firmware state

No third-party packages needed: standard library only.

Setup:
  1. Create a device for this board in the Golioth console and grab its
     PSK-ID and PSK (Credentials tab). Add the device to the cohort you
     deploy to.
  2. Configure the env vars below, then:
       python3 ota_gateway.py          # one poll+update cycle
       python3 ota_gateway.py --watch  # poll forever

AUTH NOTE: the CoAP gateway uses DTLS-PSK. Over HTTPS on gw.golioth.io the
DTLS handshake isn't available, so the PSK is presented at the application
layer. This script defaults to HTTP Basic (psk-id:psk), which is the usual
mapping, but confirm the exact scheme with Golioth (Chris). If they want a
different header, set GOLIOTH_AUTH_HEADER and it is sent verbatim.
"""

import os
import ssl
import json
import time
import base64
import hashlib
import shlex
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urljoin

# ------------------------- CONFIG (env vars) -------------------------
GW        = os.environ.get("GOLIOTH_GW", "https://gw.golioth.io")
PSK_ID    = os.environ.get("GOLIOTH_PSK_ID", "")   # e.g. "uno-q-01@unoq-gestures"
PSK       = os.environ.get("GOLIOTH_PSK", "")
PACKAGE   = os.environ.get("GOLIOTH_PACKAGE", "main")
POLL_SECONDS = int(os.environ.get("GOLIOTH_POLL_SECONDS", "30"))

STATE_FILE = Path(os.environ.get("GATEWAY_STATE_FILE", "/home/arduino/ota_state.json"))
WORK_DIR   = Path(os.environ.get("GATEWAY_WORK_DIR", "/home/arduino/ota_artifacts"))

# How to flash. {path} is replaced with the downloaded artifact file.
# Reuses your repo's proven wrapper. Whatever this command consumes (ELF vs
# raw .bin) is the artifact type you upload with publish_update.py.
FLASH_CMD  = os.environ.get("GATEWAY_FLASH_CMD", "./scripts/flash.sh {path}")

# Auth. Default is HTTP Basic with psk-id:psk. Override with a full header
# value if Golioth wants something else, e.g. "Bearer <token>".
AUTH_HEADER = os.environ.get("GOLIOTH_AUTH_HEADER", "")
# ---------------------------------------------------------------------

# Firmware states (Golioth device OTA API)
S_IDLE, S_DOWNLOADING, S_DOWNLOADED, S_UPDATED = 0, 1, 2, 3

_SSL = ssl.create_default_context()


def log(msg: str) -> None:
    print(f"[ota-gateway] {msg}", flush=True)


def auth_value() -> str:
    if AUTH_HEADER:
        return AUTH_HEADER
    raw = f"{PSK_ID}:{PSK}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def request(method: str, url: str, body: bytes | None = None,
            content_type: str | None = None) -> bytes:
    headers = {"Authorization": auth_value()}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, context=_SSL, timeout=120) as resp:
        return resp.read()


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_manifest() -> dict:
    data = request("GET", urljoin(GW, "/.u/desired"))
    if not data:
        return {}
    return json.loads(data)


def pick_component(manifest: dict) -> dict | None:
    # components is absent OR explicitly null when nothing is deployed
    for comp in (manifest.get("components") or []):
        if comp.get("package") == PACKAGE:
            return comp
    return None


def download(comp: dict) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    version = comp["version"]
    uri = comp.get("uri") or f"/.u/c/{PACKAGE}@{version}"
    url = urljoin(GW, uri)
    log(f"downloading {url}")
    data = request("GET", url)

    expected = comp.get("hash")
    if expected:
        got = hashlib.sha256(data).hexdigest()
        if got != expected:
            raise RuntimeError(f"sha256 mismatch: expected {expected}, got {got}")
        log("sha256 verified")

    # Saved as .elf: the artifact IS the Zephyr ELF (flash.sh / OpenOCD need
    # the section load addresses). The name is cosmetic (flash.sh checks the
    # ELF magic regardless), but .bin here was misleading.
    out = WORK_DIR / f"{PACKAGE}-{version}.elf"
    out.write_bytes(data)
    log(f"saved {out} ({len(data)} bytes, type={comp.get('type')})")
    return out


def report(state: int, version: str | None = None,
           target: str | None = None, reason: int = 0) -> None:
    payload = {"state": state, "reason": reason, "package": PACKAGE}
    if version is not None:
        payload["version"] = version
    if target is not None:
        payload["target"] = target
    try:
        request("POST", urljoin(GW, f"/.u/c/{PACKAGE}"),
                body=json.dumps(payload).encode(),
                content_type="application/json")
    except Exception as e:
        log(f"state report failed (non-fatal): {e}")


def flash(path: Path) -> None:
    cmd = FLASH_CMD.format(path=shlex.quote(str(path)))
    log(f"flashing: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    log("flash complete")


def check_once() -> bool:
    """One poll+update cycle. Returns True if an update was applied."""
    if not PSK_ID or not PSK:
        raise SystemExit("set GOLIOTH_PSK_ID and GOLIOTH_PSK")

    manifest = get_manifest()
    seq = manifest.get("sequenceNumber")
    comps = manifest.get("components") or []
    log(f"desired: seq={seq}, packages={[c.get('package') for c in comps]}")
    comp = pick_component(manifest)
    if comp is None:
        log(f"no '{PACKAGE}' component in desired manifest "
            f"(nothing deployed to this device's cohort yet)")
        return False

    target = comp["version"]
    state = load_state()
    current = state.get("version")

    if target == current:
        log(f"up to date (version {target})")
        return False

    log(f"update available: {current or 'none'} -> {target}")
    report(S_DOWNLOADING, version=current, target=target)
    path = download(comp)
    report(S_DOWNLOADED, version=current, target=target)

    flash(path)
    report(S_UPDATED, version=target, target=target)
    report(S_IDLE, version=target)  # now running the new version

    state.update({"version": target, "package": PACKAGE})
    save_state(state)
    log(f"now running {PACKAGE}-{target}")
    return True


def watch() -> None:
    log(f"watching package '{PACKAGE}' every {POLL_SECONDS}s")
    while True:
        try:
            check_once()
        except urllib.error.HTTPError as e:
            log(f"http error {e.code}: {e.reason}")
        except Exception as e:
            log(f"error: {e}")
        time.sleep(POLL_SECONDS)


def main() -> None:
    ap = argparse.ArgumentParser(description="Golioth device HTTP -> STM32 OTA gateway")
    ap.add_argument("--watch", action="store_true", help="poll forever")
    args = ap.parse_args()
    if args.watch:
        watch()
    else:
        check_once()


if __name__ == "__main__":
    main()