# test_hardware.py
# Interactive hardware test for all sensors and the speaker.
#
# Controls (during any test):
#   SPACE  — trigger test action (snapshot / play sound)
#   N      — move to next sensor
#   Q      — quit

import sys
import select
import time
from machine import TouchPad, ADC, DAC, Pin
import config

# ---------------------------------------------------------------------------
# Hardware init
# ---------------------------------------------------------------------------

_touch_phone = TouchPad(Pin(config.PIN_TOUCH_PHONE))   # GPIO32 / T9
_touch_btn   = TouchPad(Pin(config.PIN_BTN))            # GPIO15 / T3

_fsr = ADC(Pin(config.PIN_FSR))                         # GPIO34
_fsr.atten(ADC.ATTN_11DB)
_fsr.width(ADC.WIDTH_12BIT)

_dac = DAC(Pin(config.PIN_DAC))                         # GPIO26
_dac.write(128)

# ---------------------------------------------------------------------------
# Keyboard helper
# ---------------------------------------------------------------------------

_poll = select.poll()
_poll.register(sys.stdin, select.POLLIN)

def read_key():
    if _poll.poll(0):
        return sys.stdin.read(1).lower()
    return None

# ---------------------------------------------------------------------------
# Audio helpers (local — does not import audio.py to stay self-contained)
# ---------------------------------------------------------------------------

def _play_tone(freq_hz, duration_ms, volume=0.6):
    amp            = int(127 * volume)
    high           = 128 + amp
    low            = 128 - amp
    half_period_us = 500_000 // freq_hz
    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    state = True
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        _dac.write(high if state else low)
        state = not state
        time.sleep_us(half_period_us)
    _dac.write(128)

def _play_beep(volume):
    _play_tone(880, 250, volume)
    _play_tone(440, 250, volume)

def _play_startup():
    for freq in (440, 660, 880):
        _play_tone(freq, 150, 0.6)

def _play_shutdown():
    for freq in (880, 660, 440):
        _play_tone(freq, 150, 0.6)

# ---------------------------------------------------------------------------
# Test functions — each returns 'n' (next) or 'q' (quit)
# ---------------------------------------------------------------------------

def test_touch_phone():
    print("\n" + "=" * 44)
    print("  TEST 1 — Phone Capacitive Touch (GPIO32)")
    print("=" * 44)
    print(f"  Threshold : {config.TOUCH_THRESHOLD}  (lower = detected)")
    print("  Place phone on pad — watch value drop")
    print("  SPACE = snapshot | N = next | Q = quit\n")

    last_tick = time.ticks_ms()
    while True:
        key = read_key()
        if key == 'q':
            return 'q'
        if key == 'n':
            return 'n'

        val      = _touch_phone.read()
        detected = val < config.TOUCH_THRESHOLD

        if time.ticks_diff(time.ticks_ms(), last_tick) >= 300:
            label = "<<< PHONE DETECTED" if detected else "              "
            print("  touch = {:>5}   {}".format(val, label), end='\r')
            last_tick = time.ticks_ms()

        if key == ' ':
            label = "DETECTED" if detected else "not detected"
            print("\n  [SNAPSHOT]  touch = {}   ({})".format(val, label))

        time.sleep_ms(50)


def test_fsr():
    print("\n" + "=" * 44)
    print("  TEST 2 — FSR Pressure Sensor (GPIO34)")
    print("=" * 44)
    print(f"  Threshold : {config.FSR_THRESHOLD}  (higher = weight detected)")
    print("  Place phone / object on sensor — watch value rise")
    print("  SPACE = snapshot | N = next | Q = quit\n")

    last_tick = time.ticks_ms()
    while True:
        key = read_key()
        if key == 'q':
            return 'q'
        if key == 'n':
            return 'n'

        val      = sum(_fsr.read() for _ in range(3)) // 3
        detected = val > config.FSR_THRESHOLD

        if time.ticks_diff(time.ticks_ms(), last_tick) >= 300:
            label = "<<< WEIGHT DETECTED" if detected else "               "
            print("  fsr   = {:>5}   {}".format(val, label), end='\r')
            last_tick = time.ticks_ms()

        if key == ' ':
            label = "DETECTED" if detected else "not detected"
            print("\n  [SNAPSHOT]  fsr = {}   ({})".format(val, label))

        time.sleep_ms(50)


def test_button():
    print("\n" + "=" * 44)
    print("  TEST 3 — Power Button Touch (GPIO15)")
    print("=" * 44)
    print(f"  Threshold : {config.BTN_THRESHOLD}  (lower = finger held)")
    print("  Hold finger on back button pad — watch value drop")
    print("  SPACE = snapshot | N = next | Q = quit\n")

    last_tick = time.ticks_ms()
    while True:
        key = read_key()
        if key == 'q':
            return 'q'
        if key == 'n':
            return 'n'

        val      = _touch_btn.read()
        detected = val < config.BTN_THRESHOLD

        if time.ticks_diff(time.ticks_ms(), last_tick) >= 300:
            label = "<<< BUTTON HELD" if detected else "             "
            print("  btn   = {:>5}   {}".format(val, label), end='\r')
            last_tick = time.ticks_ms()

        if key == ' ':
            label = "HELD" if detected else "not held"
            print("\n  [SNAPSHOT]  btn = {}   ({})".format(val, label))

        time.sleep_ms(50)


def test_speaker():
    SOUNDS = [
        ("Alarm beep  — LOW  (30%)",  lambda: _play_beep(0.30)),
        ("Alarm beep  — MED  (65%)",  lambda: _play_beep(0.65)),
        ("Alarm beep  — HIGH (100%)", lambda: _play_beep(1.00)),
        ("Startup chime",             _play_startup),
        ("Shutdown chime",            _play_shutdown),
    ]
    idx = [0]   # list so the lambda can mutate it

    def show_prompt():
        print("\n  SPACE will play: {}".format(SOUNDS[idx[0]][0]))
        print("  (press SPACE again to cycle to next sound)")

    print("\n" + "=" * 44)
    print("  TEST 4 — Speaker (GPIO26 → PAM8302)")
    print("=" * 44)
    print("  SPACE = play sound / cycle | N = next | Q = quit")
    show_prompt()

    while True:
        key = read_key()
        if key == 'q':
            _dac.write(128)
            return 'q'
        if key == 'n':
            _dac.write(128)
            return 'n'

        if key == ' ':
            name, fn = SOUNDS[idx[0]]
            print("\n  Playing: {}...".format(name))
            fn()
            idx[0] = (idx[0] + 1) % len(SOUNDS)
            show_prompt()

        time.sleep_ms(50)

# ---------------------------------------------------------------------------
# Main — menu then sequential tests
# ---------------------------------------------------------------------------

TESTS = [
    ("Phone Capacitive Touch  (GPIO32 / T9)", test_touch_phone),
    ("FSR Pressure Sensor     (GPIO34)",      test_fsr),
    ("Power Button Touch      (GPIO15 / T3)", test_button),
    ("Speaker                 (GPIO26 / DAC)",test_speaker),
]

def show_menu():
    print("\n" + "=" * 44)
    print("  Hardware Test — Select a sensor")
    print("=" * 44)
    for i, (name, _) in enumerate(TESTS):
        print("  {}. {}".format(i + 1, name))
    print("\n  Enter 1–{} to begin, Q to quit: ".format(len(TESTS)), end="")

def run():
    print("Behavioral Conditioning Device — Hardware Test")
    idx = 0   # current test index

    while True:
        show_menu()
        # Block here until a valid key is pressed
        while True:
            key = read_key()
            if key == 'q':
                print("q\nExiting.")
                _dac.write(128)
                return
            if key in [str(i + 1) for i in range(len(TESTS))]:
                idx = int(key) - 1
                print(key)
                break
            time.sleep_ms(50)

        # Run tests sequentially from the chosen starting point
        while idx < len(TESTS):
            _, fn = TESTS[idx]
            result = fn()
            if result == 'q':
                print("\nExiting.")
                _dac.write(128)
                return
            # result == 'n' → advance to next test
            idx += 1
            if idx >= len(TESTS):
                print("\n\nAll tests complete.")
                break   # loop back to menu

run()
