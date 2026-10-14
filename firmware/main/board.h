// Board bring-up: display (ST7789 over SPI), touch (CST816 over I2C), backlight,
// and LVGL on top. Pins come from menuconfig (Wall Volume Panel → Pins).
#pragma once

#include "lvgl.h"

#define LCD_H_RES 170
#define LCD_V_RES 320

// Starts the display, touch and LVGL. Returns the LVGL display.
lv_display_t *board_init(void);

// Backlight 0-100 %
void board_backlight(int percent);
