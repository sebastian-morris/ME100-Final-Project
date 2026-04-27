# config.py — hardware pin assignments, thresholds, and timing constants

# --- WiFi (needed for notifications and logging) ---
WIFI_SSID     = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# --- ntfy.sh push notifications ---
# Use a unique, hard-to-guess name to avoid topic collisions (e.g. focus-x7k2-seb)
NTFY_TOPIC      = "focus-device-yourname"
NOTIFY_COOLDOWN = 30   # minimum seconds between repeat notifications

# --- Pin assignments ---
PIN_TOUCH = 4    # T0 / GPIO4  — capacitive touch (built-in TouchPad)
PIN_FSR   = 34   # A2 / GPIO34 — FSR voltage divider (ADC1, Wi-Fi safe)
PIN_DAC   = 26   # A0 / GPIO26 — DAC2 audio out to PAM8302 SIGNAL pin
PIN_LED   = 13   # Onboard red LED — status indicator

# --- Sensor thresholds (run sensors.calibrate() to find your values) ---
# TouchPad reads LOWER when the phone is present (capacitance increases)
TOUCH_THRESHOLD = 400   # phone present when read() < this value

# FSR ADC reads HIGHER when weight is applied (voltage divider with 10kΩ fixed)
# No phone  → R_FSR ~200kΩ → ~195 ADC counts
# Phone on  → R_FSR ~5kΩ   → ~2700 ADC counts
FSR_THRESHOLD = 1000    # phone present when read() > this value

# --- Timing (seconds) ---
GRACE_PERIOD         = 30   # silence window after phone removed before alarm
ESCALATION_INTERVAL  = 30   # seconds between volume escalations

# --- Alarm volume levels (0.0 – 1.0 maps to DAC amplitude) ---
VOLUME_LOW  = 0.30
VOLUME_MED  = 0.65
VOLUME_HIGH = 1.00

# --- Audio tone config ---
TONE_HIGH        = 880   # Hz — first tone in each beep cycle
TONE_LOW         = 440   # Hz — second tone in each beep cycle
TONE_DURATION_MS = 250   # ms each tone plays before switching

# --- Polling ---
SENSOR_POLL_MS = 100   # ms between sensor reads in IDLE / GRACE states
