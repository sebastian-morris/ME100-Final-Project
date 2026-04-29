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

### Starting a Session
1. User holds the **touch button on the back of the device for 2 seconds**
2. Device plays a startup chime confirming it is now ON
3. ntfy.sh push notification sent: *"Session started! Place your phone on the device to begin."*
4. User places phone on device → both sensors confirm presence → **IDLE (monitoring) state**

### During a Session
5. Phone is removed → **push notification fires instantly** via ntfy.sh
6. 30-second grace period begins (no audio)
7. Grace period expires, phone still off → **ALARM starts at low volume**
8. Every 30 seconds the alarm escalates in volume
9. Phone is returned → alarm stops, session data logged, device resets to **IDLE**

### Ending a Session
10. User holds the **touch button for 5 seconds** (phone **must** be on device to end session)
    - If phone is **not** on device: push notification sent — *"Put your phone back on the device before ending the session."* Button hold is cancelled.
    - If phone **is** on device: session ends cleanly
11. Device plays a shutdown chime
12. ntfy.sh sends thank-you notification + session summary:
    - Total session length
    - Number of phone pickup alerts triggered
13. Device enters **OFF state** — sensors disabled, alarm disabled, no monitoring

---

## State Machine

| State | Trigger In | Action | Trigger Out |
|-------|-----------|--------|-------------|
| `OFF` | Power-up / session end | Device inactive — no monitoring, no alarms | 2s button hold → `STARTING` |
| `STARTING` | 2s button hold detected | Play startup chime, send "session started" notification | → `WAITING` |
| `WAITING` | `STARTING` completes | Blink LED at 1 Hz, wait for phone to be placed | Phone detected → `IDLE` |
| `IDLE` | Phone detected on pad (both sensors) | Monitor sensors every 100 ms | Phone removed → `GRACE` |
| `GRACE` | Phone removed | Send first-warning notification, start 30s timer | Phone returned → `IDLE`; timer expires → `ALARM` |
| `ALARM` | Grace period expires | Play escalating two-tone beep, log escalation events | Phone returned → `LOG` |
| `LOG` | Phone returned from ALARM | Write session row to Google Sheets, reset timers | → `IDLE` |
| `STOPPING` | 5s button hold (phone on device) | Play shutdown chime, send session-end notification with stats | → `OFF` |

### State Machine Diagram

```
                     2s hold
           OFF ─────────────► STARTING ──► WAITING
            ▲                                 │
            │                           phone placed
            │                                 │
         STOPPING ◄──────────────────────── IDLE
            ▲         5s hold                  │
            │       (phone on device)    phone removed
            │                                  │
            │                                  ▼
            │                               GRACE ◄── phone returned (no log)
            │                                  │
            │                            30s expires
            │                                  │
            │                                  ▼
            │                               ALARM ──── phone returned
            │                                  │              │
            │                            escalates            ▼
            │                            every 30s           LOG ──► IDLE
            │
            │   (5s hold attempted, phone NOT on device)
            └── blocked; send "put phone on device" notification
```

---

## Touch Button — Power Control

**Placement:** Back of the 3D-printed housing (accessible without disrupting the workspace)  
**Hardware:** ESP32 built-in capacitive touch pin + small exposed copper pad on housing exterior  
**Pin:** GPIO15 (Touch pin T3) — separate from the phone-detection touch pad

### Hold-Time Logic

| Action | Hold Duration | Phone Required? | Result |
|--------|--------------|-----------------|--------|
| Power ON | 2 seconds | No | Startup chime + "session started" notification |
| Power OFF | 5 seconds | **Yes** | Shutdown chime + session-stats notification |
| Power OFF (phone absent) | 5 seconds | Phone missing | Notification: "place phone first"; no shutdown |

**Why require phone on device to power off?**  
Prevents the user from gaming the system — they cannot end the session early while their phone is already in their hand. Ending a session requires physically placing the phone back first.

**Why hold times instead of single tap?**  
Accidental brush of the touch pad will not trigger state changes. A deliberate 2-second hold is unambiguous. The 5-second hold for OFF adds extra friction to discourage premature session termination.

### Startup Chime (ON)
Three short rising tones: **440 Hz → 660 Hz → 880 Hz**, each 150 ms, played via DAC → PAM8302 → speaker.

### Shutdown Chime (OFF)
Three short descending tones: **880 Hz → 660 Hz → 440 Hz**, each 150 ms.

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

## Session Stats Notification (on Power OFF)

When the user ends a session, a single ntfy.sh notification is sent containing:

```
Title:   "Session Complete 🎉"
Body:    "Great work! Session: 47 min | Phone pickups: 2"
Priority: default
Tags:    "white_check_mark"
```

The session stats tracked are:
- **Session duration** — time from `STARTING` to `STOPPING` state
- **Number of phone pickups** — total number of times GRACE state was entered
  (each GRACE entry = one unauthorized phone removal = one alert)

---

## Hardware Components

| Component | Part | Notes |
|-----------|------|-------|
| Microcontroller | Adafruit Huzzah32 ESP32 Feather | MicroPython, Wi-Fi, built-in touch pins, DAC |
| Phone presence — capacitive | ESP32 built-in touch pin + copper foil pad | Solder foil to ESP32 touch pin contact area; large pad sized to phone footprint |
| Phone presence — pressure | DF9-16 Force Sensitive Resistor (FSR) | Voltage divider with fixed resistor, analog read |
| Power button | ESP32 built-in touch pin + small copper pad on housing back | Separate touch pin from phone pad; no external component needed |
| Speaker amplifier | Adafruit STEMMA Audio Amp (PAM8302) | 2.5W at 4Ω, fixed 24dB gain, trim pot for volume |
| Speaker | 4Ω, 3W, 2.8" x 1.2" enclosed | Bare wire connection to amp terminal block |

### Why dual sensors for phone detection?
- Capacitive alone: could be defeated by placing any conductive object on the pad
- FSR alone: could be defeated by placing any weighted object on the sensor
- Both together: requires a phone-like object (conductive + weighted) — much harder to spoof

### Sensor specs reference
**FSR (DF9-16):**
- Trigger threshold: resistance drops below 200kΩ at ~20g force
- Pressure range: 20g – 2kg
- Read method: voltage divider (FSR + fixed resistor to GND), ADC pin

**Capacitive pad (phone detection):**
- Uses ESP32 built-in capacitive touch (TouchPad class in MicroPython)
- Copper foil soldered to touch pin expands sensing area to phone footprint
- Touch reading: lower value = more capacitance = object present

**Power button (touch pad):**
- Same ESP32 built-in touch hardware, different pin (GPIO15 / T3)
- Small copper pad exposed on back face of housing — no external component
- Polled every 50 ms; rising-edge timestamp used to measure hold duration

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

### Copper Foil Capacitive Sensor (phone detection)
- Large foil pad (phone footprint) → ESP32 **GPIO32 (Touch pin T9)**
- No external resistor needed — ESP32 has built-in capacitive touch hardware

### Power Button Touch Pad
- Small copper pad on back of housing → ESP32 **GPIO15 (Touch pin T3)**
- No external resistor needed — same ESP32 built-in touch hardware

> ⚠️ **Pin change from original spec:** Wiring diagram uses GPIO32 (T9) for capacitive touch. The pin assignments table originally listed GPIO4 (T0). GPIO32 (T9) is confirmed. Update `config.py` accordingly.

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
- ESP32 sends HTTP POST to `https://ntfy.sh/focus-device-yourname` for all events
- Notification appears on phone in ~1–2 seconds total

**Topic security:** ntfy.sh topics are public by default — anyone who knows the topic name can subscribe. Use a random-looking name (e.g. `focus-x7k2-seb`) to prevent accidental collisions. Sufficient for a class project.

### Notification Events

| Trigger | Title | Message | Priority |
|---------|-------|---------|----------|
| Session starts (button ON) | "Focus Device" | "Session started! Place your phone on the device." | `default` |
| Phone removed (GRACE) | "Focus Device ⚠️" | "Put your phone down and get back to work!" | `high` |
| Alarm escalation (optional) | "FOCUS DEVICE 🚨" | "Still distracted? The alarm is getting louder." | `urgent` |
| Turn-off blocked (no phone) | "Focus Device" | "Place your phone on the device before ending the session." | `default` |
| Session ends (button OFF) | "Session Complete 🎉" | "Great work! Session: X min \| Phone pickups: Y" | `default` |

### ntfy.sh Priority Levels

| Priority | Behavior |
|----------|----------|
| `min` | No sound, no popup — silently added to tray |
| `low` | No sound, shows in notification tray |
| `default` | Normal notification sound |
| `high` | Loud, bypasses some silencing |
| `urgent` | Maximum — cuts through Do Not Disturb |

### Latency breakdown

| Leg | Latency |
|-----|---------|
| ESP32 → ntfy.sh server (HTTP POST) | ~200–500 ms |
| ntfy.sh → phone push notification | ~500 ms – 1.5 s |
| **Total end-to-end** | **~1–2 seconds** |

---

## Data Logging — Google Sheets via Apps Script

**Method:** Google Apps Script published as a web app  
**Why:** No OAuth from the ESP32 required — just an HTTP GET to a URL  
**Setup:** ~15 minutes, completely free

**Columns logged per session:**
- Timestamp (ISO 8601)
- Session duration (minutes)
- Number of phone pickups (GRACE entries)
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
├── sensors.py         ← Capacitive + FSR read, phone_present(), power button hold detection
├── audio.py           ← Alarm beep, startup chime, shutdown chime via DAC
├── notifications.py   ← ntfy.sh HTTP POST wrapper  ✅ DESIGNED
├── data_logger.py     ← Google Apps Script HTTP GET for Sheets
└── main.py            ← State machine: OFF → STARTING → WAITING → IDLE → GRACE → ALARM → LOG → STOPPING → OFF
```

---

## Pin Assignments

| Signal | ESP32 Pin | GPIO | Notes |
|--------|-----------|------|-------|
| Phone capacitive pad | T9 | GPIO32 | Built-in TouchPad, large copper foil for phone footprint |
| FSR analog read | A2 | GPIO34 | ADC1 channel — ADC2 unavailable when Wi-Fi active |
| DAC audio out | A0 | GPIO26 | DAC1 — connected to PAM8302 SIGNAL pin |
| Power button touch pad | T3 | GPIO15 | Built-in TouchPad, small copper pad on housing back |
| Status LED | — | GPIO13 | Onboard red LED |

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
| Power button | ESP32 built-in touch pin (T3/GPIO15) + copper pad | No extra hardware; same tech as phone sensor; hidden on back |
| Power ON hold time | 2 seconds | Long enough to prevent accidental trigger; short enough to feel responsive |
| Power OFF hold time | 5 seconds | Extra friction discourages premature session termination |
| Power OFF requirement | Phone must be on device | Prevents gaming the system by ending session while phone already in hand |
| Startup/shutdown audio | 3-tone rising/falling chime | Distinct from alarm; clearly signals state change to user |
| Session stats on shutdown | Duration + pickup count via ntfy.sh | Immediate feedback loop; reinforces behavior change over time |
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
- [x] Design power on/off touch button system
- [ ] Confirm copper foil attachment method to ESP32 touch pins (T9 for phone, T3 for button)
- [ ] Confirm final touch pin assignments — update config.py
- [ ] Decide ntfy.sh topic name
- [ ] Write and test `notifications.py` (add session_start, session_end_stats, button_blocked functions)
- [ ] Write and test power button hold detection in `sensors.py`
- [ ] Write startup and shutdown chimes in `audio.py`
- [ ] Update `main.py` state machine to include OFF, STARTING, STOPPING states
- [ ] Set up Google Sheet and deploy Apps Script web app
- [ ] Write and test `data_logger.py`
- [ ] 3D print housing — confirm sensor placement dimensions + back-panel button cutout
- [ ] Calibrate FSR threshold and capacitive touch threshold in `config.py`
- [ ] Calibrate power button touch threshold (GPIO15) in `config.py`

---

## How to Use This Document in Future Claude Chats

Upload this file to your Claude project knowledge. Claude will read it at the start of each conversation and have full context on all decisions made. Update the **Open Items** section as tasks are completed, and add any new decisions to the **Key Design Decisions** table.

*Last updated: touch-button power on/off system designed and integrated — startup/shutdown chimes, session-stats notification, phone-required-to-power-off logic*
