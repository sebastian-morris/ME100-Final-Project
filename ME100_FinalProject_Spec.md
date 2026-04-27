# ME100 Final Project — Behavioral Conditioning Productivity Device
## Complete Project Specification (living document — update as decisions change)

---

## Project Overview

A physical IoT productivity device that uses **escalating auditory negative reinforcement** to train the user to keep their phone on the device during work sessions. Unlike lockboxes or screen-time apps, this device conditions behavior rather than forcing compliance.

**Course:** ME100 — Internet of Things  
**Platform:** Adafruit Huzzah32 ESP32 Feather  
**Language:** MicroPython  
**Power:** USB-C through the ESP32 power port  
**Housing:** 3D printed via makerspace  

---

## Operational Flow

1. User places phone on the device to begin a focused work session
2. Both sensors (capacitive + FSR) confirm phone is present → **IDLE state**
3. Phone is removed → **push notification fires instantly** via ntfy.sh
4. 30-second grace period begins
5. Grace period expires, phone still off → **ALARM starts at low volume**
6. Every 30 seconds the alarm escalates in volume
7. Phone is returned → alarm stops, session data is logged, device resets to IDLE

---

## State Machine

| State | Trigger In | Action | Trigger Out |
|-------|-----------|--------|-------------|
| IDLE | Phone detected on pad (both sensors) | Monitor sensors | Either sensor loses detection |
| GRACE | Phone removed | Send ntfy.sh push notification immediately, start 30s timer | Phone returned → IDLE, or timer expires → ALARM |
| ALARM | Grace period expires | Play escalating two-tone beep, log escalation events | Phone returned → LOG → IDLE |
| LOG | Phone returned from ALARM | Write session row to Google Sheets, reset timers | → IDLE |

---

## Alarm Escalation Schedule

| Time after removal | State | Volume | Behavior |
|-------------------|-------|--------|----------|
| 0s | Grace period | — | ntfy.sh push sent, no audio |
| +30s | Alarm begins | 30% | Two-tone alternating beep (880 Hz / 440 Hz) |
| +60s | Escalation 1 | 65% | Same pattern, louder |
| +90s | Escalation 2 | 100% | Maximum volume, stays until phone returned |

Two-tone pattern: alternates between **880 Hz** and **440 Hz**, each tone ~250ms, via ESP32 DAC → PAM8302 amp → speaker.

---

## Hardware Components

| Component | Part | Notes |
|-----------|------|-------|
| Microcontroller | Adafruit Huzzah32 ESP32 Feather | MicroPython, Wi-Fi, built-in touch pins, DAC |
| Capacitive sensor | ESP32 built-in touch pin + copper foil pad | Solder foil to ESP32 touch pin contact area |
| Pressure sensor | DF9-16 Force Sensitive Resistor (FSR) | Voltage divider with fixed resistor, analog read |
| Speaker amplifier | Adafruit STEMMA Audio Amp (PAM8302) | 2.5W at 4Ω, fixed 24dB gain, trim pot for volume |
| Speaker | 4Ω, 3W, 2.8" x 1.2" enclosed | Bare wire connection to amp terminal block |

### Why dual sensors?
- Capacitive alone: could be defeated by placing any conductive object on the pad
- FSR alone: could be defeated by placing any weighted object on the sensor
- Both together: requires a phone-like object (conductive + weighted) — much harder to spoof

### Sensor specs reference
**FSR (DF9-16):**
- Trigger threshold: resistance drops below 200kΩ at ~20g force
- Pressure range: 20g – 2kg
- Read method: voltage divider (FSR + fixed resistor to GND), ADC pin

**Capacitive pad:**
- Uses ESP32 built-in capacitive touch (TouchPad class in MicroPython)
- Copper foil soldered to touch pin expands sensing area to phone footprint
- Touch reading: lower value = more capacitance = object present

**PAM8302 Amp:**
- Input: A0 (DAC pin, GPIO26) on Huzzah32
- Power: 3.3V from Huzzah32
- Output power: 1.5W at 8Ω / 2.5W at 4Ω
- Has onboard trim potentiometer for master volume control
- Wiring: Feather A0 → SIGNAL, Feather 3.3V → VIN, Feather GND → GND

---

## Wiring Diagram — Confirmed Connections

Wiring diagram generated and verified in session. Full connection list below.

### FSR Pressure Sensor (voltage divider circuit)
- One leg of the FSR → ESP32 **3V3** pin
- Other leg → ESP32 **GPIO34 / A2** (analog input) AND top of **10kΩ resistor**
- Bottom of 10kΩ resistor → **GND**
- Forms a voltage divider: as pressure increases, FSR resistance drops, voltage at A2 rises

### Copper Foil Capacitive Sensor
- Foil pad → ESP32 **GPIO32 (Touch pin T9)**
- No external resistor needed — ESP32 has built-in capacitive touch hardware

> ⚠️ **Pin change from original spec:** Wiring diagram uses GPIO32 (T9) for capacitive touch. The pin assignments table below uses GPIO4 (T0). Confirm which physical pin you solder the foil to before final assembly, and update `config.py` accordingly.

### STEMMA Audio Amp (PAM8302)
- **SIGNAL** → ESP32 **GPIO26 / DAC** (clean analog audio)
- **VIN** → ESP32 **3V3**
- **GND** → ESP32 **GND**
- **VO+** (bridge output positive) → Speaker **positive wire**
- **VO−** (bridge output negative) → Speaker **negative wire**
- ⚠️ VO+ and VO− are bridge-tied — do NOT connect either to ground

### Speaker
- Positive bare wire → Amp **VO+**
- Negative bare wire → Amp **VO−**

### ADC safety note
GPIO34 (ADC1) is used for the FSR. ADC2 pins are disabled when WiFi is active — this wiring avoids that conflict entirely.

---

## Notification System — ntfy.sh

**Service:** [ntfy.sh](https://ntfy.sh) — free, open-source push notifications  
**Why chosen over SMS/email:**
- SMS (Adafruit IO): requires paid IO Plus account, 25 msg/day cap, US/Canada only
- SMS (Twilio): costs money per message, overkill
- Email (SMTP): too slow (5–30s), easy to ignore, undermines conditioning
- ntfy.sh: free forever, instant (<1s), native iOS/Android push, 5 lines of MicroPython, no account required, unlimited messages

**How it works:**
- User installs ntfy app on phone and subscribes to a private topic (e.g. `focus-device-yourname`)
- ESP32 sends HTTP POST to `https://ntfy.sh/focus-device-yourname` when phone is removed
- Notification appears on phone in ~1–2 seconds total

**Topic security:** ntfy.sh topics are public by default — anyone who knows the topic name can subscribe. Use a random-looking name (e.g. `focus-x7k2-seb`) to prevent accidental collisions. Sufficient for a class project.

### ntfy.sh Priority Levels

| Priority | Behavior |
|----------|----------|
| `min` | No sound, no popup — silently added to tray |
| `low` | No sound, shows in notification tray |
| `default` | Normal notification sound |
| `high` | Loud, bypasses some silencing |
| `urgent` | Maximum — cuts through Do Not Disturb |

**Recommended usage for this project:**
- First warning (phone just removed): `priority: high`
- Escalated warning (if phone not returned and you want a second notification): `priority: urgent`

### Latency breakdown

| Leg | Latency |
|-----|---------|
| ESP32 → ntfy.sh server (HTTP POST) | ~200–500 ms |
| ntfy.sh → phone push notification | ~500 ms – 1.5 s |
| **Total end-to-end** | **~1–2 seconds** |

This is fast enough that the notification arrives before most users can even unlock their phone after picking it up — well within the behavioral conditioning window.

**MicroPython call (reference):**
```python
import urequests
urequests.post(
    "https://ntfy.sh/YOUR_TOPIC_NAME",
    data="Get back to work!",
    headers={"Title": "Focus Device", "Priority": "high", "Tags": "warning"}
)
```

Full implementation lives in `notifications.py` — see code summary.

---

## Data Logging — Google Sheets via Apps Script

**Method:** Google Apps Script published as a web app  
**Why:** No OAuth from the ESP32 required — just an HTTP GET to a URL  
**Setup:** ~15 minutes, completely free

**Columns logged per session:**
- Timestamp (ISO 8601)
- Session duration (minutes)
- Number of alerts triggered
- Max escalation level reached (0/1/2/3)
- Session ID (for tracking improvement over time)

**ESP32 sends:**
```
GET https://script.google.com/macros/s/YOURKEY/exec?duration=45&alerts=2&max_level=2
```

**Apps Script snippet (reference):**
```javascript
function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.appendRow([
    new Date(),
    e.parameter.duration,
    e.parameter.alerts,
    e.parameter.max_level
  ]);
  return ContentService.createTextOutput("OK");
}
```

---

## Planned Code File Structure

```
Final Project/
├── config.py          ← WiFi creds, ntfy topic, pin numbers, timing constants, thresholds
├── sensors.py         ← Capacitive + FSR read, phone_present() function
├── audio.py           ← Two-tone beep, volume stepping via DAC
├── notifications.py   ← ntfy.sh HTTP POST wrapper  ✅ DESIGNED
├── data_logger.py     ← Google Apps Script HTTP GET for Sheets
└── main.py            ← State machine: IDLE → GRACE → ALARM → LOG → IDLE
```

---

## Pin Assignments

| Signal | ESP32 Pin | Notes |
|--------|-----------|-------|
| Capacitive pad | T0 (GPIO4) | Built-in TouchPad, attach copper foil here |
| FSR analog read | A2 (GPIO34) | ADC1 channel — ADC2 unavailable when Wi-Fi active |
| DAC audio out | A0 (GPIO26) | DAC1 — connected to PAM8302 SIGNAL pin |
| (optional) Status LED | GPIO13 (onboard LED) | Visual feedback during states |

> ⚠️ **Important:** On ESP32, ADC2 pins (GPIO0, 2, 4, 12–15, 25–27) are **shared with Wi-Fi** and cannot be used for ADC when Wi-Fi is active. Always use ADC1 pins (GPIO32–39) for analog sensors.

---

## Key Design Decisions & Rationale

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sensor combo | Capacitive + FSR | Dual-factor detection, hard to spoof |
| Capacitive method | ESP32 built-in touch pin + copper foil | No external IC needed, saves cost |
| Pressure sensor | FSR (DF9-16) | Load cell too expensive/complex, FSR sufficient |
| Audio | DAC → PAM8302 → 4Ω speaker | Clean analog signal, adjustable volume, 2.5W plenty loud |
| Notification | ntfy.sh | Free, instant, native push, minimal ESP32 code, no account or rate limits |
| Notification rejected | Adafruit IO SMS | Requires paid IO Plus plan, 25 msg/day cap, US/Canada only — too restrictive for testing |
| Data storage | Google Sheets via Apps Script | Free, no OAuth headache, visual dashboard easy |
| Grace period | 30 seconds | Short enough for behavioral conditioning association |
| Alarm tones | 880 Hz / 440 Hz alternating | Two-tone is more annoying than single tone |
| Language | MicroPython | Course requirement / familiarity |
| Power | USB-C via ESP32 port | Simple, no battery management needed |
| FSR pulldown resistor | 10kΩ | Gives good ADC range: ~195 counts (no phone) vs ~2730 counts (phone present) |

---

## Open Items / Still To Do

- [x] Complete wiring diagram with resistor values
- [x] Determine FSR voltage divider resistor value (10kΩ confirmed)
- [x] Choose notification system (ntfy.sh chosen, notifications.py designed)
- [ ] Confirm copper foil attachment method to ESP32 touch pin
- [ ] Confirm final touch pin — GPIO4 (T0) vs GPIO32 (T9) — update config.py
- [ ] Decide ntfy.sh topic name
- [ ] Write and test `notifications.py`
- [ ] Set up Google Sheet and deploy Apps Script web app
- [ ] Write and test `data_logger.py`
- [ ] 3D print housing — confirm sensor placement dimensions
- [ ] Calibrate FSR threshold and capacitive touch threshold in `config.py`

---

## How to Use This Document in Future Claude Chats

Upload this file to your Claude project knowledge. Claude will read it at the start of each conversation and have full context on all decisions made. Update the **Open Items** section as tasks are completed, and add any new decisions to the **Key Design Decisions** table.

*Last updated: wiring diagram confirmed, ntfy.sh selected and designed, Adafruit IO rejected*
