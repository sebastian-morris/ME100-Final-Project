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

# Internal state for button hold timer
_btn_press_start = None


def read_touch_phone():
    """Raw touch value from phone pad (GPIO32). Decreases when phone is present."""
    return _touch_phone.read()


def read_touch_btn():
    """Raw touch value from power button pad (GPIO15). Decreases when finger is held."""
    return _touch_btn.read()


def read_fsr(samples=3):
    """Averaged raw ADC value (0–4095). Increases as FSR pressure rises."""
    return sum(_fsr.read() for _ in range(samples)) // samples


def phone_present():
    """True when BOTH sensors indicate the phone is on the pad."""
    touch_ok  = read_touch_phone() < config.TOUCH_THRESHOLD
    weight_ok = read_fsr()         > config.FSR_THRESHOLD
    return touch_ok and weight_ok


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
            _btn_press_start = now                          # finger just landed
        elif time.ticks_diff(now, _btn_press_start) >= required_ms:
            _btn_press_start = None                         # reset so it doesn't re-fire
            return True
    else:
        _btn_press_start = None                             # finger lifted, reset timer

    return False


def calibrate(samples=10, delay_ms=50):
    """Interactive calibration helper — run in Thonny REPL to find all thresholds."""
    print("=== Sensor Calibration ===\n")

    # --- Phone touch pad ---
    input("Remove the phone from the pad, then press Enter...")
    t_vals, f_vals = [], []
    for _ in range(samples):
        t_vals.append(read_touch_phone())
        f_vals.append(read_fsr(samples=1))
        time.sleep_ms(delay_ms)
    t_base = sum(t_vals) // samples
    f_base = sum(f_vals) // samples
    print(f"  NO PHONE  →  touch={t_base}   fsr={f_base}")

    input("Place the phone on the pad, then press Enter...")
    t_vals, f_vals = [], []
    for _ in range(samples):
        t_vals.append(read_touch_phone())
        f_vals.append(read_fsr(samples=1))
        time.sleep_ms(delay_ms)
    t_phone = sum(t_vals) // samples
    f_phone = sum(f_vals) // samples
    print(f"  PHONE ON  →  touch={t_phone}   fsr={f_phone}")

    t_mid = (t_base + t_phone) // 2
    f_mid = (f_base + f_phone) // 2
    print(f"\n  → TOUCH_THRESHOLD = {t_mid}   (between {t_phone} and {t_base})")
    print(f"  → FSR_THRESHOLD   = {f_mid}   (between {f_base} and {f_phone})")

    # --- Power button pad ---
    print()
    input("Release the button pad (no finger), then press Enter...")
    b_vals = []
    for _ in range(samples):
        b_vals.append(read_touch_btn())
        time.sleep_ms(delay_ms)
    b_base = sum(b_vals) // samples
    print(f"  BTN IDLE   →  btn={b_base}")

    input("Hold your finger on the button pad, then press Enter...")
    b_vals = []
    for _ in range(samples):
        b_vals.append(read_touch_btn())
        time.sleep_ms(delay_ms)
    b_held = sum(b_vals) // samples
    print(f"  BTN HELD   →  btn={b_held}")

    b_mid = (b_base + b_held) // 2
    print(f"\n  → BTN_THRESHOLD   = {b_mid}   (between {b_held} and {b_base})")

    print("\nPaste all three values into config.py.")
