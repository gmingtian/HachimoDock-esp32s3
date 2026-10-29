# [Input] ESP-IDF environment, project sources, optional target-specific version override, and Git build identity.
# [Output] Versioned ESP32-P4 firmware project with target-isolated protocol/build metadata.
# [Pos] Firmware build entry for firmware.
# [Sync] If this file changes, update `firmware/.folder.md` and README.md.

cmake_minimum_required(VERSION 3.16)

if("$ENV{PET_P4_CHIP_FAMILY}" STREQUAL "v3")
  set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.v3.defaults")
endif()
if(IDF_TARGET STREQUAL "esp32s3" OR "$ENV{IDF_TARGET}" STREQUAL "esp32s3")
  set(PET_BUILD_S3 ON)
  set(SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.s3.defaults")
  set(SDKCONFIG "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.s3")
  set(COMPONENTS main)
  set(COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/main" "$ENV{IDF_PATH}/components")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
if(PET_BUILD_S3)
  idf_build_set_property(DEPENDENCIES_LOCK "${CMAKE_CURRENT_LIST_DIR}/dependencies.s3.lock")
endif()
if("$ENV{PET_P4_CHIP_FAMILY}" STREQUAL "v3")
  idf_build_set_property(DEPENDENCIES_LOCK "${CMAKE_CURRENT_LIST_DIR}/dependencies.v3.lock")
endif()
set(PROJECT_VER "0.7.103-p4-r1")
if(PET_BUILD_S3)
  set(PROJECT_VER "0.7.103-s3-r2")
endif()
if(DEFINED ENV{PET_P4_PROJECT_VER_OVERRIDE} AND NOT "$ENV{PET_P4_PROJECT_VER_OVERRIDE}" STREQUAL "")
  set(PROJECT_VER "$ENV{PET_P4_PROJECT_VER_OVERRIDE}")
endif()
set(PET_P4_UART_BAUD 4000000)
if(DEFINED ENV{PET_P4_UART_BAUD_OVERRIDE} AND NOT "$ENV{PET_P4_UART_BAUD_OVERRIDE}" STREQUAL "")
  set(PET_P4_UART_BAUD "$ENV{PET_P4_UART_BAUD_OVERRIDE}")
endif()
set(PET_P4_PROTOCOL_SCHEMA 7)
set(PET_P4_GIT_SHA "unknown")
set(PET_P4_BUILD_DIRTY 0)
find_program(PET_P4_GIT_EXECUTABLE git)
if(PET_P4_GIT_EXECUTABLE)
  execute_process(
    COMMAND ${PET_P4_GIT_EXECUTABLE} -C ${CMAKE_CURRENT_LIST_DIR} rev-parse --short=12 HEAD
    RESULT_VARIABLE PET_P4_GIT_SHA_RESULT
    OUTPUT_VARIABLE PET_P4_GIT_SHA_OUTPUT
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(PET_P4_GIT_SHA_RESULT EQUAL 0 AND NOT PET_P4_GIT_SHA_OUTPUT STREQUAL "")
    set(PET_P4_GIT_SHA "${PET_P4_GIT_SHA_OUTPUT}")
  endif()
  execute_process(
    COMMAND ${PET_P4_GIT_EXECUTABLE} -C ${CMAKE_CURRENT_LIST_DIR} status --porcelain --untracked-files=normal
    RESULT_VARIABLE PET_P4_GIT_STATUS_RESULT
    OUTPUT_VARIABLE PET_P4_GIT_STATUS_OUTPUT
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(PET_P4_GIT_STATUS_RESULT EQUAL 0 AND NOT PET_P4_GIT_STATUS_OUTPUT STREQUAL "")
    set(PET_P4_BUILD_DIRTY 1)
  endif()
endif()
set(PET_P4_BUILD_ID "${PROJECT_VER}+${PET_P4_GIT_SHA}")
if(PET_P4_BUILD_DIRTY)
  string(APPEND PET_P4_BUILD_ID "-dirty")
endif()
message(STATUS "P4 build identity: ${PET_P4_BUILD_ID}, protocol schema ${PET_P4_PROTOCOL_SCHEMA}, UART ${PET_P4_UART_BAUD}")
if(PET_BUILD_S3)
  project(pet_manager_s3_runtime)
else()
  project(pet_manager_p4_runtime)
endif()
