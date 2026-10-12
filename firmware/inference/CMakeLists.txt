cmake_minimum_required(VERSION 3.20.0)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/model)

if(DEFINED CONFIG_EI_IKS02A1) # using the edge-impulse-sdk-zephyr module
    message(STATUS "CONFIG_EI_IKS02A1")
    # This firmware uses X-Nucleo IKS02A1 shield
    set(SHIELD x_nucleo_iks02a1)
elseif(DEFINED CONFIG_EI_IKS01A3)
    message(STATUS "CONFIG_EI_IKS01A3")
    set(SHIELD x_nucleo_iks01a3)
elseif(DEFINED CONFIG_EI_IKS4A1)
    message(STATUS "CONFIG_EI_IKS4A1")
    # This firmware uses X-Nucleo IKS4A1 shield (upstream Zephyr shield)
    set(SHIELD x_nucleo_iks4a1)
else()
    message(FATAL_ERROR "No supported IMU shield defined! Please enable CONFIG_EI_IKS02A1, CONFIG_EI_IKS01A3 or CONFIG_EI_IKS4A1 in prj.conf")
    exit(1)
endif()

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(ei-zephyr-imu-inference)

include(utils/cmake/utils.cmake)

# Needed for colorful output
zephyr_compile_options(-fdiagnostics-color=always)

# Project include directories
set(INCLUDES
    .
    src
    )
include_directories(${INCLUDES})

# add all sources to the project
target_sources(app PRIVATE src/main.cpp)
if(DEFINED CONFIG_EI_IKS02A1)
target_sources(app PRIVATE src/sensors/iks02a1/ei_accelerometer.cpp)
target_sources(app PRIVATE src/sensors/iks02a1/ei_inertial.cpp)
elseif(DEFINED CONFIG_EI_IKS01A3)
target_sources(app PRIVATE src/sensors/iks01a3/ei_accelerometer.cpp)
target_sources(app PRIVATE src/sensors/iks01a3/ei_inertial.cpp)
elseif(DEFINED CONFIG_EI_IKS4A1)
target_sources(app PRIVATE src/sensors/iks4a1/ei_accelerometer.cpp)
target_sources(app PRIVATE src/sensors/iks4a1/ei_inertial.cpp)
endif()
target_sources(app PRIVATE src/inference/inferencing.cpp)
