/* Button gestures: debounce, short press, hold, double press ([button]). */
#include <unity.h>

#include "umi/core/button.h"
#include "umi/protocol_gen.h"

static umi_button_t b;

void setUp(void)
{
    umi_button_init(&b);
}

void tearDown(void) {}

/* Ticks every 10 ms like the application, up to and including until_ms. */
static void run_until(uint32_t from_ms, uint32_t until_ms)
{
    for (uint32_t t = from_ms; t <= until_ms; t += 10) {
        umi_button_tick(&b, t);
    }
}

static void press(uint32_t t_ms, uint32_t hold_ms)
{
    umi_button_edge(&b, t_ms, true);
    run_until(t_ms, t_ms + hold_ms - 1);
    umi_button_edge(&b, t_ms + hold_ms, false);
}

static void expect(umi_gesture_kind_t kind, uint32_t t_ms)
{
    umi_gesture_t g;
    TEST_ASSERT_TRUE_MESSAGE(umi_button_next(&b, &g), "a gesture was expected");
    TEST_ASSERT_EQUAL_INT(kind, g.kind);
    TEST_ASSERT_EQUAL_UINT32(t_ms, g.t_ms);
}

static void expect_none(void)
{
    umi_gesture_t g;
    TEST_ASSERT_FALSE_MESSAGE(umi_button_next(&b, &g), "no gesture was expected");
}

static void test_short_press_is_reported_after_the_double_press_gap(void)
{
    press(1000, 150);
    run_until(1150, 1150 + UMI_BUTTON_DOUBLE_PRESS_GAP_MS);
    expect(UMI_GESTURE_DOWN, 1000);
    expect_none();
    run_until(1500, 1600);
    expect(UMI_GESTURE_SHORT, 1000);
    expect_none();
}

static void test_bounces_are_one_press(void)
{
    umi_button_edge(&b, 1000, true);
    umi_button_edge(&b, 1003, false);
    umi_button_edge(&b, 1006, true);
    run_until(1010, 1170);
    umi_button_edge(&b, 1180, false);
    umi_button_edge(&b, 1182, true);
    umi_button_edge(&b, 1185, false);
    run_until(1190, 2000);
    expect(UMI_GESTURE_DOWN, 1006);
    expect(UMI_GESTURE_SHORT, 1006);
    expect_none();
}

static void test_glitch_shorter_than_debounce_is_ignored(void)
{
    umi_button_edge(&b, 1000, true);
    umi_button_edge(&b, 1000 + UMI_BUTTON_DEBOUNCE_MS - 5, false);
    run_until(1000, 3000);
    expect_none();
}

static void test_hold_fires_while_held(void)
{
    umi_button_edge(&b, 1000, true);
    run_until(1000, 1000 + UMI_BUTTON_HOLD_MS - 10);
    expect(UMI_GESTURE_DOWN, 1000);
    expect_none();
    run_until(2000, 2000);
    expect(UMI_GESTURE_HOLD, 1000);
    /* Releasing later adds nothing. */
    umi_button_edge(&b, 2600, false);
    run_until(2600, 4000);
    expect_none();
}

static void test_double_press_undoes_instead_of_flagging(void)
{
    press(1000, 120);
    run_until(1120, 1290);
    press(1300, 120);
    run_until(1420, 3000);
    expect(UMI_GESTURE_DOWN, 1000);
    expect(UMI_GESTURE_DOUBLE, 1000);
    expect_none();
}

static void test_second_press_after_the_gap_is_a_new_gesture(void)
{
    press(1000, 100);
    run_until(1100, 1100 + UMI_BUTTON_DOUBLE_PRESS_GAP_MS + 50);
    press(1100 + UMI_BUTTON_DOUBLE_PRESS_GAP_MS + 60, 100);
    run_until(1700, 3000);
    expect(UMI_GESTURE_DOWN, 1000);
    expect(UMI_GESTURE_SHORT, 1000);
    expect(UMI_GESTURE_DOWN, 1510);
    expect(UMI_GESTURE_SHORT, 1510);
}

static void test_release_being_debounced_at_hold_time_is_a_short_press(void)
{
    /* Released 5 ms before hold_ms: the release is only confirmed after it. */
    umi_button_edge(&b, 1000, true);
    run_until(1000, 1990);
    umi_button_edge(&b, 1995, false);
    run_until(2000, 3000);
    expect(UMI_GESTURE_DOWN, 1000);
    expect(UMI_GESTURE_SHORT, 1000);
    expect_none();
}

static void test_second_press_being_debounced_at_gap_end_is_a_double(void)
{
    press(1000, 100);
    run_until(1100, 1440);
    umi_button_edge(&b, 1445, true); /* within the gap, confirmed only at 1475 */
    run_until(1450, 1600);
    umi_button_edge(&b, 1600, false);
    run_until(1600, 2500);
    expect(UMI_GESTURE_DOWN, 1000);
    expect(UMI_GESTURE_DOUBLE, 1000);
    expect_none();
}

static void test_edges_decide_expired_timers_in_order(void)
{
    /* No tick between the press and a release well after hold_ms: the hold
     * must still be decided before the release is applied. */
    umi_button_edge(&b, 1000, true);
    umi_button_edge(&b, 2500, false);
    run_until(2500, 3500);
    expect(UMI_GESTURE_DOWN, 1000);
    expect(UMI_GESTURE_HOLD, 1000);
    expect_none();
}

static void test_pending_since_covers_undecided_gestures(void)
{
    uint32_t t;
    TEST_ASSERT_FALSE(umi_button_pending_since(&b, &t));
    umi_button_edge(&b, 1000, true);
    TEST_ASSERT_TRUE(umi_button_pending_since(&b, &t));
    TEST_ASSERT_EQUAL_UINT32(1000, t);
    run_until(1000, 1100);
    umi_button_edge(&b, 1100, false);
    run_until(1100, 1300);
    TEST_ASSERT_TRUE(umi_button_pending_since(&b, &t));
    TEST_ASSERT_EQUAL_UINT32(1000, t);
    run_until(1300, 1600);
    TEST_ASSERT_FALSE(umi_button_pending_since(&b, &t));
}

static void test_times_survive_the_u32_wrap(void)
{
    uint32_t start = UINT32_MAX - 100;
    umi_button_edge(&b, start, true);
    for (uint32_t i = 0; i < 1200; i += 10) {
        umi_button_tick(&b, start + i);
    }
    expect(UMI_GESTURE_DOWN, start);
    expect(UMI_GESTURE_HOLD, start);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_short_press_is_reported_after_the_double_press_gap);
    RUN_TEST(test_bounces_are_one_press);
    RUN_TEST(test_glitch_shorter_than_debounce_is_ignored);
    RUN_TEST(test_hold_fires_while_held);
    RUN_TEST(test_double_press_undoes_instead_of_flagging);
    RUN_TEST(test_second_press_after_the_gap_is_a_new_gesture);
    RUN_TEST(test_release_being_debounced_at_hold_time_is_a_short_press);
    RUN_TEST(test_second_press_being_debounced_at_gap_end_is_a_double);
    RUN_TEST(test_edges_decide_expired_timers_in_order);
    RUN_TEST(test_pending_since_covers_undecided_gestures);
    RUN_TEST(test_times_survive_the_u32_wrap);
    return UNITY_END();
}
