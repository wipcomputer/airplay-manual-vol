#include "encoder.h"

#include "driver/gpio.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#define MAX_KNOBS 3
#define DEBOUNCE_US 5000

typedef struct {
    int a, b, sw;
    uint8_t state;      // last A/B as 2 bits
    int8_t acc;         // quadrature steps toward the next detent
    int sw_level;
    int64_t sw_changed;
} knob_pins_t;

static knob_pins_t knobs[MAX_KNOBS];
static int knob_count;
static QueueHandle_t queue;

// Quadrature table: index = (old << 2) | new, value = step direction
static const int8_t QDEC[16] = { 0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0 };

static void IRAM_ATTR on_edge(void *arg)
{
    int k = (int)arg;
    knob_pins_t *p = &knobs[k];
    BaseType_t woke = pdFALSE;
    uint8_t now = (gpio_get_level(p->a) << 1) | gpio_get_level(p->b);
    if (now != p->state) {
        p->acc += QDEC[(p->state << 2) | now];
        p->state = now;
        if (p->acc >= CONFIG_WVP_ENC_STEPS_PER_DETENT || p->acc <= -CONFIG_WVP_ENC_STEPS_PER_DETENT) {
            enc_event_t ev = { .type = ENC_TURN, .knob = k, .value = p->acc > 0 ? 1 : -1 };
            p->acc = 0;
            xQueueSendFromISR(queue, &ev, &woke);
        }
    }
    int sw = gpio_get_level(p->sw);
    int64_t t = esp_timer_get_time();
    if (sw != p->sw_level && t - p->sw_changed > DEBOUNCE_US) {
        p->sw_level = sw;
        p->sw_changed = t;
        enc_event_t ev = { .type = sw == 0 ? ENC_PRESS : ENC_RELEASE, .knob = k };   // switch pulls to GND
        xQueueSendFromISR(queue, &ev, &woke);
    }
    if (woke) portYIELD_FROM_ISR();
}

QueueHandle_t encoder_init(int count)
{
    const int pins[MAX_KNOBS][3] = {
        { CONFIG_WVP_ENC1_A, CONFIG_WVP_ENC1_B, CONFIG_WVP_ENC1_SW },
        { CONFIG_WVP_ENC2_A, CONFIG_WVP_ENC2_B, CONFIG_WVP_ENC2_SW },
        { CONFIG_WVP_ENC3_A, CONFIG_WVP_ENC3_B, CONFIG_WVP_ENC3_SW },
    };
    knob_count = count > MAX_KNOBS ? MAX_KNOBS : count;
    queue = xQueueCreate(32, sizeof(enc_event_t));
    gpio_install_isr_service(0);
    for (int k = 0; k < knob_count; k++) {
        knob_pins_t *p = &knobs[k];
        p->a = pins[k][0]; p->b = pins[k][1]; p->sw = pins[k][2];
        gpio_config_t io = {
            .pin_bit_mask = (1ULL << p->a) | (1ULL << p->b) | (1ULL << p->sw),
            .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE, .intr_type = GPIO_INTR_ANYEDGE,
        };
        gpio_config(&io);
        p->state = (gpio_get_level(p->a) << 1) | gpio_get_level(p->b);
        p->sw_level = gpio_get_level(p->sw);
        gpio_isr_handler_add(p->a, on_edge, (void *)k);
        gpio_isr_handler_add(p->b, on_edge, (void *)k);
        gpio_isr_handler_add(p->sw, on_edge, (void *)k);
    }
    return queue;
}
