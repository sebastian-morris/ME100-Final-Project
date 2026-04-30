# main.py — Behavioral Conditioning Device
# State machine: OFF → STARTING → WAITING → IDLE → GRACE → ALARM → LOG → STOPPING → OFF

import time
import network
from machine import Pin
import config
import sensors
import audio
import notifications

# ---------------------------------------------------------------------------
# data_logger stub — replace when data_logger.py is written
# ---------------------------------------------------------------------------

def log_session(duration_s, pickup_count, max_level):
    # TODO: replace with data_logger.log_session() once that module is written
    print("[data_logger] duration={}s  pickups={}  max_level={}".format(
        duration_s, pickup_count, max_level))

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

OFF      = "OFF"
STARTING = "STARTING"
WAITING  = "WAITING"
IDLE     = "IDLE"
GRACE    = "GRACE"     # 0–30 s: silent window, one notification sent on entry
WARN     = "WARN"      # 30–35 s: quiet beep + kind notification sent on entry
ALARM    = "ALARM"     # 35 s+: loud repeating beep + spam notifications
LOG      = "LOG"
STOPPING = "STOPPING"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_led = Pin(config.PIN_LED, Pin.OUT)

def _led_on():  _led.value(1)
def _led_off(): _led.value(0)

def _blink(times, on_ms=80, off_ms=80):
    for _ in range(times):
        _led_on();  time.sleep_ms(on_ms)
        _led_off(); time.sleep_ms(off_ms)

def _elapsed_s(start_ticks):
    return time.ticks_diff(time.ticks_ms(), start_ticks) // 1000

def _alarm_level(elapsed_alarm_s):
    """Return (level 1–3, volume) based on seconds since ALARM state was entered."""
    step = config.ESCALATION_INTERVAL
    if elapsed_alarm_s < step:
        return 1, config.VOLUME_LOW
    elif elapsed_alarm_s < 2 * step:
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
    for _ in range(20):                 # 10-second timeout
        if wlan.isconnected():
            break
        time.sleep_ms(500)
    if wlan.isconnected():
        print("WiFi connected —", wlan.ifconfig()[0])
    else:
        print("WiFi failed — notifications unavailable this session")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    state                  = OFF
    session_start_ticks    = 0   # set once in STARTING; base for full session duration
    removal_ticks          = 0   # set each GRACE entry; base for grace/warn/alarm timing
    alarm_start_ticks      = 0   # set when ALARM entered; base for escalation schedule
    last_alarm_notify_ticks = 0  # tracks when last spam notification was sent
    pickup_count           = 0   # total phone removals this session
    total_phone_off_s      = 0   # total seconds phone was off the device this session
    alert_count            = 0   # alarm escalations this removal (resets each GRACE entry)
    max_level              = 0   # highest alarm level this removal (resets each GRACE entry)
    session_max_level      = 0   # highest alarm level reached across whole session

    print("Behavioral Conditioning Device — OFF")
    audio.silence()
    _led_off()

    while True:

        # ── OFF ─────────────────────────────────────────────────────────────
        # Device inactive. Poll button every 50 ms. 2s hold → STARTING.
        if state == OFF:
            if sensors.check_button_hold(config.POWER_ON_HOLD_MS):
                print("Button held 2s → STARTING")
                state = STARTING
            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── STARTING ────────────────────────────────────────────────────────
        # Chime, WiFi, session-start notification, then auto-calibrate both
        # sensors while the phone is still off the pad.
        elif state == STARTING:
            _blink(3)
            audio.play_startup_chime()
            _connect_wifi()
            notifications.send_session_start()
            sensors.calibrate_baseline()   # touch threshold + FSR baseline (no phone)
            session_start_ticks = time.ticks_ms()
            pickup_count      = 0
            alert_count       = 0
            max_level         = 0
            session_max_level = 0
            print("Session started → WAITING (place phone on pad)")
            state = WAITING

        # ── WAITING ─────────────────────────────────────────────────────────
        # Blink LED 1 Hz. Use touch-only detection (FSR not calibrated yet).
        # The moment touch confirms placement, calibrate FSR with phone present,
        # then arm the device.
        elif state == WAITING:
            _led_on();  time.sleep_ms(500)
            _led_off(); time.sleep_ms(500)
            if sensors.touch_detected():
                sensors.calibrate_with_phone()   # FSR threshold (phone on pad)
                print("Phone detected, sensors calibrated → IDLE")
                _led_on()
                state = IDLE

        # ── IDLE ────────────────────────────────────────────────────────────
        # Phone is on pad. Fast raw check every 50 ms keeps button hold detection
        # precise. Full time-averaged phone_present() is only called when the quick
        # check suggests the phone may have been removed (avoids 1-2 s blocking
        # in the normal steady-state loop).
        elif state == IDLE:
            _led_on()

            # Quick instantaneous read — non-blocking
            touch_raw = sensors.read_touch_phone()
            fsr_raw   = sensors.read_fsr()
            possibly_gone = (touch_raw > config.TOUCH_THRESHOLD or
                             fsr_raw < config.FSR_THRESHOLD)

            if possibly_gone and not sensors.phone_present():
                # Confirmed absent over 2-second averaged window
                print("Phone removed → GRACE (pickup #{})".format(pickup_count + 1))
                removal_ticks  = time.ticks_ms()
                pickup_count  += 1
                alert_count    = 0
                max_level      = 0
                notifications.send_first_warning()
                state = GRACE

            elif sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
                # Phone confirmed present (quick check passed) — clean shutdown allowed
                print("Button held 5s → STOPPING")
                state = STOPPING

            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── GRACE ───────────────────────────────────────────────────────────
        # 0–30 s silent window. ONE notification was sent on entry (in IDLE).
        # Phone returned → IDLE. Grace expires → WARN.
        elif state == GRACE:
            _led_off()

            if sensors.phone_present():
                total_phone_off_s += _elapsed_s(removal_ticks)
                print("Phone returned during grace → IDLE")
                notifications.reset_cooldown()
                state = IDLE

            elif _elapsed_s(removal_ticks) >= config.GRACE_PERIOD:
                # Grace over: play one quiet beep and send one kind notification
                print("Grace expired → WARN")
                audio.play_quiet_beep()
                notifications.send_gentle_reminder()
                state = WARN

            elif sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
                print("Button hold blocked — put phone on device first")
                notifications.send_btn_blocked()

            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── WARN ────────────────────────────────────────────────────────────
        # 30–35 s window after quiet-beep warning. No audio. Waiting for
        # phone return or 5s to elapse before full alarm starts.
        elif state == WARN:
            _led_off()

            if sensors.phone_present():
                print("Phone returned during warning → IDLE")
                notifications.reset_cooldown()
                state = IDLE

            elif _elapsed_s(removal_ticks) >= config.GRACE_PERIOD + config.WARN_DURATION:
                # 5 s warning window over — start full alarm
                print("Warning expired → ALARM")
                alarm_start_ticks       = time.ticks_ms()
                last_alarm_notify_ticks = alarm_start_ticks
                notifications.send_alarm_spam()   # first spam fires immediately on alarm entry
                state = ALARM

            elif sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
                print("Button hold blocked — put phone on device first")
                notifications.send_btn_blocked()

            else:
                time.sleep_ms(config.BTN_POLL_MS)

        # ── ALARM ───────────────────────────────────────────────────────────
        # Full alarm: escalating two-tone beep + spam notifications every
        # ALARM_NOTIFY_INTERVAL seconds. Escalation is timed from alarm_start_ticks.
        elif state == ALARM:
            elapsed_alarm = _elapsed_s(alarm_start_ticks)
            level, volume = _alarm_level(elapsed_alarm)

            if level > max_level:
                max_level = level
                if level > session_max_level:
                    session_max_level = level
                alert_count += 1
                print("Alarm level {} — {}%".format(level, int(volume * 100)))

            # Spam notification on interval
            if time.ticks_diff(time.ticks_ms(), last_alarm_notify_ticks) >= config.ALARM_NOTIFY_INTERVAL * 1000:
                notifications.send_alarm_spam()
                last_alarm_notify_ticks = time.ticks_ms()

            if sensors.phone_present():
                print("Phone returned → LOG")
                audio.silence()
                notifications.reset_cooldown()
                state = LOG
            else:
                audio.play_beep(volume)     # blocks ~500 ms

        # ── LOG ─────────────────────────────────────────────────────────────
        # Phone returned from ALARM. Log this alarm event, then resume IDLE.
        elif state == LOG:
            _led_on()
            event_duration_s   = _elapsed_s(removal_ticks)
            total_phone_off_s += event_duration_s
            log_session(event_duration_s, alert_count, max_level)
            print("Alarm event logged — {}s gone, {} escalation(s), level {}".format(
                event_duration_s, alert_count, max_level))
            time.sleep_ms(1000)
            state = IDLE

        # ── STOPPING ────────────────────────────────────────────────────────
        # Session ending. Play shutdown chime, send session summary, log full session.
        elif state == STOPPING:
            _blink(3)
            audio.play_shutdown_chime()
            duration_s = _elapsed_s(session_start_ticks)
            notifications.send_session_end(duration_s, pickup_count, total_phone_off_s)
            log_session(duration_s, pickup_count, session_max_level)
            print("Session ended — {}s total, {} pickup(s), session max level {}".format(
                duration_s, pickup_count, session_max_level))
            _led_off()
            state = OFF


# Run immediately when the file is executed in Thonny
run()
