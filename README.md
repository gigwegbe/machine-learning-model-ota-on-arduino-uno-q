# Gesture recognition on the Arduino UNO Q with Edge Impulse and Zephyr

Train an accelerometer gesture model (idle / wave / updown) in Edge Impulse Studio and run it on the
STM32 side of the **Arduino UNO Q** with the **X-NUCLEO-IKS4A1** sensor shield, on Zephyr RTOS.

## What's in here

```
.
├── west.yml                     West manifest: pulls Zephyr + Edge Impulse SDK into the workspace
├── firmware/
│   ├── data-forwarder/          Firmware 1: streams accel x,y,z at 100 Hz for data collection
│   │   └── boards/arduino_uno_q.overlay   Routes the console to lpuart1 (REQUIRED, see below)
│   └── inference/               Firmware 2: runs your trained model (Edge Impulse example + IKS4A1 support)
│       ├── boards/arduino_uno_q.overlay   Same console overlay (REQUIRED here too)
│       └── model/               <- you unzip your Edge Impulse "Zephyr library" here (git-ignored)
├── patches/iks4a1.patch         The IKS4A1 changes against upstream ei-zephyr-imu-inference, for reference
├── scripts/                     bridge.sh / build.sh / flash.sh helpers, plus ei_capture.py (data upload)
├── ota/                         Golioth OTA: publish_update.py (push a model) + ota_gateway.py (board pulls + flashes)
└── docs/                        Beginner's guide + proposal
```

Two firmwares, one board: you flash `data-forwarder` first to record training data, then `inference`
with your model inside. Both read the same sensor (LIS2DUXS12) in the same units, so training data and
live data match. Both also need the same console overlay.

## Hardware

| Part | Notes |
| --- | --- |
| Arduino UNO Q | Linux side (Qualcomm QRB2210) handles USB/Wi-Fi; STM32U585 runs Zephyr and the model |
| X-NUCLEO-IKS4A1 | Jumpers **J4 and J5 on 1-2 and 11-12** (Mode 1, factory default). Other modes hide the sensors from Zephyr |
| USB-C cable / PD dongle | The board runs Linux; give it a proper power source |

## UNO Q realities (read this first)

The UNO Q is two computers on one board: a Qualcomm chip running Debian Linux (owns USB and Wi-Fi) and an
STM32U585 running Zephyr (runs your model). That split breaks three assumptions the normal Zephyr flow makes.

**1. `west flash` does not work.** It spawns OpenOCD on your laptop, which has no debug adapter. The
programmer lives on the board's Linux side. You flash by running a bridge on the board and driving it with
gdb from your laptop (see "Flashing" below).

**2. The console does not go to USB.** The board default routes the STM32 console to `usart1` on pins
PB6/PB7, which are the D0/D1 header pins. Nothing on Linux or your laptop can read those. The UART wired to
the Linux side is `lpuart1` (PG5-PG8). Each app in this repo therefore ships a
`boards/arduino_uno_q.overlay` that re-points the console to `lpuart1`. Zephyr auto-applies it because of
the filename, no extra flag needed. If you build a new app for this board, copy that overlay in or you get
silence.

**3. You read output on the board, not on your laptop.** With the console on `lpuart1`, the STM32's output
surfaces on the board's Linux side as `/dev/ttyHS1`. But the `arduino-router` service holds that port, so
you stop it first (see "Reading serial output").

### 1. Install tools (once)

Build host is your laptop (Linux or macOS). Ubuntu 22.04/24.04:

```bash
sudo apt update && sudo apt install --no-install-recommends git cmake ninja-build gperf \
  ccache dfu-util device-tree-compiler wget python3-dev python3-pip python3-setuptools \
  python3-tk python3-wheel python3-venv xz-utils file make gcc gcc-multilib g++-multilib \
  libsdl2-dev libmagic1 android-tools-adb
```

### 2. Create the Zephyr workspace (once)

```bash
mkdir -p ~/unoq-ml && cd ~/unoq-ml
python3 -m venv .venv && source .venv/bin/activate
pip install west

west init -m https://github.com/gigwegbe/machine-learning-model-ota-on-arduino-uno-q.git .
west update                                    # downloads Zephyr + modules, takes a while
west zephyr-export
pip install -r zephyr/scripts/requirements.txt
west sdk install --toolchains arm-zephyr-eabi
```

You now have `~/unoq-ml/machine-learning-model-ota-on-arduino-uno-q/` (this repo) next to `zephyr/` and `modules/`.
All commands below run from inside this repo with the venv active:

```bash
cd ~/unoq-ml && source .venv/bin/activate && cd unoq-edge-impulse-gestures
```

### 3. Collect data

Build and flash the data forwarder:

```bash
scripts/build.sh forwarder
scripts/bridge.sh          # Terminal 1 - leave running, wait for "Listening on port 3333"
scripts/flash.sh forwarder # Terminal 2
```

`scripts/flash.sh` runs the gdb-load method described under "Flashing". Before the first flash after any
reboot, run `sudo chmod 666 /dev/gpiochip1` on the board (`adb shell`), or the bridge fails with a GPIO
permission error.

### Build Terminal

```bash
[190/190] Linking C executable zephyr/zephyr.elf
Memory region         Used Size  Region Size  %age Used
           FLASH:       45184 B         2 MB      2.15%
             RAM:        7328 B       768 KB      0.93%
           SRAM0:           0 B       768 KB      0.00%
        IDT_LIST:           0 B        32 KB      0.00%
Generating files from /Users/george/zephyrproject/machine-learning-model-ota-on-arduino-uno-q/firmware/data-forwarder/build/zephyr/zephyr.elf for board: arduino_uno_q/stm32u585xx
```

### Bridge Terminal

```bash
(.venv) george@192 machine-learning-model-ota-on-arduino-uno-q % scripts/bridge.sh         
Starting bridge - keep this terminal open. Ctrl-C to stop.
3333
Open On-Chip Debugger 0.12.0+dev-ge6a2c12f4 (2025-05-22-15:51)
Licensed under GNU GPL v2
For bug reports, read
        http://openocd.org/doc/doxygen/bugs.html
debug_level: 2
clock_config
Info : Linux GPIOD JTAG/SWD bitbang driver (libgpiod v2)
Info : Note: The adapter "linuxgpiod" doesn't support configurable speed
Info : SWD DPIDR 0x0be12477
Info : [stm32u5.ap0] Examination succeed
Info : [stm32u5.cpu] Cortex-M33 r0p4 processor detected
Info : [stm32u5.cpu] target has 8 breakpoints, 4 watchpoints
Info : [stm32u5.cpu] Examination succeed
Info : [stm32u5.ap0] gdb port disabled
Info : [stm32u5.cpu] starting gdb server on 3333
Info : Listening on port 3333 for gdb connections
Info : Listening on port 6666 for tcl connections
Info : Listening on port 4444 for telnet connections

```

### Flashing Terminal

```bash
Loading section datas, size 0x1e4 lma 0x800ae38
Loading section device_states, size 0x34 lma 0x800b01c
Loading section .last_section, size 0x4 lma 0x800b050
--Type <RET> for more, q to quit, c to continue without paging--
Start address 0x08002224, load size 45136
Transfer rate: 7 KB/sec, 3224 bytes/write.
Detaching from program: /Users/george/zephyrproject/machine-learning-model-ota-on-arduino-uno-q/firmware/data-forwarder/build/zephyr/zephyr.elf, Remote target
[Inferior 1 (Remote target) detached]
```

### Board Terminal

```bash
0.182,0.479,9.677
0.191,0.488,9.686
0.182,0.469,9.705
0.182,0.431,9.686
0.172,0.431,9.744
0.144,0.392,9.705
0.144,0.325,9.686
0.201,0.373,9.610
arduino@George-Uno:~$ 
```

Sanity check the numbers are flowing. **On the board** (`adb shell`):

```bash
sudo systemctl stop arduino-router                 # it holds /dev/ttyHS1
sudo stty -F /dev/ttyHS1 115200 raw -echo
sudo cat /dev/ttyHS1
```

Move the board and you should see three numbers per line at ~100 Hz, one axis near ±9.8 when still. Stop
with Ctrl-C.

Upload labelled samples to Edge Impulse. The stock `edge-impulse-data-forwarder` does not work here (it
only accepts USB serial devices, and our data is on `/dev/ttyHS1` on the board). Use the included capture
script instead, **on the board**:

```bash
# one-time: pyserial on the board
sudo apt-get update && sudo apt-get install -y python3-serial   # or: pip install --break-system-packages pyserial

python3 scripts/ei_capture.py --label idle --seconds 10         # repeat per label
```

It reads `/dev/ttyHS1` and posts to the Edge Impulse ingestion API. Record at least 2 minutes each of
`idle`, `wave`, `updown`, then in Studio do **Perform train/test split**.

### 4. Train

Studio → **Create impulse**: window **2000 ms**, stride 200 ms, **frequency 100 Hz** (must match the
firmware), add **Spectral Analysis** + **Classification**. Generate features, train (~60 cycles), check
**Model testing** accuracy.

[Building Impulse](./assets/impulse-building.png)

[Training Result](./assets/impulse-building.png)

```bash
(.venv) george@192 machine-learning-model-ota-on-arduino-uno-q % unzip -o ~/Downloads/arduino-uno-q-continous-model-deployment-golioth-zephyr-module-v3.zip  -d firmware/inference/model/
Archive:  /Users/george/Downloads/arduino-uno-q-continous-model-deployment-golioth-zephyr-module-v3.zip
   creating: firmware/inference/model//model-parameters
  inflating: firmware/inference/model//model-parameters/model_metadata.h  
  inflating: firmware/inference/model//model-parameters/model_variables.h  
   creating: firmware/inference/model//tflite-model
  inflating: firmware/inference/model//tflite-model/trained_model_ops_define.h  
  inflating: firmware/inference/model//tflite-model/tflite_learn_1105163_3_compiled.h  
  inflating: firmware/inference/model//tflite-model/tflite_learn_1105163_3_compiled.cpp  
  inflating: firmware/inference/model//tflite-model/check_version.cpp  
   creating: firmware/inference/model//zephyr
  inflating: firmware/inference/model//zephyr/module.yml  
  inflating: firmware/inference/model//CMakeLists.txt  
  inflating: firmware/inference/model//west.yml  
  inflating: firmware/inference/model//README.md  
(.venv) george@192 machine-learning-model-ota-on-arduino-uno-q % 
```
