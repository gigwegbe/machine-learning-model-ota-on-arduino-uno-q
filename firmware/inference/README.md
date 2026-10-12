# Edge Impulse IMU Inference on Zephyr

This repository demonstrates how to run IMU-based Edge Impulse models on Zephyr using the **[Edge Impulse Zephyr Module](https://docs.edgeimpulse.com/hardware/deployments/run-zephyr-module)**.  
Drop in your model > build > flash > get real-time motion inference.

## Initialize This Repo

```bash
west init https://github.com/edgeimpulse/ei-zephyr-imu-inference.git
cd ei-zephyr-imu-inference
west update
```

This fetches:
- Zephyr RTOS
- Edge Impulse Zephyr SDK module
- All module dependencies

## Update the Model

In Edge Impulse Studio go to:  
**Deployment** > **Zephyr library** > **Build**

Download the generated `.zip`

Extract into the `model/` folder:

```bash
unzip -o ~/Downloads/your-model.zip -d model/
```

Your `model/` directory should contain:
- `CMakeLists.txt`
- `edge-impulse-sdk/`
- `model-parameters/`
- `tflite-model/`

## Supported shield

The project support the following sensor shield:
- [X-NUCLEO-IKS02A1](https://www.st.com/en/evaluation-tools/x-nucleo-iks02a1.html) enabled passing `-DCONFIG_EI_IKS02A1=y`
- [IKS01A3](https://www.st.com/en/evaluation-tools/x-nucleo-iks01a3.html) enabled passing `-DCONFIG_EI_IKS01A3=y`
- [X-NUCLEO-IKS4A1](https://www.st.com/en/evaluation-tools/x-nucleo-iks4a1.html) enabled passing `-DCONFIG_EI_IKS4A1=y` (uses LIS2DUXS12 accel + LSM6DSV16X 6-axis IMU; shield jumpers J4/J5 must be in Mode 1 / standard I2C)

## Build

Choose your board and the shield you are targeting,

For example: Nucleo U585ZI + IKS01A3
```bash
west build --pristine -b nucleo_u585zi_q -- -DCONFIG_EI_IKS01A3=y
```

Or Renesas EK RA6M5 + IKS02A1
```bash
west build --pristine -b ek_ra6m5 -- -DCONFIG_EI_IKS02A1=y
```
Or Arduino UNO Q + IKS4A1
```bash
west build --pristine -b arduino_uno_q -- -DCONFIG_EI_IKS4A1=y
```

> [!NOTE]
> You need to define one of the supported shield otherwise the build will fail with an error.

## Flash

```bash
west flash
```

Or specify runner:

```bash
west flash --runner jlink
west flash --runner nrfjprog
west flash --runner openocd
```

## Sensors Supported

All sensors accessible through I²C/SPI + Zephyr sensor drivers are compatible.

## Project Structure

```
├── CMakeLists.txt          # Build configuration
├── prj.conf                # Zephyr config
├── west.yml                # Manifest (declares Edge Impulse SDK module)
├── model/                  # Your Edge Impulse model (Zephyr library)
└── src/
    ├── main.cpp
    ├── inference/          # Inference state machine
    └── sensors/            # IMU interface
```

## How It Works

1. **Initialize** - Sensor setup via Zephyr sensor API
2. **Sample** - Continuous data collection at model frequency
3. **Buffer** - Circular buffer stores samples
4. **Infer** - Run classifier when buffer full
5. **Output** - Print classification results
6. **Loop** - Repeat

## Configuration

Key settings in `prj.conf`:

```properties
CONFIG_EDGE_IMPULSE_SDK=y        # Enable Edge Impulse SDK
CONFIG_MAIN_STACK_SIZE=8192      # Adjust for your model size
CONFIG_SENSOR=y                  # Enable sensor subsystem
CONFIG_I2C=y                     # Enable I2C for sensors
```

For larger models, increase stack size:

```properties
CONFIG_MAIN_STACK_SIZE=16384
```

## Using in Your Own Project

Add to your `west.yml`:

```yaml
projects:
  - name: edge-impulse-sdk-zephyr
    path: modules/edge-impulse-sdk-zephyr
    revision: v1.75.4  # See https://github.com/edgeimpulse/edge-impulse-sdk-zephyr/tags
    url: https://github.com/edgeimpulse/edge-impulse-sdk-zephyr
```

Then:

```bash
west update
```

Add to your `CMakeLists.txt`:

```cmake
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/model)
```

## Troubleshooting

### **Module not found**
```bash
west update
```

### **Insufficient memory**
```properties
# In prj.conf
CONFIG_MAIN_STACK_SIZE=16384
```

### **Sensor not detected**
```properties
# In prj.conf - enable debug logging
CONFIG_I2C_LOG_LEVEL_DBG=y
CONFIG_SENSOR_LOG_LEVEL_DBG=y
```


### Cyclic Dependency Error

**Symptom:**
```
CMake Error at .../zephyr/cmake/modules/zephyr_module.cmake:73 (message):
  Unmet or cyclic dependencies in modules:
  /path/to/your-project/model
  depends on: ['edge-impulse-sdk-zephyr']
```

**Cause:**
Your project has **two** `module.yml` files registering different parts of your application as Zephyr modules. This creates a hierarchical conflict where the module system can't determine the correct dependency resolution order.

**How to Check:**
From your project root, run:
```bash
find . -maxdepth 2 -name "module.yml"
```

You should see **only ONE** result:
```
./model/zephyr/module.yml  ✓ CORRECT
```

If you see **both** of these:
```
./zephyr/module.yml        DELETE THIS
./model/zephyr/module.yml  KEEP THIS
```

**Fix:**
Delete the `zephyr/module.yml` file at your project root:
```bash
rm zephyr/module.yml
```

Then run:
```bash
west update
west build -b <your_board> -p
```

**Why This Happens:**
- `model/zephyr/module.yml` correctly registers your trained ML model as a module
- `zephyr/module.yml` incorrectly registers the entire application as a module
- The build system finds the project-level module first, then encounters the model module nested inside, creating a circular dependency

**Key Principle:**
Only the `model` should be a Zephyr module. Your application project is a Zephyr **application**, not a module.


## Resources


- [Edge Impulse SDK for Zephyr](https://github.com/edgeimpulse/edge-impulse-sdk-zephyr)



Clear BSD License - see `LICENSE` file  
Copyright (c) 2025 EdgeImpulse Inc.
