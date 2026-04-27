# main.py — state machine: WAITING → IDLE → GRACE → ALARM → LOG → IDLE

import time
from machine import Pin
import config
import sensors
import audio

# ---------------------------------------------------------------------------
# Stubs — replace with real implementations once those modules are written
# ---------------------------------------------------------------------------

def send_notification():
    # TODO: implement in notifications.py (ntfy.sh HTTP POST)
    print("[notifications] push sent")

def log_session(duration_s, alert_count, max_level):
    # TODO: implement in data_logger.py (Google Sheets via Apps Script)
    print(f"[data_logger] duration={duration_s}s  alerts={alert_count}  max_level={max_level}")

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

WAITING = "WAITING"   # startup: waiting for phone to be placed
IDLE    = "IDLE"      # phone on pad, all quiet
GRACE   = "GRACE"     # phone just removed, 30-s silent window
ALARM   = "ALARM"     # grace expired, escalating beeps
LOG     = "LOG"       # phone returned, log the session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_led = Pin(config.PIN_LED, Pin.OUT)

def _led_on():  _led.value(1)
def _led_off(): _led.value(0)

def _elapsed_s(start_ticks):
    return time.ticks_diff(time.ticks_ms(), start_ticks) // 1000

def _alarm_level(elapsed_s):
    """Return (level 1–3, volume) based on how long the alarm has been running."""
    grace = config.GRACE_PERIOD
    step  = config.ESCALATION_INTERVAL
    if elapsed_s < grace + step:
        return 1, config.VOLUME_LOW
    elif elapsed_s < grace + 2 * step:
        return 2, config.VOLUME_MED
    else:
        return 3, config.VOLUME_HIGH

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    state         = WAITING
    removal_ticks = 0
    session_ticks = 0
    alert_count   = 0
    max_level     = 0

    print("Behavioral Conditioning Device — starting up")
    audio.silence()
    _led_off()

    while True:

        # ── WAITING ─────────────────────────────────────────────────────────
        if state == WAITING:
            # Blink LED slowly to signal "ready, place phone to begin"
            _led_on()
            time.sleep_ms(500)
            _led_off()
            time.sleep_ms(500)
            if sensors.phone_present():
                print("Phone detected → IDLE")
                state = IDLE

        # ── IDLE ────────────────────────────────────────────────────────────
        elif state == IDLE:
            _led_on()
            if not sensors.phone_present():
                print("Phone removed → GRACE")
                removal_ticks = time.ticks_ms()
                session_ticks = removal_ticks
                alert_count   = 0
                max_level     = 0
                send_notification()
                state = GRACE
            else:
                time.sleep_ms(config.SENSOR_POLL_MS)

        # ── GRACE ───────────────────────────────────────────────────────────
        elif state == GRACE:
            _led_off()
            if sensors.phone_present():
                print("Phone returned during grace → IDLE")
                state = IDLE
            elif _elapsed_s(removal_ticks) >= config.GRACE_PERIOD:
                print("Grace expired → ALARM level 1")
                state = ALARM
            else:
                time.sleep_ms(config.SENSOR_POLL_MS)

        # ── ALARM ───────────────────────────────────────────────────────────
        elif state == ALARM:
            elapsed = _elapsed_s(removal_ticks)
            level, volume = _alarm_level(elapsed)

            # Log each escalation once
            if level > max_level:
                max_level    = level
                alert_count += 1
                print(f"Alarm level {level} — volume {int(volume * 100)}%")

            # Check sensors before each beep so return detection is ~500 ms
            if sensors.phone_present():
                print("Phone returned → LOG")
                audio.silence()
                state = LOG
            else:
                audio.play_beep(volume)   # blocks ~500 ms

        # ── LOG ─────────────────────────────────────────────────────────────
        elif state == LOG:
            _led_on()
            duration_s = _elapsed_s(session_ticks)
            log_session(duration_s, alert_count, max_level)
            print(f"Session complete — {duration_s}s, {alert_count} alert(s), max level {max_level}")
            time.sleep_ms(1000)   # brief pause so LEDs are visible
            state = IDLE


# Run immediately when the file is executed in Thonny
run()
