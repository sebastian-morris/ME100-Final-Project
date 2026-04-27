# Behavioral Conditioning Productivity Device — Code Summary

MicroPython codebase for the Adafruit Huzzah32 ESP32 Feather. Runs in Thonny.

---

## File Structure

```
Final Project/
├── config.py          # All constants: pins, thresholds, timing, volumes
├── sensors.py         # Capacitive touch + FSR reads, phone_present()
├── audio.py           # Square-wave tone generation via DAC → PAM8302
├── main.py            # State machine (5 states)
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
| `PIN_TOUCH` | `4` | GPIO4 / T0 — built-in ESP32 TouchPad |
| `PIN_FSR` | `34` | GPIO34 / A2 — ADC1 channel (Wi-Fi safe) |
| `PIN_DAC` | `26` | GPIO26 / A0 — DAC2 audio output |
| `PIN_LED` | `13` | Onboard red LED |
| `TOUCH_THRESHOLD` | `400` | TouchPad reads **below** this when phone is present |
| `FSR_THRESHOLD` | `1000` | ADC reads **above** this when phone weight is on pad |
| `GRACE_PERIOD` | `30` | Seconds of silence after phone removed before alarm |
| `ESCALATION_INTERVAL` | `30` | Seconds between volume steps |
| `VOLUME_LOW/MED/HIGH` | `0.30 / 0.65 / 1.00` | DAC amplitude fractions at each alarm level |
| `TONE_HIGH` / `TONE_LOW` | `880 / 440` Hz | Two-tone beep frequencies |
| `TONE_DURATION_MS` | `250` | How long each tone plays per beep cycle |
| `SENSOR_POLL_MS` | `100` | Polling interval in IDLE and GRACE states |
| `NOTIFY_COOLDOWN` | `30` | Minimum seconds between repeat notifications |

**First thing to do:** run `sensors.calibrate()` and update `TOUCH_THRESHOLD` and `FSR_THRESHOLD` with real measured values.

---

## sensors.py

Manages both presence sensors. The dual-sensor requirement prevents spoofing.

### Functions

#### `read_touch() → int`
Returns a raw value from the ESP32 built-in TouchPad on GPIO4. The value **decreases** when a conductive object (phone) is placed on the copper foil pad.

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
- `read_touch() < TOUCH_THRESHOLD` (capacitance detected)
- `read_fsr() > FSR_THRESHOLD` (weight detected)

This AND logic is the anti-spoofing guarantee. A conductive non-phone won't have enough weight; a weighted non-phone won't be conductive.

#### `calibrate()`
Interactive helper to measure actual sensor values. Run from the Thonny REPL:
```python
import sensors
sensors.calibrate()
```
Prompts you to remove then place the phone, measures 10 samples each, and prints suggested threshold values to paste into `config.py`.

---

## audio.py

Generates two-tone alarm audio through the DAC → PAM8302 → speaker chain.

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
Private. Drives a square wave at `freq_hz` for `duration_ms` milliseconds. Blocks the calling thread for the full duration. Returns DAC to midpoint (128) when done.

Half-period timing:
- 880 Hz → 568 µs per half-cycle
- 440 Hz → 1136 µs per half-cycle

#### `play_beep(volume)`
Public. Plays one full two-tone cycle: 880 Hz for 250 ms, then 440 Hz for 250 ms. Blocks for ~500 ms total. Called in a loop by the ALARM state in `main.py`.

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

For this device: use `"high"` for the first-warning notification in GRACE state. If a second notification is ever sent (optional escalation), use `"urgent"`.

### Topic security
ntfy.sh topics are public — anyone who knows the name can subscribe or post. Use a random-looking topic name in `config.py` (e.g. `focus-x7k2-seb`) to prevent accidental collisions. This is sufficient for a class project. A paid ntfy.sh account supports private topics if needed later.

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

    # Cooldown guard — don't spam notifications
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


def reset_cooldown():
    """Reset the cooldown timer — call this when phone is returned to pad."""
    global _last_notify_time
    _last_notify_time = 0
```

### Usage in main.py

```python
import notifications

# In GRACE state, on entry:
notifications.send_first_warning()

# When phone is returned:
notifications.reset_cooldown()
```

### WiFi dependency
`notifications.py` requires an active WiFi connection. WiFi is managed in `main.py` at startup using `network.WLAN`. If the POST fails (network dropout), the function catches the exception and prints an error — the alarm still runs normally since the notification is a supplementary warning, not the primary conditioning mechanism.

---

## main.py

Implements the five-state machine. Imports `config`, `sensors`, `audio`, and `notifications`. Logging calls are stubs until `data_logger.py` is written.

### States

```
         phone placed
WAITING ──────────────► IDLE
                          │
                    phone removed
                          │
                          ▼
                        GRACE  ◄─── phone returned (no log)
                          │
                    30s expires
                          │
                          ▼
                        ALARM ──── phone returned
                          │              │
                    escalates            ▼
                    every 30s           LOG
                                         │
                                    resets to
                                         ▼
                                        IDLE
```

### State details

| State | LED | What happens |
|-------|-----|-------------|
| `WAITING` | Blinks 1 Hz | Startup only. Waits for phone to be placed before the system arms. Prevents spurious GRACE triggers on boot. |
| `IDLE` | On solid | Phone is on pad. Polls sensors every 100 ms. Transitions to GRACE the moment both sensors go false. |
| `GRACE` | Off | Phone just removed. Calls `notifications.send_first_warning()` immediately. Polls sensors every 100 ms. If phone returns → IDLE. If 30 s elapses → ALARM. |
| `ALARM` | Off | Phone still absent. Calls `audio.play_beep(volume)` in a loop (~500 ms per iteration). Checks sensors before each beep, so response to phone return is ≤ 500 ms. Volume escalates on a fixed schedule. |
| `LOG` | On solid | Phone returned from ALARM. Calls `log_session(duration_s, alert_count, max_level)` stub. Calls `notifications.reset_cooldown()`. Brief 1 s pause, then returns to IDLE. |

### Alarm escalation schedule

Time is measured from the moment the phone was removed (not from when the alarm started).

| Elapsed time | Alarm level | Volume |
|---|---|---|
| 0–30 s | — (GRACE, silent) | none |
| 30–60 s | Level 1 | 30% |
| 60–90 s | Level 2 | 65% |
| 90 s+ | Level 3 | 100% |

### Session data tracked

| Variable | Meaning |
|----------|---------|
| `removal_ticks` | `ticks_ms()` when phone was removed — used for all timing |
| `session_ticks` | Same value, kept for duration calculation |
| `alert_count` | Number of level escalations (1→2→3); max 3 per session |
| `max_level` | Highest alarm level reached (0 if phone returned during grace) |

### Stubs (to be replaced when data_logger.py is written)

```python
def log_session(duration_s, alert_count, max_level):
    # TODO: implement in data_logger.py
    print(f"[data_logger] duration={duration_s}s  alerts={alert_count}  max_level={max_level}")
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
   Copy the printed threshold values into `config.py`.
7. **Wire the FSR voltage divider:** 3.3 V → 10 kΩ resistor → GPIO34 → FSR → GND.
8. **Wire the PAM8302:** GPIO26 → SIGNAL, 3.3 V → VIN, GND → GND, speaker to VO+ / VO−.
9. **Run `main.py`** — the device boots into WAITING and blinks until the phone is placed.

---

## Pin reference

| Signal | ESP32 Pin | GPIO | Notes |
|--------|-----------|------|-------|
| Capacitive touch | T0 | GPIO4 | Built-in TouchPad, attach copper foil |
| FSR analog in | A2 | GPIO34 | ADC1 — stays valid with Wi-Fi on |
| DAC audio out | A0 | GPIO26 | DAC2 — to PAM8302 SIGNAL |
| Status LED | — | GPIO13 | Onboard red LED |

**ADC note:** ADC2 pins (GPIO0, 2, 12–15, 25–27) are shared with the Wi-Fi radio and will return invalid readings when Wi-Fi is active. Always use ADC1 (GPIO32–39) for analog sensors.
