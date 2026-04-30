# sensors.py — capacitive touch sensors (phone + button) and FSR pressure sensor

from machine import TouchPad, ADC, Pin
import time
import config

# Phone presence — large copper foil pad, GPIO32 (T9)
_touch_phone = TouchPad(Pin(config.PIN_TOUCH_PHONE))

# Power button — small copper pad on back of housing, GPIO15 (T3)
_touch_btn = TouchPad(Pin(config.PIN_BTN))

# FSR pressure sensor — voltage divider on GPIO34 (ADC1, Wi-Fi safe)
_fsr = ADC(Pin(config.PIN_FSR))
_fsr.atten(ADC.ATTN_11DB)       # full 0–3.3 V range
_fsr.width(ADC.WIDTH_12BIT)     # 12-bit resolution → 0–4095

# Internal state
_btn_press_start = None
_fsr_base        = None   # no-phone FSR baseline, set by calibrate_baseline()


# ---------------------------------------------------------------------------
# Raw reads
# ---------------------------------------------------------------------------

def read_touch_phone():
    """Instantaneous touch value from phone pad (GPIO32). Decreases when phone present."""
    return _touch_phone.read()


def read_touch_btn():
    """Instantaneous touch value from button pad (GPIO15). Decreases when finger held."""
    return _touch_btn.read()


def read_fsr(samples=3):
    """Averaged raw ADC value (0–4095). Increases as FSR pressure rises."""
    return sum(_fsr.read() for _ in range(samples)) // samples


# ---------------------------------------------------------------------------
# Time-averaged touch helpers
# ---------------------------------------------------------------------------

def _avg_touch_phone(duration_ms, interval_ms=50):
    """Sample the phone touch sensor repeatedly over duration_ms and return the mean."""
    n = max(1, duration_ms // interval_ms)
    total = 0
    for _ in range(n):
        total += read_touch_phone()
        time.sleep_ms(interval_ms)
    return total // n


def touch_detected():
    """
    Touch-only presence check (no FSR). Uses 1-second average.
    Used in WAITING state before FSR is calibrated.
    """
    return _avg_touch_phone(1000) < config.TOUCH_THRESHOLD


# ---------------------------------------------------------------------------
# Phone presence (time-averaged, both sensors)
# ---------------------------------------------------------------------------

def phone_present():
    """
    Time-averaged phone presence detection using both sensors.

    ON  — 1-second touch average below TOUCH_THRESHOLD AND FSR above FSR_THRESHOLD.
    OFF — two consecutive 1-second touch windows above threshold (2 s confirmation).
    """
    avg1 = _avg_touch_phone(1000)

    if avg1 < config.TOUCH_THRESHOLD:
        return read_fsr() > config.FSR_THRESHOLD

    # First window above threshold — take a second 1 s window to confirm absence
    avg2 = _avg_touch_phone(1000)

    if avg2 < config.TOUCH_THRESHOLD:
        # Phone returned during confirmation window
        return read_fsr() > config.FSR_THRESHOLD

    return False   # both windows above threshold — phone absent


# ---------------------------------------------------------------------------
# Button hold detection (non-blocking)
# ---------------------------------------------------------------------------

def check_button_hold(required_ms):
    """
    Non-blocking button hold checker. Call in a polling loop.
    Returns True once the button has been held continuously for required_ms.
    Resets automatically when finger is lifted or after firing.
    """
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


# ---------------------------------------------------------------------------
# Auto-calibration (two-phase, called from main.py)
# ---------------------------------------------------------------------------

def _write_config_value(name, value):
    """Replace the `name = ...` line in config.py with the calibrated value."""
    try:
        with open('config.py', 'r') as f:
            lines = f.read().split('\n')
        new_lines = []
        for line in lines:
            if line.strip().startswith(name):
                new_lines.append('{} = {}   # auto-calibrated'.format(name, value))
            else:
                new_lines.append(line)
        with open('config.py', 'w') as f:
            f.write('\n'.join(new_lines))
        return True
    except Exception as e:
        print("  Could not write config.py: {}".format(e))
        return False


def calibrate_baseline():
    """
    Phase 1 — called during STARTING state (no phone on pad).

    Measures touch and FSR baselines with nothing on the device.
    Sets TOUCH_THRESHOLD = touch_baseline - 30 and writes it to config.py.
    Stores FSR baseline internally for use by calibrate_with_phone().
    """
    global _fsr_base
    print("Calibrating sensors (no phone on pad)...")

    # Touch baseline → set threshold
    touch_baseline    = _avg_touch_phone(1000)
    new_touch_thresh  = touch_baseline - 30
    config.TOUCH_THRESHOLD = new_touch_thresh
    _write_config_value('TOUCH_THRESHOLD', new_touch_thresh)
    print("  Touch baseline : {}  →  TOUCH_THRESHOLD = {}".format(
        touch_baseline, new_touch_thresh))

    # FSR baseline — stored for phase 2
    _fsr_base = read_fsr(samples=10)
    print("  FSR baseline   : {}  (stored for phase 2)".format(_fsr_base))


def calibrate_with_phone():
    """
    Phase 2 — called during WAITING state, the moment touch detects the phone.

    Measures FSR with phone on the pad.
    Sets FSR_THRESHOLD = midpoint(fsr_baseline, fsr_with_phone) and writes to config.py.
    """
    global _fsr_base
    print("Calibrating FSR with phone on pad...")

    fsr_phone = read_fsr(samples=10)
    base      = _fsr_base if _fsr_base is not None else 0
    new_fsr_thresh = (base + fsr_phone) // 2

    config.FSR_THRESHOLD = new_fsr_thresh
    _write_config_value('FSR_THRESHOLD', new_fsr_thresh)
    print("  FSR with phone : {}  (baseline was {})  →  FSR_THRESHOLD = {}".format(
        fsr_phone, base, new_fsr_thresh))


# ---------------------------------------------------------------------------
# Interactive calibration (manual / REPL use)
# ---------------------------------------------------------------------------

def calibrate(samples=20, interval_ms=50):
    """
    Full interactive calibration — run from the Thonny REPL.
    Walks through all three thresholds with prompts.
    """
    print("=== Manual Sensor Calibration ===\n")

    # Touch
    input("Ensure NO phone is on the pad, then press Enter...")
    print("  Sampling ({} readings)...".format(samples))
    total = 0
    for _ in range(samples):
        total += read_touch_phone()
        time.sleep_ms(interval_ms)
    baseline     = total // samples
    new_thresh   = baseline - 30
    config.TOUCH_THRESHOLD = new_thresh
    _write_config_value('TOUCH_THRESHOLD', new_thresh)
    print("  Baseline: {}  →  TOUCH_THRESHOLD = {}".format(baseline, new_thresh))

    input("Place phone on pad to verify...")
    avg = _avg_touch_phone(1000)
    print("  {} — 1s avg={}, threshold={}".format(
        "OK" if avg < new_thresh else "WARNING NOT DETECTED", avg, new_thresh))

    # FSR
    print()
    input("Remove phone, then press Enter for FSR...")
    f_base = read_fsr(samples=10)
    print("  FSR (no phone): {}".format(f_base))
    input("Place phone, then press Enter...")
    f_phone = read_fsr(samples=10)
    f_mid   = (f_base + f_phone) // 2
    config.FSR_THRESHOLD = f_mid
    _write_config_value('FSR_THRESHOLD', f_mid)
    print("  FSR (phone): {}  →  FSR_THRESHOLD = {}".format(f_phone, f_mid))

    # Button
    print()
    input("Release button, then press Enter...")
    b_base = read_touch_btn()
    input("Hold button, then press Enter...")
    b_held = read_touch_btn()
    b_mid  = (b_base + b_held) // 2
    print("  Button idle={} held={}  →  BTN_THRESHOLD = {}".format(b_base, b_held, b_mid))
    print("  Set BTN_THRESHOLD = {} in config.py".format(b_mid))

    print("\nCalibration complete.")
