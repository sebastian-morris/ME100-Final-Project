# Behavioral Conditioning Productivity Device — Code Summary

MicroPython codebase for the Adafruit Huzzah32 ESP32 Feather. Runs in Thonny.

---

## File Structure

```
Final Project/
├── config.py          # All constants: pins, thresholds, timing, volumes, hold times  ✅
├── sensors.py         # Phone touch, FSR, button hold detection                       ✅
├── audio.py           # Alarm beep, startup chime, shutdown chime                     ✅
├── notifications.py   # ntfy.sh push notification wrapper                             ✅
├── main.py            # 8-state machine                                               ✅
├── data_logger.py     # Google Sheets via Apps Script                                 ❌ NOT WRITTEN
└── test files         # test_hardware.py, test_speaker.py, test_capacitance.py, test_notification.py
```

---

## config.py

Single source of truth. All other modules import from here.

| Constant | Default | Description |
|----------|---------|-------------|
| `WIFI_SSID` / `WIFI_PASSWORD` | set | Fill in before first run |
| `NTFY_TOPIC` | `"focus-device-yourname"` | Unique ntfy.sh topic name |
| `NOTIFY_COOLDOWN` | `30` | Min seconds between repeat notifications |
| `PIN_TOUCH_PHONE` | `32` | GPIO32 / T9 — phone capacitive pad (large copper foil) |
| `PIN_FSR` | `34` | GPIO34 / A2 — FSR voltage divider (ADC1, Wi-Fi safe) |
| `PIN_DAC` | `26` | GPIO26 / A0 — DAC2 audio out to PAM8302 |
| `PIN_BTN` | `15` | GPIO15 / T3 — power button touch pad (back of housing) |
| `PIN_LED` | `13` | Onboard red LED |
| `TOUCH_THRESHOLD` | `400` | Phone pad reads **below** this when phone is present |
| `BTN_THRESHOLD` | `400` | Button pad reads **below** this when finger is held |
| `FSR_THRESHOLD` | `1000` | ADC reads **above** this when phone weight detected |
| `POWER_ON_HOLD_MS` | `2000` | Hold duration to turn device ON |
| `POWER_OFF_HOLD_MS` | `5000` | Hold duration to turn device OFF |
| `GRACE_PERIOD` | `30` | Seconds of silence after phone removed |
| `ESCALATION_INTERVAL` | `30` | Seconds between volume steps |
| `VOLUME_LOW/MED/HIGH` | `0.30 / 0.65 / 1.00` | DAC amplitude at each alarm level |
| `TONE_HIGH` / `TONE_LOW` | `880 / 440` Hz | Alarm two-tone frequencies |
| `TONE_DURATION_MS` | `250` | Duration of each alarm tone |
| `CHIME_TONE_MS` | `150` | Duration of each startup/shutdown chime note |
| `SENSOR_POLL_MS` | `100` | Sensor polling interval in WAITING / GRACE |
| `BTN_POLL_MS` | `50` | Button polling interval in OFF / IDLE |

---

## sensors.py

Manages phone presence (dual-sensor) and power button hold detection.

### Hardware

| Sensor | Pin | Detection |
|--------|-----|-----------|
| Phone capacitive pad | GPIO32 (T9) | `read_touch_phone() < TOUCH_THRESHOLD` |
| FSR pressure | GPIO34 (ADC1) | `read_fsr() > FSR_THRESHOLD` |
| Power button pad | GPIO15 (T3) | `read_touch_btn() < BTN_THRESHOLD` |

```
3.3V ──── FSR (DF9-16) ──── GPIO34 ──── 10kΩ ──── GND
```
More pressure → lower FSR resistance → higher voltage at GPIO34 → higher ADC count.

### Functions

**`phone_present() → bool`** — True only when both sensors fire (AND logic prevents spoofing).

**`check_button_hold(required_ms) → bool`** — Non-blocking. Call in a loop at `BTN_POLL_MS` intervals. Returns `True` once the finger has been held continuously for `required_ms`. Resets automatically on finger lift or after firing.

```python
_btn_press_start = None

def check_button_hold(required_ms):
    global _btn_press_start
    touching = read_touch_btn() < config.BTN_THRESHOLD
    now = time.ticks_ms()
    if touching:
        if _btn_press_start is None:
            _btn_press_start = now
        elif time.ticks_diff(now, _btn_press_start) >= required_ms:
            _btn_press_start = None
            return True
    else:
        _btn_press_start = None
    return False
```

**`calibrate()`** — Interactive REPL helper. Measures baselines for all three thresholds (phone touch, FSR, button) and prints suggested values to paste into `config.py`.

---

## audio.py

Square-wave tone generation via DAC2 (GPIO26) → PAM8302 amp → speaker.

### Signal path
```
ESP32 GPIO26 (DAC2) → PAM8302 SIGNAL → 4Ω / 3W speaker
```

### Volume mapping
DAC output is 0–255 (0–3.3 V), centered at 128. Volume scales amplitude symmetrically:

| Volume | amp | DAC high | DAC low |
|--------|-----|----------|---------|
| 30% | 38 | 166 | 90 |
| 65% | 83 | 211 | 45 |
| 100% | 127 | 255 | 1 |

### Functions

| Function | Description |
|----------|-------------|
| `play_beep(volume)` | One alarm cycle: 880 Hz (250 ms) + 440 Hz (250 ms). Blocks ~500 ms. |
| `play_startup_chime()` | Rising: 440 → 660 → 880 Hz, 150 ms each. Called on STARTING. |
| `play_shutdown_chime()` | Falling: 880 → 660 → 440 Hz, 150 ms each. Called on STOPPING. |
| `silence()` | Sets DAC to 128 (midpoint = no AC signal = no sound). |

---

## notifications.py

Sends push notifications via ntfy.sh. Requires active WiFi.

### Notification events

| Function | When called | Priority |
|----------|-------------|----------|
| `send_session_start()` | STARTING state | `default` |
| `send_first_warning()` | GRACE state entry (phone removed) | `high` |
| `send_escalation_warning()` | Optional, during ALARM escalation | `urgent` |
| `send_btn_blocked()` | 5s hold attempted, phone absent | `default` |
| `send_session_end(duration_s, pickups)` | STOPPING state | `default` |
| `reset_cooldown()` | Phone returned to pad | — |

All calls (except `send_session_end`) respect a `NOTIFY_COOLDOWN` guard to prevent spam. `send_session_end` bypasses cooldown — it always fires.

---

## main.py

### Device workflow

#### Starting a session
1. Device is in **OFF** state — no monitoring, no alarms
2. User holds back button **2 seconds** → **STARTING**
3. LED blinks 3×, startup chime plays, WiFi connects, "Session started" notification sent
4. → **WAITING**: LED blinks 1 Hz until phone is placed on pad
5. Both sensors confirm phone → **IDLE**

#### During a session
6. Phone removed → **GRACE**: first-warning notification sent instantly, 30 s silent timer starts
7. Phone returned during grace → back to **IDLE** (no log)
8. Grace expires → **ALARM**: two-tone beep at 30% volume
9. Every 30 s: volume escalates (65% → 100%)
10. Phone returned during alarm → **LOG**: alarm event written to Sheets stub, → **IDLE**

#### Ending a session
11. From **IDLE** only: hold button **5 seconds** (phone MUST be on pad) → **STOPPING**
    - If phone is absent when hold completes: `send_btn_blocked()` fired, state stays
12. Shutdown chime plays, session-end notification sent (duration + pickup count)
13. → **OFF**

### State machine

```
              2s hold
    OFF ─────────────► STARTING ──► WAITING
     ▲                                  │
     │                            phone placed
     │                                  │
  STOPPING ◄──────────────────────── IDLE
     ▲        5s hold                    │
     │      (phone on pad)         phone removed
     │                                  │
     │                               GRACE ◄── phone returned (no log)
     │                                  │
     │                             30s expires
     │                                  │
     │                               ALARM ──── phone returned
     │                                  │              │
     │                            escalates            ▼
     │                            every 30s          LOG ──► IDLE
     │
     └── 5s hold, phone absent → send_btn_blocked(), stay in current state
```

### State reference

| State | LED | Key actions |
|-------|-----|-------------|
| `OFF` | Off | Poll button every 50 ms. 2s hold → `STARTING`. |
| `STARTING` | Blinks 3× | Chime, WiFi connect, `send_session_start()`. Reset `pickup_count`, `session_max_level`. Record `session_start_ticks`. → `WAITING`. |
| `WAITING` | Blinks 1 Hz | Poll `phone_present()` every 100 ms. Phone placed → `IDLE`. |
| `IDLE` | Solid on | Poll sensors + button every 50 ms. Phone removed → `GRACE`. 5s hold (phone present) → `STOPPING`. |
| `GRACE` | Off | Increment `pickup_count`. `send_first_warning()`. Poll sensors + button every 50 ms. Phone returned → `IDLE`. 30 s expires → `ALARM`. 5s hold (phone absent) → `send_btn_blocked()`. |
| `ALARM` | Off | `play_beep(volume)` loop (~500 ms/cycle). Check sensors before each beep. Escalate volume on schedule. Phone returned → `LOG`. |
| `LOG` | Solid on | Log alarm event (duration, escalations, max level) via `data_logger` stub. `reset_cooldown()`. 1 s pause → `IDLE`. |
| `STOPPING` | Blinks 3× | `play_shutdown_chime()`. Compute `duration_s` from `session_start_ticks`. `send_session_end(duration_s, pickup_count)`. Log full session. → `OFF`. |

### Session variables

| Variable | Set in | Meaning |
|----------|--------|---------|
| `session_start_ticks` | `STARTING` | `ticks_ms()` when device turned on — base for full session duration |
| `removal_ticks` | `GRACE` entry | `ticks_ms()` when phone removed — base for grace/alarm timing |
| `pickup_count` | `GRACE` entry (+1 each time) | Total phone removals this session |
| `alert_count` | `ALARM` (per removal) | Escalation levels crossed this removal (resets each GRACE entry) |
| `max_level` | `ALARM` (per removal) | Highest alarm level this removal (resets each GRACE entry) |
| `session_max_level` | `ALARM` (session-wide) | Highest alarm level reached across whole session |

### Alarm escalation

Elapsed time measured from `removal_ticks` (moment phone was removed).

| Elapsed | Level | Volume |
|---------|-------|--------|
| 0–30 s | — (GRACE) | none |
| 30–60 s | 1 | 30% |
| 60–90 s | 2 | 65% |
| 90 s+ | 3 | 100% |

---

## Setup checklist

1. Flash MicroPython onto the Huzzah32.
2. Open Thonny, connect via serial port.
3. Fill in `config.py`: WiFi credentials, `NTFY_TOPIC`.
4. Install ntfy app on phone, subscribe to the topic.
5. Upload all `.py` files to the ESP32 filesystem.
6. Run `sensors.calibrate()` in the REPL — paste results into `config.py`.
7. Wire FSR: 3.3 V → FSR → GPIO34 + 10 kΩ → GND.
8. Wire PAM8302: GPIO26 → SIGNAL, 3.3 V → VIN, GND → GND, speaker to VO+/VO−.
9. Attach copper foil: large pad → GPIO32 (T9), small pad → GPIO15 (T3).
10. Run `main.py` — device boots into OFF. Hold back button 2 s to start.

---

## Pin reference

| Signal | ESP32 Pin | GPIO |
|--------|-----------|------|
| Phone capacitive touch | T9 | GPIO32 |
| FSR analog in | A2 | GPIO34 (ADC1 — valid with Wi-Fi on) |
| DAC audio out | A0 | GPIO26 (DAC2) |
| Power button touch | T3 | GPIO15 |
| Status LED | — | GPIO13 |

**ADC note:** ADC2 pins (GPIO0, 2, 4, 12–15, 25–27) conflict with Wi-Fi. Always use ADC1 (GPIO32–39).
