idf_component_register(
    SRCS "main.c" "board.c" "encoder.c" "wifi.c" "panel.c" "ui.c" "lock.c"
         "drivers/device.c" "drivers/sonos.c" "drivers/syng.c" "drivers/huum.c"
    INCLUDE_DIRS "." "drivers"
    REQUIRES esp_lcd esp_driver_spi esp_driver_i2c esp_driver_gpio esp_wifi esp_netif
             esp_event nvs_flash esp_http_client esp-tls json esp_timer mbedtls esp_http_server)
