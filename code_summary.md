# Behavioral Conditioning Productivity Device — Code Summary

MicroPython codebase for the Adafruit Huzzah32 ESP32 Feather. Runs in Thonny.

---

## File Structure

```
Final Project/
├── config.py          # All constants: pins, thresholds, timing, volumes, hold times
├── sensors.py         # Capacitive touch + FSR reads, phone_present(), power button hold detection
├── audio.py           # Alarm beep, startup chime, shutdown chime via DAC → PAM8302
├── main.py            # State machine (8 states)
├── notifications.py   # ntfy.sh push notification  ✅ DESIGNED
└── data_logger.py     # NOT YET WRITTEN — Google Sheets logging stub
```

---

## config.py

Single source of truth. All other modules import from here — no magic numbers anywhere else.

| Constant | Default | Description |
|----------|---------|-------------|
| `WIFI_SSID` / `WIFI_PASSWORD` | `"YOUR_..."` | Fill in before first run |
| `NTFY_TOPIC` | `"focus-device-yourname"` | Your unique ntfy.sh topic — change before use |
| `PIN_TOUCH_PHONE` | `32` | GPIO32 / T9 — phone capacitive pad (large copper foil) |
| `PIN_FSR` | `34` | GPIO34 / A2 — ADC1 channel (Wi-Fi safe) |
| `PIN_DAC` | `26` | GPIO26 / A0 — DAC2 audio output |
| `PIN_BTN` | `15` | GPIO15 / T3 — power button touch pad (back of housing) |
| `PIN_LED` | `13` | Onboard red LED |
| `TOUCH_THRESHOLD` | `400` | Phone TouchPad reads **below** this when phone is present |
| `BTN_THRESHOLD` | `400` | Button TouchPad reads **below** this when finger is held |
| `FSR_THRESHOLD` | `1000` | ADC reads **above** this when phone weight is on pad |
| `POWER_ON_HOLD_MS` | `2000` | Hold duration in ms to turn device ON |
| `POWER_OFF_HOLD_MS` | `5000` | Hold duration in ms to turn device OFF |
| `GRACE_PERIOD` | `30` | Seconds of silence after phone removed before alarm |
| `ESCALATION_INTERVAL` | `30` | Seconds between volume steps |
| `VOLUME_LOW/MED/HIGH` | `0.30 / 0.65 / 1.00` | DAC amplitude fractions at each alarm level |
| `TONE_HIGH` / `TONE_LOW` | `880 / 440` Hz | Alarm two-tone frequencies |
| `CHIME_TONE_MS` | `150` | Duration of each note in startup/shutdown chime |
| `TONE_DURATION_MS` | `250` | How long each alarm tone plays per beep cycle |
| `SENSOR_POLL_MS` | `100` | Polling interval in IDLE and GRACE states |
| `BTN_POLL_MS` | `50` | Polling interval for power button hold detection |
| `NOTIFY_COOLDOWN` | `30` | Minimum seconds between repeat notifications |

**First thing to do:** run `sensors.calibrate()` and update `TOUCH_THRESHOLD`, `BTN_THRESHOLD`, and `FSR_THRESHOLD` with real measured values.

---

## sensors.py

Manages both presence sensors and the power button hold detection. Dual-sensor phone detection prevents spoofing. Power button uses a separate touch pin.

### Functions

#### `read_touch_phone() → int`
Returns a raw value from the ESP32 built-in TouchPad on GPIO32 (T9). The value **decreases** when a conductive object (phone) is placed on the large copper foil pad.

#### `read_touch_btn() → int`
Returns a raw value from the ESP32 built-in TouchPad on GPIO15 (T3). The value **decreases** when a finger is held on the small button pad on the back of the housing.

#### `read_fsr(samples=3) → int`
Returns an averaged 12-bit ADC reading (0–4095) from the FSR voltage divider on GPIO34. The value **increases** as weight is applied because the FSR's resistance drops, raising the voltage at the divider midpoint.

```
3.3V ──── 10kΩ fixed ──── GPIO34 ──── FSR (DF9-16) ──── GND
                          (ADC read point)
```

Estimated ADC values with a 10 kΩ fixed resistor:

| Condition | R_FSR | Vout | ADC counts |
|-----------|-------|------|------------|
| No phone | ~200 kΩ | 0.16 V | ~195 |
| Phone (~150 g) | ~5 kΩ | 2.2 V | ~2730 |

#### `phone_present() → bool`
Returns `True` only if **both** conditions are met:
- `read_touch_phone() < TOUCH_THRESHOLD` (capacitance detected)
- `read_fsr() > FSR_THRESHOLD` (weight detected)

This AND logic is the anti-spoofing guarantee. A conductive non-phone won't have enough weight; a weighted non-phone won't be conductive.

#### `check_button_hold(required_ms) → bool`
Non-blocking power button hold checker. Call this in a polling loop. Returns `True` when the button has been held continuously for `required_ms` milliseconds, `False` otherwise. Resets the internal timer the moment the finger is lifted.

**Implementation logic:**
```python
_btn_press_start = None   # module-level variable

def check_button_hold(required_ms):
    global _btn_press_start
    touching = read_touch_btn() < config.BTN_THRESHOLD
    now = time.ticks_ms()

    if touching:
        if _btn_press_start is None:
            _btn_press_start = now          # finger just landed
        elif time.ticks_diff(now, _btn_press_start) >= required_ms:
            _btn_press_start = None         # reset so it doesn't re-fire
            return True
    else:
        _btn_press_start = None             # finger lifted, reset timer

    return False
```

This pattern is called in the OFF state polling loop with `required_ms = config.POWER_ON_HOLD_MS`, and during IDLE/GRACE/ALARM states with `required_ms = config.POWER_OFF_HOLD_MS`.

#### `calibrate()`
Interactive helper to measure actual sensor values. Run from the Thonny REPL:
```python
import sensors
sensors.calibrate()
```
Prompts you to remove then place the phone, and separately press then release the button, measures 10 samples each, and prints suggested threshold values to paste into `config.py`.

---

## audio.py

Generates alarm audio and chimes through the DAC → PAM8302 → speaker chain.

### Signal path

```
ESP32 GPIO26 (DAC2)  →  PAM8302 SIGNAL pin  →  4Ω / 3W speaker
                         (24 dB gain, shutdown tied high = always on)
```

### How volume works

The DAC output ranges 0–255, representing 0–3.3 V. Audio is centered at the midpoint (128 = 1.65 V). Volume scales the amplitude symmetrically around that center:

| Volume | `amp` value | DAC high | DAC low |
|--------|-------------|----------|---------|
| 30% | 38 | 166 | 90 |
| 65% | 83 | 211 | 45 |
| 100% | 127 | 255 | 1 |

### Why square wave (not sine wave)

Square wave generation in MicroPython requires only toggling between two DAC values and `time.sleep_us()`. Sine wave generation requires a lookup table and much tighter timing loops. For an alarm, square waves are also perceptually harsher — intentionally more annoying.

### Functions

#### `_play_square_tone(freq_hz, duration_ms, volume)`
Private. Drives a square wave at `freq_hz` for `duration_ms` milliseconds at the given volume fraction (0.0–1.0). Blocks the calling thread for the full duration. Returns DAC to midpoint (128) when done.

Half-period timing:
- 880 Hz → 568 µs per half-cycle
- 660 Hz → 758 µs per half-cycle
- 440 Hz → 1136 µs per half-cycle

#### `play_beep(volume)`
Public. Plays one full alarm two-tone cycle: 880 Hz for 250 ms, then 440 Hz for 250 ms. Blocks for ~500 ms total. Called in a loop by the ALARM state in `main.py`.

#### `play_startup_chime()`
Plays the session-start sound: **440 Hz → 660 Hz → 880 Hz**, each 150 ms. Total ~450 ms. Called once when entering the `STARTING` state.

#### `play_shutdown_chime()`
Plays the session-end sound: **880 Hz → 660 Hz → 440 Hz**, each 150 ms. Total ~450 ms. Called once when entering the `STOPPING` state.

#### `silence()`
Writes 128 to the DAC, centering the output at the amp's common-mode voltage. No AC component = no sound. Called on startup and whenever the alarm stops.

---

## notifications.py

Sends push notifications to the user's phone via **ntfy.sh** — a free, open-source push notification service. No account required. No daily message limits.

### How ntfy.sh works
The ESP32 sends a plain HTTP POST to `https://ntfy.sh/YOUR_TOPIC`. Anyone subscribed to that topic in the ntfy mobile app receives the push notification immediately. Total latency from ESP32 POST to phone vibrating is ~1–2 seconds.

**User setup (one time):**
1. Install the ntfy app (iOS or Android — both free)
2. Subscribe to the topic name set in `config.py`
3. Enable notifications for the app

### Priority levels

| Priority string | Phone behavior |
|----------------|----------------|
| `"min"` | No sound, silently added to notification tray |
| `"low"` | No sound, appears in tray |
| `"default"` | Normal notification sound |
| `"high"` | Loud, bypasses some silencing |
| `"urgent"` | Maximum — cuts through Do Not Disturb |

### Notification events

| Function | When called | Priority |
|----------|-------------|----------|
| `send_session_start()` | STARTING state | `default` |
| `send_first_warning()` | GRACE state entry | `high` |
| `send_escalation_warning()` | Optional, during ALARM | `urgent` |
| `send_btn_blocked()` | 5s hold attempted, phone absent | `default` |
| `send_session_end(duration_s, pickups)` | STOPPING state | `default` |

### Full implementation

```python
# notifications.py
import urequests
import time
import config

_last_notify_time = 0

def send_notification(message, title="Focus Device", priority="high", tags="warning"):
    """
    Send a push notification via ntfy.sh.

    Args:
        message  (str): Body text of the notification
        title    (str): Bold title line shown on phone
        priority (str): min | low | default | high | urgent
        tags     (str): Emoji shortcode shown next to title (e.g. "warning" = ⚠️)

    Returns:
        True on success, False on failure
    """
    global _last_notify_time

    now = time.time()
    if now - _last_notify_time < config.NOTIFY_COOLDOWN:
        print("[notifications] skipped — cooldown active")
        return False

    url = "https://ntfy.sh/" + config.NTFY_TOPIC
    headers = {
        "Title":    title,
        "Priority": priority,
        "Tags":     tags
    }

    try:
        response = urequests.post(url, data=message, headers=headers)
        response.close()
        _last_notify_time = now
        print("[notifications] sent:", message)
        return True
    except Exception as e:
        print("[notifications] FAILED:", e)
        return False


def send_session_start():
    """Called in STARTING state — device just turned on."""
    send_notification(
        message="Session started! Place your phone on the device to begin.",
        title="Focus Device",
        priority="default",
        tags="stopwatch"
    )


def send_first_warning():
    """Called immediately when phone leaves pad (GRACE state entry)."""
    send_notification(
        message="Put your phone down and get back to work!",
        title="Focus Device",
        priority="high",
        tags="warning"
    )


def send_escalation_warning():
    """Optional: called if you want a second notification during ALARM state."""
    send_notification(
        message="Still distracted? The alarm is getting louder.",
        title="FOCUS DEVICE",
        priority="urgent",
        tags="rotating_light"
    )


def send_btn_blocked():
    """Called when 5s power-off hold is attempted but phone is not on the device."""
    send_notification(
        message="Place your phone on the device before ending the session.",
        title="Focus Device",
        priority="default",
        tags="hand"
    )


def send_session_end(duration_s, pickups):
    """
    Called in STOPPING state — session complete.

    Args:
        duration_s (int): Total session length in seconds
        pickups    (int): Number of times phone was removed (GRACE entries)
    """
    duration_min = duration_s // 60
    message = "Great work! Session: {} min | Phone pickups: {}".format(duration_min, pickups)
    # Bypass cooldown for session-end — always send this
    global _last_notify_time
    _last_notify_time = 0
    send_notification(
        message=message,
        title="Session Complete",
        priority="default",
        tags="white_check_mark"
    )


def reset_cooldown():
    """Reset the cooldown timer — call this when phone is returned to pad."""
    global _last_notify_time
    _last_notify_time = 0
```

### Usage in main.py

```python
import notifications

# STARTING state:
notifications.send_session_start()

# GRACE state entry:
notifications.send_first_warning()

# 5s hold attempted but phone missing:
notifications.send_btn_blocked()

# STOPPING state:
notifications.send_session_end(duration_s, pickups)

# Phone returned after alarm:
notifications.reset_cooldown()
```

### WiFi dependency
`notifications.py` requires an active WiFi connection. WiFi is managed in `main.py` at startup using `network.WLAN`. If the POST fails (network dropout), the function catches the exception and prints an error — the alarm still runs normally since the notification is supplementary to the primary conditioning mechanism.

---

## main.py

Implements the eight-state machine. Imports `config`, `sensors`, `audio`, and `notifications`.

### States

```
             2s btn hold
    OFF ───────────────► STARTING ──► WAITING
     ▲                                   │
     │                             phone placed
     │                                   │
  STOPPING ◄──────────────────────────  IDLE
     ▲        5s btn hold                 │
     │      (phone on device)       phone removed
     │                                   │
     │                                   ▼
     │                                 GRACE ◄── phone returned (no log)
     │                                   │
     │                             30s expires
     │                                   │
     │                                   ▼
     │                                 ALARM ──── phone returned
     │                                   │              │
     │                             escalates            ▼
     │                             every 30s           LOG
     │                                                   │
     │                                              resets to IDLE
     │
     └── (5s hold, phone absent → send_btn_blocked(), stay in current state)
```

### State details

| State | LED | What happens |
|-------|-----|-------------|
| `OFF` | Off | Device inactive. Polls button every 50 ms. On 2s hold → `STARTING`. |
| `STARTING` | Blinks fast 3× | Play startup chime. Send `session_start` notification. Record `session_start_ticks`. Reset `pickup_count = 0`. → `WAITING`. |
| `WAITING` | Blinks 1 Hz | Wait for phone to be placed. Polls sensors every 100 ms. Prevents spurious GRACE on boot. |
| `IDLE` | On solid | Phone is on pad. Polls sensors every 100 ms. Also polls button (5s hold). Phone removed → `GRACE`. 5s hold → `STOPPING`. |
| `GRACE` | Off | Phone removed. Increment `pickup_count`. Send `send_first_warning()`. Poll sensors every 100 ms. Also polls button (5s hold, phone absent → `send_btn_blocked()`). Phone returns → `IDLE`. Timer expires → `ALARM`. |
| `ALARM` | Off | Phone still absent. `play_beep(volume)` in a loop. Check sensors before each beep (≤500 ms response). Volume escalates on schedule. Button poll skipped (non-blocking loop required for audio). Phone returned → `LOG`. |
| `LOG` | On solid | Phone returned from ALARM. Write session row to Google Sheets. `reset_cooldown()`. Brief 1s pause → `IDLE`. |
| `STOPPING` | Blinks fast 3× | Play shutdown chime. Compute `duration_s`. Call `send_session_end(duration_s, pickup_count)`. Call `data_logger.log_session(...)`. → `OFF`. |

### Session data tracked

| Variable | Meaning |
|----------|---------|
| `session_start_ticks` | `ticks_ms()` when device entered `STARTING` — used to compute total session duration |
| `removal_ticks` | `ticks_ms()` when phone was removed — used for grace/alarm timing |
| `pickup_count` | Number of times GRACE state was entered (= phone removals = alerts) |
| `alert_count` | Number of alarm level escalations (1→2→3); max 3 per removal |
| `max_level` | Highest alarm level reached this session |

### Alarm escalation schedule

Time is measured from the moment the phone was removed (not from when the alarm started).

| Elapsed time | Alarm level | Volume |
|---|---|---|
| 0–30 s | — (GRACE, silent) | none |
| 30–60 s | Level 1 | 30% |
| 60–90 s | Level 2 | 65% |
| 90 s+ | Level 3 | 100% |

### Power button polling in IDLE and GRACE

Since the device must simultaneously monitor sensors AND watch for a 5-second button hold, both are polled in the same tight loop:

```python
# In IDLE state loop (pseudocode):
while True:
    if not sensors.phone_present():
        state = GRACE
        break
    if sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
        state = STOPPING
        break
    time.sleep_ms(config.BTN_POLL_MS)   # 50 ms — faster than SENSOR_POLL_MS
```

In `GRACE` state, if 5s hold is detected with phone absent:
```python
if sensors.check_button_hold(config.POWER_OFF_HOLD_MS):
    if not sensors.phone_present():
        notifications.send_btn_blocked()   # tell user to put phone back first
    else:
        state = STOPPING
        break
```

### Stubs (to be replaced when data_logger.py is written)

```python
def log_session(duration_s, pickup_count, max_level):
    # TODO: implement in data_logger.py
    print("[data_logger] duration={}s  pickups={}  max_level={}".format(
        duration_s, pickup_count, max_level))
```

---

## Setup checklist

1. **Flash MicroPython** onto the Huzzah32 if not already done.
2. **Open Thonny**, connect to the ESP32 via the correct COM/serial port.
3. **Upload all `.py` files** to the ESP32's filesystem (`/`).
4. **Fill in `config.py`:**
   - WiFi SSID and password
   - `NTFY_TOPIC` — your chosen topic name (e.g. `focus-x7k2-seb`)
5. **Set up ntfy on your phone:**
   - Install the ntfy app (iOS / Android)
   - Subscribe to the same topic name set in `config.py`
6. **Calibrate sensors:**
   ```python
   # Run in Thonny REPL (not main.py)
   import sensors
   sensors.calibrate()
   ```
   Copy the printed threshold values into `config.py` — includes phone touch, FSR, and button touch thresholds.
7. **Wire the FSR voltage divider:** 3.3 V → 10 kΩ resistor → GPIO34 → FSR → GND.
8. **Wire the PAM8302:** GPIO26 → SIGNAL, 3.3 V → VIN, GND → GND, speaker to VO+ / VO−.
9. **Attach copper foil pads:**
   - Large pad (phone footprint) → GPIO32 (T9)
   - Small pad (button, back of housing) → GPIO15 (T3)
10. **Run `main.py`** — device boots into `OFF` state. Hold the back button for 2 seconds to start a session.

---

## Pin reference

| Signal | ESP32 Pin | GPIO | Notes |
|--------|-----------|------|-------|
| Phone capacitive touch | T9 | GPIO32 | Built-in TouchPad, large copper foil |
| FSR analog in | A2 | GPIO34 | ADC1 — stays valid with Wi-Fi on |
| DAC audio out | A0 | GPIO26 | DAC2 — to PAM8302 SIGNAL |
| Power button touch | T3 | GPIO15 | Built-in TouchPad, small copper pad on back |
| Status LED | — | GPIO13 | Onboard red LED |

**ADC note:** ADC2 pins (GPIO0, 2, 12–15, 25–27) are shared with the Wi-Fi radio and will return invalid readings when Wi-Fi is active. Always use ADC1 (GPIO32–39) for analog sensors.
