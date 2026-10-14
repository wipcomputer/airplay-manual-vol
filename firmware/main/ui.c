#include "ui.h"

#include <string.h>
#include "board.h"
#include "encoder.h"
#include "esp_lvgl_port.h"

#define WHITE lv_color_hex(0xFFFFFF)
#define DIM   lv_color_hex(0x4A4A4A)
#define TRACK lv_color_hex(0x2A2A2A)
#define RED   lv_color_hex(0xDC3A2F)

static QueueHandle_t queue;
static lv_obj_t *scr, *name_lbl, *knob_lbl, *num_lbl, *unit_lbl, *bar, *mute, *lock_lbl, *msg_lbl, *ring;

static void post(enc_event_type_t type, int value)
{
    enc_event_t ev = { .type = type, .knob = -1, .value = value };
    xQueueSend(queue, &ev, 0);
}

static void on_screen(lv_event_t *e) { post(TOUCH_WAKE, 0); }
static void on_mute(lv_event_t *e) { post(TOUCH_MUTE, 0); }

static void on_bar(lv_event_t *e)
{
    lv_indev_t *indev = lv_indev_active();
    if (!indev) return;
    lv_point_t p;
    lv_indev_get_point(indev, &p);
    lv_area_t a;
    lv_obj_get_coords(bar, &a);
    int h = lv_area_get_height(&a);
    int level = h > 0 ? (a.y2 - p.y) * 100 / h : 0;
    post(TOUCH_LEVEL, level < 0 ? 0 : level > 100 ? 100 : level);
}

static lv_obj_t *label(lv_obj_t *parent, const lv_font_t *font, lv_color_t color)
{
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, color, 0);
    return l;
}

void ui_init(QueueHandle_t events)
{
    queue = events;
    lvgl_port_lock(0);
    scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x0A0A0A), 0);
    lv_obj_add_event_cb(scr, on_screen, LV_EVENT_PRESSED, NULL);

    name_lbl = label(scr, &lv_font_montserrat_14, lv_color_hex(0xB8B8B8));
    lv_obj_set_style_text_letter_space(name_lbl, 3, 0);
    lv_obj_align(name_lbl, LV_ALIGN_TOP_MID, 0, 28);
    knob_lbl = label(scr, &lv_font_montserrat_14, lv_color_hex(0x808080));
    lv_obj_align(knob_lbl, LV_ALIGN_TOP_MID, 0, 50);

    // Level bar: right of centre, like the mockups; touch to set
    bar = lv_bar_create(scr);
    lv_obj_set_size(bar, 8, 150);
    lv_obj_align(bar, LV_ALIGN_TOP_LEFT, 119, 72);
    lv_bar_set_range(bar, 0, 100);
    lv_obj_set_style_radius(bar, 0, 0);
    lv_obj_set_style_radius(bar, 0, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(bar, TRACK, 0);
    lv_obj_set_style_bg_color(bar, WHITE, LV_PART_INDICATOR);
    lv_obj_set_ext_click_area(bar, 18);
    lv_obj_add_event_cb(bar, on_bar, LV_EVENT_PRESSING, NULL);

    num_lbl = label(scr, &lv_font_montserrat_48, WHITE);
    lv_obj_align(num_lbl, LV_ALIGN_TOP_RIGHT, -60, 172);
    unit_lbl = label(scr, &lv_font_montserrat_20, WHITE);
    lv_obj_align_to(unit_lbl, num_lbl, LV_ALIGN_OUT_RIGHT_TOP, 2, 4);

    // Mute circle
    mute = lv_obj_create(scr);
    lv_obj_set_size(mute, 40, 40);
    lv_obj_align(mute, LV_ALIGN_BOTTOM_MID, 0, -32);
    lv_obj_set_style_radius(mute, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(mute, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_color(mute, WHITE, 0);
    lv_obj_set_style_border_width(mute, 2, 0);
    lv_obj_set_ext_click_area(mute, 14);
    lv_obj_remove_flag(mute, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(mute, on_mute, LV_EVENT_CLICKED, NULL);

    lock_lbl = label(scr, &lv_font_montserrat_14, lv_color_hex(0xB0B0B0));
    lv_label_set_text(lock_lbl, LV_SYMBOL_EYE_CLOSE "\nHOLD KNOB");
    lv_obj_set_style_text_align(lock_lbl, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(lock_lbl, LV_ALIGN_BOTTOM_MID, 0, -28);

    msg_lbl = label(scr, &lv_font_montserrat_14, RED);
    lv_obj_align(msg_lbl, LV_ALIGN_BOTTOM_MID, 0, -40);

    // Hold-to-lock progress, shown across the bottom edge while it fills
    ring = lv_bar_create(scr);
    lv_obj_set_size(ring, LCD_H_RES - 20, 4);
    lv_obj_align(ring, LV_ALIGN_BOTTOM_MID, 0, -8);
    lv_obj_set_style_bg_opa(ring, LV_OPA_TRANSP, 0);
    lv_obj_set_style_bg_color(ring, RED, LV_PART_INDICATOR);
    lvgl_port_unlock();
}

static void show(lv_obj_t *o, bool visible)
{
    if (visible) lv_obj_remove_flag(o, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(o, LV_OBJ_FLAG_HIDDEN);
}

void ui_show(const ui_model_t *m)
{
    lvgl_port_lock(0);
    bool on = m->awake;
    bool dim = m->muted || m->locked || !m->connected;
    bool sw = m->control == CONTROL_SWITCH;

    lv_label_set_text(name_lbl, m->has_device ? m->name : "NO DEVICE");
    lv_label_set_text(knob_lbl, m->knob);
    lv_label_set_text(num_lbl, m->number);
    lv_label_set_text(unit_lbl, m->unit);
    lv_obj_align_to(unit_lbl, num_lbl, LV_ALIGN_OUT_RIGHT_TOP, 2, 4);
    lv_obj_set_style_text_color(num_lbl, dim ? DIM : WHITE, 0);
    lv_bar_set_value(bar, m->muted ? 0 : m->bar, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar, (m->locked || !m->connected) ? lv_color_hex(0x555555) : WHITE, LV_PART_INDICATOR);
    bool red = m->muted && !sw;
    lv_obj_set_style_bg_opa(mute, red ? LV_OPA_COVER : LV_OPA_TRANSP, 0);
    lv_obj_set_style_bg_color(mute, RED, 0);
    lv_obj_set_style_border_color(mute, red ? RED : WHITE, 0);
    lv_label_set_text(msg_lbl, m->has_device && !m->connected ? "NO SPEAKER" : "");
    lv_bar_set_value(ring, m->hold_progress, LV_ANIM_OFF);

    show(name_lbl, on);
    show(knob_lbl, on && m->knob[0]);
    show(num_lbl, on && m->has_device);
    show(unit_lbl, on && m->has_device && m->unit[0]);
    show(bar, on && m->has_device && !sw);
    show(mute, on && m->has_device && !sw && !m->locked && m->connected);
    show(lock_lbl, on && m->locked);
    show(msg_lbl, on && m->has_device && !m->connected);
    show(ring, m->hold_progress > 0);
    lvgl_port_unlock();
    board_backlight(on || m->hold_progress > 0 ? 100 : 0);   // 01 IDLE: dark glass
}
