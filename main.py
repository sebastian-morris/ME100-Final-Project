# main.py — 8-state machine:
#   OFF → STARTING → WAITING → IDLE → GRACE → ALARM → LOG → STOPPING → OFF

import time
import network
from machine import Pin
import config
import sensors
import audio
import notifications

# ---------------------------------------------------------------------------
# Stub — replace when data_logger.py is written
# ---------------------------------------------------------------------------

def log_session(duration_s, pickup_count, max_level):
    # TODO: implement in data_logger.py (Google Sheets via Apps Script)
    print("[data_logger] duration={}s  pickups={}  max_level={}".format(
        duration_s, pickup_count, max_level))

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

OFF      = "OFF"
STARTING = "STARTING"
WAITING  = "WAITING"
IDLE     = "IDLE"
GRACE    = "GRACE"
ALARM    = "ALARM"
LOG      = "LOG"
STOPPING = "STOPPING"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_led = Pin(config.PIN_LED, Pin.OUT)

def _led_on():   _led.value(1)
def _led_off():  _led.value(0)

def _blink(times, on_ms=80, off_ms=80):
    for _ in range(times):
        _led_on();  time.sleep_ms(on_ms)
        _led_off(); time.sleep_ms(off_ms)

def _elapsed_s(start_ticks):
    return time.ticks_diff(time.ticks_ms(), start_ticks) // 1000

def _alarm_level(elapsed_s):
    """Return (level 1–3, volume) based on seconds since phone was removed."""
    grace = config.GRACE_PERIOD
    step  = config.ESCALATION_INTERVAL
    if elapsed_s < grace + step:
        return 1, config.VOLUME_LOW
    elif elapsed_s < grace + 2 * step:
        return 2, config.VOLUME_MED
    else:
        return 3, config.VOLUME_HIGH

def _connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return
    print("Connecting to WiFi...")
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep_ms(500)
    if wlan.isconnected():
        print("WiFi connected —", wlan.ifconfig()[0])
    else:
        print("WiFi failed — notifications unavailable")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    state              = OFF
    session_start_ticks = 0
    removal_ticks      = 0
    pickup_count       = 0
    alert_count        = 0
    max_level          = 0

    print("Behavioral Conditioning Device — ready (OFF)")
    audio.silence()
    _led_off()

    while True:

        # ── OFF ─────────────────────────────────────────────────────────────
        if state == OFF:
            if sensors.check_button_hold(config.POWER_ON_HOLD_MS):
                print("Button held 2s → STARTING")
                state = STARTING
            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── STARTING ────────────────────────────────────────────────────────
        elif state == STARTING:
            _blink(3)
            audio.play_startup_chime()
            _connect_wifi()
            notifications.send_session_start()
            session_start_ticks = time.ticks_ms()
            pickup_count  = 0
            alert_count   = 0
            max_level     = 0
            print("Session started → WAITING")
            state = WAITING

        # ── WAITING ─────────────────────────────────────────────────────────
        elif state == WAITING:
            _led_on()
            time.sleep_ms(500)
            _led_off()
            time.sleep_ms(500)
            if sensors.phone_present():
                print("Phone detected → IDLE")
                _led_on()
                state = IDLE

        # ── IDLE ────────────────────────────────────────────────────────────
        elif state == IDLE:
            _led_on()
            if not sensors.phone_present():
                print("Phone removed → GRACE")
                removal_ticks  = time.ticks_ms()
                pickup_count  += 1
                alert_count    = 0
                max_level      = 0
                notifications.send_first_warning()
                state = GRACE
            elif sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
                print("Button held 5s → STOPPING")
                state = STOPPING
            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── GRACE ───────────────────────────────────────────────────────────
        elif state == GRACE:
            _led_off()
            if sensors.phone_present():
                print("Phone returned during grace → IDLE")
                notifications.reset_cooldown()
                state = IDLE
            elif _elapsed_s(removal_ticks) >= config.GRACE_PERIOD:
                print("Grace expired → ALARM level 1")
                state = ALARM
            elif sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
                # 5s hold attempted while phone is off the pad — blocked
                print("Button hold blocked — phone not on device")
                notifications.send_btn_blocked()
            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── ALARM ───────────────────────────────────────────────────────────
        elif state == ALARM:
            elapsed = _elapsed_s(removal_ticks)
            level, volume = _alarm_level(elapsed)

            if level > max_level:
                max_level    = level
                alert_count += 1
                print("Alarm level {} — {}%".format(level, int(volume * 100)))

            # Check sensors before each beep — max response latency ~500 ms
            if sensors.phone_present():
                print("Phone returned → LOG")
                audio.silence()
                notifications.reset_cooldown()
                state = LOG
            else:
                audio.play_beep(volume)   # blocks ~500 ms

        # ── LOG ─────────────────────────────────────────────────────────────
        elif state == LOG:
            _led_on()
            duration_s = _elapsed_s(removal_ticks)
            log_session(duration_s, alert_count, max_level)
            print("Alarm log: {}s, {} escalation(s), max level {}".format(
                duration_s, alert_count, max_level))
            time.sleep_ms(1000)
            state = IDLE

        # ── STOPPING ────────────────────────────────────────────────────────
        elif state == STOPPING:
            _blink(3)
            audio.play_shutdown_chime()
            duration_s = _elapsed_s(session_start_ticks)
            notifications.send_session_end(duration_s, pickup_count)
            log_session(duration_s, pickup_count, max_level)
            print("Session ended — {}s, {} pickup(s)".format(duration_s, pickup_count))
            _led_off()
            state = OFF


# Run immediately when the file is executed in Thonny
run()
