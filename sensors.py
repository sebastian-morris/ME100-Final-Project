# sensors.py — capacitive touch and FSR pressure sensor

from machine import TouchPad, ADC, Pin
import time
import config

_touch = TouchPad(Pin(config.PIN_TOUCH))

_fsr = ADC(Pin(config.PIN_FSR))
_fsr.atten(ADC.ATTN_11DB)       # full 0–3.3 V range
_fsr.width(ADC.WIDTH_12BIT)     # 12-bit resolution → 0–4095


def read_touch():
    """Raw touch value. Decreases when conductive object (phone) is present."""
    return _touch.read()


def read_fsr(samples=3):
    """Averaged raw ADC value (0–4095). Increases as FSR pressure rises."""
    return sum(_fsr.read() for _ in range(samples)) // samples


def phone_present():
    """True when BOTH sensors indicate the phone is on the pad."""
    touch_ok  = read_touch() < config.TOUCH_THRESHOLD
    weight_ok = read_fsr()   > config.FSR_THRESHOLD
    return touch_ok and weight_ok


def calibrate(samples=10, delay_ms=50):
    """Interactive calibration helper — run this in Thonny REPL to find thresholds."""
    print("=== Sensor Calibration ===")

    input("Remove the phone from the pad, then press Enter...")
    t_vals, f_vals = [], []
    for _ in range(samples):
        t_vals.append(read_touch())
        f_vals.append(read_fsr(samples=1))
        time.sleep_ms(delay_ms)
    t_base = sum(t_vals) // samples
    f_base = sum(f_vals) // samples
    print(f"  NO PHONE  →  touch={t_base}   fsr={f_base}")

    input("Place the phone on the pad, then press Enter...")
    t_vals, f_vals = [], []
    for _ in range(samples):
        t_vals.append(read_touch())
        f_vals.append(read_fsr(samples=1))
        time.sleep_ms(delay_ms)
    t_phone = sum(t_vals) // samples
    f_phone = sum(f_vals) // samples
    print(f"  PHONE ON  →  touch={t_phone}   fsr={f_phone}")

    t_mid = (t_base + t_phone) // 2
    f_mid = (f_base + f_phone) // 2
    print(f"\nSuggested thresholds for config.py:")
    print(f"  TOUCH_THRESHOLD = {t_mid}   (between {t_phone} and {t_base})")
    print(f"  FSR_THRESHOLD   = {f_mid}   (between {f_base} and {f_phone})")
