# Target-only application: tasks and wiring. Everything else is in lib/,
# built by PlatformIO. The devkit env passes UMI_SIM_SCENARIO
# (board_build.cmake_extra_args) to embed the scenario its sensors replay.
if(DEFINED UMI_SIM_SCENARIO)
    set(scenario EMBED_TXTFILES ${CMAKE_SOURCE_DIR}/${UMI_SIM_SCENARIO})
endif()

idf_component_register(
    SRCS main.c ble.c
    INCLUDE_DIRS .
    PRIV_REQUIRES bt nvs_flash esp_timer esp_hw_support esp_driver_gpio esp_driver_i2c
                  esp_driver_i2s esp_driver_ledc esp_driver_rmt esp_driver_tsens esp_driver_uart
                  fatfs wear_levelling vfs mbedtls
    ${scenario})
