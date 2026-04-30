# config.py — hardware pin assignments, thresholds, and timing constants

# --- WiFi (needed for notifications and logging) ---
WIFI_SSID     = 'Berkeley-IoT'
WIFI_PASSWORD = 'NjW&021O'

# --- ntfy.sh push notifications ---
# Use a unique, hard-to-guess name to avoid topic collisions (e.g. focus-x7k2-seb)
NTFY_TOPIC      = "focus-device-yourname"
NOTIFY_COOLDOWN = 30   # minimum seconds between repeat notifications

# --- Pin assignments ---
PIN_TOUCH_PHONE = 32   # T9 / GPIO32 — phone capacitive pad (large copper foil)
PIN_FSR         = 34   # A2 / GPIO34 — FSR voltage divider (ADC1, Wi-Fi safe)
PIN_DAC         = 26   # A0 / GPIO26 — DAC2 audio out to PAM8302 SIGNAL pin
PIN_BTN         = 15   # T3 / GPIO15 — power button touch pad (back of housing)
PIN_LED         = 13   # Onboard red LED — status indicator

# --- Sensor thresholds (run sensors.calibrate() to find your values) ---
# TouchPad reads LOWER when object is present (capacitance increases)
TOUCH_THRESHOLD = 400   # phone present when read() < this value
BTN_THRESHOLD   = 400   # button held when read() < this value

# FSR ADC reads HIGHER when weight is applied (voltage divider with 10kΩ fixed)
# No phone  → R_FSR ~200kΩ → ~195 ADC counts
# Phone on  → R_FSR ~5kΩ   → ~2730 ADC counts
FSR_THRESHOLD = 1000    # phone present when read() > this value

# --- Power button hold times (milliseconds) ---
POWER_ON_HOLD_MS  = 2000   # hold 2s to turn device ON
POWER_OFF_HOLD_MS = 5000   # hold 5s to turn device OFF (phone must be on pad)

# --- Timing (seconds) ---
GRACE_PERIOD          = 30   # silence window after phone removed
WARN_DURATION         = 5    # seconds between quiet-beep warning and full alarm
ESCALATION_INTERVAL   = 30   # seconds between volume escalations once alarm is running
ALARM_NOTIFY_INTERVAL = 30   # seconds between repeated spam notifications in ALARM state

# --- Alarm volume levels (0.0 – 1.0 maps to DAC amplitude) ---
VOLUME_LOW  = 0.30
VOLUME_MED  = 0.65
VOLUME_HIGH = 1.00

# --- Audio tone config ---
TONE_HIGH        = 880   # Hz — first tone in each alarm beep cycle
TONE_LOW         = 440   # Hz — second tone in each alarm beep cycle
TONE_DURATION_MS = 250   # ms each alarm tone plays before switching
CHIME_TONE_MS    = 150   # ms each note plays in startup / shutdown chime

# --- Polling intervals (milliseconds) ---
SENSOR_POLL_MS = 100   # sensor polling in IDLE / GRACE states
BTN_POLL_MS    = 50    # button polling (faster for responsive hold detection)
